package vn.adas.caotoc.core

/**
 * Bám vết đơn giản theo IoU (thay ByteTrack của Ultralytics ở bản desktop), chỉ dùng khi tắt bám vết dày.
 * Ghép tham lam theo IoU giảm dần giữa hộp mới và hộp cuối của track (cùng lớp) để gán ID ổn định.
 */
class IouTracker(private val iouThreshold: Double = 0.3, private val maxAgeS: Double = 1.0) {
    private class Track(val id: Int, var last: Detection, var lastSeen: Double)

    private val tracks = ArrayList<Track>()
    private var nextId = 1

    fun reset() {
        tracks.clear()
        nextId = 1
    }

    /** Gán trackId cho các detection (sửa tại chỗ) và trả về chính danh sách đó. */
    fun update(dets: List<Detection>, t: Double): List<Detection> {
        data class Pair3(val v: Double, val ti: Int, val di: Int)

        val pairs = ArrayList<Pair3>()
        for (ti in tracks.indices) for (di in dets.indices) {
            if (tracks[ti].last.classId != dets[di].classId) continue
            val v = iou(tracks[ti].last.box, dets[di].box)
            if (v >= iouThreshold) pairs += Pair3(v, ti, di)
        }
        pairs.sortByDescending { it.v }
        val usedT = HashSet<Int>(); val usedD = HashSet<Int>()
        for ((_, ti, di) in pairs) {
            if (ti in usedT || di in usedD) continue
            usedT += ti; usedD += di
            val tr = tracks[ti].apply { last = dets[di]; lastSeen = t }
            dets[di].trackId = tr.id
        }
        for (di in dets.indices) {
            if (di in usedD) continue
            val tr = Track(nextId++, dets[di], t)
            tracks += tr
            dets[di].trackId = tr.id
        }
        tracks.removeAll { t - it.lastSeen > maxAgeS }
        return dets
    }
}
