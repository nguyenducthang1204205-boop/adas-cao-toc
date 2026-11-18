package vn.adas.caotoc.ui.settings

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
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
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.ArrowBack
import androidx.compose.material.icons.outlined.DashboardCustomize
import androidx.compose.material.icons.outlined.Memory
import androidx.compose.material.icons.outlined.NotificationsActive
import androidx.compose.material.icons.outlined.Shield
import androidx.compose.material.icons.outlined.SocialDistance
import androidx.compose.material.icons.outlined.Speed
import androidx.compose.material.icons.outlined.Videocam
import androidx.compose.material.icons.rounded.Add
import androidx.compose.material.icons.rounded.ChevronRight
import androidx.compose.material.icons.rounded.PlayArrow
import androidx.compose.material.icons.rounded.Remove
import androidx.compose.material.icons.rounded.RestartAlt
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Slider
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import vn.adas.caotoc.core.CLASS_LABELS_VI
import vn.adas.caotoc.core.LEGAL_GAP_TABLE
import vn.adas.caotoc.core.LEGAL_MIN_SPEED
import vn.adas.caotoc.core.PerfLevel
import vn.adas.caotoc.core.Risk
import vn.adas.caotoc.core.computeThresholds
import vn.adas.caotoc.core.r
import vn.adas.caotoc.core.vn
import vn.adas.caotoc.core.vnNum
import vn.adas.caotoc.data.AppSettings
import vn.adas.caotoc.data.SettingsStore
import vn.adas.caotoc.service.AlertPlayer
import vn.adas.caotoc.service.UsbCamState
import vn.adas.caotoc.service.UsbCamera
import vn.adas.caotoc.ui.theme.AppColors
import vn.adas.caotoc.ui.theme.AppText
import vn.adas.caotoc.ui.theme.Radii
import vn.adas.caotoc.ui.theme.Space
import kotlin.math.roundToInt

/**
 * Cài đặt: nhóm theo thẻ (cảnh báo, ngưỡng theo dải tốc độ, camera, tốc độ, hiệu năng, nhận diện, hiển thị, an toàn),
 * hàng ≥ 64 dp. Nhóm "Ngưỡng cảnh báo" giống tab cùng tên trong Cài đặt của bản desktop (gui/dialogs/settings.py).
 */
@OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)
@Composable
fun SettingsScreen(store: SettingsStore, alerts: AlertPlayer, usb: UsbCamera, onBenchmark: () -> Unit, onBack: () -> Unit) {
    val s by store.settings.collectAsStateWithLifecycle()
    val usbState by usb.state.collectAsStateWithLifecycle()
    fun set(f: (AppSettings) -> AppSettings) = store.update(f)
    val a = s.alert
    Column(Modifier.fillMaxSize().background(AppColors.surface)) {
        TopAppBar(
            title = { Text("Cài đặt", style = AppText.title.copy(fontSize = 20.sp)) },
            navigationIcon = { IconButton(onBack) { Icon(Icons.AutoMirrored.Rounded.ArrowBack, "Quay lại") } },
            colors = TopAppBarDefaults.topAppBarColors(containerColor = AppColors.surface),
        )
        LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(start = Space.lg, end = Space.lg, bottom = Space.xxl),
            horizontalAlignment = Alignment.CenterHorizontally) {
            item {
                Group(Icons.Outlined.NotificationsActive, "Cảnh báo") {
                    SwitchRow("Âm bíp cảnh báo", "Bíp thưa khi CẢNH BÁO, dồn dập khi NGUY HIỂM", a.soundEnabled,
                        { v -> set { it.copy(alert = it.alert.copy(soundEnabled = v)) } }) {
                        Row(horizontalArrangement = Arrangement.spacedBy(Space.sm)) {
                            PreviewChip("Nghe thử cảnh báo", AppColors.warning) { alerts.preview(Risk.WARNING) }
                            PreviewChip("Nghe thử nguy hiểm", AppColors.danger) { alerts.preview(Risk.DANGER) }
                        }
                    }
                    SwitchRow("Giọng nói tiếng Việt",
                        if (alerts.voiceAvailable) "Nói \"Giữ khoảng cách\" / \"Nguy hiểm, giảm tốc ngay\" khi mức cảnh báo tăng"
                        else "Điện thoại chưa có giọng đọc tiếng Việt - cài trong Cài đặt › Chuyển văn bản thành giọng nói",
                        a.voiceEnabled, { v -> set { it.copy(alert = it.alert.copy(voiceEnabled = v)) } })
                    SwitchRow("Chỉ cảnh báo xe cùng làn", "Bỏ qua xe ở làn bên cạnh", a.onlyEgoLane,
                        { v -> set { it.copy(alert = it.alert.copy(onlyEgoLane = v)) } })
                    SliderRow("Chống báo giả", "Nguy hiểm phải kéo dài ngần này mới báo (tránh báo nhầm do nhận diện chập chờn)",
                        a.escalateSeconds.toFloat(), 0f..0.5f, 9, "${vn(a.escalateSeconds, 2)} s") { v ->
                        set { it.copy(alert = it.alert.copy(escalateSeconds = (v * 20).roundToInt() / 20.0)) }
                    }
                }
            }
            item { Group(Icons.Outlined.SocialDistance, "Ngưỡng cảnh báo") { ThresholdRows(s, ::set) } }
            item { Group(Icons.Outlined.Videocam, "Camera") { CameraSourceRow(s, usbState, ::set) } }
            item {
                Group(Icons.Outlined.Speed, "Tốc độ xe") {
                    SwitchRow("Lấy tốc độ từ GPS", "Tắt, hoặc khi chưa bắt được GPS: dùng tốc độ nhập tay (nút − / + trên màn hình lái)",
                        s.useGps, { v -> set { it.copy(useGps = v) } })
                }
            }
            item { Group(Icons.Outlined.Speed, "Hiệu năng") { PerfRows(s, ::set, onBenchmark) } }
            item {
                Group(Icons.Outlined.Memory, "Nhận diện") {
                    SwitchRow("Tăng tốc GPU", "Tự đo GPU và CPU khi khởi động, dùng bên nhanh hơn", s.preferGpu, { v -> set { it.copy(preferGpu = v) } })
                    SwitchRow("Bám vết giữa các lần nhận diện",
                        "Đo lại vị trí xe giữa hai lần YOLO (vài ms mỗi khung) - khoảng cách cập nhật 10-30 lần/giây kể cả khi YOLO chậm",
                        s.denseTracking, { v -> set { it.copy(denseTracking = v) } })
                    SliderRow("Độ chắc chắn tối thiểu", "Thấp: bắt nhiều xe hơn nhưng dễ nhận nhầm", s.confidence.toFloat(), 0.15f..0.8f, 12,
                        "${(s.confidence * 100).roundToInt()} %") { v -> set { it.copy(confidence = (v * 20).roundToInt() / 20.0) } }
                    Column(Modifier.padding(Space.lg)) {
                        Text("Loại phương tiện cảnh báo", style = AppText.bodyStrong)
                        Spacer(Modifier.height(Space.sm))
                        FlowRow(horizontalArrangement = Arrangement.spacedBy(Space.sm), verticalArrangement = Arrangement.spacedBy(Space.sm)) {
                            for (c in listOf("car", "truck", "bus", "Jeepney", "motorcycle")) {
                                val on = c in s.enabledClasses
                                Chip(if (c == "Jeepney") "Xe khách nhỏ" else CLASS_LABELS_VI.getValue(c), on) {
                                    set { it.copy(enabledClasses = if (on) it.enabledClasses - c else it.enabledClasses + c) }
                                }
                            }
                        }
                    }
                    SwitchRow("Xoay ảnh 180°", "Bật nếu khung xe lệch ngược so với hình (máy gắn ngược chiều)", s.rotate180,
                        { v -> set { it.copy(rotate180 = v) } })
                    SwitchRow("Tự hoàn thiện căn chỉnh khi chạy",
                        "Đo đường chân trời từ 2 vạch làn trong lúc lái và báo khi camera bị xê dịch", s.autoCalib,
                        { v -> set { it.copy(autoCalib = v) } })
                }
            }
            item {
                Group(Icons.Outlined.DashboardCustomize, "Hiển thị") {
                    SwitchRow("Thông số kỹ thuật", "Hiện FPS, thời gian YOLO và bộ suy luận trên màn hình lái (khi demo, chẩn đoán)",
                        s.showTech, { v -> set { it.copy(showTech = v) } })
                }
            }
            item {
                Group(Icons.Outlined.Shield, "An toàn") {
                    Text(
                        "Ứng dụng chỉ hỗ trợ cảnh báo, không thay thế sự chú ý của người lái và không phải thiết bị ADAS " +
                            "được chứng nhận. Khoảng cách chỉ đúng sau khi căn chỉnh camera cho đúng vị trí gắn máy; sai số " +
                            "tăng mạnh ngoài khoảng 80 m và khi đường dốc. Không thao tác điện thoại khi xe đang chạy.",
                        style = AppText.caption, modifier = Modifier.padding(Space.lg),
                    )
                }
            }
            item {
                Text("ADAS Cao tốc 2.0 · YOLOv11 + IPM · Kotlin", style = AppText.caption.copy(fontSize = 12.sp),
                    modifier = Modifier.padding(top = Space.lg))
            }
        }
    }
}

/** Khoảng cách CẢNH BÁO khi đường khô cho từng dải tốc độ; mỗi dải từ 60 km/h không thấp hơn luật. */
@Composable
private fun ThresholdRows(s: AppSettings, set: ((AppSettings) -> AppSettings) -> Unit) {
    val p = s.policy
    @Composable
    fun applied(v: Double) {
        val t = computeThresholds(v, p)
        Text(buildAnnotatedString {
            append(if (v < LEGAL_MIN_SPEED) "Ở ${v.r()} km/h: " else "Đang áp dụng: ")
            withStyle(SpanStyle(color = AppColors.warning)) { append("cảnh báo < ${t.safeM.r()} m") }
            append(" · ")
            withStyle(SpanStyle(color = AppColors.danger)) { append("nguy hiểm < ${t.dangerM.r()} m") }
        }, style = AppText.caption.copy(fontSize = 12.sp))
    }
    Text("Khoảng cách CẢNH BÁO cho từng dải tốc độ khi đường khô ráo. Từ 60 km/h, mỗi dải không được thấp hơn " +
        "mức tối thiểu của Bộ GTVT (Thông tư 31/2019/TT-BGTVT); chỉ được đặt xa hơn.",
        style = AppText.caption, modifier = Modifier.padding(start = Space.lg, end = Space.lg, top = Space.md, bottom = Space.sm))
    StepperRow("Dưới 60 km/h", "Tài xế tự chủ động · giữ quãng đường xe đi trong số giây này", { applied(50.0) },
        "${vnNum(s.timeGapS)} giây", "thời gian giữ khoảng cách dưới 60 km/h",
        onMinus = if (s.timeGapS > AppSettings.TIME_GAP_RANGE.start) ({ set { it.copy(timeGapS = AppSettings.clampTimeGap(it.timeGapS - 0.5)) } }) else null,
        onPlus = if (s.timeGapS < AppSettings.TIME_GAP_RANGE.endInclusive) ({ set { it.copy(timeGapS = AppSettings.clampTimeGap(it.timeGapS + 0.5)) } }) else null)
    for (i in LEGAL_GAP_TABLE.indices) {
        val (vmax, legal) = LEGAL_GAP_TABLE[i]
        fun bump(d: Double) = set { st -> st.copy(bandGapsM = st.bandGapsM.toMutableList().also { it[i] = AppSettings.clampBand(i, it[i] + d) }) }
        StepperRow(
            if (i == 0) "60 km/h" else "Trên ${LEGAL_GAP_TABLE[i - 1].first.r()} đến ${vmax.r()} km/h",
            "Luật tối thiểu ${legal.r()} m", { applied(vmax) }, "${s.bandGapsM[i].r()} m",
            "ngưỡng cảnh báo dải ${if (i == 0) "60" else "đến ${vmax.r()}"} km/h",
            onMinus = if (s.bandGapsM[i] > legal) ({ bump(-5.0) }) else null,
            onPlus = if (s.bandGapsM[i] < AppSettings.MAX_BAND_GAP_M) ({ bump(5.0) }) else null,
        )
    }
    Column(Modifier.padding(start = Space.sm, end = Space.lg, top = Space.xs, bottom = Space.md)) {
        TextButton({ set { it.withDefaultBands() } }, enabled = !s.bandsAreDefault) {
            Icon(Icons.Rounded.RestartAlt, null, Modifier.size(20.dp))
            Spacer(Modifier.width(Space.sm))
            Text("Đặt lại bằng mức tối thiểu theo luật")
        }
        Text("Khi mưa, sương mù, đường trơn... các ngưỡng trên được nhân thêm hệ số theo điều kiện đường. " +
            "Ngưỡng NGUY HIỂM = ngưỡng cảnh báo × ${vnNum(p.dangerRatio)}.",
            style = AppText.caption.copy(fontSize = 12.sp), modifier = Modifier.padding(start = Space.sm))
    }
}

/** Mức hiệu năng (tự động / khóa), thấy xa, đo hiệu năng. */
/** Chọn nguồn hình: camera của máy (điện thoại) hoặc camera hành trình cắm USB (màn hình Android ô tô). */
@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun CameraSourceRow(s: AppSettings, usb: UsbCamState, set: ((AppSettings) -> AppSettings) -> Unit) {
    val status = when {
        usb.streaming -> "Đang dùng: ${usb.name} · ${usb.width}x${usb.height}"
        usb.attached -> "Đang cắm: ${usb.name}"
        else -> "Chưa cắm camera USB"
    }
    Column(Modifier.padding(Space.lg)) {
        Text("Nguồn camera", style = AppText.bodyStrong)
        Spacer(Modifier.height(2.dp))
        Text("Tự động: dùng camera hành trình khi có camera USB cắm vào màn hình xe, không thì camera của máy. $status.",
            style = AppText.caption)
        Spacer(Modifier.height(Space.sm))
        FlowRow(horizontalArrangement = Arrangement.spacedBy(Space.sm), verticalArrangement = Arrangement.spacedBy(Space.sm)) {
            for ((key, label) in listOf("auto" to "Tự động", "phone" to "Camera của máy", "usb" to "Camera hành trình USB")) {
                Chip(label, s.cameraSource == key) { set { it.copy(cameraSource = key) } }
            }
        }
    }
    Divider()
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun PerfRows(s: AppSettings, set: ((AppSettings) -> AppSettings) -> Unit, onBenchmark: () -> Unit) {
    val modes = linkedMapOf("auto" to "Tự động", "high" to "Cao", "medium" to "Trung bình", "low" to "Thấp")
    val measured = PerfLevel.fromKey(s.lastLevel)
    Column(Modifier.padding(Space.lg)) {
        Text("Mức hiệu năng", style = AppText.bodyStrong)
        Spacer(Modifier.height(2.dp))
        Text("Tự động: đo máy và nhiệt độ, hạ nhịp xử lý khi máy chậm hoặc nóng; đường trống thì nhận diện thưa đi. " +
            "Cao: bám vết mọi khung. Trung bình: 15 lần/giây. Thấp: 10 lần/giây, camera 480p." +
            (measured?.let { " Máy này đo được: mức ${it.label}." } ?: ""), style = AppText.caption)
        Spacer(Modifier.height(Space.sm))
        FlowRow(horizontalArrangement = Arrangement.spacedBy(Space.sm), verticalArrangement = Arrangement.spacedBy(Space.sm)) {
            for ((k, label) in modes) Chip(label, s.perfMode == k) { set { it.copy(perfMode = k) } }
        }
    }
    Divider()
    SwitchRow("Thấy xe ở xa", "Cứ 3 lần nhận diện có 1 lần nhìn kỹ vùng quanh điểm tụ (xe xa to gấp đôi). " +
        "Tự bỏ qua khi có xe gần, đang cảnh báo hoặc máy yếu", s.farDetect, { v -> set { it.copy(farDetect = v) } }, divider = false)
    Divider()
    val last = s.benchHistory.firstOrNull()
    Row(
        Modifier.fillMaxWidth().heightIn(min = 64.dp).clickable(role = Role.Button, onClick = onBenchmark).padding(Space.lg, Space.md),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(Modifier.weight(1f)) {
            Text("Đo hiệu năng máy", style = AppText.bodyStrong)
            Text(
                if (last == null) "Chạy thử 30 giây trên video mẫu: độ mượt, thời gian YOLO, mức hiệu năng"
                else "Lần gần nhất: YOLO ${last.optDouble("yolo_avg").r()} ms, cảnh báo ${vn(last.optDouble("result_hz"))} lần/giây, " +
                    "giật ${vn(last.optDouble("jank_pct"))} %",
                style = AppText.caption,
            )
        }
        Icon(Icons.Rounded.ChevronRight, null, tint = AppColors.textSecondary)
    }
}

// ---------------------------------------------------------------------- thành phần

/** Nhóm cài đặt: tiêu đề + thẻ chứa các hàng, ngăn bởi đường kẻ mảnh. */
@Composable
private fun Group(icon: ImageVector, title: String, content: @Composable () -> Unit) {
    Column(Modifier.widthIn(max = 760.dp).fillMaxWidth().padding(top = Space.lg)) {
        Row(Modifier.padding(start = Space.xs, bottom = Space.sm), verticalAlignment = Alignment.CenterVertically) {
            Box(Modifier.size(28.dp).background(AppColors.accentSoft, RoundedCornerShape(8.dp)), contentAlignment = Alignment.Center) {
                Icon(icon, null, tint = AppColors.accent, modifier = Modifier.size(17.dp))
            }
            Spacer(Modifier.width(Space.sm + 2.dp))
            Text(title.uppercase(), style = AppText.overline, modifier = Modifier.semantics { heading() })
        }
        val shape = RoundedCornerShape(Radii.md)
        Column(Modifier.fillMaxWidth().clip(shape).background(AppColors.surfaceRaised).border(1.dp, AppColors.stroke, shape)) { content() }
    }
}

@Composable
private fun Divider() = HorizontalDivider(Modifier.padding(horizontal = Space.lg), color = AppColors.stroke)

@Composable
private fun SwitchRow(
    title: String, subtitle: String, value: Boolean, onChange: (Boolean) -> Unit,
    divider: Boolean = true, extra: (@Composable () -> Unit)? = null,
) {
    Row(
        Modifier.fillMaxWidth().heightIn(min = 64.dp).clickable(role = Role.Switch) { onChange(!value) }.padding(Space.lg, Space.md),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(Modifier.weight(1f)) {
            Text(title, style = AppText.bodyStrong)
            Spacer(Modifier.height(2.dp))
            Text(subtitle, style = AppText.caption)
            if (extra != null) {
                Spacer(Modifier.height(Space.sm + 2.dp))
                extra()
            }
        }
        Spacer(Modifier.width(Space.md))
        Switch(value, onChange, colors = SwitchDefaults.colors(checkedTrackColor = AppColors.accent, checkedThumbColor = Color.White,
            uncheckedTrackColor = AppColors.surfaceRaised, uncheckedBorderColor = AppColors.strokeStrong, uncheckedThumbColor = AppColors.textSecondary))
    }
    if (divider) Divider()
}

@Composable
private fun SliderRow(title: String, subtitle: String, value: Float, range: ClosedFloatingPointRange<Float>, steps: Int, display: String, onChange: (Float) -> Unit) {
    Column(Modifier.padding(start = Space.lg, end = Space.lg, top = Space.md, bottom = Space.xs)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(title, style = AppText.bodyStrong, modifier = Modifier.weight(1f))
            Text(display, style = AppText.caption.copy(color = AppColors.accent, fontWeight = FontWeight.Bold),
                modifier = Modifier.background(AppColors.accentSoft, RoundedCornerShape(50)).padding(horizontal = Space.sm + 2.dp, vertical = Space.xs))
        }
        Spacer(Modifier.height(2.dp))
        Text(subtitle, style = AppText.caption)
        Slider(value, onChange, valueRange = range, steps = steps)
    }
    Divider()
}

/** Hàng có nút − / + (48 dp) chỉnh một số; nút mờ đi khi chạm giới hạn. */
@Composable
private fun StepperRow(title: String, caption: String, detail: @Composable () -> Unit, value: String, what: String,
                       onMinus: (() -> Unit)?, onPlus: (() -> Unit)?) {
    Row(Modifier.padding(Space.lg, Space.md), verticalAlignment = Alignment.CenterVertically) {
        Column(Modifier.weight(1f)) {
            Text(title, style = AppText.bodyStrong)
            Spacer(Modifier.height(2.dp))
            Text(caption, style = AppText.caption)
            Spacer(Modifier.height(2.dp))
            detail()
        }
        Spacer(Modifier.width(Space.sm))
        StepButton(Icons.Rounded.Remove, "Giảm $what", onMinus)
        Text(value, textAlign = TextAlign.Center, style = AppText.bodyStrong.copy(fontSize = 16.sp, fontWeight = FontWeight.Bold),
            modifier = Modifier.width(72.dp).semantics { contentDescription = "$what: $value" })
        StepButton(Icons.Rounded.Add, "Tăng $what", onPlus)
    }
}

@Composable
private fun StepButton(icon: ImageVector, label: String, onClick: (() -> Unit)?) {
    val on = onClick != null
    Box(
        Modifier
            .size(48.dp)
            .clip(CircleShape)
            .background(if (on) AppColors.accentSoft else Color.Transparent)
            .border(1.dp, if (on) AppColors.accent.copy(alpha = 0.5f) else AppColors.stroke, CircleShape)
            .clickable(enabled = on, role = Role.Button, onClickLabel = label) { onClick?.invoke() }
            .semantics { contentDescription = label },
        contentAlignment = Alignment.Center,
    ) {
        Icon(icon, null, tint = if (on) AppColors.accent else AppColors.textTertiary, modifier = Modifier.size(22.dp))
    }
}

@Composable
private fun Chip(label: String, selected: Boolean, onClick: () -> Unit) {
    FilterChip(
        selected = selected, onClick = onClick,
        label = { Text(label, style = AppText.caption.copy(color = if (selected) AppColors.text else AppColors.textSecondary)) },
        shape = RoundedCornerShape(50),
        colors = FilterChipDefaults.filterChipColors(containerColor = AppColors.surfaceRaised, selectedContainerColor = AppColors.accentSoft,
            selectedLeadingIconColor = AppColors.accent),
        border = FilterChipDefaults.filterChipBorder(true, selected, borderColor = AppColors.stroke, selectedBorderColor = AppColors.accent),
        modifier = Modifier.heightIn(min = 48.dp),
    )
}

@Composable
private fun PreviewChip(label: String, color: Color, onClick: () -> Unit) {
    Row(
        Modifier
            .heightIn(min = 48.dp)
            .clip(RoundedCornerShape(50))
            .background(color.copy(alpha = 0.12f))
            .border(1.dp, color.copy(alpha = 0.45f), RoundedCornerShape(50))
            .clickable(role = Role.Button, onClick = onClick)
            .padding(horizontal = Space.md),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(Icons.Rounded.PlayArrow, null, tint = color, modifier = Modifier.size(18.dp))
        Spacer(Modifier.width(Space.xs))
        Text(label, style = AppText.caption.copy(color = AppColors.text, fontSize = 12.sp))
    }
}
