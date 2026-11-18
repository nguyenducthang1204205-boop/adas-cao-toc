// Plugin khai báo ở gốc, áp dụng trong từng module. AGP 9 tự biên dịch Kotlin (built-in Kotlin);
// kotlin-android chỉ được đặt lên classpath để chọn phiên bản Kotlin, không áp dụng.
plugins {
    alias(libs.plugins.android.application) apply false
    alias(libs.plugins.kotlin.android) apply false
    alias(libs.plugins.kotlin.compose) apply false
}

// Đường dẫn dự án có dấu ("Đồ án"): java.exe đọc classpath / @argfile theo bảng mã ANSI của Windows nên làm
// hỏng chữ "Đ" -> JVM chạy unit test không tìm thấy lớp. Khi đó đặt thư mục build sang đường dẫn ASCII.
val asciiBuildRoot = System.getenv("LOCALAPPDATA")?.let { file("$it/adas_android_build") }
if (asciiBuildRoot != null && rootDir.absolutePath.any { it.code > 127 }) {
    allprojects { layout.buildDirectory.set(asciiBuildRoot.resolve(path.trim(':').ifEmpty { "root" })) }
}
