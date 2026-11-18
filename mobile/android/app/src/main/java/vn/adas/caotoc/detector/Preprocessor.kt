package vn.adas.caotoc.detector

import vn.adas.caotoc.core.CropRect
import vn.adas.caotoc.core.Letterbox
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.FloatBuffer
import kotlin.math.floor

/**
 * Ảnh YUV420 -> tensor RGB 0..1 letterbox NHWC (float32) cho mô hình TFLite.
 *
 * Lấy mẫu láng giềng gần nhất qua bảng tra chỉ số dựng sẵn (không tạo ảnh RGB trung gian), vừa cắt vùng
 * (xem core/Roi.kt), vừa đổi màu, vừa thu nhỏ trong một vòng lặp. Đổi màu bằng số nguyên (hệ số x1024)
 * và bảng tra 0..255 -> 0..1 thay cho phép tính số thực từng điểm ảnh.
 */
class Preprocessor(val inW: Int, val inH: Int) {
    /** Bộ đệm vào của interpreter (direct, thứ tự byte của máy). */
    val input: ByteBuffer = ByteBuffer.allocateDirect(inW * inH * 3 * 4).order(ByteOrder.nativeOrder())
    private val floats: FloatBuffer = input.asFloatBuffer()
    private val row = FloatArray(inW * 3)

    /** Letterbox của vùng cắt: hộp giải mã ra ở tọa độ vùng cắt, cộng crop.x / crop.y để về khung gốc. */
    var letterbox: Letterbox? = null
        private set
    private var xmap = IntArray(0)
    private var ymap = IntArray(0)
    private var key: List<Any>? = null

    private fun prepare(w: Int, h: Int, rot: Boolean, c: CropRect) {
        val k = listOf(w, h, rot, c)
        if (k == key) return
        val lb = Letterbox.of(c.w, c.h, inW, inH)
        val padChanged = letterbox?.let { it.newW != lb.newW || it.newH != lb.newH } ?: true
        letterbox = lb
        key = k
        // cột/hàng nguồn cho từng cột/hàng đích (tâm pixel); vùng cắt tính trên ảnh đã xoay đứng, xoay 180°
        // thì lật chỉ số về bộ đệm cảm biến
        xmap = IntArray(lb.newW) { x ->
            val sx = (c.x + floor((x + 0.5) / lb.r).toInt()).coerceIn(c.x, c.x + c.w - 1).coerceIn(0, w - 1)
            if (rot) w - 1 - sx else sx
        }
        ymap = IntArray(lb.newH) { y ->
            val sy = (c.y + floor((y + 0.5) / lb.r).toInt()).coerceIn(c.y, c.y + c.h - 1).coerceIn(0, h - 1)
            if (rot) h - 1 - sy else sy
        }
        if (padChanged) {
            floats.clear()
            val pad = 114f / 255f // nền xám như Ultralytics
            for (i in 0 until inW * inH * 3) floats.put(pad)
        }
    }

    /** [crop] null = cả khung. Trả về [input] đã sẵn sàng cho interpreter. */
    fun run(f: FramePacket, crop: CropRect? = null): ByteBuffer {
        prepare(f.width, f.height, f.rotate180, crop ?: CropRect(0, 0, f.width, f.height))
        val lb = letterbox!!
        val yp = f.y; val up = f.u; val vp = f.v
        for (y in 0 until lb.newH) {
            val sy = ymap[y]
            val yr = sy * f.yRowStride
            val uvr = (sy shr 1) * f.uvRowStride
            var o = 0
            for (x in 0 until lb.newW) {
                val sx = xmap[x]
                val yy = yp[yr + sx].toInt() and 0xFF
                val uvi = uvr + (sx shr 1) * f.uvPixelStride
                val u = (up[uvi].toInt() and 0xFF) - 128
                val v = (vp[uvi].toInt() and 0xFF) - 128
                // BT.601 toàn dải: R = Y + 1,402 V; G = Y - 0,344 U - 0,714 V; B = Y + 1,772 U
                val r = (yy + ((1436 * v) shr 10)).coerceIn(0, 255)
                val g = (yy - ((352 * u + 731 * v) shr 10)).coerceIn(0, 255)
                val b = (yy + ((1815 * u) shr 10)).coerceIn(0, 255)
                row[o++] = UNIT[r]; row[o++] = UNIT[g]; row[o++] = UNIT[b]
            }
            floats.position(((y + lb.top) * inW + lb.left) * 3)
            floats.put(row, 0, lb.newW * 3)
        }
        input.rewind()
        return input
    }

    companion object {
        /** 0..255 -> 0..1 (khớp phép chia /255 của bản Python). */
        private val UNIT = FloatArray(256) { it / 255f }
    }
}
