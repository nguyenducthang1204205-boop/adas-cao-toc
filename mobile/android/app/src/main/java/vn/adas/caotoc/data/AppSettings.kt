package vn.adas.caotoc.data

import android.content.Context
import android.util.Log
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import org.json.JSONArray
import org.json.JSONObject
import vn.adas.caotoc.core.AlertConfig
import vn.adas.caotoc.core.CalibrationConfig
import vn.adas.caotoc.core.DEFAULT_BAND_GAPS_M
import vn.adas.caotoc.core.DEFAULT_TIME_GAP_S
import vn.adas.caotoc.core.LEGAL_GAP_TABLE
import vn.adas.caotoc.core.MODIFIERS
import vn.adas.caotoc.core.PerfLevel
import vn.adas.caotoc.core.ROAD_CONDITIONS
import vn.adas.caotoc.core.SafetyPolicy
import vn.adas.caotoc.core.conditionPolicy

/** Cài đặt của app (bất biến; đổi bằng [SettingsStore.update]). Khóa JSON giống bản Flutter trước đây. */
data class AppSettings(
    val calibration: CalibrationConfig = CalibrationConfig(),
    /** Người dùng đã căn chỉnh camera cho lần gắn máy này chưa. */
    val calibrated: Boolean = false,
    /** Tự hoàn thiện căn chỉnh khi chạy + báo camera xê dịch (giống auto_calib của bản desktop). */
    val autoCalib: Boolean = true,
    val alert: AlertConfig = AlertConfig(),
    val conditionKey: String = "dry",
    val modifierKeys: Set<String> = emptySet(),
    /** Tầm nhìn (m) trợ lý nhận ra từ câu mô tả; 0 = không giới hạn. */
    val visibilityM: Double = 0.0,
    /** Dưới 60 km/h: quy tắc thời gian (2-6 giây). */
    val timeGapS: Double = DEFAULT_TIME_GAP_S,
    /** Ngưỡng cảnh báo đường khô theo dải tốc độ (>= luật). */
    val bandGapsM: List<Double> = DEFAULT_BAND_GAPS_M,
    val manualSpeedKmh: Double = 80.0,
    val useGps: Boolean = true,
    val preferGpu: Boolean = true,
    val rotate180: Boolean = false,
    /** Nguồn hình: 'auto' (camera hành trình USB khi có cắm, không thì camera của máy) | 'phone' | 'usb'. */
    val cameraSource: String = "auto",
    /** Nhận diện thưa, bám vết dày. */
    val denseTracking: Boolean = true,
    /** Hiện thông số kỹ thuật (FPS, YOLO) trên màn hình lái. */
    val showTech: Boolean = false,
    /** 'auto' (bộ điều tốc tự chọn theo máy, nhiệt độ) hoặc khóa 'high' / 'medium' / 'low'. */
    val perfMode: String = "auto",
    /** Mức bộ điều tốc chọn ở lần chạy trước: 'low' thì camera mở ở 480p ngay từ đầu. */
    val lastLevel: String = "",
    /** Xen kẽ khung khóa hẹp quanh điểm tụ để thấy xe ở xa. */
    val farDetect: Boolean = true,
    /** Kết quả đo hiệu năng gần nhất trước, tối đa [MAX_BENCH] lần - để so sánh giữa các máy/bản. */
    val benchHistory: List<JSONObject> = emptyList(),
    val confidence: Double = 0.35,
    val enabledClasses: Set<String> = setOf("car", "truck", "bus", "Jeepney"),
    /** Đã đọc lời nhắc an toàn ở màn hình chào. */
    val disclaimerAccepted: Boolean = false,
) {
    /** Yếu tố cộng thêm theo thứ tự của bảng MODIFIERS (tên điều kiện giống bản desktop). */
    val policy: SafetyPolicy
        get() = conditionPolicy(conditionKey, MODIFIERS.keys.filter { it in modifierKeys }, visibilityM,
            SafetyPolicy(timeGapS = timeGapS, bandGapsM = bandGapsM))

    val forcedLevel: PerfLevel? get() = PerfLevel.fromKey(perfMode)

    /** Camera mở ở 480p (mức Thấp: khóa tay, hoặc tự động và lần trước bộ điều tốc chọn Thấp). */
    val lowCamera: Boolean get() = perfMode == "low" || (perfMode == "auto" && lastLevel == "low")

    /** Áp dụng điều kiện do Trợ lý AI hoặc ô chọn nhanh đưa ra. */
    fun withCondition(key: String, mods: Iterable<String>, visibility: Double) =
        copy(conditionKey = key, modifierKeys = mods.toSet(), visibilityM = visibility.coerceIn(0.0, 1000.0))

    fun withDefaultBands() = copy(timeGapS = DEFAULT_TIME_GAP_S, bandGapsM = DEFAULT_BAND_GAPS_M)

    val bandsAreDefault: Boolean
        get() = timeGapS == DEFAULT_TIME_GAP_S && bandGapsM.indices.all { bandGapsM[it] == LEGAL_GAP_TABLE[it].second }

    fun toJson(): JSONObject = JSONObject()
        .put("calibration", calibration.toJson())
        .put("calibrated", calibrated)
        .put("auto_calib", autoCalib)
        .put("alert", alert.toJson())
        .put("condition", conditionKey)
        .put("modifiers", JSONArray(modifierKeys.toList()))
        .put("visibility_m", visibilityM)
        .put("time_gap_s", timeGapS)
        .put("band_gaps_m", JSONArray(bandGapsM))
        .put("manual_speed_kmh", manualSpeedKmh)
        .put("use_gps", useGps)
        .put("prefer_gpu", preferGpu)
        .put("rotate180", rotate180)
        .put("camera_source", cameraSource)
        .put("dense_tracking", denseTracking)
        .put("show_tech", showTech)
        .put("perf_mode", perfMode)
        .put("last_level", lastLevel)
        .put("far_detect", farDetect)
        .put("bench_history", JSONArray(benchHistory))
        .put("confidence", confidence)
        .put("enabled_classes", JSONArray(enabledClasses.toList()))
        .put("disclaimer_ok", disclaimerAccepted)

    companion object {
        const val MAX_BENCH = 20
        val TIME_GAP_RANGE = 2.0..6.0
        const val MAX_BAND_GAP_M = 300.0
        val CAMERA_SOURCES = listOf("auto", "phone", "usb")

        /** Giới hạn giống bản desktop: 2-6 giây; mỗi dải từ mức luật đến 300 m. */
        fun clampTimeGap(v: Double) = v.coerceIn(TIME_GAP_RANGE)
        fun clampBand(i: Int, v: Double) = v.coerceIn(LEGAL_GAP_TABLE[i].second, MAX_BAND_GAP_M)

        fun fromJson(j: JSONObject): AppSettings {
            val d = AppSettings()
            fun strings(key: String): List<String>? =
                j.optJSONArray(key)?.let { a -> List(a.length()) { a.getString(it) } }
            val bands = j.optJSONArray("band_gaps_m")?.let { a -> List(a.length()) { a.getDouble(it) } } ?: emptyList()
            val cond = j.optString("condition", "dry")
            val perf = j.optString("perf_mode", "auto")
            val source = j.optString("camera_source", "auto")
            return AppSettings(
                calibration = j.optJSONObject("calibration")?.let(CalibrationConfig::fromJson) ?: d.calibration,
                calibrated = j.optBoolean("calibrated", false),
                autoCalib = j.optBoolean("auto_calib", true),
                alert = j.optJSONObject("alert")?.let(AlertConfig::fromJson) ?: d.alert,
                conditionKey = if (cond in ROAD_CONDITIONS) cond else "dry",
                modifierKeys = strings("modifiers")?.filter { it in MODIFIERS }?.toSet() ?: emptySet(),
                visibilityM = j.optDouble("visibility_m", 0.0).coerceIn(0.0, 1000.0),
                timeGapS = clampTimeGap(j.optDouble("time_gap_s", DEFAULT_TIME_GAP_S)),
                bandGapsM = LEGAL_GAP_TABLE.indices.map { clampBand(it, bands.getOrElse(it) { DEFAULT_BAND_GAPS_M[it] }) },
                manualSpeedKmh = j.optDouble("manual_speed_kmh", 80.0),
                useGps = j.optBoolean("use_gps", true),
                preferGpu = j.optBoolean("prefer_gpu", true),
                rotate180 = j.optBoolean("rotate180", false),
                cameraSource = if (source in CAMERA_SOURCES) source else "auto",
                denseTracking = j.optBoolean("dense_tracking", true),
                showTech = j.optBoolean("show_tech", false),
                perfMode = if (perf in setOf("auto", "high", "medium", "low")) perf else "auto",
                lastLevel = j.optString("last_level", ""),
                farDetect = j.optBoolean("far_detect", true),
                benchHistory = j.optJSONArray("bench_history")?.let { a -> List(a.length()) { a.getJSONObject(it) } } ?: emptyList(),
                confidence = j.optDouble("confidence", 0.35),
                enabledClasses = strings("enabled_classes")?.toSet() ?: d.enabledClasses,
                disclaimerAccepted = j.optBoolean("disclaimer_ok", false),
            )
        }
    }
}

/** Lưu cài đặt bằng SharedPreferences (một chuỗi JSON); phát thay đổi qua [settings]. */
class SettingsStore(context: Context) {
    private val prefs = context.getSharedPreferences("adas", Context.MODE_PRIVATE)
    private val state = MutableStateFlow(load())
    val settings: StateFlow<AppSettings> = state.asStateFlow()
    val value: AppSettings get() = state.value

    /** Không bao giờ ném lỗi: cài đặt hỏng/không đọc được thì dùng mặc định để app vẫn khởi động. */
    private fun load(): AppSettings = try {
        prefs.getString(KEY, null)?.let { AppSettings.fromJson(JSONObject(it)) } ?: AppSettings()
    } catch (e: Exception) {
        Log.w(TAG, "Không đọc được cài đặt, dùng mặc định", e)
        AppSettings()
    }

    fun update(f: (AppSettings) -> AppSettings) {
        state.update(f)
        prefs.edit().putString(KEY, state.value.toJson().toString()).apply()
    }

    private companion object {
        const val KEY = "adas_settings_v2"
        const val TAG = "SettingsStore"
    }
}
