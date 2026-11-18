package vn.adas.caotoc.ui.drive

import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.ReceiptLong
import androidx.compose.material.icons.automirrored.rounded.Send
import androidx.compose.material.icons.outlined.DeleteOutline
import androidx.compose.material.icons.outlined.SmartToy
import androidx.compose.material.icons.outlined.WifiOff
import androidx.compose.material.icons.rounded.Close
import androidx.compose.material.icons.rounded.Verified
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.AssistChip
import androidx.compose.material3.AssistChipDefaults
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.PrimaryTabRow
import androidx.compose.material3.Tab
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import vn.adas.caotoc.core.CLASS_LABELS_VI
import vn.adas.caotoc.core.MODIFIERS
import vn.adas.caotoc.core.ROAD_CONDITIONS
import vn.adas.caotoc.core.Violation
import vn.adas.caotoc.core.r
import vn.adas.caotoc.core.vn
import vn.adas.caotoc.core.vnFactor
import vn.adas.caotoc.data.ViolationLog
import vn.adas.caotoc.ui.components.SelectTile
import vn.adas.caotoc.ui.components.conditionIcon
import vn.adas.caotoc.ui.components.modifierIcon
import vn.adas.caotoc.ui.theme.AppColors
import vn.adas.caotoc.ui.theme.AppText
import vn.adas.caotoc.ui.theme.Radii
import vn.adas.caotoc.ui.theme.Space
import vn.adas.caotoc.ui.theme.riskColor
import vn.adas.caotoc.ui.theme.riskIcon
import vn.adas.caotoc.ui.theme.riskLabel
import java.time.LocalDate
import java.time.format.DateTimeFormatter

/** Bảng chọn điều kiện đường (mở từ cụm tốc độ). Ô lớn ≥ 72 dp, áp dụng ngay khi chạm. */
@OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)
@Composable
fun ConditionSheet(
    conditionKey: String,
    modifierKeys: Set<String>,
    onCondition: (String) -> Unit,
    onModifier: (String) -> Unit,
    onDismiss: () -> Unit,
) {
    ModalBottomSheet(onDismiss, sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true),
        containerColor = AppColors.surface, scrimColor = AppColors.scrim, sheetMaxWidth = 820.dp) {
        Column(Modifier.verticalScroll(rememberScrollState()).padding(horizontal = Space.xl).padding(bottom = Space.xl)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("Điều kiện đường", style = AppText.title, modifier = Modifier.weight(1f))
                IconButton(onDismiss) { Icon(Icons.Rounded.Close, "Đóng") }
            }
            Text("Khoảng cách cần giữ được nhân theo độ bám mặt đường: đường càng trơn, hệ số càng lớn.", style = AppText.caption)
            Spacer(Modifier.height(Space.lg))
            BoxWithConstraints {
                val n = if (maxWidth > 640.dp) 5 else 3
                val w = (maxWidth - Space.md * (n - 1)) / n
                FlowRow(horizontalArrangement = Arrangement.spacedBy(Space.md), verticalArrangement = Arrangement.spacedBy(Space.md)) {
                    for (c in ROAD_CONDITIONS.values) {
                        SelectTile(conditionIcon(c.key), c.shortName, "×${vnFactor(c.factor)}", conditionKey == c.key,
                            { onCondition(c.key) }, Modifier.width(w))
                    }
                }
            }
            Spacer(Modifier.height(Space.xl))
            Text("YẾU TỐ KHÁC", style = AppText.overline)
            Spacer(Modifier.height(Space.sm))
            BoxWithConstraints {
                val w = (maxWidth - Space.md * 2) / 3
                FlowRow(horizontalArrangement = Arrangement.spacedBy(Space.md), verticalArrangement = Arrangement.spacedBy(Space.md)) {
                    for ((key, m) in MODIFIERS) {
                        SelectTile(modifierIcon(key), m.shortName, "×${vnFactor(m.factor)}", key in modifierKeys,
                            { onModifier(key) }, Modifier.width(w))
                    }
                }
            }
            Spacer(Modifier.height(Space.md))
            Text(ROAD_CONDITIONS.getValue(conditionKey).advice, style = AppText.caption)
        }
    }
}

/** Câu gợi ý nhanh: giống ConditionPanel.QUICK của bản desktop (cùng câu gửi trợ lý). */
private val QUICK_PROMPTS = listOf(
    Triple("dry", "Khô ráo", "Đường khô ráo, trời nắng, tầm nhìn tốt"),
    Triple("wet", "Mưa nhỏ", "Trời mưa nhỏ, mặt đường ướt"),
    Triple("heavy_rain", "Mưa to", "Trời đang mưa to, mặt đường đọng nước"),
    Triple("fog", "Sương mù", "Có sương mù dày, tầm nhìn khoảng 100 m"),
    Triple("slippery", "Trơn trượt", "Mặt đường trơn trượt do dầu loang"),
    Triple("night", "Ban đêm", "Đang lái xe ban đêm trên cao tốc"),
    Triple("heavy_vehicle", "Chở nặng", "Tôi lái xe tải đang chở nặng"),
    Triple("tired", "Mệt mỏi", "Tôi đã lái lâu và cảm thấy buồn ngủ"),
)

/**
 * Bảng "Trợ lý AI | Vi phạm" - tương ứng hai thẻ dưới cùng cột phải của bản desktop (ChatPanel + EventLog
 * trong gui/widgets/tabs.py). Mở từ nút trên màn hình lái.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AssistantSheet(
    chat: List<ChatMessage>,
    log: ViolationLog.Snapshot,
    onAsk: (String) -> Unit,
    onClearLog: () -> Unit,
    onDismiss: () -> Unit,
) {
    var tab by rememberSaveable { mutableIntStateOf(0) }
    ModalBottomSheet(onDismiss, sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true),
        containerColor = AppColors.surface, scrimColor = AppColors.scrim, sheetMaxWidth = 820.dp) {
        Column(Modifier.fillMaxHeight(0.94f).imePadding()) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                PrimaryTabRow(selectedTabIndex = tab, modifier = Modifier.weight(1f), containerColor = AppColors.surface,
                    contentColor = AppColors.text, divider = {}) {
                    TabLabel(tab == 0, { tab = 0 }, Icons.Outlined.SmartToy, "Trợ lý AI")
                    TabLabel(tab == 1, { tab = 1 }, Icons.AutoMirrored.Outlined.ReceiptLong,
                        if (log.sessionCount > 0) "Vi phạm (${log.sessionCount})" else "Vi phạm")
                }
                IconButton(onDismiss) { Icon(Icons.Rounded.Close, "Đóng") }
            }
            if (tab == 0) ChatTab(chat, onAsk) else ViolationTab(log, onClearLog)
        }
    }
}

/** Tab gọn một dòng (biểu tượng cạnh chữ) để chừa chỗ cho nội dung trên màn hình ngang. */
@Composable
private fun TabLabel(selected: Boolean, onClick: () -> Unit, icon: androidx.compose.ui.graphics.vector.ImageVector, text: String) {
    Tab(selected, onClick, Modifier.height(48.dp), selectedContentColor = AppColors.text, unselectedContentColor = AppColors.textSecondary) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Icon(icon, null, Modifier.size(20.dp))
            Spacer(Modifier.width(Space.sm))
            Text(text, style = AppText.bodyStrong)
        }
    }
}

@OptIn(ExperimentalFoundationApi::class)
@Composable
private fun ChatTab(chat: List<ChatMessage>, onAsk: (String) -> Unit) {
    var input by rememberSaveable { mutableStateOf("") }
    fun submit(text: String) {
        val t = text.trim()
        if (t.isEmpty()) return
        input = ""
        onAsk(t)
    }
    Column(Modifier.fillMaxSize()) {
        Row(Modifier.padding(horizontal = Space.lg, vertical = Space.sm), verticalAlignment = Alignment.CenterVertically) {
            Icon(Icons.Outlined.WifiOff, null, tint = AppColors.textSecondary, modifier = Modifier.size(14.dp))
            Spacer(Modifier.width(Space.xs + 2.dp))
            Text("Chế độ: trợ lý offline · miễn phí, không cần Internet", style = AppText.caption.copy(fontSize = 12.sp))
        }
        // tin mới nhất ở dưới, luôn trong tầm nhìn
        LazyColumn(Modifier.weight(1f), reverseLayout = true, contentPadding = PaddingValues(horizontal = Space.lg, vertical = Space.md),
            verticalArrangement = Arrangement.spacedBy(Space.sm)) {
            items(chat.asReversed()) { Bubble(it) }
        }
        LazyRow(contentPadding = PaddingValues(horizontal = Space.lg), horizontalArrangement = Arrangement.spacedBy(Space.sm)) {
            items(QUICK_PROMPTS) { (key, label, text) ->
                AssistChip(
                    onClick = { submit(text) },
                    label = { Text(label, style = AppText.caption.copy(color = AppColors.text)) },
                    leadingIcon = {
                        Icon(if (key in ROAD_CONDITIONS) conditionIcon(key) else modifierIcon(key), null,
                            tint = AppColors.accent, modifier = Modifier.size(18.dp))
                    },
                    colors = AssistChipDefaults.assistChipColors(containerColor = AppColors.surfaceRaised),
                    border = AssistChipDefaults.assistChipBorder(true, borderColor = AppColors.stroke),
                    shape = RoundedCornerShape(50),
                    modifier = Modifier.semantics { contentDescription = "Gửi cho Trợ lý AI: \"$text\"" },
                )
            }
        }
        Row(Modifier.padding(horizontal = Space.lg, vertical = Space.sm), verticalAlignment = Alignment.CenterVertically) {
            OutlinedTextField(
                value = input, onValueChange = { input = it }, modifier = Modifier.weight(1f),
                placeholder = { Text("Mô tả tình huống, vd: đang mưa, tôi chạy 90 km/h…", style = AppText.body.copy(color = AppColors.textSecondary)) },
                textStyle = AppText.body, singleLine = true, shape = RoundedCornerShape(Radii.md),
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Send),
                keyboardActions = KeyboardActions(onSend = { submit(input) }),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedContainerColor = AppColors.surfaceRaised, unfocusedContainerColor = AppColors.surfaceRaised,
                    unfocusedBorderColor = AppColors.stroke, focusedBorderColor = AppColors.accent,
                ),
            )
            Spacer(Modifier.width(Space.sm))
            Button({ submit(input) }, Modifier.height(52.dp)) {
                Icon(Icons.AutoMirrored.Rounded.Send, null, Modifier.size(18.dp))
                Spacer(Modifier.width(Space.xs))
                Text("Gửi")
            }
        }
    }
}

@Composable
private fun Bubble(m: ChatMessage) {
    val user = m.fromUser
    Box(Modifier.fillMaxWidth(), contentAlignment = if (user) Alignment.CenterEnd else Alignment.CenterStart) {
        val shape = RoundedCornerShape(Radii.md, Radii.md, if (user) 4.dp else Radii.md, if (user) Radii.md else 4.dp)
        Column(
            Modifier
                .widthIn(max = 560.dp)
                .background(if (user) AppColors.accentSoft else AppColors.surfaceRaised, shape)
                .border(1.dp, if (user) AppColors.accent.copy(alpha = 0.4f) else AppColors.stroke, shape)
                .padding(horizontal = Space.md + 2.dp, vertical = Space.md - 2.dp),
        ) {
            if (!user) {
                Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(bottom = Space.xs)) {
                    Icon(Icons.Outlined.SmartToy, null, tint = AppColors.accent, modifier = Modifier.size(14.dp))
                    Spacer(Modifier.width(Space.xs + 2.dp))
                    Text("TRỢ LÝ", style = AppText.overline.copy(color = AppColors.accent))
                }
            }
            Text(m.text, style = AppText.body.copy(fontSize = 14.sp))
            m.note?.let { Text(it, style = AppText.caption.copy(fontSize = 12.sp), modifier = Modifier.padding(top = Space.xs)) }
        }
    }
}

@Composable
private fun ViolationTab(log: ViolationLog.Snapshot, onClear: () -> Unit) {
    var confirm by remember { mutableStateOf(false) }
    Column(Modifier.fillMaxSize()) {
        Row(Modifier.padding(start = Space.lg, end = Space.sm, top = Space.sm), verticalAlignment = Alignment.CenterVertically) {
            Text("Phiên giám sát #${log.sessionId} · ${log.sessionCount} vi phạm · đã lưu ${log.items.size}",
                style = AppText.caption.copy(fontSize = 12.sp), modifier = Modifier.weight(1f))
            if (log.items.isNotEmpty()) {
                TextButton({ confirm = true }) {
                    Icon(Icons.Outlined.DeleteOutline, null, Modifier.size(18.dp))
                    Spacer(Modifier.width(Space.xs))
                    Text("Xóa")
                }
            }
        }
        if (log.items.isEmpty()) {
            Column(Modifier.fillMaxSize().padding(Space.xl), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center) {
                Icon(Icons.Rounded.Verified, null, tint = AppColors.safe, modifier = Modifier.size(40.dp))
                Spacer(Modifier.height(Space.md))
                Text("Chưa có vi phạm nào", style = AppText.title)
                Spacer(Modifier.height(Space.xs))
                Text("Mỗi lần khoảng cách tới xe phía trước xuống dưới ngưỡng, hệ thống ghi lại một đợt tại đây.",
                    style = AppText.caption, textAlign = TextAlign.Center)
            }
        } else {
            LazyColumn(contentPadding = PaddingValues(Space.lg), verticalArrangement = Arrangement.spacedBy(Space.sm)) {
                items(log.items, key = { it.id }) { ViolationTile(it) }
            }
        }
    }
    if (confirm) {
        AlertDialog(
            onDismissRequest = { confirm = false },
            title = { Text("Xóa nhật ký vi phạm?") },
            text = { Text("Toàn bộ các đợt vi phạm đã lưu trên điện thoại sẽ bị xóa.") },
            confirmButton = {
                Button({ confirm = false; onClear() }, colors = ButtonDefaults.buttonColors(containerColor = AppColors.dangerFill)) { Text("Xóa") }
            },
            dismissButton = { TextButton({ confirm = false }) { Text("Hủy") } },
            containerColor = AppColors.surfaceRaised,
        )
    }
}

private val TIME = DateTimeFormatter.ofPattern("HH:mm:ss")
private val DAY_TIME = DateTimeFormatter.ofPattern("dd/MM HH:mm:ss")

@Composable
fun ViolationTile(v: Violation) {
    val c = riskColor(v.level)
    val time = (if (v.startedAt.toLocalDate() == LocalDate.now()) TIME else DAY_TIME).format(v.startedAt)
    val vehicle = (CLASS_LABELS_VI[v.className] ?: v.className) + (v.trackId?.let { " #$it" } ?: "")
    val duration = v.durationS?.let { "${vn(it)} s" } ?: "đang diễn ra"
    val shape = RoundedCornerShape(Radii.md)
    Row(
        Modifier
            .fillMaxWidth()
            .background(AppColors.surfaceRaised, shape)
            .border(if (v.open) 1.5.dp else 1.dp, if (v.open) c else AppColors.stroke, shape)
            .semantics { contentDescription = "${riskLabel(v.level)}, $vehicle, nhỏ nhất ${vn(v.minDistanceM)} mét, lúc $time" }
            .padding(Space.md),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(Modifier.size(40.dp).background(c.copy(alpha = 0.16f), CircleShape), contentAlignment = Alignment.Center) {
            Icon(riskIcon(v.level), null, tint = c, modifier = Modifier.size(22.dp))
        }
        Spacer(Modifier.width(Space.md))
        Column(Modifier.weight(1f)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(riskLabel(v.level), style = AppText.overline.copy(color = c))
                Spacer(Modifier.width(Space.sm))
                Text(vehicle, style = AppText.bodyStrong.copy(fontSize = 14.sp), maxLines = 1, overflow = TextOverflow.Ellipsis)
            }
            Spacer(Modifier.height(2.dp))
            Text("$time · ${v.speedKmh.r()} km/h · ngưỡng ${v.safeM.r()} m · $duration",
                style = AppText.caption.copy(fontSize = 12.sp), maxLines = 1, overflow = TextOverflow.Ellipsis)
            if (v.weatherFactor > 1.0) {
                Text("${v.condition} · ×${vnFactor(v.weatherFactor)}", style = AppText.caption.copy(fontSize = 12.sp),
                    maxLines = 1, overflow = TextOverflow.Ellipsis)
            }
        }
        Spacer(Modifier.width(Space.md))
        Column(horizontalAlignment = Alignment.End) {
            Text(buildAnnotatedString {
                withStyle(SpanStyle(color = c, fontSize = 20.sp, fontWeight = AppText.title.fontWeight)) { append(vn(v.minDistanceM)) }
                withStyle(SpanStyle(color = AppColors.textSecondary, fontSize = 13.sp)) { append(" m") }
            }, style = AppText.title)
            val ttc = v.minTtcS
            Text(if (ttc != null && ttc < 60) "TTC ${vn(ttc)} s" else "TTC --", style = AppText.caption.copy(fontSize = 12.sp))
        }
    }
}
