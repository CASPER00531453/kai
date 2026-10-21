@file:OptIn(ExperimentalMaterial3Api::class)

package com.attention.app

import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Bundle
import android.provider.Settings
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.Image
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.graphics.drawable.toBitmap
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent { AttentionTheme { AttentionApp() } }
    }
}

@Composable
private fun AttentionApp() {
    val context = LocalContext.current
    val store = remember { Store.get(context) }
    val now by rememberNow()
    var tab by rememberSaveable { mutableIntStateOf(0) }

    LaunchedEffect(now) { store.completeSessionIfDone(now) }

    Scaffold(
        bottomBar = {
            NavigationBar {
                listOf("🎯" to "Odak", "🚫" to "Uygulamalar", "⚙️" to "Ayarlar").forEachIndexed { i, (icon, label) ->
                    NavigationBarItem(
                        selected = tab == i,
                        onClick = { tab = i },
                        icon = { Text(icon, fontSize = 20.sp) },
                        label = { Text(label) },
                    )
                }
            }
        },
    ) { padding ->
        Box(Modifier.padding(padding).fillMaxSize()) {
            when (tab) {
                0 -> HomeScreen(store, now, openSettings = { tab = 2 }, openApps = { tab = 1 })
                1 -> AppsScreen(store, now)
                else -> SettingsScreen(store, now)
            }
        }
    }
}

/** Erişilebilirlik izni ekran dışında açıldığı için, uygulamaya dönünce yeniden kontrol eder. */
@Composable
private fun rememberBlockerEnabled(): Boolean {
    val context = LocalContext.current
    var enabled by remember { mutableStateOf(BlockerService.isEnabled(context)) }
    val owner = LocalLifecycleOwner.current
    DisposableEffect(owner) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_RESUME) enabled = BlockerService.isEnabled(context)
        }
        owner.lifecycle.addObserver(observer)
        onDispose { owner.lifecycle.removeObserver(observer) }
    }
    return enabled
}

private fun openAccessibilitySettings(context: Context) {
    context.startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
}

@Composable
private fun HomeScreen(store: Store, now: Long, openSettings: () -> Unit, openApps: () -> Unit) {
    store.watch()
    val context = LocalContext.current
    val blockerOn = rememberBlockerEnabled()

    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        Column {
            Text("Attention", fontSize = 32.sp, fontWeight = FontWeight.Bold)
            Muted("Dikkatini geri al. Önce iş, sonra mola.")
        }

        if (!blockerOn) {
            Section("⚠️ Engelleme servisi kapalı") {
                Muted(
                    "Uygulamaları kilitleyebilmem için Erişilebilirlik ayarlarından \"Attention\"ı aç. " +
                        "Göremiyorsan veya gri ise: Ayarlar → Uygulamalar → Attention → sağ üst ⋮ → " +
                        "\"Kısıtlanmış ayarlara izin ver\" de, sonra tekrar dene."
                )
                Button(onClick = { openAccessibilitySettings(context) }) { Text("Erişilebilirliği aç") }
            }
        }
        if (store.apiKey.isBlank()) {
            Section("🔑 Groq API anahtarı yok") {
                Muted("Fotoğraf kontrolü ve AI koç için console.groq.com'dan ücretsiz anahtar alıp ekle.")
                OutlinedButton(onClick = openSettings) { Text("Ayarlara git") }
            }
        }

        StatusCard(store, now, openApps)
        FocusPicker(store)
        SessionCard(store, now)
        ProofCard(store, now)

        Section("📊 İstatistik") {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Stat("${store.approvedCount}", "kanıt")
                Stat("${store.sessionsDone}", "oturum")
                Stat("${store.focusMinutes}", "odak dk")
                Stat("${store.blockCount}", "engellenen")
            }
        }
    }
}

@Composable
private fun Stat(value: String, label: String) {
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Text(value, fontSize = 22.sp, fontWeight = FontWeight.Bold)
        Muted(label)
    }
}

@Composable
private fun StatusCard(store: Store, now: Long, openApps: () -> Unit) {
    val count = store.blocked.size
    Section {
        when {
            !store.blockingEnabled -> {
                Text("⏸ Engelleme duraklatıldı", fontSize = 20.sp, fontWeight = FontWeight.SemiBold, color = Bad)
                Muted("Ayarlar sekmesinden tekrar açabilirsin.")
            }
            count == 0 -> {
                Text("Henüz kilitli uygulama yok", fontSize = 20.sp, fontWeight = FontWeight.SemiBold)
                Button(onClick = openApps) { Text("Dikkatimi dağıtanları seç") }
            }
            store.isSessionActive(now) -> {
                Text("🔒 Odak modundasın", fontSize = 20.sp, fontWeight = FontWeight.SemiBold)
                Muted("$count uygulama kilitli. Odak: ${store.focus.emoji} ${store.focusLabel()}")
            }
            store.isOnBreak(now) -> {
                Text("🔓 Mola: ${formatDuration(store.unlockUntil - now)}", fontSize = 20.sp, fontWeight = FontWeight.SemiBold, color = Good)
                Muted("Hak ettin, tadını çıkar. Bitince her şey yeniden kilitlenir.")
                TextButton(onClick = { store.endBreak() }) { Text("Molayı şimdi bitir") }
            }
            else -> {
                Text("🔒 $count uygulama kilitli", fontSize = 20.sp, fontWeight = FontWeight.SemiBold)
                Muted("Açmak için: odak oturumu tamamla ya da yaptığın işi fotoğrafla kanıtla.")
            }
        }
    }
}

private class AppEntry(val pkg: String, val label: String, val icon: ImageBitmap?)

private val SUGGESTED = setOf(
    "com.instagram.android", "com.zhiliaoapp.musically", "com.ss.android.ugc.trill", "com.google.android.youtube",
    "com.twitter.android", "com.facebook.katana", "com.snapchat.android", "com.reddit.frontpage",
    "com.pinterest", "tv.twitch.android.app", "com.netflix.mediaclient", "com.instagram.barcelona",
)

@Composable
private fun AppsScreen(store: Store, now: Long) {
    store.watch()
    val context = LocalContext.current
    var apps by remember { mutableStateOf<List<AppEntry>?>(null) }
    var query by remember { mutableStateOf("") }
    val locked = store.isSessionActive(now)

    LaunchedEffect(Unit) {
        apps = withContext(Dispatchers.IO) { loadApps(context) }
    }

    Column(Modifier.fillMaxSize().padding(horizontal = 16.dp)) {
        Spacer(Modifier.size(16.dp))
        Text("Dikkat dağıtıcılar", fontSize = 26.sp, fontWeight = FontWeight.Bold)
        Muted(
            if (locked) "Odak oturumu sürerken listeden çıkarma yapılamaz."
            else "Seçtiğin uygulamalar molan yokken açılamaz."
        )
        Spacer(Modifier.size(10.dp))
        OutlinedTextField(
            value = query,
            onValueChange = { query = it },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
            placeholder = { Text("Ara…") },
        )
        val list = apps
        if (list == null) {
            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
        } else {
            val blocked = store.blocked
            val shown = list.filter { query.isBlank() || it.label.contains(query, ignoreCase = true) }
                .sortedWith(compareByDescending<AppEntry> { it.pkg in blocked }.thenByDescending { it.pkg in SUGGESTED })
            LazyColumn(contentPadding = PaddingValues(vertical = 8.dp)) {
                items(shown, key = { it.pkg }) { app ->
                    val checked = app.pkg in blocked
                    val canToggle = !(locked && checked)
                    Row(
                        Modifier.fillMaxWidth()
                            .clickable(enabled = canToggle) {
                                store.blocked = if (checked) blocked - app.pkg else blocked + app.pkg
                            }
                            .padding(vertical = 8.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        if (app.icon != null) Image(app.icon, null, Modifier.size(40.dp)) else Spacer(Modifier.size(40.dp))
                        Spacer(Modifier.width(14.dp))
                        Column(Modifier.weight(1f)) {
                            Text(app.label, fontSize = 16.sp)
                            if (app.pkg in SUGGESTED && !checked) {
                                Text("dikkat dağıtıcı olabilir", fontSize = 12.sp, color = MaterialTheme.colorScheme.primary)
                            }
                        }
                        Checkbox(checked = checked, onCheckedChange = null, enabled = canToggle)
                    }
                }
            }
        }
    }
}

private fun loadApps(context: Context): List<AppEntry> {
    val pm = context.packageManager
    val launcher = Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER)
    val iconPx = (40 * context.resources.displayMetrics.density).toInt()
    return pm.queryIntentActivities(launcher, PackageManager.MATCH_ALL)
        .map { it.activityInfo.applicationInfo }
        .distinctBy { it.packageName }
        .filter { it.packageName != context.packageName }
        .map { info ->
            AppEntry(
                pkg = info.packageName,
                label = pm.getApplicationLabel(info).toString(),
                icon = runCatching { pm.getApplicationIcon(info).toBitmap(iconPx, iconPx).asImageBitmap() }.getOrNull(),
            )
        }
        .sortedBy { it.label.lowercase() }
}

@Composable
private fun SettingsScreen(store: Store, now: Long) {
    store.watch()
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val blockerOn = rememberBlockerEnabled()
    var key by remember { mutableStateOf(store.apiKey) }
    var showKey by remember { mutableStateOf(false) }
    var vision by remember { mutableStateOf(store.visionModel) }
    var text by remember { mutableStateOf(store.textModel) }
    var testResult by remember { mutableStateOf<String?>(null) }
    var confirmPause by remember { mutableStateOf(false) }

    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        Text("Ayarlar", fontSize = 26.sp, fontWeight = FontWeight.Bold)

        Section("🤖 Groq AI") {
            Muted("console.groq.com → API Keys bölümünden ücretsiz anahtar oluştur. Anahtar sadece bu telefonda saklanır.")
            OutlinedTextField(
                value = key,
                onValueChange = { key = it },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
                label = { Text("API anahtarı (gsk_…)") },
                visualTransformation = if (showKey) VisualTransformation.None else PasswordVisualTransformation(),
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
                trailingIcon = { TextButton(onClick = { showKey = !showKey }) { Text(if (showKey) "Gizle" else "Göster") } },
            )
            OutlinedTextField(
                value = vision, onValueChange = { vision = it }, modifier = Modifier.fillMaxWidth(),
                singleLine = true, label = { Text("Görsel model (fotoğraf kontrolü)") },
            )
            OutlinedTextField(
                value = text, onValueChange = { text = it }, modifier = Modifier.fillMaxWidth(),
                singleLine = true, label = { Text("Metin model (AI koç)") },
            )
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = {
                    store.apiKey = key
                    store.visionModel = vision
                    store.textModel = text
                    vision = store.visionModel
                    text = store.textModel
                    testResult = "Kaydedildi."
                }) { Text("Kaydet") }
                OutlinedButton(onClick = {
                    store.apiKey = key
                    testResult = "Test ediliyor…"
                    scope.launch {
                        testResult = try {
                            val reply = withContext(Dispatchers.IO) {
                                Groq.chat(
                                    key.trim(), text.trim().ifEmpty { Store.DEFAULT_TEXT_MODEL },
                                    JSONArray().put(JSONObject().put("role", "user").put("content", "Sadece 'tamam' yaz.")),
                                    maxTokens = 10,
                                )
                            }
                            "✅ Bağlantı çalışıyor: $reply"
                        } catch (e: Exception) {
                            "❌ ${e.message}"
                        }
                    }
                }) { Text("Test et") }
            }
            testResult?.let { Muted(it) }
        }

        Section("🎁 Ödüller") {
            Stepper("Fotoğraf kanıtı başına mola", store.rewardMinutes, 5) { store.rewardMinutes = it }
            Stepper("İki kanıt arası bekleme", store.cooldownMinutes, 15) { store.cooldownMinutes = it }
            Muted("Odak oturumu ödülü süreye göre: 25 dk → 8 dk mola, 60 dk → 20 dk mola.")
        }

        Section("🛡 Engelleme") {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text("Engelleme açık")
                    Muted(if (store.isSessionActive(now)) "Odak oturumu sürerken kapatılamaz." else "Kapatmak kolay, açık tutmak marifet.")
                }
                Switch(
                    checked = store.blockingEnabled,
                    enabled = !store.isSessionActive(now),
                    onCheckedChange = { on -> if (on) store.blockingEnabled = true else confirmPause = true },
                )
            }
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(if (blockerOn) "✅ Erişilebilirlik servisi açık" else "❌ Erişilebilirlik servisi kapalı", Modifier.weight(1f))
                TextButton(onClick = { openAccessibilitySettings(context) }) { Text("Aç") }
            }
            Muted(
                "Android 13+ ve APK ile kurduysan: Ayarlar → Uygulamalar → Attention → ⋮ → " +
                    "\"Kısıtlanmış ayarlara izin ver\" demen gerekebilir."
            )
        }
    }

    if (confirmPause) {
        AlertDialog(
            onDismissRequest = { confirmPause = false },
            title = { Text("Engellemeyi kapat?") },
            text = { Text("Bunu reels izlemek için mi yapıyorsun? Dürüst ol. 🙂") },
            confirmButton = {
                TextButton(onClick = { store.blockingEnabled = false; confirmPause = false }) { Text("Kapat", color = Bad) }
            },
            dismissButton = { Button(onClick = { confirmPause = false }) { Text("Vazgeç") } },
        )
    }
}

@Composable
private fun Stepper(label: String, value: Int, step: Int, onChange: (Int) -> Unit) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Text(label, Modifier.weight(1f))
        OutlinedButton(onClick = { onChange(value - step) }) { Text("−") }
        Text("$value dk", Modifier.padding(horizontal = 10.dp), fontWeight = FontWeight.SemiBold)
        OutlinedButton(onClick = { onChange(value + step) }) { Text("+") }
    }
}
