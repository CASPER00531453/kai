package com.caspertechnology.kai.ui

import android.os.SystemClock
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.caspertechnology.kai.R
import com.caspertechnology.kai.app.AppModel
import com.caspertechnology.kai.core.Spacing
import com.caspertechnology.kai.core.TypeScale
import com.caspertechnology.kai.mochi.BotState
import com.caspertechnology.kai.mochi.MochiEngine
import com.caspertechnology.kai.mochi.MochiView
import kotlin.math.cos
import kotlin.math.sin

/**
 * Kai: the computer's screen or camera, live. Kai looks along: a camera at its eye for the
 * camera, a magnifying glass for the screen, the same as on the computer's island (props.ts).
 */
@Composable
fun ViewerScreen(model: AppModel, onBack: () -> Unit) {
    val t = tokens()
    val source = model.viewSource
    // Leaving the screen stops the picture: the computer must not go on sending for nobody.
    DisposableEffect(Unit) { onDispose { model.stopView() } }
    val clock = remember { { SystemClock.elapsedRealtimeNanos() / 1e6 } }
    val engine = remember { MochiEngine(clock, sound = model.sounds) }
    if (engine.state != BotState.SEARCHING) engine.setState(BotState.SEARCHING)

    Column(Modifier.fillMaxSize().padding(Gutter), verticalArrangement = Arrangement.spacedBy(Gap)) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            Box(Modifier.size(92.dp)) {
                MochiView(engine, Modifier.fillMaxSize())
                if (source != null) ViewProp(source, engine, Modifier.fillMaxSize())
            }
            Column(Modifier.weight(1f)) {
                Text(
                    stringResource(if (source == "camera" || (source == null && model.viewReason == "no_camera")) R.string.view_camera_title else R.string.view_screen_title),
                    style = TypeScale.TITLE.style(t.text.c()),
                )
                Text(
                    when {
                        source != null && model.viewFrame == null -> stringResource(R.string.view_connecting)
                        source != null -> stringResource(R.string.view_live, model.viewFps)
                        model.viewReason == "no_camera" -> stringResource(R.string.view_no_camera)
                        model.viewReason == "link" -> stringResource(R.string.view_link_lost)
                        else -> stringResource(R.string.view_stopped)
                    },
                    style = TypeScale.BODY.style(t.textDim.c()),
                )
            }
        }
        Box(
            Modifier.fillMaxWidth().weight(1f).clip(RoundedCornerShape(18.dp)).background(Color(0xFF0B0C10)),
            contentAlignment = Alignment.Center,
        ) {
            val frame = model.viewFrame
            if (frame != null) {
                Image(frame, contentDescription = null, modifier = Modifier.fillMaxSize(), contentScale = ContentScale.Fit)
            } else {
                Text(stringResource(R.string.view_waiting), style = TypeScale.BODY.style(Color(0xFF8E939C)))
            }
        }
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            if (source != null) {
                PillButton(stringResource(R.string.view_stop), onClick = { model.stopView() }, Modifier.weight(1f), kind = PillKind.DANGER)
            } else {
                PillButton(stringResource(R.string.view_screen_button), onClick = { model.startView("screen") }, Modifier.weight(1f))
                PillButton(stringResource(R.string.view_camera_button), onClick = { model.startView("camera") }, Modifier.weight(1f))
            }
            PillButton(stringResource(R.string.view_back), onClick = onBack, Modifier.weight(1f))
        }
        Text(stringResource(R.string.view_privacy), style = TypeScale.SECONDARY.style(t.textFaint.c()))
    }
}

/**
 * What Kai holds while it looks, drawn over its [MochiView] with the same geometry:
 * r = width * 0.3, the right eye of the ghost at (cx + 0.31 r, cy - 0.02 r).
 */
@Composable
fun ViewProp(source: String, engine: MochiEngine, modifier: Modifier = Modifier) {
    var tick by remember { mutableLongStateOf(0L) }
    LaunchedEffect(source) {
        while (true) {
            androidx.compose.runtime.withFrameNanos { tick = it }
        }
    }
    Canvas(modifier) {
        tick // redraw every frame
        val w = size.width
        val r = w * 0.3f
        val cx = w / 2 + (engine.ox * r).toFloat()
        val cy = size.height / 2 + (engine.particleOverhang / 2).toFloat() + (engine.oy * r).toFloat() + r * 0.06f
        val now = (System.nanoTime() / 1e9).toFloat()
        if (source == "camera") drawCamera(cx + r * 0.31f, cy - r * 0.02f, r, now) else drawMagnifier(cx + r * 0.31f, cy - r * 0.02f, r, now)
    }
}

private fun DrawScope.hand(x: Float, y: Float, r: Float) {
    drawOval(Color(0xFFE9EEF7), Offset(x - r * 0.14f, y - r * 0.12f), Size(r * 0.28f, r * 0.24f))
}

private fun DrawScope.drawCamera(ex: Float, ey: Float, r: Float, t: Float) {
    val w = r * 0.95f
    val h = r * 0.62f
    val left = ex - w * 0.42f
    val top = ey - h / 2
    drawRoundRect(Color(0xFF23262D), Offset(left, top), Size(w, h), CornerRadius(r * 0.12f))
    drawRoundRect(Color(0xFF2F333C), Offset(left + w * 0.58f, top - h * 0.18f), Size(w * 0.28f, h * 0.22f), CornerRadius(r * 0.04f))
    drawCircle(Color(0xFFF4505E), r * 0.045f, Offset(left + w * 0.2f, top + h * 0.02f))
    drawCircle(Color(0xFF101216), h * 0.36f, Offset(ex, ey))
    drawCircle(Color(0xFF5B6170), h * 0.36f, Offset(ex, ey), style = Stroke(r * 0.05f))
    drawCircle(Brush.radialGradient(listOf(Color(0xFF4DB5FF), Color(0xFF0B2A44)), Offset(ex, ey), h * 0.3f), h * 0.26f, Offset(ex, ey))
    drawCircle(Color(0xBFFFFFFF), h * 0.06f, Offset(ex + cos(t * 1.3f) * h * 0.1f, ey - h * 0.1f))
    if ((t * 2).toInt() % 2 == 0) drawCircle(Color(0xFFFF3B4A), r * 0.05f, Offset(left + w * 0.9f, top + h * 0.2f))
    hand(left + w * 0.12f, top + h * 0.95f, r)
    hand(left + w * 0.95f, top + h * 0.9f, r)
}

private fun DrawScope.drawMagnifier(ex: Float, ey: Float, r: Float, t: Float) {
    val gx = ex + sin(t * 1.6f) * r * 0.05f
    val gr = r * 0.34f
    val hx = gx + gr * 1.5f
    val hy = ey + gr * 1.6f
    drawLine(Color(0xFF8A5A2B), Offset(gx + gr * 0.72f, ey + gr * 0.72f), Offset(hx, hy), strokeWidth = r * 0.13f, cap = StrokeCap.Round)
    drawCircle(Color(0x47AADCFF), gr, Offset(gx, ey))
    drawCircle(Color(0xFFC9CED8), gr, Offset(gx, ey), style = Stroke(r * 0.075f))
    drawOval(Color(0x8CFFFFFF), Offset(gx - gr * 0.57f, ey - gr * 0.5f), Size(gr * 0.44f, gr * 0.24f))
    hand(hx, hy, r)
}
