package vn.adas.caotoc.service

import android.content.Context
import android.media.AudioAttributes
import android.media.SoundPool
import android.speech.tts.TextToSpeech
import android.util.Log
import vn.adas.caotoc.R
import vn.adas.caotoc.core.Risk
import java.util.Locale

/**
 * Âm thanh cảnh báo: bíp lặp theo mức (giống AlertManager desktop) + câu nói tiếng Việt khi nâng mức.
 * Bíp dùng SoundPool (độ trễ thấp), giọng nói dùng TextToSpeech vi-VN nếu máy có.
 */
class AlertPlayer(context: Context) : AutoCloseable {
    private val pool = SoundPool.Builder()
        .setMaxStreams(2)
        .setAudioAttributes(
            AudioAttributes.Builder()
                .setUsage(AudioAttributes.USAGE_ASSISTANCE_NAVIGATION_GUIDANCE)
                .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                .build(),
        )
        .build()
    private val sounds = mapOf(
        Risk.WARNING to pool.load(context, R.raw.warning, 1),
        Risk.DANGER to pool.load(context, R.raw.danger, 1),
    )
    private var tts: TextToSpeech? = null

    @Volatile var voiceAvailable = false
        private set
    private var lastBeep = -1e9
    private var lastVoice = -1e9
    private var prev = Risk.SAFE

    init {
        tts = TextToSpeech(context.applicationContext) { status ->
            val t = tts ?: return@TextToSpeech
            if (status == TextToSpeech.SUCCESS) {
                val r = t.setLanguage(Locale.forLanguageTag("vi-VN"))
                voiceAvailable = r != TextToSpeech.LANG_MISSING_DATA && r != TextToSpeech.LANG_NOT_SUPPORTED
                if (voiceAvailable) t.setSpeechRate(1.1f)
            } else {
                Log.i(TAG, "TTS không khả dụng ($status)")
            }
        }
    }

    /** Gọi mỗi khung với mức cảnh báo ổn định; [now] tính bằng giây. */
    @Synchronized
    fun update(level: Risk, now: Double, sound: Boolean, voice: Boolean) {
        val escalated = level.rank > prev.rank
        prev = level
        if (voice && voiceAvailable && escalated && now - lastVoice >= VOICE_COOLDOWN_S) {
            lastVoice = now
            PHRASES[level]?.let { tts?.speak(it, TextToSpeech.QUEUE_FLUSH, null, "adas-alert") }
            lastBeep = now // nhường chỗ cho câu nói
            return
        }
        val interval = INTERVALS[level] ?: return
        if (!sound || now - lastBeep < interval) return
        lastBeep = now
        play(level)
    }

    fun preview(level: Risk) = play(level)

    private fun play(level: Risk) {
        sounds[level]?.let { pool.play(it, 1f, 1f, 1, 0, 1f) }
    }

    override fun close() {
        pool.release()
        tts?.shutdown()
        tts = null
    }

    private companion object {
        const val TAG = "AlertPlayer"
        val INTERVALS = mapOf(Risk.DANGER to 0.28, Risk.WARNING to 0.9)
        val PHRASES = mapOf(Risk.WARNING to "Giữ khoảng cách", Risk.DANGER to "Nguy hiểm, giảm tốc ngay")
        const val VOICE_COOLDOWN_S = 5.0
    }
}
