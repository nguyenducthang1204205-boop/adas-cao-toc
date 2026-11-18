package vn.adas.caotoc.service

import android.app.ActivityManager
import android.content.Context
import android.os.Build
import android.os.PowerManager

/** Trạng thái nhiệt theo thang Android PowerManager; [headroom] 1,0 = ngưỡng hạ xung mạnh (null = không rõ). */
data class ThermalReading(val status: Int, val headroom: Double?)

/** Nhiệt độ máy (cho bộ điều tốc hiệu năng) và thông tin máy (cho báo cáo benchmark). */
object DeviceInfo {
    /** -1 = máy không hỗ trợ (Android < 10). Dư nhiệt dự báo 10 s tới chỉ có từ Android 11. */
    fun thermal(context: Context): ThermalReading {
        val pm = context.getSystemService(Context.POWER_SERVICE) as PowerManager
        val status = if (Build.VERSION.SDK_INT >= 29) pm.currentThermalStatus else -1
        val headroom = if (Build.VERSION.SDK_INT >= 30) pm.getThermalHeadroom(10).toDouble() else Double.NaN
        return ThermalReading(status, headroom.takeUnless { it.isNaN() })
    }

    fun thermalName(s: Int): String = when (s) {
        0 -> "bình thường"
        1 -> "hơi ấm"
        2 -> "ấm"
        3 -> "nóng"
        4 -> "rất nóng"
        5, 6 -> "quá nóng"
        else -> "không rõ"
    }

    data class Info(val model: String, val soc: String, val os: String, val cores: Int, val ramMb: Long)

    fun info(context: Context): Info {
        val am = context.getSystemService(Context.ACTIVITY_SERVICE) as ActivityManager
        val mem = ActivityManager.MemoryInfo().also { am.getMemoryInfo(it) }
        val soc = if (Build.VERSION.SDK_INT >= 31) "${Build.SOC_MANUFACTURER} ${Build.SOC_MODEL}" else Build.HARDWARE
        return Info(
            model = "${Build.MANUFACTURER} ${Build.MODEL}",
            soc = soc,
            os = "Android ${Build.VERSION.RELEASE} (API ${Build.VERSION.SDK_INT})",
            cores = Runtime.getRuntime().availableProcessors(),
            ramMb = mem.totalMem / (1024 * 1024),
        )
    }
}
