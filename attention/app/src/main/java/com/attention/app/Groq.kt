package com.attention.app

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.util.Base64
import org.json.JSONArray
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.io.File
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL

/** Groq'un OpenAI uyumlu chat API'si için küçük, bağımlılıksız istemci. Ağ çağrıları bloklar; IO thread'inde çağır. */
object Groq {
    private const val ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"

    data class Verdict(val approved: Boolean, val confidence: Int, val reason: String)

    fun chat(apiKey: String, model: String, messages: JSONArray, maxTokens: Int, temperature: Double = 0.2): String {
        if (apiKey.isBlank()) throw IOException("Groq API anahtarı yok. Ayarlar sekmesinden ekle.")
        val body = JSONObject()
            .put("model", model)
            .put("messages", messages)
            .put("temperature", temperature)
            .put("max_completion_tokens", maxTokens)
        val conn = (URL(ENDPOINT).openConnection() as HttpURLConnection).apply {
            requestMethod = "POST"
            connectTimeout = 20_000
            readTimeout = 60_000
            doOutput = true
            setRequestProperty("Authorization", "Bearer $apiKey")
            setRequestProperty("Content-Type", "application/json")
        }
        try {
            conn.outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }
            val code = conn.responseCode
            val stream = if (code in 200..299) conn.inputStream else conn.errorStream
            val text = stream?.bufferedReader()?.use { it.readText() } ?: ""
            if (code !in 200..299) {
                val msg = runCatching { JSONObject(text).getJSONObject("error").getString("message") }.getOrNull()
                throw IOException(
                    when (code) {
                        401 -> "API anahtarı geçersiz (401)."
                        429 -> "Groq limitine takıldın, biraz sonra tekrar dene (429)."
                        else -> "Groq hatası $code: ${msg ?: text.take(200)}"
                    }
                )
            }
            return JSONObject(text).getJSONArray("choices").getJSONObject(0)
                .getJSONObject("message").getString("content").trim()
        } finally {
            conn.disconnect()
        }
    }

    fun verifyPhoto(apiKey: String, model: String, focus: FocusMode, custom: String, jpegBase64: String): Verdict {
        val activity = if (focus == FocusMode.CUSTOM) {
            "${custom.ifBlank { "Kullanıcının belirlediği üretken bir aktivite" }}. " +
                "Fotoğraf bu aktivitenin şu an yapıldığını göstermeli."
        } else {
            "${focus.title} — ${focus.proof}"
        }
        val system = """
            Sen "Attention" adlı odak uygulamasının katı ama adil denetçisisin.
            Kullanıcı telefondaki dikkat dağıtıcı uygulamaların (Instagram, TikTok vb.) kilidini açmak için
            şu aktiviteyi gerçekten yaptığını bir fotoğrafla kanıtlamaya çalışıyor:
            $activity

            Kurallar:
            - Fotoğraf aktivitenin şu an yapıldığına dair somut kanıt göstermeli.
            - Telefon ekran görüntüsü, başka bir fotoğrafın fotoğrafı, internetten bulunmuş görsel,
              alakasız sahne, çok karanlık/bulanık ya da ne olduğu anlaşılmayan kareleri reddet.
            - Kapalı kitap, boş defter, kapalı bilgisayar gibi "niyet" gösteren ama yapılmış iş göstermeyen kareleri reddet.
            - Emin değilsen reddet.
            Sadece şu JSON ile cevap ver, başka hiçbir şey yazma:
            {"approved": true veya false, "confidence": 0-100 arası sayı, "reason": "kısa, samimi Türkçe açıklama"}
        """.trimIndent()
        val messages = JSONArray()
            .put(JSONObject().put("role", "system").put("content", system))
            .put(
                JSONObject().put("role", "user").put(
                    "content", JSONArray()
                        .put(JSONObject().put("type", "text").put("text", "İşte kanıt fotoğrafım."))
                        .put(
                            JSONObject().put("type", "image_url").put(
                                "image_url", JSONObject().put("url", "data:image/jpeg;base64,$jpegBase64")
                            )
                        )
                )
            )
        val reply = chat(apiKey, model, messages, maxTokens = 300, temperature = 0.1)
        val start = reply.indexOf('{')
        val end = reply.lastIndexOf('}')
        if (start < 0 || end <= start) throw IOException("AI cevabı anlaşılamadı: ${reply.take(120)}")
        val json = JSONObject(reply.substring(start, end + 1))
        val confidence = json.optInt("confidence", 0)
        return Verdict(
            approved = json.optBoolean("approved", false) && confidence >= 60,
            confidence = confidence,
            reason = json.optString("reason", "").ifBlank { "Açıklama yok." },
        )
    }

    fun motivation(apiKey: String, model: String, focusLabel: String, appName: String): String {
        val messages = JSONArray()
            .put(
                JSONObject().put("role", "system").put(
                    "content",
                    "Kullanıcının kendine hakim olmasına yardım eden bir odak koçusun. " +
                        "En fazla 2 kısa cümlelik, samimi, biraz iğneleyici ama destekleyici Türkçe bir mesaj yaz. " +
                        "En fazla 1 emoji kullan. Tırnak işareti kullanma."
                )
            )
            .put(
                JSONObject().put("role", "user").put(
                    "content",
                    "Az önce $appName uygulamasını açmaya çalıştım. Aslında odaklanmam gereken şey: $focusLabel."
                )
            )
        return chat(apiKey, model, messages, maxTokens = 120, temperature = 0.9)
    }

    fun fallbackMotivation(focusLabel: String): String = listOf(
        "Reels bekleyebilir, $focusLabel bekleyemez.",
        "15 saniyelik videolar 3 saatini yiyor. $focusLabel'a dön.",
        "Gelecekteki sen, şu an kapattığın bu uygulama için teşekkür edecek.",
        "Önce $focusLabel, sonra kazandığın molanın tadını çıkar.",
    ).random()
}

object Images {
    /** Fotoğrafı en fazla [maxSide] piksele küçültüp (base64 JPEG, önizleme bitmap) döner. */
    fun load(file: File, maxSide: Int = 1024): Pair<String, Bitmap> {
        val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        BitmapFactory.decodeFile(file.absolutePath, bounds)
        if (bounds.outWidth <= 0) throw IOException("Fotoğraf okunamadı.")
        var sample = 1
        while (maxOf(bounds.outWidth, bounds.outHeight) / (sample * 2) >= maxSide) sample *= 2
        val decoded = BitmapFactory.decodeFile(file.absolutePath, BitmapFactory.Options().apply { inSampleSize = sample })
            ?: throw IOException("Fotoğraf okunamadı.")
        val scale = maxSide.toFloat() / maxOf(decoded.width, decoded.height)
        val bmp = if (scale < 1f) {
            Bitmap.createScaledBitmap(decoded, (decoded.width * scale).toInt(), (decoded.height * scale).toInt(), true)
        } else {
            decoded
        }
        val out = ByteArrayOutputStream()
        bmp.compress(Bitmap.CompressFormat.JPEG, 80, out)
        return Base64.encodeToString(out.toByteArray(), Base64.NO_WRAP) to bmp
    }
}
