package vn.adas.caotoc.ui.calibration

import android.content.Context
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import android.view.Surface
import androidx.camera.core.Camera
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.gestures.detectDragGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.ArrowBack
import androidx.compose.material.icons.outlined.DirectionsCar
import androidx.compose.material.icons.outlined.LocalShipping
import androidx.compose.material3.Button
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.Shadow
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.drawText
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.rememberTextMeasurer
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlin.math.abs
import kotlin.math.hypot
import vn.adas.caotoc.core.CalibrationConfig
import vn.adas.caotoc.core.CameraPose
import vn.adas.caotoc.core.LANE_WIDTH_M
import vn.adas.caotoc.core.PoseCamera
import vn.adas.caotoc.core.V3
import vn.adas.caotoc.core.VEHICLE_PRESETS
import vn.adas.caotoc.core.Vec2
import vn.adas.caotoc.core.calibFromPose
import vn.adas.caotoc.core.poseFromGravity
import vn.adas.caotoc.core.vn
import vn.adas.caotoc.service.LensFocal
import vn.adas.caotoc.service.UsbCamera
import vn.adas.caotoc.ui.components.SelectTile
import vn.adas.caotoc.ui.drive.CameraView
import vn.adas.caotoc.ui.drive.CoverTransform
import vn.adas.caotoc.ui.theme.AppColors
import vn.adas.caotoc.ui.theme.AppText
import vn.adas.caotoc.ui.theme.BeVietnamPro
import vn.adas.caotoc.ui.theme.Radii
import vn.adas.caotoc.ui.theme.Space

private val STEPS = listOf("Xe và số đo", "Đường chân trời", "Hoàn tất")
private const val MAX_ROLL_DEG = 20.0
/** Góc quay (đường chéo) thường ghi trên hộp camera hành trình. */
private val DASHCAM_FOVS = listOf(120, 140, 150, 170)
private const val DEFAULT_DASHCAM_FOV = 140

/**
 * Tiêu cự / chiều rộng ảnh từ góc quay đường chéo của camera hành trình. Ống kính góc rộng gần với mô hình
 * mắt cá đều góc (r = f·θ) nên dùng f = nửa đường chéo / nửa góc (rad) - đúng độ phóng đại ở giữa ảnh, vùng
 * đo khoảng cách. Chỉ là điểm xuất phát: khi chạy đều app tự chỉnh theo GPS (OnlineCalib.kt).
 */
private fun dashcamFocalW(fovDeg: Int, w: Double, h: Double): Double = hypot(w, h) / 2 / Math.toRadians(fovDeg / 2.0) / w

/**
 * Căn chỉnh camera 3 bước (giống trình căn chỉnh của bản desktop, gui/dialogs/calibration_wizard.py):
 *  1. Xe và số đo: chọn loại xe (điền sẵn số đo điển hình) hoặc nhập chiều cao camera + khoảng cách tới đầu xe.
 *  2. Đường chân trời: vẽ theo cảm biến trọng lực, đổi ngay khi chỉnh giá đỡ (kiểu camera hành trình); tiêu cự
 *     lấy từ thông số ống kính Camera2. Lệch thì kéo trên ảnh.
 *     Camera hành trình USB ([usb] khác null, màn hình ô tô): cảm biến nằm ở màn hình chứ không gắn với camera nên
 *     không dùng; chân trời kéo tay hoặc để app tự đo từ vạch làn, tiêu cự ước lượng theo góc quay ghi trên hộp.
 *  3. Hoàn tất: khi lái, app tự hoàn thiện căn chỉnh từ 2 vạch làn (OnlineCalib.kt) và báo kết quả tự kiểm tra;
 *     thang khoảng cách tự chỉnh theo GPS (EgoSpeed.kt).
 * "Nâng cao" mở màn hình chấm 4 điểm cũ ([ManualCalibration]).
 */
@Composable
fun CalibrationScreen(
    initial: CalibrationConfig, imageW: Double, imageH: Double, lowRes: Boolean, lens: LensFocal?, rotate180: Boolean,
    autoCalib: Boolean, usb: UsbCamera?, onCamera: (Camera) -> Unit, onSave: (CalibrationConfig, Boolean) -> Unit,
    onBack: () -> Unit,
) {
    var advanced by remember { mutableStateOf(false) }
    if (advanced) {
        ManualCalibration(initial, imageW, imageH, lowRes, usb, rotate180, onSave = { onSave(it, autoCalib) }, onBack = { advanced = false })
        return
    }
    val external = usb != null
    val focal = lens?.focalW(imageW, imageH)
    var pose by remember {
        mutableStateOf(
            if (initial.pose.active) initial.pose.copy(refined = false)
            else VEHICLE_PRESETS.getValue("car").let { (_, h, b) -> CameraPose(vehicle = "car", heightM = h, bumperM = b) },
        )
    }
    // camera hành trình: tiêu cự đã chỉnh theo GPS / tốc độ ở lần trước thì giữ, không thì ước lượng theo góc quay
    var fov by remember {
        mutableStateOf(if (initial.pose.active && initial.pose.focalSource in setOf("gps", "speed")) null else DEFAULT_DASHCAM_FOV)
    }
    // tiêu cự thật của ống kính luôn được dùng khi máy khai báo
    val withFocal = when {
        external -> fov?.let { pose.copy(focalW = dashcamFocalW(it, imageW, imageH), focalSource = "fov") } ?: pose
        focal != null -> pose.copy(focalW = focal, focalSource = "camera")
        else -> pose
    }
    var step by remember { mutableStateOf(0) }
    var follow by remember { mutableStateOf(!initial.pose.active && !external) } // chân trời theo cảm biến cho tới khi kéo tay
    var height by remember { mutableStateOf(fmt(pose.heightM)) }
    var bumper by remember { mutableStateOf(fmt(pose.bumperM)) }
    var auto by remember { mutableStateOf(autoCalib) }
    var error by remember { mutableStateOf<String?>(null) }
    val down = if (external) null else rememberGravityInCamera(rotate180)
    val sensed = down?.let { poseFromGravity(withFocal, it, imageW, imageH) }
    // máy dựng dọc / nghiêng quá nhiều so với mặt đường: không dùng cảm biến (chân trời vô nghĩa)
    val tilted = sensed != null && abs(sensed.rollDeg) > MAX_ROLL_DEG
    val shown = if (follow && sensed != null && !tilted) sensed else withFocal
    fun read(t: String, def: Double, lo: Double, hi: Double) = t.replace(',', '.').toDoubleOrNull()?.coerceIn(lo, hi) ?: def
    val final = shown.copy(heightM = read(height, pose.heightM, 0.5, 4.0), bumperM = read(bumper, pose.bumperM, 0.0, 5.0))

    Row(Modifier.fillMaxSize().background(AppColors.bg).safeDrawingPadding()) {
        Box(Modifier.weight(1f).fillMaxHeight().padding(Space.md).clip(RoundedCornerShape(Radii.md))) {
            CameraView(Modifier.fillMaxSize(), usb, lowRes, rotate180, contain = true, onCamera = onCamera)
            if (step == 1) {
                HorizonOverlay(final, imageW, imageH) { du, dv ->
                    follow = false
                    pose = shown.copy(vpX = (shown.vpX + du / imageW).coerceIn(0.2, 0.8), vpY = (shown.vpY + dv / imageH).coerceIn(0.15, 0.8))
                }
            }
        }
        Column(Modifier.width(360.dp).fillMaxHeight().background(AppColors.surface).border(1.dp, AppColors.stroke)) {
            Column(Modifier.weight(1f).verticalScroll(rememberScrollState()).padding(horizontal = Space.lg, vertical = Space.sm)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    IconButton(onBack) { Icon(Icons.AutoMirrored.Rounded.ArrowBack, "Quay lại, không lưu") }
                    Spacer(Modifier.width(Space.xs))
                    Text("Căn chỉnh camera", style = AppText.title.copy(fontSize = 20.sp))
                }
                Text("Bước ${step + 1}/3 · ${STEPS[step]}", style = AppText.caption.copy(color = AppColors.accent, fontWeight = FontWeight.Bold))
                Spacer(Modifier.height(Space.md))
                when (step) {
                    0 -> {
                        Text("Camera gắn trên xe nào? Chọn để điền sẵn số đo điển hình (máy gắn giữa kính lái).", style = AppText.caption)
                        Spacer(Modifier.height(Space.sm))
                        for (row in VEHICLE_PRESETS.entries.chunked(2)) {
                            Row(horizontalArrangement = Arrangement.spacedBy(Space.sm), modifier = Modifier.padding(bottom = Space.sm)) {
                                for ((key, preset) in row) {
                                    val (label, h, b) = preset
                                    SelectTile(if (key in setOf("car", "suv")) Icons.Outlined.DirectionsCar else Icons.Outlined.LocalShipping,
                                        label, "cao ${vn(h, 2)} m", pose.vehicle == key, {
                                            pose = pose.copy(vehicle = key, heightM = h, bumperM = b, heightMeasured = false)
                                            height = fmt(h); bumper = fmt(b)
                                        }, Modifier.weight(1f))
                                }
                            }
                        }
                        Row(horizontalArrangement = Arrangement.spacedBy(Space.md)) {
                            Field("Chiều cao camera", "Mặt đường -> ống kính", height, { height = it; pose = pose.copy(heightMeasured = true) }, Modifier.weight(1f))
                            Field("Tới đầu xe", "Ống kính -> cản trước", bumper, { bumper = it }, Modifier.weight(1f))
                        }
                        Spacer(Modifier.height(Space.sm))
                        SwitchLine("Đã đo chiều cao bằng thước", pose.heightMeasured) { pose = pose.copy(heightMeasured = it) }
                        Text(if (pose.heightMeasured) "Giữ đúng chiều cao này; khi lái app báo bề rộng làn đo được để tự kiểm tra."
                        else "Không đo cũng được: khi lái, app tự ước lượng chiều cao theo làn cao tốc 3,75 m.", style = AppText.caption)
                    }
                    1 -> {
                        Text("Đường xanh phải trùng chân trời, tâm ngắm chỉ đúng hướng đường chạy, 2 nét đứt song song với vạch làn.",
                            style = AppText.caption.copy(color = AppColors.text))
                        Spacer(Modifier.height(Space.sm))
                        Text(when {
                            external -> "Camera hành trình: kéo trên ảnh để đường xanh trùng chân trời. Không chắc thì để " +
                                "nguyên - khi lái app tự đo chân trời từ 2 vạch làn."
                            tilted -> "Máy đang nghiêng ${vn(abs(sensed.rollDeg), 0)}° so với mặt đường: hãy gắn máy nằm ngang, " +
                                "camera sau nhìn thẳng ra đường."
                            follow && down != null -> "Đang theo cảm biến nghiêng của máy: chỉnh giá đỡ cho chân trời nằm khoảng giữa ảnh."
                            down == null -> "Máy không có cảm biến trọng lực: hãy kéo trên ảnh."
                            else -> "Đã chỉnh tay. Lệch thì kéo tiếp trên ảnh."
                        }, style = AppText.caption.copy(color = if (tilted) AppColors.warning else AppColors.textSecondary))
                        if (!follow && down != null && !tilted) TextButton({ follow = true }) { Text("Theo cảm biến", color = AppColors.accent) }
                        Spacer(Modifier.height(Space.sm))
                        if (external) {
                            Text("Góc quay của camera (ghi trên hộp)", style = AppText.bodyStrong)
                            Spacer(Modifier.height(Space.xs))
                            Row(horizontalArrangement = Arrangement.spacedBy(Space.xs)) {
                                for (d in DASHCAM_FOVS) {
                                    FilterChip(fov == d, { fov = d }, { Text("$d°") },
                                        colors = FilterChipDefaults.filterChipColors(selectedContainerColor = AppColors.accentSoft))
                                }
                            }
                            Text(if (fov != null) "Tiêu cự ước lượng theo góc quay $fov°; khi chạy đều app tự chỉnh lại theo GPS."
                            else "Giữ tiêu cự đã chỉnh theo GPS ở lần trước (${vn(final.focalW * imageW, 0)} điểm ảnh).", style = AppText.caption)
                        } else {
                            Text(if (focal != null) "Tiêu cự lấy từ thông số ống kính của máy (${vn(final.focalW * imageW, 0)} điểm ảnh)."
                            else "Máy không khai báo tiêu cự: dùng góc nhìn mặc định, khoảng cách xa có thể lệch.", style = AppText.caption)
                        }
                    }
                    else -> {
                        Summary("Loại xe", VEHICLE_PRESETS[final.vehicle]?.first ?: "Khác")
                        Summary("Chiều cao camera", "${vn(final.heightM, 2)} m " + if (final.heightMeasured) "(đã đo)" else "(ước lượng)")
                        Summary("Tới đầu xe", "${vn(final.bumperM, 1)} m")
                        Summary("Chân trời", "hàng ${vn(final.vpY * imageH, 0)}/${vn(imageH, 0)} · nghiêng ${vn(final.rollDeg, 1)}°")
                        Spacer(Modifier.height(Space.md))
                        Text("Khi lái: \"Đang tự hoàn thiện căn chỉnh 0-100 %\" hiện trên màn hình, cần khoảng 5-10 giây thấy rõ 2 vạch làn. " +
                            "Xong sẽ báo kết quả, ví dụ \"Làn đo được 3,72 m - đạt\". Sau khoảng nửa phút chạy đều, app so tốc độ " +
                            "đo từ vạch kẻ với GPS và tự chỉnh thang khoảng cách - không cần nhập gì. Camera bị xê dịch thì app " +
                            "tự căn chỉnh lại.", style = AppText.caption)
                        Spacer(Modifier.height(Space.sm))
                        SwitchLine("Tự hoàn thiện khi lái", auto) { auto = it }
                        error?.let { Text(it, style = AppText.caption.copy(color = AppColors.danger)) }
                    }
                }
                Spacer(Modifier.height(Space.md))
                TextButton({ advanced = true }) { Text("Nâng cao: chấm 4 điểm", color = AppColors.accent) }
            }
            Row(Modifier.fillMaxWidth().border(1.dp, AppColors.stroke).padding(Space.lg, Space.md), horizontalArrangement = Arrangement.spacedBy(Space.md)) {
                OutlinedButton({ if (step > 0) step-- else onBack() }, Modifier.weight(1.2f).height(52.dp),
                    contentPadding = PaddingValues(horizontal = Space.sm)) {
                    Text(if (step > 0) "Quay lại" else "Hủy", maxLines = 1, softWrap = false)
                }
                Button({
                    if (step < 2) {
                        pose = final
                        step++
                    } else {
                        runCatching { calibFromPose(final, imageW, imageH, initial) }
                            .onSuccess { onSave(it, auto) }
                            .onFailure { error = it.message }
                    }
                }, Modifier.weight(1.8f).height(52.dp)) { Text(if (step < 2) "Tiếp" else "Lưu căn chỉnh") }
            }
        }
    }
}

/** Đường chân trời, tâm ngắm, hành lang 1 làn và vạch 10-50 m theo tư thế; kéo để dời điểm tụ ([onDrag]: pixel ảnh). */
@Composable
private fun HorizonOverlay(pose: CameraPose, imageW: Double, imageH: Double, onDrag: (Double, Double) -> Unit) {
    val measurer = rememberTextMeasurer()
    val cam = PoseCamera(pose.copy(active = true), imageW, imageH)
    val drag by rememberUpdatedState(onDrag) // pointerInput giữ khối lệnh: luôn gọi bản mới nhất (tư thế hiện tại)
    Canvas(
        Modifier.fillMaxSize()
            .semantics { contentDescription = "Ảnh camera với đường chân trời. Kéo để chỉnh." }
            .pointerInput(imageW, imageH) {
                detectDragGestures { change, delta ->
                    val tf = CoverTransform(imageW, imageH, androidx.compose.ui.geometry.Size(size.width.toFloat(), size.height.toFloat()), contain = true)
                    val a = tf.unmap(change.position - delta); val b = tf.unmap(change.position)
                    drag(b.x - a.x, b.y - a.y)
                }
            },
    ) {
        val tf = CoverTransform(imageW, imageH, size, contain = true)
        fun at(p: Vec2) = tf.map(p)
        val dash = PathEffect.dashPathEffect(floatArrayOf(10.dp.toPx(), 7.dp.toPx()))
        for (x in listOf(-LANE_WIDTH_M / 2, LANE_WIDTH_M / 2)) {
            drawLine(Color.White.copy(alpha = 0.6f), at(cam.groundToImage(x, 2.0)), at(cam.groundToImage(x, 120.0)), 1.5.dp.toPx(), pathEffect = dash)
        }
        val label = TextStyle(fontFamily = BeVietnamPro, color = Color.White, fontSize = 12.sp, fontWeight = FontWeight.SemiBold,
            shadow = Shadow(Color.Black, blurRadius = 4f))
        var lastY = Float.POSITIVE_INFINITY
        for (d in listOf(10.0, 20.0, 30.0, 50.0)) {
            val a = at(cam.groundToImage(-LANE_WIDTH_M / 2, d)); val b = at(cam.groundToImage(LANE_WIDTH_M / 2, d))
            if (a.y < tf.dy || a.y > size.height) continue
            drawLine(Color.White.copy(alpha = 0.75f), a, b, 1.5.dp.toPx())
            if (lastY - b.y < 16.dp.toPx()) continue
            lastY = b.y
            drawText(measurer.measure("${d.toInt()} m", label), topLeft = b + Offset(6.dp.toPx(), -8.dp.toPx()))
        }
        val (h1, h2) = cam.horizonPoints()
        drawLine(AppColors.accent, at(h1), at(h2), 2.5.dp.toPx())
        val c = at(cam.vp)
        drawLine(AppColors.accent, c, at(cam.groundToImage(0.0, 2.0)), 1.5.dp.toPx(), pathEffect = dash)
        drawCircle(Color.Black.copy(alpha = 0.5f), 11.dp.toPx(), c, style = androidx.compose.ui.graphics.drawscope.Stroke(4.dp.toPx()))
        drawCircle(AppColors.accent, 11.dp.toPx(), c, style = androidx.compose.ui.graphics.drawscope.Stroke(2.dp.toPx()))
        for ((dx, dy) in listOf(1f to 0f, -1f to 0f, 0f to 1f, 0f to -1f)) {
            drawLine(AppColors.accent, c + Offset(dx * 14.dp.toPx(), dy * 14.dp.toPx()), c + Offset(dx * 22.dp.toPx(), dy * 22.dp.toPx()), 2.dp.toPx())
        }
        drawText(measurer.measure("Đường chân trời", label), topLeft = at(h1) + Offset(8.dp.toPx(), -22.dp.toPx()))
    }
}

/**
 * Hướng trọng lực trong hệ ảnh phân tích (x phải, y xuống, z theo trục camera sau), làm mượt; null nếu máy không
 * có cảm biến. Ảnh phân tích luôn thẳng theo màn hình ngang (DriveViewModel xoay 180° khi cần), nên chỉ cần
 * hướng xoay màn hình; [rotate180]: cài đặt "Xoay ảnh 180°".
 */
@Composable
private fun rememberGravityInCamera(rotate180: Boolean): V3? {
    val context = LocalContext.current
    val view = LocalView.current
    var down by remember { mutableStateOf<V3?>(null) }
    DisposableEffect(rotate180) {
        val sm = context.getSystemService(Context.SENSOR_SERVICE) as SensorManager
        val gravity = sm.getDefaultSensor(Sensor.TYPE_GRAVITY)
        val sensor = gravity ?: sm.getDefaultSensor(Sensor.TYPE_ACCELEROMETER)
        val g = FloatArray(3)
        var have = false
        val listener = object : SensorEventListener {
            override fun onSensorChanged(e: SensorEvent) {
                val a = if (gravity != null || !have) 1f else 0.1f // gia tốc kế thô: lọc thông thấp
                for (i in 0..2) g[i] += a * (e.values[i] - g[i])
                have = true
                // giá trị cảm biến hướng lên trời -> đổi dấu thành hướng xuống đất (hệ thiết bị)
                val dx = -g[0].toDouble(); val dy = -g[1].toDouble(); val dz = -g[2].toDouble()
                var (x, y) = when (view.display?.rotation) {
                    Surface.ROTATION_90 -> -dy to -dx
                    Surface.ROTATION_270 -> dy to dx
                    Surface.ROTATION_180 -> -dx to dy
                    else -> dx to -dy
                }
                if (rotate180) { x = -x; y = -y }
                val v = V3(x, y, -dz)
                if (v.norm() > 1.0) down = v
            }

            override fun onAccuracyChanged(s: Sensor?, accuracy: Int) {}
        }
        if (sensor != null) sm.registerListener(listener, sensor, SensorManager.SENSOR_DELAY_UI)
        onDispose { sm.unregisterListener(listener) }
    }
    return down
}

@Composable
private fun SwitchLine(text: String, checked: Boolean, onChange: (Boolean) -> Unit) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Text(text, style = AppText.body, modifier = Modifier.weight(1f))
        Switch(checked, onChange)
    }
}

@Composable
private fun Summary(label: String, value: String) {
    Row(Modifier.padding(vertical = 3.dp)) {
        Text(label, style = AppText.caption, modifier = Modifier.width(130.dp))
        Text(value, style = AppText.bodyStrong)
    }
}
