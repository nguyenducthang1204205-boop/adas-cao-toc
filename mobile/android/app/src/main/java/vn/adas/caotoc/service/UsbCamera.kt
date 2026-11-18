package vn.adas.caotoc.service

import android.content.Context
import android.graphics.SurfaceTexture
import android.hardware.usb.UsbDevice
import android.os.Handler
import android.os.HandlerThread
import android.util.Log
import android.view.Surface
import com.serenegiant.usb.DeviceFilter
import com.serenegiant.usb.IFrameCallback
import com.serenegiant.usb.USBMonitor
import com.serenegiant.usb.UVCCamera
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import vn.adas.caotoc.R
import java.nio.ByteBuffer
import kotlin.math.abs

/** Trạng thái camera hành trình USB cho giao diện. */
data class UsbCamState(
    /** Có camera UVC đang cắm vào máy. */
    val attached: Boolean = false,
    val name: String? = null,
    /** Đang phát hình (khung NV21 [width] x [height]). */
    val streaming: Boolean = false,
    val width: Int = 0,
    val height: Int = 0,
    /** Người dùng bấm "Hủy" ở hộp thoại cấp quyền USB. */
    val denied: Boolean = false,
    val error: String? = null,
) {
    /** Có dùng camera USB không: chọn hẳn "usb", hoặc "auto" và đang có camera cắm vào. */
    fun selected(source: String): Boolean = source == "usb" || (source == "auto" && attached)

    /** Lý do chưa có hình để báo trên màn hình lái; null: bình thường (đang mở hoặc đang phát). */
    fun problem(): String? = when {
        !attached -> "Chưa thấy camera hành trình. Cắm camera USB vào cổng USB của màn hình xe, " +
            "hoặc chọn \"Camera của máy\" trong Cài đặt."
        denied -> "Chưa được phép dùng camera USB. Nhấn Thử lại rồi chọn Cho phép " +
            "(đánh dấu \"Luôn mở\" để lần sau app tự mở khi bật máy xe)."
        else -> error
    }
}

/** Một khung NV21 từ camera USB; [buffer] chỉ hợp lệ trong lúc gọi lại. */
class UsbFrame(val buffer: ByteBuffer, val width: Int, val height: Int)

/**
 * Camera hành trình cắm USB (chuẩn UVC) qua thư viện org.uvccamera (libuvc + libusb, không cần root).
 *
 * Mọi thao tác mở / đóng / đổi bề mặt chạy tuần tự trên một luồng riêng. Thiết bị sống theo Activity
 * ([start] ở onStart, [stop] ở onStop - trả camera cho app ghi hình của hãng khi app không hiển thị); hình chỉ
 * chạy khi có bề mặt xem trước ([attachSurface]). Khung NV21 đến trên luồng thu hình của thư viện: [analyzer]
 * xử lý ngay tại đó (như ImageAnalysis của CameraX); thư viện chỉ giữ khung mới nhất nên xử lý chậm thì khung
 * cũ bị bỏ, không xếp hàng.
 */
class UsbCamera(context: Context) {
    private val app = context.applicationContext
    private val _state = MutableStateFlow(UsbCamState())
    val state: StateFlow<UsbCamState> = _state.asStateFlow()

    private val handler = Handler(HandlerThread("adas-usb").apply { start() }.looper)
    private var monitor: USBMonitor? = null
    private var camera: UVCCamera? = null
    private var texture: SurfaceTexture? = null
    private var surface: Surface? = null
    private var previewing = false
    private var lowRes = false
    @Volatile private var frameW = 0
    @Volatile private var frameH = 0

    /** Nhận từng khung (null: chỉ xem trước). Gán từ luồng giao diện, đọc trên luồng thu hình. */
    @Volatile var analyzer: ((UsbFrame) -> Unit)? = null

    private val frameCallback = IFrameCallback { buf ->
        val a = analyzer ?: return@IFrameCallback
        try {
            a(UsbFrame(buf, frameW, frameH))
        } catch (e: Throwable) {
            Log.e(TAG, "Lỗi xử lý khung", e)
        }
    }

    private val listener = object : USBMonitor.OnDeviceConnectListener {
        override fun onAttach(device: UsbDevice) = post {
            _state.update { it.copy(attached = true, name = nameOf(device)) }
            if (camera == null && !_state.value.denied) monitor?.requestPermission(device)
        }

        override fun onDettach(device: UsbDevice) = post {
            if (camera?.device == device) closeCamera()
            val left = runCatching { monitor?.deviceList?.firstOrNull() }.getOrNull()
            _state.update { UsbCamState(attached = left != null, name = left?.let(::nameOf)) }
        }

        override fun onConnect(device: UsbDevice, ctrl: USBMonitor.UsbControlBlock, createNew: Boolean) = post { open(ctrl) }

        override fun onDisconnect(device: UsbDevice, ctrl: USBMonitor.UsbControlBlock) = post {
            if (camera?.device == device) closeCamera()
        }

        override fun onCancel(device: UsbDevice) = post { _state.update { it.copy(denied = true) } }
    }

    /** Bắt đầu theo dõi cắm / rút camera; camera đang cắm và đã có quyền thì mở ngay. */
    fun start() = post {
        val m = monitor ?: USBMonitor(app, listener).also {
            it.setDeviceFilter(DeviceFilter.getDeviceFilters(app, R.xml.usb_camera))
            monitor = it
        }
        if (!m.isRegistered) m.register()
        // camera có thể đã bị rút trong lúc app ẩn: cập nhật ngay, không chờ lần dò định kỳ của thư viện
        val first = runCatching { m.deviceList.firstOrNull() }.getOrNull()
        _state.update { it.copy(attached = first != null, name = first?.let(::nameOf)) }
    }

    fun stop() = post {
        closeCamera()
        monitor?.let { if (it.isRegistered) it.unregister() }
        _state.update { it.copy(streaming = false) }
    }

    /** Nút "Thử lại": hỏi lại quyền / mở lại camera đang cắm. */
    fun retry() = post {
        _state.update { it.copy(denied = false, error = null) }
        val m = monitor ?: return@post
        if (camera == null) runCatching { m.deviceList.firstOrNull() }.getOrNull()?.let { m.requestPermission(it) }
    }

    /** Mức hiệu năng Thấp: 640 px bề ngang thay vì 1280 (đổi giữa chừng thì phát lại với cỡ mới). */
    fun setLowRes(low: Boolean) = post {
        if (low == lowRes) return@post
        lowRes = low
        val cam = camera ?: return@post
        stopPreview(cam)
        runCatching { configure(cam) }.onFailure { fail("Không đổi được độ phân giải", it) }
        updatePreview()
    }

    /** Bề mặt xem trước (TextureView) sẵn sàng: bắt đầu phát hình. */
    fun attachSurface(t: SurfaceTexture) = post {
        surface?.release()
        texture = t
        surface = Surface(t)
        updatePreview()
    }

    /** Bề mặt bị hủy: dừng phát trước rồi mới giải phóng (TextureView trả false để ta tự giải phóng). */
    fun detachSurface(t: SurfaceTexture) = post {
        if (texture === t) {
            camera?.let(::stopPreview)
            surface?.release()
            surface = null
            texture = null
            _state.update { it.copy(streaming = false) }
        }
        t.release()
    }

    private fun open(ctrl: USBMonitor.UsbControlBlock) {
        closeCamera()
        val cam = try {
            UVCCamera()
        } catch (e: Throwable) { // thư viện gốc chỉ có cho chip ARM (màn hình xe, điện thoại); máy ảo x86 không nạp được
            fail("Máy này không chạy được thư viện camera USB", e)
            return
        }
        try {
            cam.open(ctrl)
            configure(cam)
            cam.setFrameCallback(frameCallback, UVCCamera.PIXEL_FORMAT_NV21)
            camera = cam
            _state.update { it.copy(attached = true, name = nameOf(ctrl.device), denied = false, error = null) }
            updatePreview()
        } catch (e: Exception) {
            runCatching { cam.destroy() }
            fail("Không mở được camera hành trình", e)
        }
    }

    /**
     * Chọn cỡ khung gần 1280 px (máy yếu: 640 px) bề ngang, ưu tiên 16:9; nén MJPEG trước (camera USB 2.0 chỉ
     * đủ băng thông cho 720p/30 khi nén), không được thì YUYV.
     */
    private fun configure(cam: UVCCamera) {
        val target = if (lowRes) 640 else 1280
        val sizes = runCatching { cam.supportedSizeList }.getOrNull().orEmpty()
            .map { it.width to it.height }.distinct()
            .sortedBy { (w, h) -> abs(w - target) + if (w * 9 == h * 16) 0 else 200 }
        for ((w, h) in sizes + listOf(target to target * 9 / 16)) {
            for (format in intArrayOf(UVCCamera.FRAME_FORMAT_MJPEG, UVCCamera.FRAME_FORMAT_YUYV)) {
                try {
                    cam.setPreviewSize(w, h, format)
                    frameW = w
                    frameH = h
                    _state.update { it.copy(width = w, height = h) }
                    return
                } catch (_: IllegalArgumentException) {
                }
            }
        }
        throw IllegalStateException("Camera không hỗ trợ cỡ khung nào phù hợp")
    }

    /** Phát hình khi có camera và bề mặt xem trước; thiếu một trong hai thì dừng. */
    private fun updatePreview() {
        val cam = camera ?: return
        val s = surface
        stopPreview(cam)
        if (s == null) return
        try {
            cam.setPreviewDisplay(s)
            cam.startPreview()
            previewing = true
            _state.update { it.copy(streaming = true, error = null) }
        } catch (e: Exception) {
            fail("Camera hành trình không phát hình", e)
        }
    }

    private fun stopPreview(cam: UVCCamera) {
        if (previewing) runCatching { cam.stopPreview() }
        previewing = false
        _state.update { it.copy(streaming = false) }
    }

    private fun closeCamera() {
        val cam = camera ?: return
        camera = null
        stopPreview(cam)
        runCatching { cam.destroy() } // đóng luôn khối điều khiển USB
    }

    private fun fail(what: String, e: Throwable) {
        Log.e(TAG, what, e)
        _state.update { it.copy(streaming = false, error = "$what: ${e.message ?: e.javaClass.simpleName}") }
    }

    private fun post(block: () -> Unit) {
        handler.post {
            try {
                block()
            } catch (e: Throwable) {
                fail("Lỗi camera USB", e)
            }
        }
    }

    private companion object {
        const val TAG = "UsbCamera"

        fun nameOf(d: UsbDevice): String =
            listOfNotNull(d.manufacturerName, d.productName).joinToString(" ").ifBlank { "Camera USB" }
    }
}
