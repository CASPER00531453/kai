package com.attention.app

import android.accessibilityservice.AccessibilityService
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.os.Handler
import android.os.Looper
import android.provider.Settings
import android.view.accessibility.AccessibilityEvent

/** Ön plana gelen uygulamayı izler; kilitli bir uygulamaysa ana ekrana atıp kilit ekranını açar. */
class BlockerService : AccessibilityService() {
    private val handler = Handler(Looper.getMainLooper())
    private lateinit var store: Store
    private var currentPkg: String? = null
    private var lastBlockPkg: String? = null
    private var lastBlockAt = 0L
    private val recheck = Runnable { check(currentPkg) }

    override fun onServiceConnected() {
        store = Store.get(this)
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent) {
        if (event.eventType != AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED) return
        val pkg = event.packageName?.toString() ?: return
        if (pkg == "com.android.systemui" || pkg == keyboardPackage()) return
        currentPkg = pkg
        check(pkg)
    }

    private fun check(pkg: String?) {
        handler.removeCallbacks(recheck)
        if (pkg == null || pkg == packageName || !::store.isInitialized) return
        val now = System.currentTimeMillis()
        store.completeSessionIfDone(now)
        if (!store.shouldBlock(pkg, now)) {
            // Mola sırasında kilitli bir uygulamadaysak, mola bitince tekrar kontrol et.
            if (store.blockingEnabled && pkg in store.blocked && store.unlockUntil > now) {
                handler.postDelayed(recheck, store.unlockUntil - now + 500)
            }
            return
        }
        if (pkg == lastBlockPkg && now - lastBlockAt < 1500) return
        lastBlockPkg = pkg
        lastBlockAt = now
        store.countBlock()
        performGlobalAction(GLOBAL_ACTION_HOME)
        startActivity(
            Intent(this, BlockActivity::class.java)
                .putExtra(BlockActivity.EXTRA_PKG, pkg)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP)
        )
    }

    private fun keyboardPackage(): String? =
        Settings.Secure.getString(contentResolver, Settings.Secure.DEFAULT_INPUT_METHOD)?.substringBefore('/')

    override fun onInterrupt() {}

    override fun onDestroy() {
        handler.removeCallbacks(recheck)
        super.onDestroy()
    }

    companion object {
        fun isEnabled(context: Context): Boolean {
            val enabled = Settings.Secure.getString(
                context.contentResolver, Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES
            ) ?: return false
            val me = ComponentName(context, BlockerService::class.java)
            return enabled.split(':').any { ComponentName.unflattenFromString(it) == me }
        }
    }
}
