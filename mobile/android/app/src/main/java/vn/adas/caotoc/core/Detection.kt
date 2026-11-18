package vn.adas.caotoc.core

import kotlin.math.max
import kotlin.math.min
import kotlin.math.roundToInt

/** Nguồn của một hộp xe: YOLO, bám vết có đo, hay mất dấu (chỉ dự đoán). */
enum class BoxSource { YOLO, TRACK, COAST }

/** Một xe trên khung hình, pixel ảnh gốc (đã xoay đứng). */
class Detection(
    val x1: Double,
    val y1: Double,
    val x2: Double,
    val y2: Double,
    val confidence: Double,
    val classId: Int,
    val className: String,
    var trackId: Int? = null,
    var source: BoxSource = BoxSource.YOLO,
) {
    val width: Double get() = x2 - x1
    val height: Double get() = y2 - y1

    /** Điểm tiếp xúc mặt đường ≈ trung điểm cạnh dưới bounding box. */
    val groundPoint: Vec2 get() = Vec2((x1 + x2) / 2, y2)

    val box: DoubleArray get() = doubleArrayOf(x1, y1, x2, y2)

    fun withSource(s: BoxSource) = Detection(x1, y1, x2, y2, confidence, classId, className, trackId, s)
}

fun iou(a: DoubleArray, b: DoubleArray): Double {
    val xx1 = max(a[0], b[0]); val yy1 = max(a[1], b[1])
    val xx2 = min(a[2], b[2]); val yy2 = min(a[3], b[3])
    val inter = max(0.0, xx2 - xx1) * max(0.0, yy2 - yy1)
    val union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return if (union > 0) inter / union else 0.0
}

/** Tham số letterbox giống Ultralytics: giữ tỉ lệ, đệm xám 114 ở giữa. */
data class Letterbox(
    val srcW: Int, val srcH: Int, val inW: Int, val inH: Int,
    val r: Double, val newW: Int, val newH: Int, val left: Int, val top: Int,
) {
    companion object {
        fun of(srcW: Int, srcH: Int, inW: Int, inH: Int): Letterbox {
            val r = min(inH.toDouble() / srcH, inW.toDouble() / srcW)
            val nw = (srcW * r).roundToInt(); val nh = (srcH * r).roundToInt()
            return Letterbox(srcW, srcH, inW, inH, r, nw, nh, (inW - nw) / 2, (inH - nh) / 2)
        }
    }
}

/**
 * Giải mã đầu ra YOLOv11 (TFLite) + NMS theo từng lớp. Bản tham chiếu Python: tools/export_mobile.py.
 *
 * [out]: tensor phẳng (4 + nc) x N - mỗi cột là một anchor [cx, cy, w, h, điểm lớp...]; mô hình xuất bằng
 * tools/export_mobile.py có tọa độ chuẩn hóa 0..1 theo ô vào ([normalized]). Trả về hộp pixel ảnh gốc.
 */
fun decodeYolo(
    out: FloatArray,
    numAnchors: Int,
    classNames: List<String>,
    lb: Letterbox,
    confThreshold: Double = 0.35,
    iouThreshold: Double = 0.45,
    normalized: Boolean = true,
    maxDet: Int = 100,
    enabledClasses: Set<String>? = null,
): List<Detection> {
    class Cand(val box: DoubleArray, val conf: Double, val cls: Int)

    val nc = classNames.size
    val n = numAnchors
    val sx = if (normalized) lb.inW.toDouble() else 1.0
    val sy = if (normalized) lb.inH.toDouble() else 1.0
    val cand = ArrayList<Cand>()
    for (i in 0 until n) {
        var best = -1.0
        var cls = 0
        for (c in 0 until nc) {
            val s = out[(4 + c) * n + i].toDouble()
            if (s > best) { best = s; cls = c }
        }
        if (best <= confThreshold) continue
        if (enabledClasses != null && classNames[cls] !in enabledClasses) continue
        val cx = out[i] * sx; val cy = out[n + i] * sy; val w = out[2 * n + i] * sx; val h = out[3 * n + i] * sy
        cand += Cand(doubleArrayOf(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2), best, cls)
    }
    cand.sortByDescending { it.conf }
    val keep = ArrayList<Cand>()
    for (c in cand) {
        if (keep.none { it.cls == c.cls && iou(it.box, c.box) > iouThreshold }) {
            keep += c
            if (keep.size >= maxDet) break
        }
    }
    val w = lb.srcW.toDouble(); val h = lb.srcH.toDouble()
    return keep.map { k ->
        val b = k.box
        Detection(
            ((b[0] - lb.left) / lb.r).coerceIn(0.0, w),
            ((b[1] - lb.top) / lb.r).coerceIn(0.0, h),
            ((b[2] - lb.left) / lb.r).coerceIn(0.0, w),
            ((b[3] - lb.top) / lb.r).coerceIn(0.0, h),
            k.conf, k.cls, classNames[k.cls],
        )
    }
}
