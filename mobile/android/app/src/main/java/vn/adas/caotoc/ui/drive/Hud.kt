package vn.adas.caotoc.ui.drive

import android.provider.Settings
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.scaleIn
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.VolumeOff
import androidx.compose.material.icons.automirrored.outlined.VolumeUp
import androidx.compose.material.icons.outlined.CheckCircle
import androidx.compose.material.icons.outlined.DirectionsCar
import androidx.compose.material.icons.outlined.NoPhotography
import androidx.compose.material.icons.outlined.SmartToy
import androidx.compose.material.icons.outlined.SocialDistance
import androidx.compose.material.icons.outlined.Speed
import androidx.compose.material.icons.outlined.Straighten
import androidx.compose.material.icons.outlined.Tune
import androidx.compose.material.icons.outlined.WarningAmber
import androidx.compose.material.icons.rounded.Add
import androidx.compose.material.icons.rounded.ChevronRight
import androidx.compose.material.icons.rounded.Remove
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.TransformOrigin
import androidx.compose.ui.layout.Layout
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.drawText
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.rememberTextMeasurer
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Constraints
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import kotlinx.coroutines.flow.StateFlow
import vn.adas.caotoc.core.CalibStatus
import vn.adas.caotoc.core.FrameResult
import vn.adas.caotoc.core.GroundPlaneMapper
import vn.adas.caotoc.core.MODIFIERS
import vn.adas.caotoc.core.ROAD_CONDITIONS
import vn.adas.caotoc.core.Risk
import vn.adas.caotoc.core.SafetyPolicy
import vn.adas.caotoc.core.Thresholds
import vn.adas.caotoc.core.VehicleState
import vn.adas.caotoc.core.computeThresholds
import vn.adas.caotoc.core.r
import vn.adas.caotoc.core.thresholdBasis
import vn.adas.caotoc.core.vn
import vn.adas.caotoc.ui.components.Badged
import vn.adas.caotoc.ui.components.GlassPanel
import vn.adas.caotoc.ui.components.Overline
import vn.adas.caotoc.ui.components.RoundAction
import vn.adas.caotoc.ui.components.StatusDot
import vn.adas.caotoc.ui.components.TabularNumber
import vn.adas.caotoc.ui.components.conditionIcon
import vn.adas.caotoc.ui.theme.AppColors
import vn.adas.caotoc.ui.theme.AppText
import vn.adas.caotoc.ui.theme.BeVietnamPro
import vn.adas.caotoc.ui.theme.Radii
import vn.adas.caotoc.ui.theme.Space
import vn.adas.caotoc.ui.theme.onRiskColor
import vn.adas.caotoc.ui.theme.riskColor
import vn.adas.caotoc.ui.theme.riskFill
import vn.adas.caotoc.ui.theme.riskIcon
import vn.adas.caotoc.ui.theme.riskLabel
import vn.adas.caotoc.ui.theme.riskMessage
import kotlin.math.max

enum class SpeedSource { GPS, MANUAL, WAITING, NO_PERMISSION, GPS_OFF }

/** Mọi thứ HUD cần để vẽ (phần trình bày thuần, không camera / không logic). */
data class HudState(
    val result: FrameResult?,
    val mapper: GroundPlaneMapper?,
    val imageW: Double,
    val imageH: Double,
    val speedKmh: Double,
    val speedSource: SpeedSource,
    val policy: SafetyPolicy,
    val conditionKey: String,
    val modifiers: Set<String>,
    val calibrated: Boolean,
    val soundOn: Boolean,
    val cameraReady: Boolean,
    /** null: ẩn thông số kỹ thuật. */
    val techText: String? = null,
    val perfNotice: PerfNotice? = null,
    val error: String? = null,
    /** Số đợt vi phạm của phiên giám sát này. */
    val violations: Int = 0,
    /** Tự hoàn thiện căn chỉnh khi chạy (null: ẩn). */
    val calib: CalibStatus? = null,
) {
    val thresholds: Thresholds get() = result?.thresholds ?: computeThresholds(speedKmh, policy)
    val level: Risk get() = result?.level ?: Risk.SAFE
}

class HudActions(
    val onCalibrate: () -> Unit = {},
    val onSettings: () -> Unit = {},
    val onToggleSound: () -> Unit = {},
    val onConditions: () -> Unit = {},
    val onSpeedStep: (Double) -> Unit = {},
    val onAssistant: (() -> Unit)? = null,
    val onRetry: (() -> Unit)? = null,
)

/**
 * Màn hình lái - phần trình bày: camera tràn viền, các cụm đồng hồ nổi.
 *
 * Thứ bậc thông tin (liếc < 1 giây): 1) màu + chữ trạng thái (banner, viền phát sáng); 2) khoảng cách tới xe
 * trước; 3) tốc độ và khoảng cách cần giữ; 4) điều khiển ở các góc. [live]: kết quả mới nhất cho overlay - chỉ
 * lớp overlay vẽ lại theo nhịp xử lý, các cụm đồng hồ dựng lại theo [s] (~10 lần/giây).
 */
@Composable
fun DriveHud(s: HudState, actions: HudActions, live: StateFlow<FrameResult?>?, camera: (@Composable () -> Unit)?) {
    BoxWithConstraints(Modifier.fillMaxSize().background(AppColors.bg)) {
        val pad = if (maxWidth > 900.dp) Space.xl else Space.lg
        val sideW = (maxWidth * 0.26f).coerceIn(212.dp, 292.dp)
        val level = s.level
        if (camera != null) {
            camera()
            OverlayLayer(live, s.result, s.mapper, s.imageW, s.imageH)
        }
        // làm tối nhẹ mép trên/dưới để cụm đồng hồ luôn đọc được trên trời sáng
        Box(
            Modifier.fillMaxSize().background(
                Brush.verticalGradient(0f to Color(0x99000000), 0.32f to Color.Transparent, 0.7f to Color.Transparent, 1f to Color(0x80000000)),
            ),
        )
        when {
            s.error != null -> ErrorCard(s.error, actions.onRetry, Modifier.align(Alignment.Center))
            !s.cameraReady -> Starting(Modifier.align(Alignment.Center))
        }
        EdgeGlow(level)
        // cụm trái: xe phía trước
        FitHeight(Modifier.align(Alignment.TopStart).padding(start = pad, top = pad, bottom = pad + 52.dp + Space.md).width(sideW), alignEnd = false) {
            DistanceCluster(s)
        }
        // cụm phải: tốc độ + khoảng cách cần giữ + điều kiện đường
        FitHeight(Modifier.align(Alignment.TopEnd).padding(end = pad, top = pad, bottom = pad).width(sideW), alignEnd = true) {
            SpeedCluster(s, actions.onConditions, actions.onSpeedStep)
        }
        // giữa trên: trạng thái
        Column(
            Modifier.align(Alignment.TopCenter).padding(top = pad, start = sideW + pad * 2, end = sideW + pad * 2),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(Space.sm),
        ) {
            AlertBanner(level, s.result?.vehicles?.size, s.result != null)
            s.perfNotice?.let { PerfNoticeView(it) }
            s.calib?.let { CalibStatusView(it, actions.onCalibrate) }
            s.techText?.let { TechReadout(it) }
        }
        if (!s.calibrated) {
            CalibrateNotice(actions.onCalibrate, Modifier.align(Alignment.BottomCenter).padding(bottom = pad, start = sideW + pad * 2, end = sideW + pad * 2))
        }
        // dock điều khiển: góc dưới trái (xa vùng nhìn đường phía trước)
        Row(Modifier.align(Alignment.BottomStart).padding(start = pad, bottom = pad), horizontalArrangement = Arrangement.spacedBy(Space.sm + 2.dp)) {
            RoundAction(
                if (s.soundOn) Icons.AutoMirrored.Outlined.VolumeUp else Icons.AutoMirrored.Outlined.VolumeOff,
                if (s.soundOn) "Tắt âm thanh cảnh báo" else "Bật âm thanh cảnh báo",
                actions.onToggleSound, active = !s.soundOn,
            )
            RoundAction(Icons.Outlined.Straighten, "Căn chỉnh camera", actions.onCalibrate)
            RoundAction(Icons.Outlined.Tune, "Cài đặt", actions.onSettings)
            actions.onAssistant?.let { open ->
                Badged(s.violations) {
                    RoundAction(Icons.Outlined.SmartToy,
                        if (s.violations > 0) "Trợ lý AI và ${s.violations} vi phạm" else "Trợ lý AI và nhật ký vi phạm", open)
                }
            }
        }
    }
}

/** Lớp overlay: tự thu kết quả mới nhất để chỉ lớp này vẽ lại theo nhịp xử lý. */
@Composable
private fun OverlayLayer(live: StateFlow<FrameResult?>?, fallback: FrameResult?, mapper: GroundPlaneMapper?, iw: Double, ih: Double) {
    val measurer = rememberTextMeasurer(cacheSize = 32)
    val renderer = remember(measurer) { OverlayRenderer(measurer) }
    val latest = live?.collectAsStateWithLifecycle()
    Canvas(Modifier.fillMaxSize()) {
        val tf = CoverTransform(iw, ih, size)
        with(renderer) { draw(latest?.value ?: fallback, mapper, tf) }
    }
}

/** Co nội dung (theo tỉ lệ) khi cao hơn chỗ cho phép - thay FittedBox(scaleDown) trên màn hình thấp. */
@Composable
private fun FitHeight(modifier: Modifier, alignEnd: Boolean, content: @Composable () -> Unit) {
    Layout(content, modifier) { measurables, constraints ->
        val p = measurables.first().measure(constraints.copy(minHeight = 0, maxHeight = Constraints.Infinity))
        val maxH = constraints.maxHeight
        val scale = if (constraints.hasBoundedHeight && p.height > maxH) maxH.toFloat() / p.height else 1f
        layout(p.width, if (scale < 1f) maxH else p.height) {
            p.placeWithLayer(0, 0) {
                scaleX = scale; scaleY = scale
                transformOrigin = TransformOrigin(if (alignEnd) 1f else 0f, 0f)
            }
        }
    }
}

// ---------------------------------------------------------------------- cụm khoảng cách

@Composable
private fun DistanceCluster(s: HudState) {
    val lead = s.result?.lead
    val thr = s.thresholds
    val level = s.level
    val color = lead?.let { riskColor(it.risk) } ?: AppColors.textSecondary
    GlassPanel(Modifier.fillMaxWidth(), accent = if (level == Risk.SAFE) null else riskColor(level)) {
        Column {
            Overline("Xe phía trước", Icons.Outlined.DirectionsCar)
            Spacer(Modifier.height(Space.sm))
            if (lead != null) {
                Row(verticalAlignment = Alignment.Bottom) {
                    TabularNumber(vn(lead.distanceM), AppText.display.copy(color = color))
                    Spacer(Modifier.width(Space.xs))
                    Text("m", style = AppText.unit.copy(fontSize = 20.sp), modifier = Modifier.padding(bottom = 8.dp))
                }
            } else {
                Text("—", style = AppText.display.copy(color = AppColors.textSecondary))
                Text("Không có xe cùng làn", style = AppText.caption)
            }
            Spacer(Modifier.height(Space.md))
            GapGauge(lead?.distanceM, thr.dangerM, thr.safeM)
            Spacer(Modifier.height(Space.md))
            Row {
                Metric("Va chạm sau", ttcText(lead), alert = (lead?.ttcS ?: 99.0) < 4, modifier = Modifier.weight(1f))
                Metric("Tiếp cận", closingText(lead), modifier = Modifier.weight(1f))
            }
        }
    }
}

private fun ttcText(v: VehicleState?) = v?.ttcS?.let { "${vn(it)} s" } ?: "—"

private fun closingText(v: VehicleState?): String {
    val c = v?.closingSpeedMps ?: return "—"
    if (kotlin.math.abs(c) < 0.5) return "—"
    return if (c > 0) "${(c * 3.6).r()} km/h" else "Xa dần"
}

@Composable
private fun Metric(label: String, value: String, modifier: Modifier = Modifier, alert: Boolean = false) {
    Column(modifier) {
        Text(label, style = AppText.caption.copy(fontSize = 12.sp))
        Spacer(Modifier.height(2.dp))
        Text(value, style = AppText.bodyStrong.copy(fontSize = 17.sp, color = if (alert) AppColors.warning else AppColors.text))
    }
}

/** Thước khoảng cách: vạch đỏ / hổ phách / xanh theo 2 ngưỡng, chấm trắng là xe phía trước. */
@Composable
fun GapGauge(distance: Double?, dangerM: Double, safeM: Double) {
    val measurer = rememberTextMeasurer()
    val label = if (distance == null) "Ngưỡng nguy hiểm ${dangerM.r()} mét, cảnh báo ${safeM.r()} mét"
    else "Xe phía trước ${distance.r()} mét; nguy hiểm dưới ${dangerM.r()}, cảnh báo dưới ${safeM.r()} mét"
    val labelStyle = TextStyle(fontFamily = BeVietnamPro, fontSize = 11.sp, fontWeight = FontWeight.SemiBold, color = AppColors.textSecondary)
    Canvas(Modifier.fillMaxWidth().height(34.dp).semantics { contentDescription = label }) {
        val maxD = max(safeM * 1.6, (distance ?: 0.0) * 1.1)
        fun x(v: Double) = ((v / maxD).coerceIn(0.0, 1.0) * size.width).toFloat()
        val barH = 6.dp.toPx(); val top = 6.dp.toPx()
        val segs = listOf(Triple(0.0, dangerM, AppColors.danger), Triple(dangerM, safeM, AppColors.warning), Triple(safeM, maxD, AppColors.safe))
        segs.forEachIndexed { i, (a, b, c) ->
            val l = x(a) + if (i == 0) 0f else 1.5.dp.toPx()
            val rr = x(b) - if (i == 2) 0f else 1.5.dp.toPx()
            if (rr > l) drawRoundRect(c.copy(alpha = if (distance == null) 0.35f else 0.85f), Offset(l, top), Size(rr - l, barH), CornerRadius(2.dp.toPx()))
        }
        for (v in doubleArrayOf(dangerM, safeM)) {
            val t = measurer.measure("${v.r()}", labelStyle)
            val tx = (x(v) - t.size.width / 2).coerceIn(0f, max(0f, size.width - t.size.width))
            drawText(t, topLeft = Offset(tx, top + barH + 5.dp.toPx()))
        }
        if (distance != null) {
            val c = Offset(x(distance), top + barH / 2)
            drawCircle(Color.Black.copy(alpha = 0.5f), 8.dp.toPx(), c)
            drawCircle(Color.White, 6.5.dp.toPx(), c)
        }
    }
}

// ---------------------------------------------------------------------- cụm tốc độ

@Composable
private fun SpeedCluster(s: HudState, onConditions: () -> Unit, onSpeedStep: (Double) -> Unit) {
    val thr = s.thresholds
    val manual = s.speedSource != SpeedSource.GPS
    val (srcColor, srcText) = when (s.speedSource) {
        SpeedSource.GPS -> AppColors.safe to "GPS"
        SpeedSource.MANUAL -> AppColors.info to "Nhập tay"
        SpeedSource.WAITING -> AppColors.warning to "Chờ GPS"
        SpeedSource.NO_PERMISSION -> AppColors.danger to "Chưa cấp quyền vị trí"
        SpeedSource.GPS_OFF -> AppColors.warning to "GPS đang tắt"
    }
    GlassPanel(Modifier.fillMaxWidth()) {
        Column {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Overline("Tốc độ", Icons.Outlined.Speed)
                Spacer(Modifier.weight(1f))
                StatusDot(srcColor, srcText)
            }
            Spacer(Modifier.height(Space.sm))
            Row(verticalAlignment = Alignment.CenterVertically) {
                Row(verticalAlignment = Alignment.Bottom) {
                    TabularNumber("${s.speedKmh.r()}", AppText.numeral)
                    Spacer(Modifier.width(Space.xs + 2.dp))
                    Text("km/h", style = AppText.unit, modifier = Modifier.padding(bottom = 4.dp))
                }
                Spacer(Modifier.weight(1f))
                if (manual) {
                    RoundAction(Icons.Rounded.Remove, "Giảm tốc độ nhập tay", { onSpeedStep(-10.0) }, size = 48.dp)
                    Spacer(Modifier.width(Space.sm))
                    RoundAction(Icons.Rounded.Add, "Tăng tốc độ nhập tay", { onSpeedStep(10.0) }, size = 48.dp)
                }
            }
            if (thr.overSpeedLimit) {
                Spacer(Modifier.height(Space.xs))
                Text("Vượt 120 km/h - tốc độ tối đa cao tốc", style = AppText.caption.copy(color = AppColors.danger))
            }
            Spacer(Modifier.height(Space.md))
            HorizontalDivider(color = AppColors.stroke)
            Spacer(Modifier.height(Space.md))
            Overline("Giữ tối thiểu", Icons.Outlined.SocialDistance)
            Spacer(Modifier.height(Space.xs))
            Row(verticalAlignment = Alignment.Bottom) {
                TabularNumber("${thr.safeM.r()}", AppText.numeral.copy(fontSize = 38.sp))
                Spacer(Modifier.width(Space.xs))
                Text("m", style = AppText.unit.copy(fontSize = 18.sp), modifier = Modifier.padding(bottom = 4.dp))
            }
            Spacer(Modifier.height(Space.xs))
            StatusDot(AppColors.danger, "Nguy hiểm dưới ${thr.dangerM.r()} m")
            Spacer(Modifier.height(2.dp))
            Text(thresholdBasis(thr, s.policy), style = AppText.caption.copy(fontSize = 12.sp))
            Spacer(Modifier.height(Space.md))
            ConditionButton(s.conditionKey, s.modifiers, onConditions)
        }
    }
}

@Composable
private fun ConditionButton(conditionKey: String, mods: Set<String>, onClick: () -> Unit) {
    val cond = ROAD_CONDITIONS.getValue(conditionKey)
    val extra = mods.map { MODIFIERS[it]?.shortName ?: it }.joinToString(" · ")
    val shape = RoundedCornerShape(Radii.md)
    Row(
        Modifier
            .fillMaxWidth()
            .heightIn(min = 52.dp)
            .clip(shape)
            .background(Color.White.copy(alpha = 0.06f))
            .border(1.dp, AppColors.stroke, shape)
            .clickable(role = Role.Button, onClick = onClick)
            .semantics { contentDescription = "Điều kiện đường: ${cond.name}${if (extra.isEmpty()) "" else ", $extra"}. Chạm để đổi" }
            .padding(horizontal = Space.md, vertical = Space.sm),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(conditionIcon(conditionKey), null, tint = AppColors.accent, modifier = Modifier.size(22.dp))
        Spacer(Modifier.width(Space.md))
        Column(Modifier.weight(1f)) {
            Text(cond.shortName, style = AppText.bodyStrong.copy(fontSize = 14.sp))
            if (extra.isNotEmpty()) Text(extra, style = AppText.caption.copy(fontSize = 12.sp), maxLines = 1, overflow = TextOverflow.Ellipsis)
        }
        Icon(Icons.Rounded.ChevronRight, null, tint = AppColors.textSecondary)
    }
}

// ---------------------------------------------------------------------- trạng thái & thông báo

@Composable
fun AlertBanner(level: Risk, vehicles: Int?, ready: Boolean) {
    val alert = level == Risk.WARNING || level == Risk.DANGER
    AnimatedContent(
        targetState = Triple(alert, level, ready),
        transitionSpec = { (fadeIn(tween(220)) + scaleIn(tween(220), initialScale = 0.96f)) togetherWith fadeOut(tween(120)) },
        label = "banner",
        modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite },
    ) { (isAlert, lv, rd) ->
        if (isAlert) {
            val fg = onRiskColor(lv)
            Row(
                Modifier
                    .shadow(28.dp, RoundedCornerShape(50), spotColor = riskColor(lv))
                    .background(riskFill(lv), RoundedCornerShape(50))
                    .padding(horizontal = Space.xl - 4.dp, vertical = Space.md - 2.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Icon(riskIcon(lv), null, tint = fg, modifier = Modifier.size(22.dp))
                Spacer(Modifier.width(Space.sm + 2.dp))
                Text(riskLabel(lv), style = AppText.bodyStrong.copy(color = fg, fontWeight = FontWeight.ExtraBold, letterSpacing = 1.2.sp))
                Box(Modifier.padding(horizontal = Space.md).width(1.dp).height(18.dp).background(fg.copy(alpha = 0.4f)))
                Text(riskMessage(lv), style = AppText.bodyStrong.copy(color = fg), maxLines = 1, overflow = TextOverflow.Ellipsis)
            }
        } else {
            GlassPanel(radius = 999.dp, padding = PaddingValues(horizontal = Space.lg, vertical = Space.sm + 2.dp)) {
                StatusDot(if (rd) AppColors.safe else AppColors.info,
                    if (!rd) "Đang khởi động nhận diện…" else "Đang giám sát · ${vehicles ?: 0} xe trong khung")
            }
        }
    }
}

/**
 * Viền phát sáng quanh màn hình theo mức cảnh báo - thấy được bằng thị giác ngoại vi, không cần nhìn
 * thẳng. NGUY HIỂM: nhịp đập 1,1 s (tắt khi hệ điều hành bật giảm chuyển động).
 */
@Composable
private fun EdgeGlow(level: Risk) {
    val context = LocalContext.current
    val reduced = remember { Settings.Global.getFloat(context.contentResolver, Settings.Global.ANIMATOR_DURATION_SCALE, 1f) == 0f }
    val on = level == Risk.WARNING || level == Risk.DANGER
    val alpha by animateFloatAsState(if (on) 1f else 0f, tween(220), label = "glow")
    val pulse = rememberInfiniteTransition(label = "pulse")
    val p by pulse.animateFloat(0.45f, 1f, infiniteRepeatable(tween(1100), RepeatMode.Reverse), label = "pulseValue")
    if (alpha <= 0f) return
    val strength = when {
        level == Risk.DANGER && !reduced -> p
        level == Risk.DANGER -> 1f
        else -> 0.7f
    }
    val color = riskColor(if (on) level else Risk.WARNING)
    Canvas(Modifier.fillMaxSize()) {
        val w = minOf(size.minDimension * 0.16f, 64.dp.toPx())
        val c0 = color.copy(alpha = 0.55f * strength * alpha); val c1 = color.copy(alpha = 0f)
        drawRect(Brush.verticalGradient(listOf(c0, c1), 0f, w), Offset.Zero, Size(size.width, w))
        drawRect(Brush.verticalGradient(listOf(c1, c0), size.height - w, size.height), Offset(0f, size.height - w), Size(size.width, w))
        drawRect(Brush.horizontalGradient(listOf(c0, c1), 0f, w), Offset.Zero, Size(w, size.height))
        drawRect(Brush.horizontalGradient(listOf(c1, c0), size.width - w, size.width), Offset(size.width - w, 0f), Size(w, size.height))
    }
}

@Composable
private fun CalibrateNotice(onCalibrate: () -> Unit, modifier: Modifier) {
    Box(modifier) {
        GlassPanel(radius = 999.dp, accent = AppColors.warning, padding = PaddingValues(start = Space.lg, end = Space.xs, top = Space.xs, bottom = Space.xs)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Outlined.Straighten, null, tint = AppColors.warning, modifier = Modifier.size(20.dp))
                Spacer(Modifier.width(Space.sm + 2.dp))
                Column {
                    Text("Chưa căn chỉnh camera", style = AppText.bodyStrong.copy(fontSize = 14.sp))
                    Text("Khoảng cách chưa chính xác", style = AppText.caption.copy(fontSize = 12.sp))
                }
                Spacer(Modifier.width(Space.xs))
                TextButton(onClick = onCalibrate) { Text("Căn chỉnh", color = AppColors.accent) }
            }
        }
    }
}

/** Tự hoàn thiện căn chỉnh: tiến độ 0-100 %, kết quả tự kiểm tra ("làn đo được 3,72 m - đạt"), camera xê dịch. */
@Composable
private fun CalibStatusView(st: CalibStatus, onCalibrate: () -> Unit) {
    val attention = st.state == "drift" || st.ok == false
    val (icon, tint) = when {
        st.state == "collecting" -> Icons.Outlined.Straighten to AppColors.accent
        attention -> Icons.Outlined.WarningAmber to AppColors.warning
        else -> Icons.Outlined.CheckCircle to AppColors.safe
    }
    GlassPanel(
        Modifier.widthIn(max = 460.dp).semantics { liveRegion = LiveRegionMode.Polite }, radius = Radii.sm,
        accent = if (attention) AppColors.warning else null,
        padding = PaddingValues(start = Space.md, end = if (attention) Space.xs else Space.md, top = Space.sm, bottom = Space.sm),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Icon(icon, null, tint = tint, modifier = Modifier.size(18.dp))
            Spacer(Modifier.width(Space.sm))
            Column(Modifier.weight(1f, fill = false)) {
                Text(st.message, style = AppText.caption.copy(fontSize = 12.sp, color = AppColors.text))
                if (st.state == "collecting") {
                    Spacer(Modifier.height(Space.xs))
                    LinearProgressIndicator(
                        progress = { st.progress / 100f }, Modifier.fillMaxWidth().height(4.dp).clip(RoundedCornerShape(2.dp)),
                        color = AppColors.accent, trackColor = AppColors.stroke,
                    )
                }
            }
            if (attention) TextButton(onClick = onCalibrate) { Text("Căn chỉnh", color = AppColors.accent) }
        }
    }
}

@Composable
private fun TechReadout(text: String) {
    GlassPanel(radius = Radii.sm, padding = PaddingValues(horizontal = Space.md, vertical = Space.xs + 2.dp)) {
        Text(text, textAlign = TextAlign.Center, style = AppText.caption.copy(fontSize = 11.sp, lineHeight = 15.sp))
    }
}

/** Kết quả tự kiểm tra máy: mức hiệu năng và nhịp cảnh báo; máy yếu thì nói rõ cảnh báo chỉ để tham khảo. */
@Composable
private fun PerfNoticeView(n: PerfNotice) {
    GlassPanel(
        Modifier.semantics { liveRegion = LiveRegionMode.Polite }, radius = Radii.sm,
        accent = if (n.weak) AppColors.warning else null,
        padding = PaddingValues(horizontal = Space.md, vertical = Space.sm),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Icon(if (n.weak) Icons.Outlined.WarningAmber else Icons.Outlined.Speed, null,
                tint = if (n.weak) AppColors.warning else AppColors.textSecondary, modifier = Modifier.size(18.dp))
            Spacer(Modifier.width(Space.sm))
            Text(n.text, textAlign = TextAlign.Center, style = AppText.caption.copy(fontSize = 12.sp, color = AppColors.text))
        }
    }
}

@Composable
private fun Starting(modifier: Modifier) {
    GlassPanel(modifier) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            CircularProgressIndicator(Modifier.size(20.dp), color = AppColors.accent, strokeWidth = 2.5.dp)
            Spacer(Modifier.width(Space.md))
            Text("Đang khởi động camera và mô hình AI…", style = AppText.body)
        }
    }
}

@Composable
private fun ErrorCard(message: String, onRetry: (() -> Unit)?, modifier: Modifier) {
    GlassPanel(modifier.widthIn(max = 440.dp), padding = PaddingValues(Space.xl)) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Icon(Icons.Outlined.NoPhotography, null, tint = AppColors.warning, modifier = Modifier.size(36.dp))
            Spacer(Modifier.height(Space.md))
            Text("Không mở được camera", style = AppText.title)
            Spacer(Modifier.height(Space.sm))
            Text(message, style = AppText.caption, textAlign = TextAlign.Center)
            if (onRetry != null) {
                Spacer(Modifier.height(Space.lg))
                Button(onClick = onRetry) { Text("Thử lại") }
            }
        }
    }
}
