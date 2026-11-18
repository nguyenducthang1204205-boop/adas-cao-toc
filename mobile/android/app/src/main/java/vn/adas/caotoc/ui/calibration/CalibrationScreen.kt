package vn.adas.caotoc.ui.calibration

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.gestures.detectDragGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.ArrowBack
import androidx.compose.material.icons.rounded.ErrorOutline
import androidx.compose.material3.Button
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.Shadow
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.drawText
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.rememberTextMeasurer
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import vn.adas.caotoc.core.CalibrationConfig
import vn.adas.caotoc.core.GroundPlaneMapper
import vn.adas.caotoc.core.Vec2
import vn.adas.caotoc.service.UsbCamera
import vn.adas.caotoc.ui.drive.CameraView
import vn.adas.caotoc.ui.drive.CoverTransform
import vn.adas.caotoc.ui.theme.AppColors
import vn.adas.caotoc.ui.theme.AppText
import vn.adas.caotoc.ui.theme.BeVietnamPro
import vn.adas.caotoc.ui.theme.Radii
import vn.adas.caotoc.ui.theme.Space

/**
 * Căn chỉnh nâng cao (IPM): kéo 4 điểm vào mép trong 2 vạch kẻ làn đang đi, nhập kích thước thật.
 * Giống hộp thoại chấm 4 điểm của bản desktop; lưới 10-60 m vẽ ngay để tự kiểm tra. Ảnh xem trước
 * hiển thị trọn khung (FIT_CENTER) để chạm được cả 4 điểm ở mép ảnh. Mặc định dùng trình 3 bước (CalibrationWizard.kt).
 */
@Composable
internal fun ManualCalibration(initial: CalibrationConfig, imageW: Double, imageH: Double, lowRes: Boolean,
                               usb: UsbCamera?, rotate180: Boolean, onSave: (CalibrationConfig) -> Unit, onBack: () -> Unit) {
    var points by remember { mutableStateOf(initial.imagePoints) }
    var active by remember { mutableStateOf<Int?>(null) }
    var width by remember { mutableStateOf(fmt(initial.rectWidthM)) }
    var length by remember { mutableStateOf(fmt(initial.rectLengthM)) }
    var near by remember { mutableStateOf(fmt(initial.nearDistanceM)) }
    var half by remember { mutableStateOf(fmt(initial.laneHalfWidthM)) }
    fun read(t: String, def: Double, lo: Double, hi: Double) = t.replace(',', '.').toDoubleOrNull()?.coerceIn(lo, hi) ?: def
    val config = initial.copy(
        imagePoints = points,
        rectWidthM = read(width, initial.rectWidthM, 1.0, 20.0),
        rectLengthM = read(length, initial.rectLengthM, 2.0, 100.0),
        nearDistanceM = read(near, initial.nearDistanceM, 0.0, 50.0),
        laneHalfWidthM = read(half, initial.laneHalfWidthM, 0.5, 5.0),
        pose = initial.pose.copy(active = false), // 4 điểm chấm tay: bộ tự hoàn thiện chỉ kiểm tra, không sửa
    )
    val mapper = GroundPlaneMapper.tryCreate(config, imageW, imageH)
    val haptic = LocalHapticFeedback.current
    val measurer = rememberTextMeasurer()

    Row(Modifier.fillMaxSize().background(AppColors.bg).safeDrawingPadding()) {
        Box(Modifier.weight(1f).fillMaxHeight().padding(Space.md).clip(RoundedCornerShape(Radii.md))) {
            CameraView(Modifier.fillMaxSize(), usb, lowRes, rotate180, contain = true)
            Canvas(
                Modifier
                    .fillMaxSize()
                    .semantics { contentDescription = "Ảnh camera với 4 điểm căn chỉnh. Kéo từng điểm vào mép trong vạch kẻ làn." }
                    .pointerInput(imageW, imageH) {
                        fun tf() = CoverTransform(imageW, imageH, androidx.compose.ui.geometry.Size(size.width.toFloat(), size.height.toFloat()), contain = true)
                        detectDragGestures(
                            onDragStart = { p ->
                                val t = tf()
                                // bán kính chạm 52 dp - lớn hơn hình tròn vẽ để dễ trúng
                                val best = points.indices.minBy { (t.map(it.ratio(points, imageW, imageH)) - p).getDistance() }
                                active = if ((t.map(best.ratio(points, imageW, imageH)) - p).getDistance() < 52.dp.toPx()) best else null
                                if (active != null) haptic.performHapticFeedback(HapticFeedbackType.TextHandleMove)
                            },
                            onDrag = { change, _ ->
                                val i = active ?: return@detectDragGestures
                                val q = tf().unmap(change.position)
                                points = points.toMutableList().also { it[i] = Vec2((q.x / imageW).coerceIn(0.0, 1.0), (q.y / imageH).coerceIn(0.0, 1.0)) }
                            },
                            onDragEnd = { active = null },
                        )
                    },
            ) {
                val tf = CoverTransform(imageW, imageH, size, contain = true)
                // lưới khoảng cách 10-60 m: phải nằm đúng trên mặt đường
                if (mapper != null) {
                    var lastLabelY = Float.POSITIVE_INFINITY
                    val label = TextStyle(fontFamily = BeVietnamPro, color = Color.White, fontSize = 12.sp, fontWeight = FontWeight.SemiBold,
                        shadow = Shadow(Color.Black, blurRadius = 4f))
                    for (d in 10..60 step 10) {
                        val hw = config.laneHalfWidthM * 1.6
                        val a = tf.map(mapper.groundToImage(-hw, d.toDouble())); val b = tf.map(mapper.groundToImage(hw, d.toDouble()))
                        if (a.y < tf.dy || b.y < tf.dy || a.y > size.height) continue
                        drawLine(Color.White.copy(alpha = 0.5f), a, b, 1.2.dp.toPx())
                        if (lastLabelY - b.y < 16.dp.toPx()) continue // gần chân trời các vạch dồn sát nhau: bỏ nhãn
                        lastLabelY = b.y
                        drawText(measurer.measure("$d m", label), topLeft = b + Offset(6.dp.toPx(), -8.dp.toPx()))
                    }
                }
                val px = points.indices.map { tf.map(it.ratio(points, imageW, imageH)) }
                val poly = Path().apply { moveTo(px[0].x, px[0].y); for (p in px.drop(1)) lineTo(p.x, p.y); close() }
                drawPath(poly, AppColors.accent.copy(alpha = 0.14f))
                drawPath(poly, AppColors.accent, style = Stroke(2.dp.toPx(), join = StrokeJoin.Round))
                val num = TextStyle(fontFamily = BeVietnamPro, color = AppColors.onAccent, fontSize = 13.sp, fontWeight = FontWeight.ExtraBold)
                px.forEachIndexed { i, c ->
                    val on = i == active
                    drawCircle(AppColors.accent.copy(alpha = if (on) 0.30f else 0.18f), (if (on) 26 else 22).dp.toPx(), c)
                    drawCircle(AppColors.accent, (if (on) 13 else 11).dp.toPx(), c)
                    val t = measurer.measure("${i + 1}", num)
                    drawText(t, topLeft = c - Offset(t.size.width / 2f, t.size.height / 2f))
                }
            }
        }
        Column(Modifier.width(340.dp).fillMaxHeight().background(AppColors.surface).border(1.dp, AppColors.stroke)) {
            Column(Modifier.weight(1f).verticalScroll(rememberScrollState()).padding(horizontal = Space.lg, vertical = Space.sm)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    IconButton(onBack) { Icon(Icons.AutoMirrored.Rounded.ArrowBack, "Quay lại, không lưu") }
                    Spacer(Modifier.width(Space.xs))
                    Text("Căn chỉnh nâng cao", style = AppText.title.copy(fontSize = 20.sp))
                }
                Hint("1", "Gắn chắc máy ở vị trí dùng khi lái.")
                Hint("2", "Kéo 1–2 vào mép trong vạch kẻ gần, 3–4 ở xa.")
                Hint("3", "Lưới 10–60 m phải nằm đúng trên mặt đường.")
                Spacer(Modifier.height(Space.lg))
                Row(horizontalArrangement = Arrangement.spacedBy(Space.md)) {
                    Field("Bề rộng làn", "Cao tốc: 3,75", width, { width = it }, Modifier.weight(1f))
                    Field("Chiều dài 1–4", "Theo vạch đứt", length, { length = it }, Modifier.weight(1f))
                }
                Spacer(Modifier.height(Space.md))
                Row(horizontalArrangement = Arrangement.spacedBy(Space.md)) {
                    Field("Đầu xe tới cạnh gần", "Tới điểm 1–2", near, { near = it }, Modifier.weight(1f))
                    Field("Nửa hành lang", "Vùng cảnh báo", half, { half = it }, Modifier.weight(1f))
                }
                if (mapper == null) {
                    Spacer(Modifier.height(Space.md))
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Rounded.ErrorOutline, null, tint = AppColors.danger, modifier = Modifier.size(18.dp))
                        Spacer(Modifier.width(Space.sm))
                        Text("4 điểm chưa tạo thành hình thang hợp lệ", style = AppText.caption.copy(color = AppColors.danger))
                    }
                }
            }
            Row(Modifier.fillMaxWidth().border(1.dp, AppColors.stroke).padding(Space.lg, Space.md), horizontalArrangement = Arrangement.spacedBy(Space.md)) {
                OutlinedButton({ points = CalibrationConfig.DEFAULT_POINTS }, Modifier.weight(1f).height(52.dp)) { Text("Mặc định") }
                Button({ onSave(config) }, Modifier.weight(2f).height(52.dp), enabled = mapper != null) { Text("Lưu căn chỉnh") }
            }
        }
    }
}

private fun Int.ratio(points: List<Vec2>, w: Double, h: Double) = Vec2(points[this].x * w, points[this].y * h)

internal fun fmt(v: Double): String = (if (v == Math.rint(v)) v.toLong().toString() else v.toString()).replace('.', ',')

@Composable
internal fun Field(label: String, hint: String, value: String, onChange: (String) -> Unit, modifier: Modifier) {
    OutlinedTextField(
        value, onChange, modifier,
        label = { Text(label) }, supportingText = { Text(hint) }, suffix = { Text("m") },
        singleLine = true, textStyle = AppText.bodyStrong,
        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
    )
}

@Composable
private fun Hint(n: String, text: String) {
    Row(Modifier.padding(top = Space.sm), verticalAlignment = Alignment.Top) {
        Box(Modifier.size(22.dp).background(AppColors.accentSoft, CircleShape), contentAlignment = Alignment.Center) {
            Text(n, style = AppText.caption.copy(color = AppColors.accent, fontWeight = FontWeight.ExtraBold, fontSize = 12.sp))
        }
        Spacer(Modifier.width(Space.sm + 2.dp))
        Text(text, style = AppText.caption.copy(color = AppColors.text))
    }
}
