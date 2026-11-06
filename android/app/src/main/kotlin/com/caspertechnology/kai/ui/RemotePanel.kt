package com.caspertechnology.kai.ui

import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.caspertechnology.kai.R
import com.caspertechnology.kai.app.AppModel
import com.caspertechnology.kai.core.Spacing
import com.caspertechnology.kai.core.TypeScale
import com.caspertechnology.kai.link.LinkState

/** Kai's Home: look at the computer's screen or camera from here. */
@Composable
fun RemotePanel(model: AppModel, onView: (String) -> Unit) {
    val t = tokens()
    val connected = model.linkState == LinkState.CONNECTED
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        SectionHeading(stringResource(R.string.remote_title))
        Panel {
            Column(Modifier.fillMaxWidth().padding(Spacing.INSIDE.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Text(
                    stringResource(
                        when {
                            !connected -> R.string.remote_offline
                            !model.viewOffered -> R.string.remote_turn_on
                            else -> R.string.remote_body
                        },
                    ),
                    style = TypeScale.SECONDARY.style(t.textDim.c()),
                )
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    val enabled = connected && model.viewOffered
                    PillButton(stringResource(R.string.view_screen_button), onClick = { onView("screen") }, Modifier.weight(1f), kind = PillKind.PRIMARY, enabled = enabled)
                    PillButton(stringResource(R.string.view_camera_button), onClick = { onView("camera") }, Modifier.weight(1f), enabled = enabled)
                }
            }
        }
    }
}

/** A newer Kai is on GitHub: one tap opens its download. */
@Composable
fun UpdatePanel(model: AppModel) {
    val update = model.update ?: return
    val t = tokens()
    val context = LocalContext.current
    Panel {
        Column(Modifier.fillMaxWidth().padding(Spacing.INSIDE.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Text(stringResource(R.string.update_title, update.version), style = TypeScale.HEADLINE.style(t.text.c()))
            Text(stringResource(R.string.update_body), style = TypeScale.SECONDARY.style(t.textDim.c()))
            PillButton(
                stringResource(R.string.update_button),
                onClick = { context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(update.url)).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) },
                Modifier.fillMaxWidth(), kind = PillKind.PRIMARY,
            )
        }
    }
}

/** Nothing is running on the computer yet: what Kai does, instead of an empty page. */
@Composable
fun IdlePanel() {
    val t = tokens()
    Panel {
        Column(Modifier.fillMaxWidth().padding(Spacing.INSIDE.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(stringResource(R.string.idle_title), style = TypeScale.HEADLINE.style(t.text.c()))
            for (line in listOf(R.string.idle_line_approvals, R.string.idle_line_questions, R.string.idle_line_view, R.string.idle_line_widgets)) {
                Text("•  " + stringResource(line), style = TypeScale.SECONDARY.style(t.textDim.c()))
            }
        }
    }
}
