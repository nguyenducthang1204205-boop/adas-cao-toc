package vn.adas.caotoc.ui.theme

import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.ErrorOutline
import androidx.compose.material.icons.rounded.Verified
import androidx.compose.material.icons.rounded.Warning
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.em
import androidx.compose.ui.unit.sp
import vn.adas.caotoc.R
import vn.adas.caotoc.core.Risk

/**
 * Hệ thống thiết kế "Night Drive": token màu, chữ, khoảng cách, bo góc. Bản desktop dùng cùng token ở
 * gui/theme.py - đổi ở đây thì đổi cả bên đó.
 *
 * Nguyên tắc (màn hình hỗ trợ lái, nhìn lướt < 1 giây, dùng chủ yếu ban đêm):
 *  - Nền OLED đen sâu; chữ trắng ngà (không trắng tinh) để không chói khi lái đêm.
 *  - Màu chỉ mang nghĩa: xanh / hổ phách / đỏ dành riêng cho mức rủi ro và luôn đi kèm chữ + biểu tượng.
 *    Màu thương hiệu (xanh dương) chỉ cho điều khiển tương tác.
 * Tương phản WCAG (đã đo): trên surface - text 16,4:1 · textSecondary 8,2:1 · textTertiary 5,0:1 ·
 * accent 6,7:1 · danger 5,7:1. Trên cụm kính khi video phía sau là trời trắng: textTertiary chỉ 3,3:1 ->
 * KHÔNG dùng textTertiary trong HUD. Chữ trắng trên danger chỉ 3,3:1 nên nền đặc dùng dangerFill (4,8:1).
 */
object AppColors {
    // nền & bề mặt
    val bg = Color(0xFF05070A)
    val surface = Color(0xFF0F141B)
    val surfaceRaised = Color(0xFF161D26)
    val glass = Color(0xD60C1117) // cụm đồng hồ nổi trên video (84 % đục: đọc được trên nền sáng)
    val glassStrong = Color(0xEB0C1117)
    val stroke = Color(0x1AFFFFFF)
    val strokeStrong = Color(0x29FFFFFF)
    val scrim = Color(0xB3000000)

    // chữ
    val text = Color(0xFFEEF2F6)
    val textSecondary = Color(0xFFA3AEBB)
    val textTertiary = Color(0xFF7B8794)

    // thương hiệu / tương tác
    val accent = Color(0xFF4C9EFF)
    val accentSoft = Color(0x294C9EFF)
    val onAccent = Color(0xFF04101F)

    // ngữ nghĩa rủi ro
    val safe = Color(0xFF2FD27A)
    val warning = Color(0xFFFFB020)
    val danger = Color(0xFFFF4D4F)
    val dangerFill = Color(0xFFD92D20)
    val info = Color(0xFF9AA8B8)
    val onWarning = Color(0xFF1A1200)
}

object Space {
    val xs = 4.dp
    val sm = 8.dp
    val md = 12.dp
    val lg = 16.dp
    val xl = 24.dp
    val xxl = 32.dp
}

object Radii {
    val sm = 10.dp
    val md = 16.dp
    val lg = 22.dp
}

/** Be Vietnam Pro (OFL): thiết kế cho tiếng Việt. Thiếu glyph μ → ↔ ● ✓ ⚠ nên không dùng trong chữ giao diện. */
val BeVietnamPro = FontFamily(
    Font(R.font.be_vietnam_pro_regular, FontWeight.Normal),
    Font(R.font.be_vietnam_pro_medium, FontWeight.Medium),
    Font(R.font.be_vietnam_pro_semi_bold, FontWeight.SemiBold),
    Font(R.font.be_vietnam_pro_bold, FontWeight.Bold),
    Font(R.font.be_vietnam_pro_extra_bold, FontWeight.ExtraBold),
)

object AppText {
    private val base = TextStyle(fontFamily = BeVietnamPro, color = AppColors.text, lineHeight = 1.2.em)

    /** Số đo chính (khoảng cách tới xe trước). */
    val display = base.copy(fontSize = 64.sp, fontWeight = FontWeight.ExtraBold, lineHeight = 1.0.em, letterSpacing = (-1.5).sp)

    /** Tốc độ xe. */
    val numeral = base.copy(fontSize = 44.sp, fontWeight = FontWeight.Bold, lineHeight = 1.0.em, letterSpacing = (-1).sp)
    val title = base.copy(fontSize = 18.sp, fontWeight = FontWeight.Bold)
    val headline = base.copy(fontSize = 28.sp, fontWeight = FontWeight.ExtraBold, letterSpacing = (-0.4).sp)
    val body = base.copy(fontSize = 15.sp, lineHeight = 1.45.em)
    val bodyStrong = base.copy(fontSize = 15.sp, fontWeight = FontWeight.SemiBold)
    val caption = base.copy(fontSize = 13.sp, fontWeight = FontWeight.Medium, color = AppColors.textSecondary)
    val unit = base.copy(fontSize = 15.sp, fontWeight = FontWeight.SemiBold, color = AppColors.textSecondary)

    /** Nhãn chữ in hoa nhỏ phía trên mỗi cụm số. */
    val overline = base.copy(fontSize = 11.sp, fontWeight = FontWeight.Bold, letterSpacing = 1.4.sp, color = AppColors.textSecondary)
}

fun riskColor(r: Risk): Color = when (r) {
    Risk.DANGER -> AppColors.danger
    Risk.WARNING -> AppColors.warning
    Risk.SAFE -> AppColors.safe
    Risk.INFO -> AppColors.info
}

fun onRiskColor(r: Risk): Color = if (r == Risk.WARNING) AppColors.onWarning else Color.White

/** Màu nền cho khối đặc (banner) theo mức rủi ro - đủ tương phản với chữ [onRiskColor]. */
fun riskFill(r: Risk): Color = if (r == Risk.DANGER) AppColors.dangerFill else riskColor(r)

fun riskIcon(r: Risk): ImageVector = when (r) {
    Risk.DANGER -> Icons.Rounded.Warning
    Risk.WARNING -> Icons.Rounded.ErrorOutline
    else -> Icons.Rounded.Verified
}

fun riskLabel(r: Risk): String = when (r) {
    Risk.DANGER -> "NGUY HIỂM"
    Risk.WARNING -> "CẢNH BÁO"
    else -> "AN TOÀN"
}

fun riskMessage(r: Risk): String = when (r) {
    Risk.DANGER -> "Giảm tốc ngay"
    Risk.WARNING -> "Giữ khoảng cách"
    else -> "Khoảng cách an toàn"
}

@Composable
fun AdasTheme(content: @Composable () -> Unit) {
    val scheme = darkColorScheme(
        primary = AppColors.accent,
        onPrimary = AppColors.onAccent,
        secondary = AppColors.accent,
        background = AppColors.bg,
        onBackground = AppColors.text,
        surface = AppColors.surface,
        onSurface = AppColors.text,
        surfaceVariant = AppColors.surfaceRaised,
        onSurfaceVariant = AppColors.textSecondary,
        surfaceContainer = AppColors.surfaceRaised,
        surfaceContainerHigh = AppColors.surfaceRaised,
        surfaceContainerLow = AppColors.surface,
        outline = AppColors.strokeStrong,
        outlineVariant = AppColors.stroke,
        error = AppColors.danger,
    )
    val t = MaterialTheme.typography
    val typography = t.copy(
        bodyLarge = AppText.body, bodyMedium = AppText.body.copy(fontSize = 14.sp), bodySmall = AppText.caption,
        titleLarge = AppText.title.copy(fontSize = 20.sp), titleMedium = AppText.title, titleSmall = AppText.bodyStrong,
        labelLarge = AppText.bodyStrong, labelMedium = AppText.caption, labelSmall = AppText.overline,
        headlineSmall = AppText.headline,
    )
    MaterialTheme(colorScheme = scheme, typography = typography, content = content)
}
