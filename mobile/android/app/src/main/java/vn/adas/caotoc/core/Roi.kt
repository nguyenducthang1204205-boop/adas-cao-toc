package vn.adas.caotoc.core

import kotlin.math.min
import kotlin.math.roundToInt

/**
 * Vùng ảnh đưa vào YOLO, tính từ hiệu chỉnh camera (giống openpilot nắn ảnh theo hiệu chỉnh về vùng
 * đường trước khi vào mô hình, thay vì đưa cả khung hình).
 *
 * - Dải rộng ("wide"): giữ nguyên bề ngang, bỏ phần trời phía trên chân trời và nắp capo phía dưới, sao
 *   cho tỉ lệ đúng bằng ô vào của mô hình -> không phí điểm ảnh vào vùng đệm, xe giữ nguyên độ phân giải.
 * - Vùng hẹp ("narrow"): ô quanh điểm tụ ở tỉ lệ ~1:1 điểm ảnh camera - xe ở xa to gấp đôi so với dải
 *   rộng (ý tưởng trường nhìn hẹp cho tầm xa của Mobileye, ở đây xen kẽ trên cùng một camera).
 */
data class CropRect(val x: Int, val y: Int, val w: Int, val h: Int)

object Roi {
    /** Phần trên chân trời giữ lại trong dải rộng (xe tải gần cao hơn camera nên nhô lên trên chân trời). */
    const val WIDE_ABOVE_HORIZON = 0.35

    /** Vị trí điểm tụ trong vùng hẹp (tính từ mép trên): xe ở xa nằm ngay dưới chân trời. */
    const val NARROW_ABOVE_HORIZON = 0.45

    /** Hàng chân trời (px) từ hiệu chỉnh; hiệu chỉnh suy biến thì lấy 45 % chiều cao. */
    fun horizonRow(m: GroundPlaneMapper): Double {
        val h = m.horizonY
        if (h == null || !h.isFinite()) return 0.45 * m.frameH
        return h.coerceIn(0.15 * m.frameH, 0.75 * m.frameH)
    }

    /** Cột điểm tụ (px): nơi trục xe (X = 0) gặp chân trời. */
    fun vanishingColumn(m: GroundPlaneMapper): Double {
        val far = m.groundToImage(0.0, 1000.0)
        if (!far.x.isFinite()) return m.frameW / 2
        return far.x.coerceIn(0.25 * m.frameW, 0.75 * m.frameW)
    }

    /** Dải rộng cùng tỉ lệ với ô vào [inW] x [inH]. Khung thấp hơn dải (ô vào "cao" hơn khung) thì lấy cả khung. */
    fun wideCrop(m: GroundPlaneMapper, calib: CalibrationConfig, frameW: Int, frameH: Int, inW: Int, inH: Int): CropRect {
        val bandH = (frameW.toDouble() * inH / inW).roundToInt()
        if (bandH >= frameH) return CropRect(0, 0, frameW, frameH)
        var top = horizonRow(m) - WIDE_ABOVE_HORIZON * bandH
        // luôn giữ vùng gần (mép dưới hình chữ nhật hiệu chỉnh + 4 %): xe ngay trước mặt quan trọng nhất
        val nearRow = calib.imagePoints.maxOf { it.y } * frameH
        val needBottom = min(frameH.toDouble(), nearRow + 0.04 * frameH)
        if (top + bandH < needBottom) top = needBottom - bandH
        val y = top.roundToInt().coerceIn(0, frameH - bandH)
        return CropRect(0, y, frameW, bandH)
    }

    /** Vùng hẹp quanh điểm tụ, ~1:1 điểm ảnh; null nếu khung quá nhỏ để có lợi (dưới 1,6 lần bề ngang ô vào). */
    fun narrowCrop(m: GroundPlaneMapper, frameW: Int, frameH: Int, inW: Int, inH: Int): CropRect? {
        if (frameW < 1.6 * inW || inH > frameH) return null
        val x = (vanishingColumn(m) - inW / 2.0).roundToInt().coerceIn(0, frameW - inW)
        val y = (horizonRow(m) - NARROW_ABOVE_HORIZON * inH).roundToInt().coerceIn(0, frameH - inH)
        return CropRect(x, y, inW, inH)
    }
}
