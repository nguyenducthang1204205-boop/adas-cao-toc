package vn.adas.caotoc.engine

import vn.adas.caotoc.core.GrayImage
import vn.adas.caotoc.detector.FramePacket
import vn.adas.caotoc.detector.Gray
import java.nio.ByteBuffer

/**
 * Khung NV21 (camera hành trình USB, service/UsbCamera.kt): Y đủ độ phân giải, sau đó V,U xen kẽ ở nửa độ phân giải.
 * Đọc như YUV_420_888 của CameraX với bước điểm ảnh UV = 2: mặt phẳng V bắt đầu ngay sau Y, U lệch thêm 1 byte -
 * nên bộ tiền xử lý và ảnh xám dùng lại nguyên vẹn. [buf] chỉ hợp lệ trong lúc gọi lại của camera.
 */
class Nv21Frame(
    private val buf: ByteBuffer,
    override val width: Int,
    override val height: Int,
    private val rot180: Boolean,
    private val reuse: () -> FramePacket?,
) : FrameInput {
    override fun gray(): GrayImage = Gray.fromPlane(slice(0, width * height), width, height, width, rot180)

    override fun packet(): FramePacket {
        val n = width * height
        val end = size(width, height)
        return FramePacket.copyOf(width, height, slice(0, n), width, slice(n + 1, end), slice(n, end - 1),
            2 * ((width + 1) / 2), 2, rot180, reuse())
    }

    private fun slice(from: Int, to: Int): ByteBuffer =
        buf.duplicate().apply { clear(); position(from); limit(to) }.slice()

    companion object {
        /** Số byte của một khung NV21 [w] x [h]. */
        fun size(w: Int, h: Int) = w * h + 2 * ((w + 1) / 2) * ((h + 1) / 2)
    }
}
