@file:OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)

package com.attention.app

import android.content.ActivityNotFoundException
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.State
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.FileProvider
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File

val Good = Color(0xFF5EE6C4)
val Bad = Color(0xFFFF6B6B)

private val Colors = darkColorScheme(
    primary = Color(0xFF8B7CFF),
    onPrimary = Color(0xFF14102E),
    secondary = Good,
    background = Color(0xFF0E0F14),
    onBackground = Color(0xFFECEDF3),
    surface = Color(0xFF0E0F14),
    onSurface = Color(0xFFECEDF3),
    surfaceVariant = Color(0xFF1B1D27),
    onSurfaceVariant = Color(0xFFA6A9B8),
    surfaceContainer = Color(0xFF15171F),
    error = Bad,
)

@Composable
fun AttentionTheme(content: @Composable () -> Unit) = MaterialTheme(colorScheme = Colors, content = content)

/** Her saniye güncellenen "şimdi"; geri sayımlar bunu okur. */
@Composable
fun rememberNow(): State<Long> {
    val now = remember { mutableLongStateOf(System.currentTimeMillis()) }
    LaunchedEffect(Unit) {
        while (true) {
            now.longValue = System.currentTimeMillis()
            delay(1000)
        }
    }
    return now
}

fun formatDuration(ms: Long): String {
    val total = (ms / 1000).coerceAtLeast(0)
    val h = total / 3600
    val m = (total % 3600) / 60
    val s = total % 60
    return if (h > 0) "%d:%02d:%02d".format(h, m, s) else "%02d:%02d".format(m, s)
}

@Composable
fun Section(title: String? = null, content: @Composable ColumnScope.() -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(20.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
    ) {
        Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            if (title != null) Text(title, fontWeight = FontWeight.SemiBold, fontSize = 17.sp)
            content()
        }
    }
}

@Composable
fun Muted(text: String) = Text(text, color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 14.sp)

@Composable
fun FocusPicker(store: Store) {
    store.watch()
    Section("Neye odaklanıyorsun?") {
        FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            FocusMode.entries.forEach { mode ->
                FilterChip(
                    selected = store.focus == mode,
                    onClick = { store.focusId = mode.id },
                    label = { Text("${mode.emoji} ${mode.title}") },
                )
            }
        }
        if (store.focus == FocusMode.CUSTOM) {
            OutlinedTextField(
                value = store.customFocus,
                onValueChange = { store.customFocus = it },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
                label = { Text("Ne yapacaksın? (ör. İngilizce kelime çalışmak)") },
            )
        }
    }
}

private sealed interface ProofState {
    data object Idle : ProofState
    data class Checking(val photo: ImageBitmap) : ProofState
    data class Done(val photo: ImageBitmap, val verdict: Groq.Verdict) : ProofState
    data class Failed(val message: String) : ProofState
}

/** Fotoğraf çek → Groq vision modeli kontrol etsin → onaylanırsa mola kazan. */
@Composable
fun ProofCard(store: Store, now: Long, onApproved: () -> Unit = {}) {
    store.watch()
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var state by remember { mutableStateOf<ProofState>(ProofState.Idle) }
    val photo = remember { File(File(context.cacheDir, "proofs").apply { mkdirs() }, "proof.jpg") }

    val camera = rememberLauncherForActivityResult(ActivityResultContracts.TakePicture()) { ok ->
        if (!ok || photo.length() == 0L) {
            state = ProofState.Idle
            return@rememberLauncherForActivityResult
        }
        scope.launch {
            try {
                val (base64, bitmap) = withContext(Dispatchers.IO) { Images.load(photo) }
                val image = bitmap.asImageBitmap()
                state = ProofState.Checking(image)
                val key = store.apiKey
                val model = store.visionModel
                val focus = store.focus
                val custom = store.customFocus
                val verdict = withContext(Dispatchers.IO) { Groq.verifyPhoto(key, model, focus, custom, base64) }
                store.recordProof(verdict.approved, System.currentTimeMillis())
                state = ProofState.Done(image, verdict)
                if (verdict.approved) onApproved()
            } catch (e: Exception) {
                state = ProofState.Failed(e.message ?: "Bilinmeyen hata")
            } finally {
                photo.delete()
            }
        }
    }

    Section("📸 Fotoğrafla kanıtla") {
        val nextAt = store.nextProofAt()
        when {
            store.isSessionActive(now) ->
                Muted("Odak oturumu sürerken kanıtla kilit açılmaz. Oturumu bitir, molanı hak et.")
            store.apiKey.isBlank() ->
                Muted("AI kontrolü için Ayarlar sekmesinden Groq API anahtarını ekle.")
            now < nextAt ->
                Muted(
                    "Sonraki fotoğraf kanıtı ${formatDuration(nextAt - now)} sonra açılır. " +
                        "Bu arada odak oturumu başlatabilirsin."
                )
            else -> {
                Muted(
                    "Şu an ${store.focus.emoji} ${store.focusLabel()} yaptığını gösteren bir fotoğraf çek. " +
                        "AI onaylarsa ${store.rewardMinutes} dk mola kazanırsın."
                )
                Button(
                    onClick = {
                        photo.delete()
                        val uri = FileProvider.getUriForFile(context, "${context.packageName}.files", photo)
                        try {
                            camera.launch(uri)
                        } catch (e: ActivityNotFoundException) {
                            state = ProofState.Failed("Kamera uygulaması bulunamadı.")
                        }
                    },
                    enabled = state !is ProofState.Checking,
                    modifier = Modifier.fillMaxWidth(),
                ) { Text("Fotoğraf çek") }
            }
        }

        when (val s = state) {
            ProofState.Idle -> {}
            is ProofState.Checking -> {
                ProofPhoto(s.photo)
                Row(verticalAlignment = Alignment.CenterVertically) {
                    CircularProgressIndicator(Modifier.size(18.dp), strokeWidth = 2.dp)
                    Spacer(Modifier.width(10.dp))
                    Text("AI kontrol ediyor…")
                }
            }
            is ProofState.Done -> {
                ProofPhoto(s.photo)
                Text(
                    if (s.verdict.approved) "✅ Onaylandı — ${store.rewardMinutes} dk mola kazandın" else "❌ Reddedildi",
                    color = if (s.verdict.approved) Good else Bad,
                    fontWeight = FontWeight.SemiBold,
                )
                Muted("${s.verdict.reason} (güven: %${s.verdict.confidence})")
            }
            is ProofState.Failed -> Text("⚠️ ${s.message}", color = Bad)
        }
    }
}

@Composable
private fun ProofPhoto(image: ImageBitmap) = Image(
    bitmap = image,
    contentDescription = "Kanıt fotoğrafı",
    contentScale = ContentScale.Crop,
    modifier = Modifier.fillMaxWidth().height(180.dp).clip(RoundedCornerShape(14.dp)),
)

/** Süreli odak oturumu: bitince süreye göre mola kazandırır, sürerken her şey kilitli. */
@Composable
fun SessionCard(store: Store, now: Long) {
    store.watch()
    var minutes by remember { mutableIntStateOf(25) }
    var confirmCancel by remember { mutableStateOf(false) }

    Section("⏱ Odak oturumu") {
        if (store.isSessionActive(now)) {
            val total = store.sessionLength * 60_000L
            val left = store.sessionEnd - now
            Text(formatDuration(left), fontSize = 44.sp, fontWeight = FontWeight.Bold)
            LinearProgressIndicator(
                progress = { if (total > 0) 1f - left.toFloat() / total else 0f },
                modifier = Modifier.fillMaxWidth(),
            )
            Muted("Bitince ${Store.sessionReward(store.sessionLength)} dk mola kazanacaksın. O zamana kadar her şey kilitli.")
            TextButton(onClick = { confirmCancel = true }) { Text("Vazgeç", color = Bad) }
        } else {
            Muted("Telefonu bırak, süre bitene kadar çalış. Bitince mola kazanırsın.")
            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                listOf(15, 25, 45, 60, 90).forEach { m ->
                    FilterChip(selected = minutes == m, onClick = { minutes = m }, label = { Text("$m dk") })
                }
            }
            Button(onClick = { store.startSession(minutes, System.currentTimeMillis()) }, modifier = Modifier.fillMaxWidth()) {
                Text("$minutes dk odaklan → ${Store.sessionReward(minutes)} dk mola")
            }
        }
    }

    if (confirmCancel) {
        AlertDialog(
            onDismissRequest = { confirmCancel = false },
            title = { Text("Gerçekten bırakıyor musun?") },
            text = { Text("Oturumu iptal edersen mola kazanamazsın ve uygulamalar kilitli kalır.") },
            confirmButton = {
                TextButton(onClick = { store.cancelSession(); confirmCancel = false }) { Text("İptal et", color = Bad) }
            },
            dismissButton = { Button(onClick = { confirmCancel = false }) { Text("Devam ediyorum") } },
        )
    }
}
