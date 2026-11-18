package vn.adas.caotoc

import android.os.Bundle
import android.view.WindowManager
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowInsetsControllerCompat
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import vn.adas.caotoc.ui.benchmark.BenchmarkScreen
import vn.adas.caotoc.ui.calibration.CalibrationScreen
import vn.adas.caotoc.ui.drive.DriveScreen
import vn.adas.caotoc.ui.drive.DriveViewModel
import vn.adas.caotoc.ui.settings.SettingsScreen
import vn.adas.caotoc.ui.theme.AdasTheme
import vn.adas.caotoc.ui.welcome.WelcomeScreen

/**
 * ADAS Cao tốc - bản Android (Kotlin + Jetpack Compose).
 * Cảnh báo khoảng cách an toàn: YOLOv11 (LiteRT) + IPM + ngưỡng theo tốc độ GPS và điều kiện đường.
 * Màn hình ngang, toàn màn hình, luôn sáng khi đang lái. Chạy được trên điện thoại (camera của máy) và trên màn hình
 * Android ô tô (camera hành trình cắm USB; cắm camera / bật máy xe thì hệ thống mở app - xem AndroidManifest.xml).
 */
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        WindowCompat.getInsetsController(window, window.decorView).apply {
            hide(WindowInsetsCompat.Type.systemBars())
            systemBarsBehavior = WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
        }
        val app = application as AdasApp
        setContent { AdasTheme { AdasNav(app) } }
    }

    // camera USB mở theo vòng đời màn hình: app ẩn đi thì trả camera cho app ghi hình của hãng
    override fun onStart() {
        super.onStart()
        (application as AdasApp).usbCamera.start()
    }

    override fun onStop() {
        (application as AdasApp).usbCamera.stop()
        super.onStop()
    }
}

private enum class Screen { DRIVE, CALIBRATION, SETTINGS, BENCHMARK }

/** Màn hình chào (kèm lời nhắc an toàn) ở lần mở đầu tiên, rồi màn hình lái và các màn hình phụ. */
@Composable
private fun AdasNav(app: AdasApp) {
    val s by app.settings.settings.collectAsStateWithLifecycle()
    if (!s.disclaimerAccepted) {
        WelcomeScreen { app.settings.update { it.copy(disclaimerAccepted = true) } }
        return
    }
    val vm: DriveViewModel = viewModel()
    var screen by rememberSaveable { mutableStateOf(Screen.DRIVE) }
    BackHandler(screen != Screen.DRIVE) {
        screen = if (screen == Screen.BENCHMARK) Screen.SETTINGS else Screen.DRIVE.also { vm.applySettings() }
    }
    when (screen) {
        Screen.DRIVE -> DriveScreen(vm, onCalibrate = { screen = Screen.CALIBRATION }, onSettings = { screen = Screen.SETTINGS })
        Screen.CALIBRATION -> {
            val lens by vm.lens.collectAsStateWithLifecycle()
            val usb by app.usbCamera.state.collectAsStateWithLifecycle()
            val external = usb.selected(s.cameraSource)
            val (w, h) = if (external && usb.width > 0) usb.width to usb.height else vm.imageSize.value
            // camera hành trình: không có thông số ống kính Camera2, cảm biến nghiêng nằm ở màn hình chứ không ở camera
            CalibrationScreen(s.calibration, w.toDouble(), h.toDouble(), s.lowCamera, if (external) null else lens, s.rotate180,
                s.autoCalib, if (external) app.usbCamera else null,
                onCamera = vm::onCamera,
                onSave = { c, auto ->
                    app.settings.update { it.copy(autoCalib = auto) }
                    vm.saveCalibration(c)
                    screen = Screen.DRIVE
                },
                onBack = { screen = Screen.DRIVE })
        }
        Screen.SETTINGS -> SettingsScreen(app.settings, vm.alerts, app.usbCamera, onBenchmark = { screen = Screen.BENCHMARK },
            onBack = { vm.applySettings(); screen = Screen.DRIVE })
        Screen.BENCHMARK -> BenchmarkScreen(app.settings) { screen = Screen.SETTINGS }
    }
}
