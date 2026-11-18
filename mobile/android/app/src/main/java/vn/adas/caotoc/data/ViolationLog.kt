package vn.adas.caotoc.data

import android.content.Context
import android.util.Log
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import org.json.JSONArray
import org.json.JSONObject
import vn.adas.caotoc.core.Violation
import vn.adas.caotoc.core.ViolationAction
import vn.adas.caotoc.core.ViolationEvent
import vn.adas.caotoc.core.ViolationRecorder

/**
 * Nhật ký vi phạm trên điện thoại (SharedPreferences, một chuỗi JSON), tương ứng bảng `violations` +
 * `monitoring_sessions` trong CSDL của bản desktop. Chỉ ghi khi mở / nâng mức / đóng đợt.
 */
class ViolationLog(context: Context) {
    /** Ảnh chụp trạng thái cho giao diện ([revision] tăng mỗi lần đổi để Compose vẽ lại). */
    data class Snapshot(val items: List<Violation>, val sessionId: Int, val revision: Int) {
        val sessionCount: Int get() = items.count { it.sessionId == sessionId }
    }

    private val prefs = context.getSharedPreferences("adas", Context.MODE_PRIVATE)
    private val items = ArrayList<Violation>() // mới nhất trước
    private var lastId = 0
    private var lastSession = 0
    private var sessionId = 0
    private val state = MutableStateFlow(Snapshot(emptyList(), 0, 0))
    val snapshot: StateFlow<Snapshot> = state.asStateFlow()

    init {
        load()
    }

    @Synchronized
    fun startSession(): ViolationRecorder {
        sessionId = ++lastSession
        save()
        publish()
        return ViolationRecorder(sessionId, nextId = { synchronized(this) { ++lastId } })
    }

    /** Nhận sự kiện từ ViolationRecorder.update / close. */
    @Synchronized
    fun apply(events: List<ViolationEvent>) {
        if (events.isEmpty()) return
        for (e in events) {
            if (e.action == ViolationAction.OPEN) {
                items.add(0, e.violation)
                while (items.size > MAX_ITEMS) items.removeAt(items.size - 1)
            }
        }
        save()
        publish()
    }

    /** Khoảng cách nhỏ nhất của đợt đang mở thay đổi theo khung: chỉ vẽ lại, không ghi. */
    @Synchronized
    fun touch() = publish()

    @Synchronized
    fun clear() {
        items.clear()
        save()
        publish()
    }

    private fun publish() {
        state.value = Snapshot(items.toList(), sessionId, state.value.revision + 1)
    }

    private fun load() {
        try {
            val s = prefs.getString(KEY, null) ?: return
            val j = JSONObject(s)
            lastId = j.optInt("last_id", 0)
            lastSession = j.optInt("last_session", 0)
            val a = j.optJSONArray("items") ?: JSONArray()
            items.clear()
            for (i in 0 until a.length()) items += Violation.fromJson(a.getJSONObject(i))
            publish()
        } catch (e: Exception) {
            Log.w(TAG, "Không đọc được nhật ký vi phạm", e)
        }
    }

    private fun save() {
        val j = JSONObject()
            .put("last_id", lastId)
            .put("last_session", lastSession)
            .put("items", JSONArray(items.map { it.toJson() }))
        prefs.edit().putString(KEY, j.toString()).apply()
    }

    private companion object {
        const val KEY = "adas_violations_v2"
        const val MAX_ITEMS = 500 // giữ các đợt gần nhất
        const val TAG = "ViolationLog"
    }
}
