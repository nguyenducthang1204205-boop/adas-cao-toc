package vn.adas.caotoc.ui.drive

import android.util.Log
import android.util.Size
import androidx.camera.core.Camera
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy
import androidx.camera.core.Preview
import androidx.camera.core.resolutionselector.AspectRatioStrategy
import androidx.camera.core.resolutionselector.ResolutionSelector
import androidx.camera.core.resolutionselector.ResolutionStrategy
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.LocalLifecycleOwner
import java.util.concurrent.Executors

/**
 * Camera sau qua CameraX: Preview (vẽ lên [PreviewView]) + ImageAnalysis YUV_420_888 cùng tỉ lệ 16:9.
 *
 * Phân tích dùng STRATEGY_KEEP_ONLY_LATEST: khi luồng xử lý còn bận, khung mới thay khung cũ ngay tại camera -
 * không bao giờ xếp hàng hay tăng trễ. [lowRes]: 640x480 cho máy yếu (mức Thấp), còn lại 1280x720 - đủ cho ô vào
 * 640 px bề ngang của mô hình. [analyzer] null: chỉ xem trước (màn hình căn chỉnh). [onCamera]: camera vừa mở
 * (đọc thông số ống kính cho căn chỉnh, xem service/CameraIntrinsics.kt).
 */
@Composable
fun CameraPreview(
    modifier: Modifier,
    lowRes: Boolean,
    fit: PreviewView.ScaleType = PreviewView.ScaleType.FILL_CENTER,
    onError: (String) -> Unit = {},
    onCamera: (Camera) -> Unit = {},
    analyzer: ((ImageProxy) -> Unit)?,
) {
    val context = LocalContext.current
    val owner = LocalLifecycleOwner.current
    val view = remember { PreviewView(context).apply { implementationMode = PreviewView.ImplementationMode.COMPATIBLE } }
    view.scaleType = fit
    DisposableEffect(owner, lowRes, analyzer != null) {
        val executor = Executors.newSingleThreadExecutor { r -> Thread(r, "adas-camera") }
        val future = ProcessCameraProvider.getInstance(context)
        var provider: ProcessCameraProvider? = null
        future.addListener({
            try {
                val p = future.get().also { provider = it }
                val target = if (lowRes) Size(640, 480) else Size(1280, 720)
                val selector = ResolutionSelector.Builder()
                    .setAspectRatioStrategy(if (lowRes) AspectRatioStrategy.RATIO_4_3_FALLBACK_AUTO_STRATEGY else AspectRatioStrategy.RATIO_16_9_FALLBACK_AUTO_STRATEGY)
                    .setResolutionStrategy(ResolutionStrategy(target, ResolutionStrategy.FALLBACK_RULE_CLOSEST_HIGHER_THEN_LOWER))
                    .build()
                val preview = Preview.Builder().setResolutionSelector(selector).build().also { it.surfaceProvider = view.surfaceProvider }
                val useCases = mutableListOf<androidx.camera.core.UseCase>(preview)
                if (analyzer != null) {
                    val analysis = ImageAnalysis.Builder()
                        .setResolutionSelector(selector)
                        .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                        .setOutputImageFormat(ImageAnalysis.OUTPUT_IMAGE_FORMAT_YUV_420_888)
                        .build()
                    analysis.setAnalyzer(executor) { img ->
                        try {
                            analyzer(img)
                        } catch (e: Throwable) {
                            Log.e("CameraPreview", "Lỗi xử lý khung", e)
                        } finally {
                            img.close()
                        }
                    }
                    useCases += analysis
                }
                p.unbindAll()
                // màn hình ô tô thường không có camera sau: dùng camera bất kỳ hệ thống khai báo (camera ngoài / AHD)
                val camera = if (p.hasCamera(CameraSelector.DEFAULT_BACK_CAMERA)) CameraSelector.DEFAULT_BACK_CAMERA
                else p.availableCameraInfos.firstOrNull()?.cameraSelector
                    ?: throw IllegalStateException("Máy không có camera. Cắm camera hành trình USB rồi chọn nguồn camera trong Cài đặt.")
                onCamera(p.bindToLifecycle(owner, camera, *useCases.toTypedArray()))
            } catch (e: Exception) {
                Log.e("CameraPreview", "Không mở được camera", e)
                onError(e.message ?: e.javaClass.simpleName)
            }
        }, ContextCompat.getMainExecutor(context))
        onDispose {
            provider?.unbindAll()
            executor.shutdown()
        }
    }
    AndroidView({ view }, modifier)
}
