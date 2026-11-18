package vn.adas.caotoc.service

import android.Manifest
import android.annotation.SuppressLint
import android.content.Context
import android.content.pm.PackageManager
import android.location.Location
import android.location.LocationListener
import android.location.LocationManager
import android.os.Build
import android.os.Looper
import android.os.SystemClock
import androidx.core.content.ContextCompat
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

enum class GpsState { OFF, NO_PERMISSION, WAITING, OK }

/** Tốc độ xe chủ từ GPS của điện thoại (thay cho đo từ vạch kẻ của bản desktop - chính xác hơn nhiều). */
class GpsSpeed(private val context: Context) {
    private val lm = context.getSystemService(Context.LOCATION_SERVICE) as LocationManager
    private val stateFlow = MutableStateFlow(GpsState.OFF)
    val state: StateFlow<GpsState> = stateFlow.asStateFlow()

    @Volatile private var kmh: Double? = null
    @Volatile private var atMs = 0L
    private var listening = false

    /** Tốc độ hợp lệ gần đây (km/h) hoặc null. */
    val speedKmh: Double?
        get() = kmh?.takeIf { SystemClock.elapsedRealtime() - atMs < STALE_AFTER_MS }

    private val listener = LocationListener { onLocation(it) }

    @SuppressLint("MissingPermission")
    fun start() {
        if (listening) return
        if (ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_FINE_LOCATION) != PackageManager.PERMISSION_GRANTED) {
            stateFlow.value = GpsState.NO_PERMISSION
            return
        }
        if (!lm.isProviderEnabled(LocationManager.GPS_PROVIDER)) {
            stateFlow.value = GpsState.OFF
            return
        }
        stateFlow.value = GpsState.WAITING
        lm.requestLocationUpdates(LocationManager.GPS_PROVIDER, 500L, 0f, listener, Looper.getMainLooper())
        listening = true
    }

    fun stop() {
        if (listening) lm.removeUpdates(listener)
        listening = false
        stateFlow.value = GpsState.OFF
    }

    private fun onLocation(p: Location) {
        if (!p.hasSpeed()) return
        // sai số tốc độ > ~11 km/h thì bỏ; máy không báo sai số thì vẫn nhận
        if (Build.VERSION.SDK_INT >= 26 && p.hasSpeedAccuracy() && p.speedAccuracyMetersPerSecond > MAX_SPEED_ACCURACY_MPS) return
        val v = p.speed * 3.6
        // làm mượt nhẹ: GPS báo 1-2 lần/giây, đủ nhanh cho ngưỡng khoảng cách
        val prev = speedKmh
        kmh = if (prev == null) v else 0.6 * v + 0.4 * prev
        atMs = SystemClock.elapsedRealtime()
        stateFlow.value = GpsState.OK
    }

    private companion object {
        const val STALE_AFTER_MS = 3000L
        const val MAX_SPEED_ACCURACY_MPS = 3.0
    }
}
