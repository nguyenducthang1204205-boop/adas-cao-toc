# Plugin gọi mã Kotlin qua JNI (package:jni): R8 không thấy lời gọi nên xóa/đổi tên hàm,
# ví dụ shared_preferences báo NoSuchMethodError ...SharedPreferencesApiRegistrar.getAll ở bản release.
-keep class io.flutter.plugins.** { *; }
-keep class com.github.dart_lang.jni.** { *; }
# TFLite GPU delegate (tflite_flutter nạp qua FFI)
-keep class org.tensorflow.lite.** { *; }
-dontwarn org.tensorflow.lite.**
# Chữ ký hàm JNI chứa kiểu Kotlin (vd. kotlin.coroutines.Continuation ở hàm suspend): R8 đổi tên
# Continuation -> "in" nên JNI không tìm thấy hàm. Giữ nguyên tên lớp thư viện chuẩn Kotlin.
-keep class kotlin.** { *; }
-keep class kotlinx.coroutines.** { *; }
