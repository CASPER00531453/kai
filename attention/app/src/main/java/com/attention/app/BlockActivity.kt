package com.attention.app

import android.content.Intent
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.OnBackPressedCallback
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/** Kilitli bir uygulama açılınca gösterilen tam ekran engel. */
class BlockActivity : ComponentActivity() {
    private var pkg by mutableStateOf<String?>(null)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        pkg = intent.getStringExtra(EXTRA_PKG)
        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() = goHome()
        })
        setContent {
            AttentionTheme {
                Surface(Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
                    BlockScreen(pkg, onHome = ::goHome, onOpen = ::openBlockedApp)
                }
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        pkg = intent.getStringExtra(EXTRA_PKG)
    }

    private fun goHome() {
        startActivity(Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_HOME).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        finish()
    }

    private fun openBlockedApp() {
        val target = pkg?.let { packageManager.getLaunchIntentForPackage(it) }
        if (target != null) startActivity(target) else goHome()
        finish()
    }

    companion object {
        const val EXTRA_PKG = "pkg"
    }
}

@Composable
private fun BlockScreen(pkg: String?, onHome: () -> Unit, onOpen: () -> Unit) {
    val context = LocalContext.current
    val store = remember { Store.get(context) }
    store.watch()
    val now by rememberNow()
    val appName = remember(pkg) {
        pkg?.let { runCatching { context.packageManager.run { getApplicationLabel(getApplicationInfo(it, 0)).toString() } }.getOrNull() }
            ?: "Bu uygulama"
    }
    var coach by remember(pkg) { mutableStateOf<String?>(null) }

    LaunchedEffect(now) { store.completeSessionIfDone(now) }
    LaunchedEffect(pkg) {
        val focus = store.focusLabel()
        coach = withContext(Dispatchers.IO) {
            runCatching { Groq.motivation(store.apiKey, store.textModel, focus, appName) }
                .getOrElse { Groq.fallbackMotivation(focus) }
        }
    }

    Column(
        Modifier.fillMaxSize().safeDrawingPadding().verticalScroll(rememberScrollState()).padding(20.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text("⛔", fontSize = 56.sp)
        Text("$appName kilitli", fontSize = 26.sp, fontWeight = FontWeight.Bold, textAlign = TextAlign.Center)
        Text(
            coach ?: "…",
            fontStyle = FontStyle.Italic,
            textAlign = TextAlign.Center,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )

        if (store.isOnBreak(now)) {
            Section("🔓 Kilit açıldı") {
                Muted("Mola: ${formatDuration(store.unlockUntil - now)} kaldı.")
                Button(onClick = onOpen, modifier = Modifier.fillMaxWidth()) { Text("$appName aç") }
            }
        } else {
            FocusPicker(store)
            SessionCard(store, now)
            ProofCard(store, now)
        }

        OutlinedButton(onClick = onHome, modifier = Modifier.fillMaxWidth()) { Text("Ana ekrana dön") }
    }
}
