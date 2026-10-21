package com.attention.app

import android.content.Context
import android.content.SharedPreferences
import androidx.compose.runtime.mutableIntStateOf

enum class FocusMode(val id: String, val emoji: String, val title: String, val proof: String) {
    STUDY(
        "study", "📚", "Ders",
        "Ders/sınav çalışması: açık ders kitabı veya slaytlar, el yazısıyla yeni alınmış notlar, " +
            "çözülmüş sorular, çalışma masası. Notların/yazının gerçekten çalışılırken çekildiği belli olmalı."
    ),
    CODE(
        "code", "💻", "Kod",
        "Kod yazmak: bilgisayar ekranında açık bir kod editörü/IDE ve üzerinde çalışılan gerçek kod. " +
            "Bu modda bilgisayar ekranının fotoğrafı kabul edilir ama ekranda kod/terminal görünmeli; " +
            "video, oyun, sosyal medya veya boş masaüstü kabul edilmez."
    ),
    GYM(
        "gym", "🏋️", "Gym",
        "Spor/antrenman: spor salonu ortamı, ağırlıklar, makineler, koşu bandı, egzersiz yapan kişi " +
            "veya antrenman sırasında çekildiği belli olan bir kare."
    ),
    CUSTOM("custom", "🎯", "Özel", "");

    companion object {
        fun byId(id: String?): FocusMode = entries.firstOrNull { it.id == id } ?: STUDY
    }
}

/**
 * Uygulamanın tüm kalıcı durumu. Hem arayüz hem de engelleme servisi aynı örneği kullanır;
 * [rev] her yazmada artar, böylece Compose ekranları değişikliği hemen görür.
 */
class Store private constructor(context: Context) {
    private val p: SharedPreferences = context.getSharedPreferences("attention", Context.MODE_PRIVATE)
    private val rev = mutableIntStateOf(0)

    /** Composable içinde çağrılırsa, durum değiştiğinde ekran yeniden çizilir. */
    fun watch(): Int = rev.intValue

    private fun edit(block: SharedPreferences.Editor.() -> Unit) {
        val e = p.edit()
        e.block()
        e.apply()
        rev.intValue++
    }

    var apiKey: String
        get() = p.getString("api_key", "") ?: ""
        set(v) = edit { putString("api_key", v.trim()) }

    var visionModel: String
        get() = p.getString("vision_model", null) ?: DEFAULT_VISION_MODEL
        set(v) = edit { putString("vision_model", v.trim().ifEmpty { DEFAULT_VISION_MODEL }) }

    var textModel: String
        get() = p.getString("text_model", null) ?: DEFAULT_TEXT_MODEL
        set(v) = edit { putString("text_model", v.trim().ifEmpty { DEFAULT_TEXT_MODEL }) }

    var blocked: Set<String>
        get() = p.getStringSet("blocked", null)?.toSet() ?: emptySet()
        set(v) = edit { putStringSet("blocked", v.toSet()) }

    var blockingEnabled: Boolean
        get() = p.getBoolean("enabled", true)
        set(v) = edit { putBoolean("enabled", v) }

    var focusId: String
        get() = p.getString("focus", FocusMode.STUDY.id) ?: FocusMode.STUDY.id
        set(v) = edit { putString("focus", v) }

    var customFocus: String
        get() = p.getString("custom_focus", "") ?: ""
        set(v) = edit { putString("custom_focus", v) }

    /** Onaylanan fotoğraf kanıtı başına kazanılan mola (dk). */
    var rewardMinutes: Int
        get() = p.getInt("reward_min", 15)
        set(v) = edit { putInt("reward_min", v.coerceIn(5, 60)) }

    /** İki fotoğraf kanıtı arasında beklenmesi gereken süre (dk). */
    var cooldownMinutes: Int
        get() = p.getInt("cooldown_min", 45)
        set(v) = edit { putInt("cooldown_min", v.coerceIn(15, 180)) }

    val unlockUntil: Long get() = p.getLong("unlock_until", 0)
    val sessionEnd: Long get() = p.getLong("session_end", 0)
    val sessionLength: Int get() = p.getInt("session_len", 0)
    val lastProofAt: Long get() = p.getLong("last_proof", 0)

    val approvedCount: Int get() = p.getInt("stat_approved", 0)
    val rejectedCount: Int get() = p.getInt("stat_rejected", 0)
    val sessionsDone: Int get() = p.getInt("stat_sessions", 0)
    val focusMinutes: Int get() = p.getInt("stat_focus_min", 0)
    val blockCount: Int get() = p.getInt("stat_blocks", 0)

    val focus: FocusMode get() = FocusMode.byId(focusId)

    fun focusLabel(): String =
        if (focus == FocusMode.CUSTOM && customFocus.isNotBlank()) customFocus.trim() else focus.title

    fun isSessionActive(now: Long) = sessionEnd > now
    fun isOnBreak(now: Long) = unlockUntil > now && !isSessionActive(now)
    fun nextProofAt(): Long = if (lastProofAt == 0L) 0 else lastProofAt + cooldownMinutes * 60_000L

    fun shouldBlock(pkg: String, now: Long): Boolean =
        blockingEnabled && pkg in blocked && (isSessionActive(now) || unlockUntil <= now)

    fun startSession(minutes: Int, now: Long) = edit {
        putLong("session_end", now + minutes * 60_000L)
        putInt("session_len", minutes)
    }

    fun cancelSession() = edit { putLong("session_end", 0) }

    /** Odak oturumu bittiyse ödülü verir. Ödül verildiyse kazanılan dakikayı döner. */
    fun completeSessionIfDone(now: Long): Int? {
        val end = sessionEnd
        if (end == 0L || end > now) return null
        val reward = sessionReward(sessionLength)
        val len = sessionLength
        edit {
            putLong("session_end", 0)
            putInt("stat_sessions", sessionsDone + 1)
            putInt("stat_focus_min", focusMinutes + len)
            putLong("unlock_until", maxOf(unlockUntil, now) + reward * 60_000L)
        }
        return reward
    }

    fun recordProof(approved: Boolean, now: Long) = edit {
        if (approved) {
            putLong("last_proof", now)
            putInt("stat_approved", approvedCount + 1)
            putLong("unlock_until", maxOf(unlockUntil, now) + rewardMinutes * 60_000L)
        } else {
            putInt("stat_rejected", rejectedCount + 1)
        }
    }

    fun endBreak() = edit { putLong("unlock_until", 0) }

    fun countBlock() = edit { putInt("stat_blocks", blockCount + 1) }

    companion object {
        const val DEFAULT_VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
        const val DEFAULT_TEXT_MODEL = "llama-3.3-70b-versatile"

        /** 25 dk odak → 8 dk mola, 60 dk → 20 dk. */
        fun sessionReward(minutes: Int): Int = maxOf(5, minutes / 3)

        @Volatile
        private var instance: Store? = null

        fun get(context: Context): Store =
            instance ?: synchronized(this) {
                instance ?: Store(context.applicationContext).also { instance = it }
            }
    }
}
