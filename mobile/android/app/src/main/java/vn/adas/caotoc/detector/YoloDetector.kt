package vn.adas.caotoc.detector

import android.content.Context
import android.os.SystemClock
import android.util.Log
import org.json.JSONObject
import org.tensorflow.lite.Interpreter
import org.tensorflow.lite.gpu.CompatibilityList
import org.tensorflow.lite.gpu.GpuDelegate
import vn.adas.caotoc.core.CropRect
import vn.adas.caotoc.core.Detection
import vn.adas.caotoc.core.decodeYolo
import java.io.FileInputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.MappedByteBuffer
import java.nio.channels.FileChannel
import kotlin.math.roundToInt

/** Mô tả mô hình (assets/models/model_meta_288x640.json, sinh bởi tools/export_mobile.py). */
data class ModelMeta(val inW: Int, val inH: Int, val classes: List<String>, val files: Map<String, String>) {
    companion object {
        fun load(context: Context, asset: String): ModelMeta {
            val j = JSONObject(context.assets.open(asset).bufferedReader().use { it.readText() })
            val inp = j.getJSONObject("input")
            val cls = j.getJSONArray("classes").let { a -> List(a.length()) { a.getString(it) } }
            val files = j.getJSONObject("files").let { f -> f.keys().asSequence().associateWith { f.getString(it) } }
            return ModelMeta(inp.getInt("width"), inp.getInt("height"), cls, files)
        }
    }
}

/** Kết quả một lần nhận diện; hộp đã ở pixel khung gốc (đã cộng gốc vùng cắt). */
class DetectResult(
    val detections: List<Detection>,
    val imageW: Int,
    val imageH: Int,
    val prepMs: Double,
    val inferMs: Double,
    /** Thời điểm chụp khung (đồng hồ của luồng xử lý, giây). */
    val tag: Double,
    val crop: CropRect,
    val narrow: Boolean,
)

/**
 * Bộ nhận diện YOLOv11 trên LiteRT (TensorFlow Lite): tiền xử lý (cắt vùng đường) -> suy luận -> giải mã + NMS.
 *
 * Lúc khởi động đo thật trên máy và giữ bộ nhanh nhất: GPU (FP16, nếu máy hỗ trợ) hoặc CPU XNNPACK
 * (INT8 dynamic-range) với 1 / 2 / 4 luồng - chip big.LITTLE (vd. Helio G96: 2 nhân mạnh + 6 nhân yếu)
 * thường chậm đi khi quá nhiều luồng vì phải chờ luồng rơi vào nhân yếu. Không an toàn đa luồng: chỉ gọi
 * [detect] từ một luồng (luồng YOLO của FrameEngine).
 */
class YoloDetector private constructor(
    val meta: ModelMeta,
    private val interpreter: Interpreter,
    private val gpu: GpuDelegate?,
    /** Mô tả bộ suy luận đang dùng, hiển thị trên HUD. */
    val backend: String,
    /** Thời gian suy luận đo lúc khởi động (bộ đã chọn, ms). */
    val benchMs: Double,
) : AutoCloseable {
    private val numAnchors = interpreter.getOutputTensor(0).shape().last()
    private val outBuf: ByteBuffer =
        ByteBuffer.allocateDirect(interpreter.getOutputTensor(0).numBytes()).order(ByteOrder.nativeOrder())
    private val out = FloatArray(outBuf.capacity() / 4)
    private val pre = Preprocessor(meta.inW, meta.inH)

    fun detect(
        frame: FramePacket, crop: CropRect, narrow: Boolean, conf: Double, iou: Double,
        enabled: Set<String>, tag: Double,
    ): DetectResult {
        val t0 = SystemClock.elapsedRealtimeNanos()
        val input = pre.run(frame, crop)
        val t1 = SystemClock.elapsedRealtimeNanos()
        outBuf.rewind()
        interpreter.run(input, outBuf)
        outBuf.rewind()
        outBuf.asFloatBuffer().get(out)
        val t2 = SystemClock.elapsedRealtimeNanos()
        val dets = decodeYolo(out, numAnchors, meta.classes, pre.letterbox!!, conf, iou, enabledClasses = enabled)
        return DetectResult(toFrame(dets, crop, frame.width, frame.height, narrow), frame.width, frame.height,
            (t1 - t0) / 1e6, (t2 - t1) / 1e6, tag, crop, narrow)
    }

    override fun close() {
        interpreter.close()
        gpu?.close()
    }

    companion object {
        private const val TAG = "YoloDetector"

        /**
         * Ô vào 288x640: đúng tỉ lệ dải đường cắt từ khung 16:9 (core/Roi.kt); mAP như 384x640 cả khung,
         * ít hơn 25 % tính toán (tools/eval_mobile.py, docs/ket_qua_mobile.json).
         */
        const val META_ASSET = "models/model_meta_288x640.json"

        /** Chạy vài giây trên máy yếu (đo GPU + 3 cấu hình CPU): gọi ở luồng nền. */
        fun create(context: Context, preferGpu: Boolean): YoloDetector {
            val meta = ModelMeta.load(context, META_ASSET)
            val gpuModel = map(context, "models/" + meta.files.getValue("fp16"))
            val cpuModel = map(context, "models/" + meta.files.getValue("int8"))
            val dummy = ByteBuffer.allocateDirect(meta.inW * meta.inH * 3 * 4).order(ByteOrder.nativeOrder())
            val errors = ArrayList<String>()

            fun bench(interp: Interpreter): Double {
                val o = ByteBuffer.allocateDirect(interp.getOutputTensor(0).numBytes()).order(ByteOrder.nativeOrder())
                val times = DoubleArray(4) {
                    dummy.rewind(); o.rewind()
                    val t = SystemClock.elapsedRealtimeNanos()
                    interp.run(dummy, o)
                    (SystemClock.elapsedRealtimeNanos() - t) / 1e6
                }
                times.sort()
                return times[1] // bỏ lần đầu (khởi động), lấy gần trung vị
            }

            var gpuDelegate: GpuDelegate? = null
            var gpuIt: Interpreter? = null
            if (preferGpu) {
                try {
                    val compat = CompatibilityList()
                    if (compat.isDelegateSupportedOnThisDevice) {
                        gpuDelegate = GpuDelegate(compat.bestOptionsForThisDevice)
                        gpuIt = Interpreter(gpuModel, Interpreter.Options().addDelegate(gpuDelegate))
                    } else {
                        errors += "GPU: máy không hỗ trợ"
                    }
                } catch (e: Throwable) {
                    errors += "GPU: ${e.message}"
                    gpuIt?.close(); gpuIt = null
                    gpuDelegate?.close(); gpuDelegate = null
                }
            }

            var cpuIt: Interpreter? = null
            var cpuMs = Double.POSITIVE_INFINITY
            var cpuName = ""
            val cores = Runtime.getRuntime().availableProcessors()
            for (n in if (cores <= 2) listOf(1, 2) else listOf(1, 2, 4)) {
                try {
                    val it = Interpreter(cpuModel, Interpreter.Options().setNumThreads(n).setUseXNNPACK(true))
                    val ms = bench(it)
                    if (ms < cpuMs) {
                        cpuIt?.close()
                        cpuIt = it; cpuMs = ms; cpuName = "CPU XNNPACK · INT8 · $n luồng"
                    } else {
                        it.close()
                    }
                } catch (e: Throwable) {
                    errors += "CPU $n luồng: ${e.message}"
                }
            }
            check(gpuIt != null || cpuIt != null) { "Không tạo được bộ suy luận TFLite: ${errors.joinToString("; ")}" }
            if (errors.isNotEmpty()) Log.i(TAG, errors.joinToString("; "))

            // GPU delegate có thể chỉ nhận một phần mô hình (phép không hỗ trợ chạy lại trên CPU) và khi đó
            // chậm hơn CPU INT8 -> đo thực tế trên máy, giữ bộ nhanh hơn.
            if (gpuIt != null) {
                val tg = bench(gpuIt)
                if (cpuIt == null || tg <= cpuMs) {
                    cpuIt?.close()
                    val name = if (cpuIt == null) "GPU · FP16" else "GPU · FP16 (${tg.roundToInt()} ms; CPU ${cpuMs.roundToInt()} ms)"
                    return YoloDetector(meta, gpuIt, gpuDelegate, name, tg)
                }
                gpuIt.close(); gpuDelegate?.close()
                return YoloDetector(meta, cpuIt, null, "$cpuName (${cpuMs.roundToInt()} ms; GPU ${tg.roundToInt()} ms)", cpuMs)
            }
            return YoloDetector(meta, cpuIt!!, null, cpuName, cpuMs)
        }

        private fun map(context: Context, asset: String): MappedByteBuffer =
            context.assets.openFd(asset).use { fd ->
                FileInputStream(fd.fileDescriptor).channel.use {
                    it.map(FileChannel.MapMode.READ_ONLY, fd.startOffset, fd.declaredLength)
                }
            }

        /**
         * Hộp trong vùng cắt -> khung gốc. Vùng hẹp: bỏ hộp chạm mép trong của vùng (xe bị cắt dở, kích thước
         * sai) - các xe đó đã có ở khung khóa rộng.
         */
        private fun toFrame(dets: List<Detection>, c: CropRect, frameW: Int, frameH: Int, narrow: Boolean): List<Detection> {
            if (c.x == 0 && c.y == 0 && !narrow) return dets
            val edge = 3.0
            return dets.filterNot { d ->
                narrow && ((d.x1 <= edge && c.x > 0) || (d.y1 <= edge && c.y > 0) ||
                    (d.x2 >= c.w - edge && c.x + c.w < frameW) || (d.y2 >= c.h - edge && c.y + c.h < frameH))
            }.map { d -> Detection(d.x1 + c.x, d.y1 + c.y, d.x2 + c.x, d.y2 + c.y, d.confidence, d.classId, d.className) }
        }
    }
}
