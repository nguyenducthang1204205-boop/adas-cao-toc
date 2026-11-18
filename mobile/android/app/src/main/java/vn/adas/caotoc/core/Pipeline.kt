package vn.adas.caotoc.core

/**
 * Chống nhiễu (giống adas/alert/engine.py): nâng mức khi mức mới kéo dài escalateSeconds (>= 2 khung), hạ mức
 * sau khi mức thấp kéo dài holdSeconds. Tính theo thời gian để nhịp xử lý 10 hay 30 Hz đều báo kịp như nhau.
 */
class AlertHysteresis(private val cfg: AlertConfig) {
    var level = Risk.SAFE
        private set
    private var candidate = Risk.SAFE
    private var count = 0
    private var since = 0.0
    private var lastRaise = 0.0

    fun update(rawIn: Risk, now: Double): Risk {
        val raw = if (rawIn == Risk.WARNING || rawIn == Risk.DANGER) rawIn else Risk.SAFE
        if (raw == candidate) {
            count++
        } else {
            candidate = raw
            count = 1
            since = now
        }
        val r = raw.rank; val cur = level.rank
        when {
            r > cur -> if (confirmed(now)) { level = raw; lastRaise = now }
            r < cur -> if (now - lastRaise >= cfg.holdSeconds) level = raw
            else -> lastRaise = now
        }
        return level
    }

    private fun confirmed(now: Double): Boolean =
        cfg.escalateSeconds <= 0 || (count >= 2 && now - since >= cfg.escalateSeconds - 1e-9)

    fun reset() {
        level = Risk.SAFE
        candidate = Risk.SAFE
        count = 0
    }
}

class FrameResult(
    val vehicles: List<VehicleState>,
    val lead: VehicleState?,
    val thresholds: Thresholds,
    val speedKmh: Double,
    val rawLevel: Risk,
    val level: Risk,
)

/**
 * Xử lý một khung (port của adas/pipeline.py, phần sau YOLO): bám vết -> khoảng cách -> ngưỡng ->
 * mức rủi ro -> chống nhiễu cảnh báo. Thuần Kotlin, kiểm thử được trên JVM.
 *
 * Nhận diện thưa, bám vết dày: YOLO chạy nền khi rảnh; MỌI khung camera đều qua [processFrame] với ảnh
 * xám để [TemplateTracker] đo lại vị trí xe, nên khoảng cách/TTC cập nhật theo tốc độ camera chứ không
 * theo tốc độ YOLO.
 */
class AdasPipeline(val calib: CalibrationConfig, private val alertCfg: AlertConfig, val frameW: Double, val frameH: Double) {
    val mapper = GroundPlaneMapper(calib, frameW, frameH)
    private val estimator = DistanceEstimator(mapper, calib)
    private val iouTracker = IouTracker() // gán id khi tắt bám vết dày
    val templates = TemplateTracker()
    private val alert = AlertHysteresis(alertCfg)

    /** Chỉ kết quả YOLO, không bám vết (gán id bằng IoU). */
    fun process(dets: List<Detection>, t: Double, speedKmh: Double, policy: SafetyPolicy): FrameResult {
        iouTracker.update(dets, t)
        return evaluate(dets, t, speedKmh, policy)
    }

    /**
     * Mỗi khung camera: [gray] là ảnh xám khung hiện tại (độ phân giải làm việc); [yolo] là kết quả YOLO mới
     * về (chụp lúc [yoloT] - trễ hơn [t] vì YOLO chạy nền) hoặc null. [yoloRoi]: vùng YOLO đã nhìn.
     */
    fun processFrame(
        gray: GrayImage, t: Double, speedKmh: Double, policy: SafetyPolicy,
        yolo: List<Detection>? = null, yoloT: Double? = null, yoloRoi: DoubleArray? = null,
    ): FrameResult {
        val dets = if (yolo != null) {
            templates.refresh(yolo, gray, t, gray.width / frameW, detT = yoloT, roi = yoloRoi)
        } else {
            templates.track(gray, t)
        }
        return evaluate(dets, t, speedKmh, policy)
    }

    private fun evaluate(dets: List<Detection>, t: Double, speedKmh: Double, policy: SafetyPolicy): FrameResult {
        val vehicles = estimator.estimate(dets, t)
        val thr = computeThresholds(speedKmh, policy)
        var raw = Risk.SAFE
        var lead: VehicleState? = null
        for (vs in vehicles) {
            if ((alertCfg.onlyEgoLane && !vs.inEgoLane) || vs.method == RangeMethod.FAR) {
                vs.risk = Risk.INFO // ngoài làn hoặc ngoài tầm đo tin cậy -> không cảnh báo
                continue
            }
            vs.risk = classifyRisk(vs.distanceM, vs.ttcS, thr, policy)
            if (vs.risk.rank > raw.rank) raw = vs.risk
            if (vs.inEgoLane && lead == null) lead = vs // đã sắp xếp gần -> xa
        }
        val level = alert.update(raw, t)
        return FrameResult(vehicles, lead, thr, speedKmh, raw, level)
    }
}
