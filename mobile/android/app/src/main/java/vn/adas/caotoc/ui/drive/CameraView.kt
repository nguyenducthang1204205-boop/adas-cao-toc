package vn.adas.caotoc.ui.drive

import android.content.Context
import android.graphics.Matrix
import android.graphics.SurfaceTexture
import android.view.TextureView
import androidx.camera.core.Camera
import androidx.camera.core.ImageProxy
import androidx.camera.view.PreviewView
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.viewinterop.AndroidView
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import vn.adas.caotoc.service.UsbCamera
import vn.adas.caotoc.service.UsbFrame
import kotlin.math.max
import kotlin.math.min

/**
 * Nguồn hình của app: camera hành trình USB khi [usb] khác null (màn hình Android ô tô), không thì camera của máy
 * qua CameraX. [contain]: hiện trọn khung (màn hình căn chỉnh), không thì tràn viền như overlay (CoverTransform).
 * [rotate180] chỉ áp cho camera USB: cài đặt "Xoay ảnh 180°" xoay cả hình xem trước lẫn khung phân tích.
 */
@Composable
fun CameraView(
    modifier: Modifier,
    usb: UsbCamera?,
    lowRes: Boolean,
    rotate180: Boolean,
    contain: Boolean = false,
    onError: (String) -> Unit = {},
    onCamera: (Camera) -> Unit = {},
    onImage: ((ImageProxy) -> Unit)? = null,
    onUsbFrame: ((UsbFrame) -> Unit)? = null,
) {
    if (usb != null) {
        UsbCameraPreview(modifier, usb, lowRes, rotate180, contain, onUsbFrame)
    } else {
        CameraPreview(modifier, lowRes, if (contain) PreviewView.ScaleType.FIT_CENTER else PreviewView.ScaleType.FILL_CENTER,
            onError, onCamera, onImage)
    }
}

/** Hình từ camera USB vẽ lên TextureView; [analyzer] nhận khung NV21 trên luồng thu hình của thư viện. */
@Composable
private fun UsbCameraPreview(
    modifier: Modifier, usb: UsbCamera, lowRes: Boolean, rotate180: Boolean, contain: Boolean, analyzer: ((UsbFrame) -> Unit)?,
) {
    val context = LocalContext.current
    val st by usb.state.collectAsStateWithLifecycle()
    val view = remember { FitTextureView(context, usb) }
    LaunchedEffect(lowRes) { usb.setLowRes(lowRes) }
    DisposableEffect(analyzer) {
        usb.analyzer = analyzer
        onDispose { if (usb.analyzer == analyzer) usb.analyzer = null }
    }
    AndroidView({ view }, modifier, update = { it.fit(st.width, st.height, contain, rotate180) })
}

/**
 * TextureView kéo giãn hình cho vừa khung nhìn; ma trận biến đổi trả lại đúng tỉ lệ ảnh - tràn viền (giống
 * FILL_CENTER của CameraX, khớp CoverTransform của overlay) hoặc hiện trọn khung.
 */
private class FitTextureView(context: Context, private val usb: UsbCamera) : TextureView(context) {
    private var imgW = 0
    private var imgH = 0
    private var contain = false
    private var rot = false

    init {
        surfaceTextureListener = object : SurfaceTextureListener {
            override fun onSurfaceTextureAvailable(t: SurfaceTexture, w: Int, h: Int) = usb.attachSurface(t)
            override fun onSurfaceTextureSizeChanged(t: SurfaceTexture, w: Int, h: Int) = applyTransform()
            override fun onSurfaceTextureDestroyed(t: SurfaceTexture): Boolean {
                usb.detachSurface(t) // dừng phát rồi tự giải phóng trên luồng camera
                return false
            }
            override fun onSurfaceTextureUpdated(t: SurfaceTexture) {}
        }
    }

    fun fit(w: Int, h: Int, contain: Boolean, rotate180: Boolean) {
        imgW = w; imgH = h; this.contain = contain; rot = rotate180
        applyTransform()
    }

    override fun onSizeChanged(w: Int, h: Int, oldw: Int, oldh: Int) {
        super.onSizeChanged(w, h, oldw, oldh)
        applyTransform()
    }

    private fun applyTransform() {
        val vw = width.toFloat(); val vh = height.toFloat()
        if (vw <= 0 || vh <= 0 || imgW <= 0 || imgH <= 0) return
        val s = if (contain) min(vw / imgW, vh / imgH) else max(vw / imgW, vh / imgH)
        setTransform(Matrix().apply {
            setScale(imgW * s / vw, imgH * s / vh, vw / 2, vh / 2)
            if (rot) postRotate(180f, vw / 2, vh / 2)
        })
    }
}
