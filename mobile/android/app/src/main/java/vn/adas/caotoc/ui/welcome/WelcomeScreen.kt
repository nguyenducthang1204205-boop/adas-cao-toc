package vn.adas.caotoc.ui.welcome

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.ArrowForward
import androidx.compose.material.icons.outlined.Info
import androidx.compose.material.icons.outlined.NotificationsActive
import androidx.compose.material.icons.outlined.RecordVoiceOver
import androidx.compose.material.icons.outlined.Smartphone
import androidx.compose.material.icons.outlined.SocialDistance
import androidx.compose.material.icons.outlined.Straighten
import androidx.compose.material.icons.outlined.Visibility
import androidx.compose.material3.Button
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import vn.adas.caotoc.ui.components.AppMark
import vn.adas.caotoc.ui.theme.AppColors
import vn.adas.caotoc.ui.theme.AppText
import vn.adas.caotoc.ui.theme.Radii
import vn.adas.caotoc.ui.theme.Space

/** Màn hình chào lần đầu: giới thiệu, 3 bước trước khi lên đường, lời nhắc an toàn. */
@Composable
fun WelcomeScreen(onStart: () -> Unit) {
    BoxWithConstraints(
        Modifier
            .fillMaxSize()
            .background(AppColors.bg)
            .drawBehind {
                // quầng sáng thương hiệu
                drawCircle(Brush.radialGradient(listOf(AppColors.accent.copy(alpha = 0.20f), Color.Transparent),
                    Offset(150.dp.toPx(), 110.dp.toPx()), 310.dp.toPx()), 310.dp.toPx(), Offset(150.dp.toPx(), 110.dp.toPx()))
            }
            .safeDrawingPadding(),
    ) {
        val wide = maxWidth > 700.dp
        val tall = maxHeight > 560.dp
        Box(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(horizontal = if (wide) 40.dp else Space.xl, vertical = Space.xl),
            contentAlignment = Alignment.Center) {
            if (wide) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(Modifier.weight(5f)) { Intro(compact = false, tall = tall) }
                    Spacer(Modifier.width(Space.xxl))
                    Box(Modifier.weight(6f)) { Steps(onStart) }
                }
            } else {
                Column {
                    Intro(compact = true, tall = tall)
                    Spacer(Modifier.height(Space.xl))
                    Steps(onStart)
                }
            }
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun Intro(compact: Boolean, tall: Boolean) {
    Column {
        AppMark(60.dp)
        Spacer(Modifier.height(Space.lg))
        Text("ADAS Cao tốc", style = AppText.headline.copy(fontSize = if (compact) 28.sp else 32.sp))
        Spacer(Modifier.height(Space.sm))
        Text("Trợ lý giữ khoảng cách an toàn trên cao tốc. AI chạy ngay trên điện thoại, không cần Internet.",
            style = AppText.body.copy(color = AppColors.textSecondary))
        Spacer(Modifier.height(Space.lg))
        if (tall) {
            FlowRow(horizontalArrangement = Arrangement.spacedBy(Space.sm), verticalArrangement = Arrangement.spacedBy(Space.sm)) {
                Feature(Icons.Outlined.Visibility, "Nhận diện xe phía trước")
                Feature(Icons.Outlined.SocialDistance, "Ngưỡng theo quy định")
                Feature(Icons.Outlined.RecordVoiceOver, "Cảnh báo bằng giọng nói")
            }
            Spacer(Modifier.height(Space.lg))
        }
        SafetyNote()
    }
}

@Composable
private fun Feature(icon: ImageVector, text: String) {
    Row(
        Modifier.background(AppColors.surfaceRaised, RoundedCornerShape(50)).border(1.dp, AppColors.stroke, RoundedCornerShape(50))
            .padding(horizontal = Space.md, vertical = Space.sm),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(icon, null, tint = AppColors.accent, modifier = Modifier.size(18.dp))
        Spacer(Modifier.width(Space.sm))
        Text(text, style = AppText.caption.copy(color = AppColors.text))
    }
}

@Composable
private fun Steps(onStart: () -> Unit) {
    val shape = RoundedCornerShape(Radii.lg)
    Column(Modifier.fillMaxWidth().background(AppColors.surface, shape).border(1.dp, AppColors.stroke, shape).padding(Space.xl)) {
        Text("TRƯỚC KHI LÊN ĐƯỜNG", style = AppText.overline)
        Spacer(Modifier.height(Space.md))
        Step(1, Icons.Outlined.Smartphone, "Gắn chắc điện thoại", "Màn hình nằm ngang, camera nhìn thẳng ra đường.")
        Step(2, Icons.Outlined.Straighten, "Căn chỉnh camera", "Chọn loại xe, kiểm tra đường chân trời.")
        Step(3, Icons.Outlined.NotificationsActive, "Lái xe, app lo phần cảnh báo", "Màu, âm thanh, giọng nói khi đi quá gần.")
        Spacer(Modifier.height(Space.lg))
        Button(onStart, Modifier.fillMaxWidth().heightIn(min = 52.dp)) {
            Text("Tôi đã hiểu, bắt đầu")
            Spacer(Modifier.width(Space.sm))
            Icon(Icons.AutoMirrored.Rounded.ArrowForward, null)
        }
    }
}

@Composable
private fun Step(n: Int, icon: ImageVector, title: String, text: String) {
    Row(Modifier.padding(bottom = Space.md), verticalAlignment = Alignment.Top) {
        Box(Modifier.size(40.dp).background(AppColors.accentSoft, RoundedCornerShape(Radii.sm + 2.dp)), contentAlignment = Alignment.Center) {
            Icon(icon, null, tint = AppColors.accent, modifier = Modifier.size(22.dp))
        }
        Spacer(Modifier.width(Space.md))
        Column {
            Text("$n. $title", style = AppText.bodyStrong)
            Spacer(Modifier.height(2.dp))
            Text(text, style = AppText.caption)
        }
    }
}

@Composable
private fun SafetyNote() {
    val shape = RoundedCornerShape(Radii.sm)
    Row(
        Modifier.background(AppColors.warning.copy(alpha = 0.08f), shape).border(1.dp, AppColors.warning.copy(alpha = 0.35f), shape).padding(Space.md),
        verticalAlignment = Alignment.Top,
    ) {
        Icon(Icons.Outlined.Info, null, tint = AppColors.warning, modifier = Modifier.size(18.dp))
        Spacer(Modifier.width(Space.sm))
        Text("Ứng dụng chỉ hỗ trợ, không thay thế sự chú ý của người lái và không phải thiết bị an toàn " +
            "được chứng nhận. Không thao tác điện thoại khi xe đang chạy.",
            style = AppText.caption.copy(color = AppColors.text, fontSize = 12.5.sp))
    }
}
