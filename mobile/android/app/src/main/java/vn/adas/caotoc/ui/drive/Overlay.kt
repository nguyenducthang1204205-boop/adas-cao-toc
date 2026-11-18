package vn.adas.caotoc.ui.drive

import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.Shadow
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.text.TextMeasurer
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.drawText
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp
import vn.adas.caotoc.core.CLASS_LABELS_VI
import vn.adas.caotoc.core.FrameResult
import vn.adas.caotoc.core.GroundPlaneMapper
import vn.adas.caotoc.core.RangeMethod
import vn.adas.caotoc.core.Risk
import vn.adas.caotoc.core.Vec2
import vn.adas.caotoc.core.VehicleState
import vn.adas.caotoc.core.r
import vn.adas.caotoc.core.vn
import vn.adas.caotoc.ui.theme.AppColors
import vn.adas.caotoc.ui.theme.BeVietnamPro
import vn.adas.caotoc.ui.theme.onRiskColor
import vn.adas.caotoc.ui.theme.riskColor
import vn.adas.caotoc.ui.theme.riskFill
import kotlin.math.max
import kotlin.math.min

/**
 * Phép co ảnh camera vào khung nhìn kiểu "cover" (giống PreviewView FILL_CENTER / BoxFit.cover):
 * ảnh [imageW] x [imageH] phủ kín [view], phần thừa bị cắt đều hai bên.
 */
class CoverTransform(val imageW: Double, val imageH: Double, view: Size, contain: Boolean = false) {
    val scale: Float = if (contain) min(view.width / imageW, view.height / imageH).toFloat()
    else max(view.width / imageW, view.height / imageH).toFloat()
    val dx: Float = ((view.width - imageW * scale) / 2).toFloat()
    val dy: Float = ((view.height - imageH * scale) / 2).toFloat()

    fun map(p: Vec2) = Offset(dx + p.x.toFloat() * scale, dy + p.y.toFloat() * scale)
    fun map(x: Double, y: Double) = Offset(dx + x.toFloat() * scale, dy + y.toFloat() * scale)
    fun unmap(o: Offset) = Vec2(((o.x - dx) / scale).toDouble(), ((o.y - dy) / scale).toDouble())
}

/**
 * Lớp vẽ trên khung camera - cùng thiết kế với render_overlay của bản desktop (gui/rendering/overlay.py):
 *  - hành lang làn trung tính; CHỈ khoảng trống tới xe phía trước được tô theo mức rủi ro của xe đó;
 *  - vạch ngưỡng nét đứt, nhãn nguy hiểm bên trái / cảnh báo bên phải (không bao giờ chồng nhau);
 *  - chevron dẫn tới xe phía trước; hộp xe dạng góc ngoặc; nhãn viên thuốc, nhãn xe phía trước ưu tiên chỗ.
 * Vẽ trong hệ tọa độ màn hình (đã co ảnh), nên nét và chữ luôn đúng kích thước dp.
 */
class OverlayRenderer(private val measurer: TextMeasurer) {
    private val labels = ArrayList<Rect>() // nhãn đã vẽ trong khung này (tránh chồng nhau)

    fun DrawScope.draw(result: FrameResult?, mapper: GroundPlaneMapper?, tf: CoverTransform) {
        px = density
        val r = result ?: return
        if (mapper != null) corridor(mapper, r, tf)
        labels.clear()
        val lead = r.lead
        if (lead != null) vehicle(lead, tf, true) // nhãn xe phía trước được ưu tiên chỗ
        for (v in r.vehicles.asReversed()) if (v !== lead) vehicle(v, tf, false)
    }

    // ------------------------------------------------------------------ thảm đường phía trước

    private fun DrawScope.corridor(m: GroundPlaneMapper, r: FrameResult, tf: CoverTransform) {
        val half = m.calib.laneHalfWidthM
        val near = max(m.calib.nearDistanceM * 0.5, 2.5)
        val thr = r.thresholds
        val far = min(thr.safeM * 1.35, m.calib.maxRangeM)
        fun g(x: Double, y: Double) = tf.map(m.groundToImage(x, y))
        fun band(y0: Double, y1: Double) = Path().apply {
            val a = g(-half, y0); val b = g(half, y0); val c = g(half, y1); val d = g(-half, y1)
            moveTo(a.x, a.y); lineTo(b.x, b.y); lineTo(c.x, c.y); lineTo(d.x, d.y); close()
        }

        // hành lang làn trung tính tới ngưỡng an toàn (không tô đỏ khi đang an toàn)
        val lead = r.lead
        val hasGap = lead != null && lead.method == RangeMethod.IPM && lead.distanceM > near
        val pn = g(0.0, near); val pf = g(0.0, far)
        drawPath(band(near, far), Brush.verticalGradient(listOf(Color.White.copy(alpha = 0f), Color.White.copy(alpha = 0.10f)), pf.y, pn.y))
        // khoảng trống tới xe phía trước, tô theo mức rủi ro của chính xe đó
        if (hasGap) {
            val color = riskColor(lead.risk)
            val pl = g(0.0, lead.distanceM)
            drawPath(band(near, lead.distanceM), Brush.verticalGradient(listOf(color.copy(alpha = 0.38f), color.copy(alpha = 0.08f)), pl.y, pn.y))
        }
        // mép hành lang: vạch mảnh sáng, mờ dần về xa
        for (side in doubleArrayOf(-half, half)) {
            val a = g(side, near); val b = g(side, far)
            drawLine(Brush.linearGradient(listOf(Color.White.copy(alpha = 0.65f), Color.White.copy(alpha = 0f)), a, b), a, b,
                strokeWidth = 2.dp, cap = StrokeCap.Round)
        }
        // vạch mốc ngưỡng: nhãn nguy hiểm bên trái, cảnh báo bên phải; không vẽ đè lên xe phía trước
        val limit = if (hasGap) lead.distanceM - 1.0 else far
        for ((d, color, right) in listOf(Triple(thr.dangerM, AppColors.danger, false), Triple(thr.safeM, AppColors.warning, true))) {
            if (d >= far || d >= limit || d <= near) continue
            val a = g(-half, d); val b = g(half, d)
            dashed(a, b, color, 2.dp)
            val label = "${d.r()} m"
            if (right) {
                pill(label, b + Offset(8.dp, -8.dp), color, 11f, filled = false)
            } else {
                pill(label, a + Offset(-8.dp, -8.dp), color, 11f, filled = false, alignRight = true)
            }
        }
        // chevron dẫn tới xe phía trước (cùng làn, đo bằng IPM)
        if (hasGap && lead.distanceM > near + 2) {
            val color = riskColor(lead.risk)
            for (f in doubleArrayOf(0.3, 0.55, 0.8)) {
                val y = near + (lead.distanceM - near) * f
                val apex = g(0.0, y + 1.5); val l = g(-half * 0.35, y); val rr = g(half * 0.35, y)
                val path = Path().apply { moveTo(l.x, l.y); lineTo(apex.x, apex.y); lineTo(rr.x, rr.y) }
                drawPath(path, color.copy(alpha = (0.35 + 0.5 * f).toFloat()), style = Stroke(3.dp, cap = StrokeCap.Round, join = StrokeJoin.Round))
            }
        }
    }

    private fun DrawScope.dashed(a: Offset, b: Offset, color: Color, w: Float) {
        val len = (b - a).getDistance()
        if (len < 1) return
        val dir = (b - a) / len
        val dash = 8.dp; val gap = 6.dp
        var s = 0f
        while (s < len) {
            drawLine(color.copy(alpha = 0.9f), a + dir * s, a + dir * min(s + dash, len), w, StrokeCap.Round)
            s += dash + gap
        }
    }

    // ------------------------------------------------------------------ xe

    private fun DrawScope.vehicle(v: VehicleState, tf: CoverTransform, isLead: Boolean) {
        val d = v.det
        val tl = tf.map(d.x1, d.y1); val br = tf.map(d.x2, d.y2)
        val rect = Rect(tl, br)
        val outOfLane = v.risk == Risk.INFO
        val color = if (isLead) riskColor(v.risk) else Color.White.copy(alpha = if (outOfLane) 0.45f else 0.75f)
        val w = if (isLead) 3.dp else 1.6.dp
        val c = min(rect.width, rect.height) * 0.22f + 4.dp
        if (isLead) {
            // quầng nhẹ sau góc ngoặc của xe đang được theo dõi
            drawRoundRect(color.copy(alpha = 0.10f), rect.topLeft, rect.size, CornerRadius(6.dp))
        }
        val stroke = Stroke(w, cap = StrokeCap.Round)
        for ((o, dx, dy) in listOf(Triple(rect.topLeft, 1f, 1f), Triple(rect.topRight, -1f, 1f),
            Triple(rect.bottomLeft, 1f, -1f), Triple(rect.bottomRight, -1f, -1f))) {
            drawPath(Path().apply { moveTo(o.x, o.y + dy * c); lineTo(o.x, o.y); lineTo(o.x + dx * c, o.y) }, color, style = stroke)
        }
        if (v.method == RangeMethod.FAR) return
        if (isLead) {
            var text = "${vn(v.distanceM)} m"
            v.ttcS?.let { text += "  ·  ${vn(it)} s" }
            pill(text, Offset(rect.center.x, rect.top - 8.dp), riskFill(v.risk), 14f, textColor = onRiskColor(v.risk), centered = true, above = true)
        } else if (v.distanceM < 90) {
            val name = CLASS_LABELS_VI[d.className] ?: d.className
            pill("$name ${v.distanceM.r()} m", Offset(rect.center.x, rect.top - 6.dp), Color(0xCC0C1117), 11f,
                textColor = AppColors.text, centered = true, above = true, avoid = true)
        }
    }

    private fun DrawScope.pill(
        text: String, at: Offset, color: Color, fontSp: Float,
        filled: Boolean = true, textColor: Color = Color.White, centered: Boolean = false, above: Boolean = false,
        alignRight: Boolean = false, avoid: Boolean = false,
    ) {
        val style = TextStyle(
            fontFamily = BeVietnamPro, fontSize = fontSp.sp, fontWeight = FontWeight.Bold,
            color = if (filled) textColor else color,
            shadow = if (filled) null else Shadow(Color.Black, blurRadius = 4.dp),
        )
        val layout = measurer.measure(text, style)
        val padH = if (filled) 9.dp else 0f; val padV = if (filled) 4.dp else 0f
        val w = layout.size.width + 2 * padH; val h = layout.size.height + 2 * padV
        val x = when { centered -> at.x - w / 2; alignRight -> at.x - w; else -> at.x }
        val y = max(0f, if (above) at.y - h else at.y)
        val rect = Rect(x, y, x + w, y + h)
        if (avoid && labels.any { it.overlaps(rect.inflate(2.dp)) }) return
        if (avoid || filled) labels += rect
        if (filled) drawRoundRect(color, rect.topLeft, rect.size, CornerRadius(h / 2))
        drawText(layout, topLeft = Offset(x + padH, y + padV))
    }

    /** dp -> px theo mật độ màn hình của lần vẽ hiện tại. */
    private val Number.dp: Float get() = toFloat() * px
    private var px = 1f
}
