package vn.adas.adas_caotoc

import android.app.ActivityManager
import android.content.Context
import android.os.Build
import android.os.PowerManager
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

class MainActivity : FlutterActivity() {
    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        // Nhiệt độ máy (bộ điều tốc hiệu năng) + thông tin máy (báo cáo benchmark)
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, "vn.adas/device").setMethodCallHandler { call, result ->
            when (call.method) {
                "thermal" -> {
                    val pm = getSystemService(Context.POWER_SERVICE) as PowerManager
                    val status = if (Build.VERSION.SDK_INT >= 29) pm.currentThermalStatus else -1
                    // dư nhiệt dự báo 10 s tới: 1,0 = ngưỡng hạ xung mạnh; NaN nếu máy không hỗ trợ / gọi quá dày
                    val headroom = if (Build.VERSION.SDK_INT >= 30) pm.getThermalHeadroom(10).toDouble() else Double.NaN
                    result.success(mapOf("status" to status, "headroom" to if (headroom.isNaN()) null else headroom))
                }
                "info" -> {
                    val am = getSystemService(Context.ACTIVITY_SERVICE) as ActivityManager
                    val mem = ActivityManager.MemoryInfo()
                    am.getMemoryInfo(mem)
                    val soc = if (Build.VERSION.SDK_INT >= 31) "${Build.SOC_MANUFACTURER} ${Build.SOC_MODEL}" else Build.HARDWARE
                    result.success(
                        mapOf(
                            "model" to "${Build.MANUFACTURER} ${Build.MODEL}",
                            "soc" to soc,
                            "os" to "Android ${Build.VERSION.RELEASE} (API ${Build.VERSION.SDK_INT})",
                            "cores" to Runtime.getRuntime().availableProcessors(),
                            "ram_mb" to (mem.totalMem / (1024 * 1024)).toInt(),
                        )
                    )
                }
                else -> result.notImplemented()
            }
        }
    }
}
