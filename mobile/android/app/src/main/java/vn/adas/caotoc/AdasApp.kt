package vn.adas.caotoc

import android.app.Application
import vn.adas.caotoc.data.SettingsStore
import vn.adas.caotoc.data.ViolationLog
import vn.adas.caotoc.service.UsbCamera

/** Đối tượng sống suốt tiến trình: kho cài đặt, nhật ký vi phạm, camera hành trình USB (dùng chung cho mọi màn hình). */
class AdasApp : Application() {
    lateinit var settings: SettingsStore
        private set
    lateinit var violations: ViolationLog
        private set
    val usbCamera: UsbCamera by lazy { UsbCamera(this) }

    override fun onCreate() {
        super.onCreate()
        settings = SettingsStore(this)
        violations = ViolationLog(this)
    }
}
