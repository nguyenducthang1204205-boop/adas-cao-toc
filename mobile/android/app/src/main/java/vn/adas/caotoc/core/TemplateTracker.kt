package vn.adas.caotoc.core

import kotlin.math.abs
import kotlin.math.ceil
import kotlin.math.floor
import kotlin.math.max
import kotlin.math.min
import kotlin.math.sqrt

/**
 * Bám vết dày giữa các lần chạy YOLO (port 1:1 của adas/detection/tracking.py - xem đó để biết thuật toán).
 *
 * Trên điện thoại YOLO chạy nền bất cứ khi nào rảnh, còn tracker chạy trên MỌI khung camera. Kết quả YOLO
 * về trễ (chụp lúc detT < t) được ghép với track theo lịch sử hộp và dời theo chuyển động đã đo từ detT.
 */
object TrackerParams {
    const val WORK_W = 640            // ảnh xám làm việc rộng tối đa 640 px
    const val GRID = 16               // lưới mẫu tối đa GRID x GRID điểm
    val SCALES = doubleArrayOf(0.97, 1.0, 1.03)
    const val MIN_NCC = 0.6
    const val SEARCH_BASE = 4.0
    const val SEARCH_REL = 0.08
    const val SEARCH_MAX = 10
    const val MAX_TRACKED = 4         // chỉ bám chi tiết các xe gần nhất
    const val COAST_MAX_S = 0.5
    const val MAX_YOLO_MISSES = 2     // YOLO bỏ sót 1 lần: bám tiếp; 2 lần liên tiếp: bỏ (tránh "xe ma")
    const val HISTORY_LEN = 64
}

/** Ảnh xám (giá trị 0..255) ở độ phân giải làm việc. */
class GrayImage(val width: Int, val height: Int, val data: FloatArray) {
    /** Nội suy song tuyến, tọa độ bị kẹp trong ảnh (giống _sample của tracking.py). */
    fun at(xIn: Double, yIn: Double): Double {
        val xm = width - 1.001; val ym = height - 1.001
        val x = xIn.coerceIn(0.0, xm); val y = yIn.coerceIn(0.0, ym)
        val x0 = floor(x).toInt(); val y0 = floor(y).toInt()
        val fx = x - x0; val fy = y - y0
        val i = y0 * width + x0
        val v00 = data[i]; val v01 = data[i + 1]; val v10 = data[i + width]; val v11 = data[i + width + 1]
        return (v00 * (1 - fx) + v01 * fx) * (1 - fy) + (v10 * (1 - fx) + v11 * fx) * fy
    }
}

class TemplateTracker {
    private class Track(
        val id: Int,
        var det: Detection,          // hộp hiện tại (pixel khung gốc)
        val template: FloatArray,    // mẫu neo đã chuẩn hóa
        val nx: Int, val ny: Int,
        val anchorW: Double, val anchorH: Double, // px ảnh làm việc
        var lastMeasT: Double,
    ) {
        var scale = 1.0
        var ncc = 1.0
        var yoloMisses = 0
        val history = ArrayDeque<Pair<Double, DoubleArray>>()

        val box: DoubleArray get() = det.box

        fun remember(t: Double) {
            history.addLast(t to box)
            if (history.size > TrackerParams.HISTORY_LEN) history.removeFirst()
        }
    }

    private val tracks = LinkedHashMap<Int, Track>()
    private var nextId = 1
    private var k = 1.0

    /** Số xe gần nhất được so khớp mẫu mỗi khung (bộ điều tốc giảm trên máy yếu). */
    var trackedLimit = TrackerParams.MAX_TRACKED

    fun reset() = tracks.clear()

    /**
     * Kết quả YOLO mới (chụp lúc [detT], mặc định = [t]): ghép track, neo lại mẫu ở khung hiện tại.
     * Trả về các hộp hiện tại: detection YOLO (đã gán id, dời theo chuyển động nếu về trễ) + các track
     * YOLO bỏ sót lần này (bám tiếp trên khung này).
     *
     * [roi] (x1, y1, x2, y2 pixel khung gốc): YOLO chỉ nhìn vùng này (khung khóa hẹp cho xe ở xa). Track không
     * nằm trọn trong vùng không bị tính là "YOLO bỏ sót" - chỉ bám tiếp như khung thường.
     */
    fun refresh(
        dets: List<Detection>, gray: GrayImage, t: Double, scaleK: Double,
        detT: Double? = null, roi: DoubleArray? = null,
    ): List<Detection> {
        k = scaleK
        val dt0 = detT ?: t
        val used = HashSet<Int>()
        val out = ArrayList<Detection>()
        for (d in dets) {
            var box = d.box
            var tr: Track? = d.trackId?.let { tracks[it] }
            if (tr == null && d.trackId == null) tr = matchIou(box, d.classId, dt0, used)
            if (tr != null && dt0 < t) {
                val past = boxAt(tr, dt0)
                if (past != null) {
                    val now = tr.box
                    box = DoubleArray(4) { i -> box[i] + (now[i] - past[i]) }
                }
            }
            val id = d.trackId ?: tr?.id ?: nextId++
            val det = Detection(box[0], box[1], box[2], box[3], d.confidence, d.classId, d.className, id, BoxSource.YOLO)
            out += det
            used += id
            val nt = anchor(id, det, gray, t)
            if (nt == null) {
                tracks.remove(id) // không lấy được mẫu: vẫn báo xe ở khung này, không bám tiếp
                continue
            }
            if (tr != null) nt.history.addAll(tr.history)
            nt.remember(t)
            tracks[id] = nt
        }
        for (id in tracks.keys.toList()) {
            if (id in used) continue
            val tr = tracks.getValue(id)
            if (roi == null || inside(tr.box, roi)) tr.yoloMisses++
            if (tr.yoloMisses >= TrackerParams.MAX_YOLO_MISSES) {
                tracks.remove(id)
                continue
            }
            step(tr, gray, t)
            if (tr.det.source == BoxSource.COAST && t - tr.lastMeasT > TrackerParams.COAST_MAX_S) {
                tracks.remove(id)
                continue
            }
            tr.remember(t)
            out += tr.det
        }
        return out
    }

    /** Khung không có kết quả YOLO mới: đo lại vị trí các xe bằng so khớp mẫu. */
    fun track(gray: GrayImage, t: Double): List<Detection> {
        val order = tracks.values.sortedByDescending { it.det.y2 } // gần trước
        val out = ArrayList<Detection>()
        for ((i, tr) in order.withIndex()) {
            if (i < trackedLimit) step(tr, gray, t) else tr.det = tr.det.withSource(BoxSource.COAST)
            if (tr.det.source == BoxSource.COAST && t - tr.lastMeasT > TrackerParams.COAST_MAX_S) {
                tracks.remove(tr.id)
                continue
            }
            tr.remember(t)
            out += tr.det
        }
        return out
    }

    private fun matchIou(box: DoubleArray, cls: Int, t: Double, used: Set<Int>): Track? {
        var best: Track? = null
        var bestIou = 0.3
        for (tr in tracks.values) {
            if (tr.id in used || tr.det.classId != cls) continue
            val past = boxAt(tr, t) ?: continue
            val v = iou(box, past)
            if (v > bestIou) { best = tr; bestIou = v }
        }
        return best
    }

    private fun boxAt(tr: Track, t: Double): DoubleArray? {
        if (tr.history.isEmpty()) return null
        var best = tr.history.first()
        for (e in tr.history) if (abs(e.first - t) < abs(best.first - t)) best = e
        return best.second
    }

    private fun anchor(id: Int, det: Detection, gray: GrayImage, t: Double): Track? {
        val x1 = det.x1 * k; val y1 = det.y1 * k; val x2 = det.x2 * k; val y2 = det.y2 * k
        val bw = x2 - x1; val bh = y2 - y1
        if (bw < 4 || bh < 4) return null
        val nx = floor(bw + 0.5).toInt().coerceIn(4, TrackerParams.GRID)
        val ny = floor(bh + 0.5).toInt().coerceIn(4, TrackerParams.GRID)
        val v = FloatArray(nx * ny)
        sampleInto(gray, (x1 + x2) / 2, (y1 + y2) / 2, bw, bh, nx, ny, v)
        var mean = 0.0
        for (e in v) mean += e
        mean /= v.size
        var varSum = 0.0
        for (e in v) varSum += (e - mean) * (e - mean)
        if (sqrt(varSum / v.size) < 2.0) return null // mẫu phẳng (đêm tối, sương): không bám được
        normalize(v)
        return Track(id, det, v, nx, ny, bw, bh, t)
    }

    /** NCC giữa mẫu neo và lưới lấy ở hộp tâm (cx, cy) cỡ bw x bh. */
    private fun ncc(tr: Track, gray: GrayImage, cx: Double, cy: Double, bw: Double, bh: Double, buf: FloatArray): Double {
        sampleInto(gray, cx, cy, bw, bh, tr.nx, tr.ny, buf)
        var mean = 0.0
        for (e in buf) mean += e
        mean /= buf.size
        var dot = 0.0; var norm = 0.0
        val tpl = tr.template
        for (i in buf.indices) {
            val c = buf[i] - mean
            dot += c * tpl[i]
            norm += c * c
        }
        return dot / max(sqrt(norm), 1e-6)
    }

    private fun step(tr: Track, gray: GrayImage, t: Double) {
        val x1 = tr.det.x1 * k; val y1 = tr.det.y1 * k; val x2 = tr.det.x2 * k; val y2 = tr.det.y2 * k
        val cx = (x1 + x2) / 2; val cy = (y1 + y2) / 2
        val bw0 = tr.anchorW * tr.scale; val bh0 = tr.anchorH * tr.scale
        val r = min(TrackerParams.SEARCH_MAX, ceil(TrackerParams.SEARCH_BASE + TrackerParams.SEARCH_REL * max(bw0, bh0)).toInt())
        val buf = FloatArray(tr.nx * tr.ny)
        // dò thô vị trí (bước 2 px) ở tỉ lệ hiện tại; thứ tự duyệt giống numpy (hàng dy ngoài, cột dx trong)
        var best = -2.0; var bx = 0; var by = 0
        var dy = -r
        while (dy <= r) {
            var dx = -r
            while (dx <= r) {
                val c = ncc(tr, gray, cx + dx, cy + dy, bw0, bh0, buf)
                if (c > best) { best = c; bx = dx; by = dy }
                dx += 2
            }
            dy += 2
        }
        // dò tinh ±1 px x 3 tỉ lệ quanh điểm tốt nhất + nội suy parabol theo bảng 3x3 của tỉ lệ được chọn
        var bj = -2.0; var jx = 1; var jy = 1; var bs = 1.0
        var c = Array(3) { DoubleArray(3) }
        for (s in TrackerParams.SCALES) {
            val cs = Array(3) { DoubleArray(3) }
            var sj = -2.0; var sx = 1; var sy = 1
            for (fy in 0 until 3) for (fx in 0 until 3) {
                val v = ncc(tr, gray, cx + bx + fx - 1, cy + by + fy - 1, bw0 * s, bh0 * s, buf)
                cs[fy][fx] = v
                if (v > sj) { sj = v; sx = fx; sy = fy }
            }
            if (sj > bj) { bj = sj; jx = sx; jy = sy; bs = s; c = cs }
        }
        var ox = (bx + jx - 1).toDouble(); var oy = (by + jy - 1).toDouble()
        if (jx == 1) ox += parabola(c[1][0], c[1][1], c[1][2])
        if (jy == 1) oy += parabola(c[0][1], c[1][1], c[2][1])
        tr.ncc = bj
        if (bj < TrackerParams.MIN_NCC) {
            tr.det = tr.det.withSource(BoxSource.COAST)
            return
        }
        tr.scale *= bs
        val bw = tr.anchorW * tr.scale; val bh = tr.anchorH * tr.scale
        val ncx = cx + ox; val ncy = cy + oy
        tr.det = Detection((ncx - bw / 2) / k, (ncy - bh / 2) / k, (ncx + bw / 2) / k, (ncy + bh / 2) / k,
            tr.det.confidence, tr.det.classId, tr.det.className, tr.id, BoxSource.TRACK)
        tr.lastMeasT = t
    }

    companion object {
        private fun sampleInto(g: GrayImage, cx: Double, cy: Double, bw: Double, bh: Double, nx: Int, ny: Int, out: FloatArray) {
            val sx = bw / nx; val sy = bh / ny
            val x0 = cx - bw / 2 + 0.5 * sx; val y0 = cy - bh / 2 + 0.5 * sy
            val xLast = x0 + (nx - 1) * sx; val yLast = y0 + (ny - 1) * sy
            var o = 0
            if (x0 < 0 || y0 < 0 || xLast > g.width - 1.001 || yLast > g.height - 1.001) {
                for (j in 0 until ny) {
                    val y = y0 + j * sy
                    for (i in 0 until nx) out[o++] = g.at(x0 + i * sx, y).toFloat()
                }
                return
            }
            // nhanh: không cần kẹp tọa độ
            val d = g.data; val w = g.width
            for (j in 0 until ny) {
                val y = y0 + j * sy
                val yi = floor(y).toInt()
                val fy = y - yi
                val row = yi * w
                for (i in 0 until nx) {
                    val x = x0 + i * sx
                    val xi = floor(x).toInt()
                    val fx = x - xi
                    val kk = row + xi
                    val a = d[kk].toDouble(); val b = d[kk + w].toDouble()
                    val top = a + (d[kk + 1] - a) * fx
                    val bot = b + (d[kk + w + 1] - b) * fx
                    out[o++] = (top + (bot - top) * fy).toFloat()
                }
            }
        }

        private fun normalize(v: FloatArray) {
            var mean = 0.0
            for (e in v) mean += e
            mean /= v.size
            var norm = 0.0
            for (i in v.indices) {
                v[i] = (v[i] - mean).toFloat()
                norm += v[i].toDouble() * v[i]
            }
            norm = max(sqrt(norm), 1e-6)
            for (i in v.indices) v[i] = (v[i] / norm).toFloat()
        }

        private fun parabola(cm: Double, c0: Double, cp: Double): Double {
            val d = cm - 2 * c0 + cp
            return if (d < 0) 0.5 * (cm - cp) / d else 0.0
        }

        private fun inside(b: DoubleArray, roi: DoubleArray): Boolean =
            b[0] >= roi[0] - 2 && b[1] >= roi[1] - 2 && b[2] <= roi[2] + 2 && b[3] <= roi[3] + 2

        /** Tỉ lệ thu nhỏ khung gốc về ảnh làm việc (≤ 640 px rộng). */
        fun workScale(frameW: Int): Double = min(1.0, TrackerParams.WORK_W.toDouble() / frameW)
    }
}
