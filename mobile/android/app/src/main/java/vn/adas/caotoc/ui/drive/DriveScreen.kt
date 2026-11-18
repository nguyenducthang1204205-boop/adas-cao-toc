package vn.adas.caotoc.ui.drive

import android.Manifest
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import kotlinx.coroutines.delay
import vn.adas.caotoc.core.GroundPlaneMapper
import vn.adas.caotoc.service.GpsState

/**
 * Màn hình lái xe - phần nối: quyền camera / vị trí, camera (của máy hoặc camera hành trình USB), ViewModel -> HUD,
 * bảng điều kiện và trợ lý. Camera USB cũng cần quyền CAMERA (Android 9+).
 * Logic nằm ở [DriveViewModel], phần trình bày ở [DriveHud].
 */
@Composable
fun DriveScreen(vm: DriveViewModel, onCalibrate: () -> Unit, onSettings: () -> Unit) {
    val context = LocalContext.current
    fun granted(p: String) = ContextCompat.checkSelfPermission(context, p) == PackageManager.PERMISSION_GRANTED
    var cameraGranted by remember { mutableStateOf(granted(Manifest.permission.CAMERA)) }
    var cameraError by remember { mutableStateOf<String?>(null) }
    val permissions = rememberLauncherForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { res ->
        cameraGranted = res[Manifest.permission.CAMERA] ?: granted(Manifest.permission.CAMERA)
        if (res[Manifest.permission.ACCESS_FINE_LOCATION] == true) vm.applySettings()
    }
    LaunchedEffect(Unit) {
        val missing = listOf(Manifest.permission.CAMERA, Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION)
            .filterNot(::granted)
        if (missing.isNotEmpty()) permissions.launch(missing.toTypedArray())
    }

    val s by vm.store.settings.collectAsStateWithLifecycle()
    val hud by vm.hud.collectAsStateWithLifecycle()
    val stats by vm.stats.collectAsStateWithLifecycle()
    val backend by vm.backend.collectAsStateWithLifecycle()
    val engineError by vm.error.collectAsStateWithLifecycle()
    val size by vm.imageSize.collectAsStateWithLifecycle()
    val notice by vm.perfNotice.collectAsStateWithLifecycle()
    val chat by vm.chat.collectAsStateWithLifecycle()
    val log by vm.log.snapshot.collectAsStateWithLifecycle()
    val gpsState by vm.gps.state.collectAsStateWithLifecycle()
    val calib by vm.calib.collectAsStateWithLifecycle()
    val usb by vm.usb.state.collectAsStateWithLifecycle()
    val useUsb = usb.selected(s.cameraSource)
    // kết quả tốt hiện 12 giây rồi ẩn; đang đo / cần chú ý thì giữ lại
    var calibHidden by remember { mutableStateOf<String?>(null) }
    LaunchedEffect(calib?.message) {
        val c = calib
        if (c != null && c.state == "done" && c.ok == true) {
            delay(12_000)
            calibHidden = c.message
        }
    }
    var sheet by rememberSaveable { mutableStateOf<String?>(null) }

    val iw = size.first.toDouble(); val ih = size.second.toDouble()
    val mapper = remember(s.calibration, iw, ih) { GroundPlaneMapper.orDefault(s.calibration, iw, ih) }
    val speedSource = when {
        !s.useGps -> SpeedSource.MANUAL
        vm.speedFromGps -> SpeedSource.GPS
        gpsState == GpsState.NO_PERMISSION -> SpeedSource.NO_PERMISSION
        gpsState == GpsState.OFF -> SpeedSource.GPS_OFF
        else -> SpeedSource.WAITING
    }
    val error = when {
        !cameraGranted -> "Ứng dụng cần quyền camera. Hãy cấp quyền trong Cài đặt của điện thoại."
        useUsb && usb.problem() != null -> usb.problem()
        !useUsb && cameraError != null -> "Lỗi camera: $cameraError"
        else -> engineError
    }
    val state = HudState(
        result = hud, mapper = mapper, imageW = iw, imageH = ih,
        speedKmh = vm.speedKmh(s), speedSource = speedSource, policy = s.policy,
        conditionKey = s.conditionKey, modifiers = s.modifierKeys, calibrated = s.calibrated,
        soundOn = s.alert.soundEnabled, cameraReady = backend != null && cameraGranted && (!useUsb || usb.streaming),
        techText = if (s.showTech) vm.techText(stats, s) else null,
        perfNotice = notice, error = error, violations = log.sessionCount,
        // chưa căn chỉnh lần nào: đã có lời nhắc căn chỉnh, kiểm tra hình thang mặc định không có ý nghĩa
        calib = calib?.takeIf { s.calibrated && it.message != calibHidden },
    )
    DriveHud(
        state,
        HudActions(
            onCalibrate = onCalibrate, onSettings = onSettings, onToggleSound = vm::toggleSound,
            onConditions = { sheet = "conditions" }, onSpeedStep = vm::stepSpeed, onAssistant = { sheet = "assistant" },
            onRetry = {
                cameraError = null
                when {
                    !cameraGranted -> permissions.launch(arrayOf(Manifest.permission.CAMERA))
                    useUsb -> { vm.usb.retry(); vm.startEngine() }
                    else -> vm.startEngine()
                }
            },
        ),
        live = vm.live,
        camera = if (cameraGranted) {
            {
                CameraView(Modifier.fillMaxSize(), usb = if (useUsb) vm.usb else null, lowRes = s.lowCamera, rotate180 = s.rotate180,
                    onError = { cameraError = it }, onCamera = vm::onCamera, onImage = vm::onImage, onUsbFrame = vm::onUsbFrame)
            }
        } else null,
    )
    when (sheet) {
        "conditions" -> ConditionSheet(s.conditionKey, s.modifierKeys, vm::setCondition, vm::toggleModifier) { sheet = null }
        "assistant" -> AssistantSheet(chat, log, vm::ask, vm.log::clear) { sheet = null }
    }
}
