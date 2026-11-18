package vn.adas.caotoc.detector

import vn.adas.caotoc.core.GrayImage
import vn.adas.caotoc.core.TrackerParams
import java.nio.ByteBuffer
import kotlin.math.roundToInt

/**
 * Một khung ảnh YUV420 (YUV_420_888 của CameraX, hoặc I420 tự tạo cho benchmark) đã chép ra mảng byte,
 * để gửi sang luồng YOLO sau khi CameraX thu hồi bộ đệm gốc.
 *
 * [rotate180]: cảm biến lắp ngược (ảnh cần xoay 180° để đứng chiều).
 */
class FramePacket(
    val width: Int,
    val height: Int,
    val y: ByteArray, val yRowStride: Int,
    val u: ByteArray, val v: ByteArray, val uvRowStride: Int, val uvPixelStride: Int,
    val rotate180: Boolean,
) {
    companion object {
        /** Chép 3 mặt phẳng (CameraX ImageProxy.planes). Dùng lại [reuse] nếu cùng kích thước để đỡ cấp phát. */
        fun copyOf(
            width: Int, height: Int,
            yBuf: ByteBuffer, yRow: Int, uBuf: ByteBuffer, vBuf: ByteBuffer, uvRow: Int, uvPix: Int,
            rotate180: Boolean, reuse: FramePacket? = null,
        ): FramePacket {
            fun copy(src: ByteBuffer, old: ByteArray?): ByteArray {
                val dup = src.duplicate().apply { rewind() }
                val dst = if (old != null && old.size == dup.remaining()) old else ByteArray(dup.remaining())
                dup.get(dst)
                return dst
            }
            val r = reuse?.takeIf { it.width == width && it.height == height }
            return FramePacket(width, height, copy(yBuf, r?.y), yRow, copy(uBuf, r?.u), copy(vBuf, r?.v), uvRow, uvPix, rotate180)
        }
    }
}

/**
 * Ảnh xám thu nhỏ cho bám vết, tạo ở MỌI khung camera (rẻ: chỉ đọc kênh Y).
 * Thu nhỏ bằng trung bình khối f x f (như cv2.INTER_AREA của bản desktop), f = round(rộng / 640).
 */
object Gray {
    fun fromPlane(plane: ByteBuffer, width: Int, height: Int, rowStride: Int, rotate180: Boolean = false): GrayImage {
        val f = (width.toDouble() / TrackerParams.WORK_W).roundToInt().coerceIn(1, 8)
        val ow = width / f; val oh = height / f
        val out = FloatArray(ow * oh)
        val inv = 1f / (f * f)
        val base = plane.position()
        var o = 0
        if (f == 2) {
            // trường hợp thường gặp (1280x720 -> 640x360): cộng số nguyên 2x2
            for (oy in 0 until oh) {
                val r0 = base + 2 * oy * rowStride; val r1 = r0 + rowStride
                for (ox in 0 until ow) {
                    val x = 2 * ox
                    val s = (plane.get(r0 + x).toInt() and 0xFF) + (plane.get(r0 + x + 1).toInt() and 0xFF) +
                        (plane.get(r1 + x).toInt() and 0xFF) + (plane.get(r1 + x + 1).toInt() and 0xFF)
                    out[o++] = s * 0.25f
                }
            }
        } else {
            for (oy in 0 until oh) for (ox in 0 until ow) {
                var sum = 0
                for (dy in 0 until f) {
                    val row = base + (oy * f + dy) * rowStride
                    for (dx in 0 until f) sum += plane.get(row + ox * f + dx).toInt() and 0xFF
                }
                out[o++] = sum * inv
            }
        }
        if (rotate180) out.reverse() // xoay 180° = đảo ngược mảng phẳng
        return GrayImage(ow, oh, out)
    }

    fun fromPacket(p: FramePacket): GrayImage = fromPlane(ByteBuffer.wrap(p.y), p.width, p.height, p.yRowStride, p.rotate180)
}
