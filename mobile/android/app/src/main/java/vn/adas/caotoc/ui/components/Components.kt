package vn.adas.caotoc.ui.components

import androidx.compose.animation.animateColorAsState
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.DarkMode
import androidx.compose.material.icons.outlined.LocalCafe
import androidx.compose.material.icons.outlined.LocalShipping
import androidx.compose.material.icons.outlined.OilBarrel
import androidx.compose.material.icons.outlined.Thunderstorm
import androidx.compose.material.icons.outlined.WaterDrop
import androidx.compose.material.icons.outlined.WbSunny
import androidx.compose.material.icons.outlined.Cloud
import androidx.compose.material.icons.rounded.CheckCircle
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import vn.adas.caotoc.ui.theme.AppColors
import vn.adas.caotoc.ui.theme.AppText
import vn.adas.caotoc.ui.theme.Radii
import vn.adas.caotoc.ui.theme.Space

/**
 * Khung "kính" nổi trên video: nền đục 84 % (không làm mờ nền - blur trên camera tốn GPU mỗi khung),
 * viền mảnh 10 %, bo góc lớn. [accent]: viền màu trạng thái.
 */
@Composable
fun GlassPanel(
    modifier: Modifier = Modifier,
    accent: Color? = null,
    radius: Dp = Radii.lg,
    padding: PaddingValues = PaddingValues(Space.lg),
    color: Color = AppColors.glass,
    content: @Composable () -> Unit,
) {
    val border by animateColorAsState(accent?.copy(alpha = 0.55f) ?: AppColors.stroke, label = "glassBorder")
    val shape = RoundedCornerShape(radius)
    Box(
        modifier
            .shadow(16.dp, shape, ambientColor = Color.Black, spotColor = Color.Black)
            .background(color, shape)
            .border(if (accent != null) 1.5.dp else 1.dp, border, shape)
            .padding(padding),
    ) { content() }
}

/** Nút tròn biểu tượng (≥ 48 dp) có nhãn cho trình đọc màn hình. */
@Composable
fun RoundAction(icon: ImageVector, label: String, onClick: () -> Unit, active: Boolean = false, size: Dp = 52.dp) {
    Box(
        Modifier
            .size(size)
            .clip(CircleShape)
            .background(if (active) AppColors.accent else AppColors.glass)
            .border(1.dp, if (active) AppColors.accent else AppColors.stroke, CircleShape)
            .clickable(role = Role.Button, onClickLabel = label, onClick = onClick)
            .semantics { contentDescription = label },
        contentAlignment = Alignment.Center,
    ) {
        Icon(icon, contentDescription = null, tint = if (active) AppColors.onAccent else AppColors.text, modifier = Modifier.size(24.dp))
    }
}

/**
 * Số hiển thị với chữ số rộng bằng nhau. Be Vietnam Pro không có tính năng tnum ("1" hẹp hơn "0" gần một
 * nửa) nên mỗi chữ số được đặt trong một ô cố định -> số nhảy liên tục không làm rung bố cục.
 */
@Composable
fun TabularNumber(text: String, style: TextStyle, modifier: Modifier = Modifier) {
    val digitW = (style.fontSize.value * 0.6f).dp
    Row(modifier.semantics { contentDescription = text }, verticalAlignment = Alignment.Bottom) {
        for (ch in text) {
            if (ch.isDigit()) {
                Text(ch.toString(), style = style, textAlign = TextAlign.Center, modifier = Modifier.width(digitW))
            } else {
                Text(ch.toString(), style = style)
            }
        }
    }
}

/** Nhãn chữ in hoa nhỏ đặt trên mỗi cụm số. */
@Composable
fun Overline(text: String, icon: ImageVector? = null, color: Color = AppColors.textSecondary) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        if (icon != null) {
            Icon(icon, contentDescription = null, tint = color, modifier = Modifier.size(14.dp))
            Spacer(Modifier.width(Space.xs + 2.dp))
        }
        Text(text.uppercase(), style = AppText.overline.copy(color = color))
    }
}

/** Viên thuốc trạng thái: chấm màu + chữ (màu không bao giờ là tín hiệu duy nhất). */
@Composable
fun StatusDot(color: Color, text: String, modifier: Modifier = Modifier) {
    Row(modifier, verticalAlignment = Alignment.CenterVertically) {
        Box(Modifier.size(8.dp).shadow(4.dp, CircleShape, spotColor = color).background(color, CircleShape))
        Spacer(Modifier.width(Space.sm))
        Text(text, style = AppText.caption, maxLines = 1, overflow = TextOverflow.Ellipsis)
    }
}

/** Ô chọn lớn (điều kiện đường, yếu tố) - chọn bằng một chạm, có dấu chọn + viền màu thương hiệu. */
@Composable
fun SelectTile(icon: ImageVector, title: String, subtitle: String, selected: Boolean, onClick: () -> Unit, modifier: Modifier = Modifier) {
    val shape = RoundedCornerShape(Radii.md)
    Box(
        modifier
            .clip(shape)
            .background(if (selected) AppColors.accentSoft else AppColors.surfaceRaised)
            .border(if (selected) 1.5.dp else 1.dp, if (selected) AppColors.accent else AppColors.stroke, shape)
            .clickable(role = Role.Checkbox, onClick = onClick)
            .semantics { contentDescription = "$title, hệ số $subtitle${if (selected) ", đang chọn" else ""}" }
            .padding(Space.md),
    ) {
        Column {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(icon, null, tint = if (selected) AppColors.accent else AppColors.text, modifier = Modifier.size(24.dp))
                Spacer(Modifier.weight(1f))
                if (selected) {
                    Icon(Icons.Rounded.CheckCircle, null, tint = AppColors.accent, modifier = Modifier.size(18.dp))
                }
            }
            Spacer(Modifier.padding(top = Space.sm))
            Text(title, style = AppText.bodyStrong.copy(fontSize = 14.sp), maxLines = 1, overflow = TextOverflow.Ellipsis)
            Text(subtitle, style = AppText.caption.copy(fontSize = 12.sp))
        }
    }
}

fun conditionIcon(key: String): ImageVector = when (key) {
    "wet" -> Icons.Outlined.WaterDrop
    "heavy_rain" -> Icons.Outlined.Thunderstorm
    "fog" -> Icons.Outlined.Cloud
    "slippery" -> Icons.Outlined.OilBarrel
    else -> Icons.Outlined.WbSunny
}

fun modifierIcon(key: String): ImageVector = when (key) {
    "night" -> Icons.Outlined.DarkMode
    "heavy_vehicle" -> Icons.Outlined.LocalShipping
    else -> Icons.Outlined.LocalCafe // mệt mỏi: gợi ý dừng nghỉ
}

/**
 * Biểu tượng app: con đường phối cảnh hội tụ về chân trời + chevron "giữ khoảng cách" màu thương hiệu.
 * Vẽ bằng vector nên sắc nét ở mọi kích thước.
 */
@Composable
fun AppMark(size: Dp = 72.dp) {
    Canvas(Modifier.size(size)) {
        val s = this.size.width
        drawRoundRect(
            Brush.linearGradient(listOf(Color(0xFF1B2B45), Color(0xFF070B12)), Offset.Zero, Offset(s, s)),
            cornerRadius = CornerRadius(s * 0.26f),
        )
        drawRoundRect(Color.White.copy(alpha = 0.10f), cornerRadius = CornerRadius(s * 0.26f), style = Stroke(s * 0.012f))
        drawCircle(
            Brush.radialGradient(listOf(AppColors.accent.copy(alpha = 0.30f), Color.Transparent), Offset(s * 0.5f, s * 0.36f), s * 0.42f),
            radius = s * 0.42f, center = Offset(s * 0.5f, s * 0.36f),
        )
        val vp = Offset(s * 0.5f, s * 0.30f)
        val road = Path().apply {
            moveTo(vp.x - s * 0.015f, vp.y); lineTo(vp.x + s * 0.015f, vp.y)
            lineTo(s * 0.86f, s * 0.86f); lineTo(s * 0.14f, s * 0.86f); close()
        }
        drawPath(road, Brush.verticalGradient(listOf(Color.White.copy(alpha = 0.05f), Color.White.copy(alpha = 0.16f)), 0f, s))
        val edge = Color.White.copy(alpha = 0.85f)
        drawLine(edge, vp, Offset(s * 0.14f, s * 0.86f), s * 0.028f, StrokeCap.Round)
        drawLine(edge, vp, Offset(s * 0.86f, s * 0.86f), s * 0.028f, StrokeCap.Round)
        for ((y, w, a) in listOf(Triple(0.74f, 0.20f, 1f), Triple(0.56f, 0.13f, 0.7f))) {
            val chev = Path().apply {
                moveTo(s * (0.5f - w), s * (y + w * 0.55f)); lineTo(s * 0.5f, s * y); lineTo(s * (0.5f + w), s * (y + w * 0.55f))
            }
            drawPath(chev, AppColors.accent.copy(alpha = a), style = Stroke(s * 0.06f, cap = StrokeCap.Round, join = StrokeJoin.Round))
        }
    }
}

/** Huy hiệu số đếm ở góc nút (số vi phạm của phiên). */
@Composable
fun Badged(count: Int, content: @Composable () -> Unit) {
    Box {
        content()
        if (count > 0) {
            Box(
                Modifier
                    .align(Alignment.TopEnd)
                    .padding(top = 0.dp)
                    .background(AppColors.warning, RoundedCornerShape(50))
                    .border(2.dp, AppColors.bg, RoundedCornerShape(50))
                    .padding(horizontal = 6.dp, vertical = 1.dp),
            ) {
                Text(if (count > 99) "99+" else "$count", style = AppText.overline.copy(color = AppColors.onWarning, letterSpacing = 0.sp))
            }
        }
    }
}
