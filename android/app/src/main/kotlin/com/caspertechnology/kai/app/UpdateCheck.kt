package com.caspertechnology.kai.app

import android.content.Context
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

/**
 * Kai: a newer APK on GitHub (CASPER00531453/kai-android, its latest release). Asked at most
 * once every six hours; only the release's version and its download address are read, and
 * nothing about the phone is sent.
 */
object UpdateCheck {
    private const val LATEST = "https://api.github.com/repos/CASPER00531453/kai-android/releases/latest"
    private const val EVERY_MS = 6 * 60 * 60 * 1000L

    data class Update(val version: String, val url: String)

    fun installedVersion(context: Context): String =
        runCatching { context.packageManager.getPackageInfo(context.packageName, 0).versionName.orEmpty() }.getOrDefault("")

    /** On a background thread: the newer release, or null (up to date, too soon, or unreachable). */
    fun check(context: Context, force: Boolean = false): Update? {
        val prefs = context.getSharedPreferences("kai_update", Context.MODE_PRIVATE)
        val now = System.currentTimeMillis()
        if (!force && now - prefs.getLong("checked_at", 0) < EVERY_MS) return cached(context, prefs.getString("version", null), prefs.getString("url", null))
        val release = runCatching { fetch() }.getOrNull() ?: return null
        prefs.edit().putLong("checked_at", now).putString("version", release.version).putString("url", release.url).apply()
        return cached(context, release.version, release.url)
    }

    private fun cached(context: Context, version: String?, url: String?): Update? {
        if (version.isNullOrBlank() || url.isNullOrBlank()) return null
        return if (newer(version, installedVersion(context))) Update(version, url) else null
    }

    private fun fetch(): Update? {
        val connection = (URL(LATEST).openConnection() as HttpURLConnection).apply {
            connectTimeout = 8000
            readTimeout = 8000
            setRequestProperty("Accept", "application/vnd.github+json")
            setRequestProperty("User-Agent", "Kai-Android")
        }
        try {
            if (connection.responseCode != 200) return null
            val o = JSONObject(connection.inputStream.bufferedReader().readText())
            val version = o.optString("tag_name").removePrefix("v")
            val assets = o.optJSONArray("assets")
            var url = o.optString("html_url")
            if (assets != null) {
                for (i in 0 until assets.length()) {
                    val a = assets.getJSONObject(i)
                    if (a.optString("name").endsWith(".apk")) url = a.optString("browser_download_url", url)
                }
            }
            // Only GitHub's own addresses are ever opened.
            if (!url.startsWith("https://github.com/")) return null
            return Update(version, url)
        } finally {
            connection.disconnect()
        }
    }

    /** "1.2.0" > "1.1.9": number by number. */
    fun newer(candidate: String, installed: String): Boolean {
        val a = candidate.split('.').map { it.toIntOrNull() ?: 0 }
        val b = installed.split('.').map { it.toIntOrNull() ?: 0 }
        for (i in 0 until maxOf(a.size, b.size)) {
            val x = a.getOrElse(i) { 0 }
            val y = b.getOrElse(i) { 0 }
            if (x != y) return x > y
        }
        return false
    }
}
