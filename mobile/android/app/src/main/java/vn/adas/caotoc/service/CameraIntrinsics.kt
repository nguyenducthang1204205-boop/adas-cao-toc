package vn.adas.caotoc.service

import android.hardware.camera2.CameraCharacteristics
import android.util.Log
import androidx.camera.camera2.interop.Camera2CameraInfo
import androidx.camera.camera2.interop.ExperimentalCamera2Interop
import androidx.camera.core.Camera
import kotlin.math.max

/**
 * Tiêu cự của ống kính theo pixel của mảng cảm biến ([fPx], mảng [arrayW] x [arrayH]), đọc từ thông số Camera2
 * để người dùng không phải căn chỉnh tiêu cự. Ảnh phân tích là mảng cảm biến thu nhỏ (và cắt theo tỉ lệ 16:9 /
 * 4:3 nhưng giữ trọn chiều còn lại) nên tỉ lệ thu nhỏ là max(rộng ảnh / rộng mảng, cao ảnh / cao mảng).
 */
data class LensFocal(val fPx: Double, val arrayW: Int, val arrayH: Int, val source: String) {
    /** Tiêu cự / chiều rộng ảnh phân tích (CameraPose.focalW). */
    fun focalW(imageW: Double, imageH: Double): Double = fPx * max(imageW / arrayW, imageH / arrayH) / imageW

    companion object {
        /**
         * Ưu tiên LENS_INTRINSIC_CALIBRATION (nhà sản xuất hiệu chỉnh, theo mảng trước hiệu chỉnh méo); không có thì
         * tiêu cự danh định (mm) x số điểm ảnh / bề rộng vật lý của cảm biến. null nếu máy không khai báo.
         */
        @androidx.annotation.OptIn(ExperimentalCamera2Interop::class)
        fun of(camera: Camera): LensFocal? = runCatching {
            val info = Camera2CameraInfo.from(camera.cameraInfo)
            val intr = info.getCameraCharacteristic(CameraCharacteristics.LENS_INTRINSIC_CALIBRATION)
            val pre = info.getCameraCharacteristic(CameraCharacteristics.SENSOR_INFO_PRE_CORRECTION_ACTIVE_ARRAY_SIZE)
            if (intr != null && intr.size >= 2 && intr[0] > 0 && pre != null && pre.width() > 0) {
                return@runCatching LensFocal(intr[0].toDouble(), pre.width(), pre.height(), "intrinsic")
            }
            val mm = info.getCameraCharacteristic(CameraCharacteristics.LENS_INFO_AVAILABLE_FOCAL_LENGTHS)?.firstOrNull()
            val phys = info.getCameraCharacteristic(CameraCharacteristics.SENSOR_INFO_PHYSICAL_SIZE)
            val pixels = info.getCameraCharacteristic(CameraCharacteristics.SENSOR_INFO_PIXEL_ARRAY_SIZE)
            val active = info.getCameraCharacteristic(CameraCharacteristics.SENSOR_INFO_ACTIVE_ARRAY_SIZE)
            if (mm == null || mm <= 0 || phys == null || phys.width <= 0 || pixels == null || active == null) return@runCatching null
            LensFocal(mm * pixels.width / phys.width.toDouble(), active.width(), active.height(), "focal_length")
        }.onFailure { Log.w("LensFocal", "Không đọc được thông số ống kính", it) }.getOrNull()
    }
}
