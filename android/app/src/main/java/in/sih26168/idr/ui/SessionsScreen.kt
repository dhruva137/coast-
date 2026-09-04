package `in`.sih26168.idr.ui

import android.content.Intent
import android.widget.Toast
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import `in`.sih26168.idr.record.QualityVerdict
import `in`.sih26168.idr.record.SessionStore
import `in`.sih26168.idr.record.SessionSummary
import `in`.sih26168.idr.ui.theme.Accent
import `in`.sih26168.idr.ui.theme.Bg
import `in`.sih26168.idr.ui.theme.Bg2
import `in`.sih26168.idr.ui.theme.Danger
import `in`.sih26168.idr.ui.theme.IdrMono
import `in`.sih26168.idr.ui.theme.IdrSans
import `in`.sih26168.idr.ui.theme.Line
import `in`.sih26168.idr.ui.theme.Mute
import `in`.sih26168.idr.ui.theme.Telem
import `in`.sih26168.idr.ui.theme.Text as Fg
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

@Composable
fun SessionsScreen() {
    val ctx = LocalContext.current
    val scope = rememberCoroutineScope()
    var sessions by remember { mutableStateOf<List<SessionSummary>>(emptyList()) }
    var busy by remember { mutableStateOf(false) }
    var renameTarget by remember { mutableStateOf<SessionSummary?>(null) }
    var renameText by remember { mutableStateOf("") }
    var deleteTarget by remember { mutableStateOf<SessionSummary?>(null) }
    var message by remember { mutableStateOf<String?>(null) }

    fun refresh() {
        scope.launch {
            busy = true
            sessions = withContext(Dispatchers.IO) { SessionStore.listSessions(ctx) }
            busy = false
        }
    }

    LaunchedEffect(Unit) { refresh() }

    Column(
        Modifier
            .fillMaxSize()
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text("SESSIONS", fontFamily = IdrMono, color = Accent, letterSpacing = 3.sp, fontSize = 12.sp)
        Text(
            "Quality-check, rename, delete, and zip/share field logs before upload.",
            color = Mute,
            fontFamily = IdrSans,
            fontSize = 13.sp,
        )
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(
                onClick = { refresh() },
                enabled = !busy,
                colors = ButtonDefaults.buttonColors(containerColor = Accent, contentColor = Bg),
                shape = RoundedCornerShape(8.dp),
            ) {
                Text("REFRESH", fontFamily = IdrMono, fontSize = 11.sp)
            }
            Button(
                onClick = {
                    scope.launch {
                        busy = true
                        withContext(Dispatchers.IO) {
                            sessions.forEach { SessionStore.evaluateAndPersist(it.dir) }
                        }
                        refresh()
                        message = "Re-scored ${sessions.size} sessions"
                    }
                },
                enabled = !busy && sessions.isNotEmpty(),
                colors = ButtonDefaults.buttonColors(containerColor = Telem, contentColor = Bg),
                shape = RoundedCornerShape(8.dp),
            ) {
                Text("RE-SCORE ALL", fontFamily = IdrMono, fontSize = 11.sp)
            }
        }
        message?.let {
            Text(it, color = Telem, fontFamily = IdrMono, fontSize = 11.sp)
        }
        Text(
            SessionStore.logsRoot(ctx).absolutePath,
            fontFamily = IdrMono,
            color = Mute,
            fontSize = 9.sp,
        )

        if (sessions.isEmpty()) {
            Text(
                if (busy) "Scanning…" else "No sessions yet. RECORD a loop first.",
                color = Mute,
                fontFamily = IdrSans,
            )
        } else {
            LazyColumn(
                verticalArrangement = Arrangement.spacedBy(10.dp),
                modifier = Modifier.fillMaxSize(),
            ) {
                items(sessions, key = { it.dir.absolutePath }) { s ->
                    SessionCard(
                        s = s,
                        enabled = !busy,
                        onCheck = {
                            scope.launch {
                                busy = true
                                val r = withContext(Dispatchers.IO) {
                                    SessionStore.evaluateAndPersist(s.dir)
                                }
                                message = r.summary
                                refresh()
                            }
                        },
                        onRename = {
                            renameTarget = s
                            renameText = s.name
                        },
                        onDelete = { deleteTarget = s },
                        onShare = {
                            scope.launch {
                                busy = true
                                try {
                                    val zip = withContext(Dispatchers.IO) {
                                        SessionStore.evaluateAndPersist(s.dir)
                                        SessionStore.zipSession(s.dir)
                                    }
                                    ctx.startActivity(Intent.createChooser(SessionStore.shareIntent(ctx, zip), "Share session"))
                                } catch (e: Exception) {
                                    Toast.makeText(ctx, e.message ?: "share failed", Toast.LENGTH_LONG).show()
                                } finally {
                                    busy = false
                                }
                            }
                        },
                    )
                }
            }
        }
    }

    renameTarget?.let { target ->
        val colors = OutlinedTextFieldDefaults.colors(
            focusedBorderColor = Accent,
            unfocusedBorderColor = Line,
            focusedLabelColor = Accent,
            unfocusedLabelColor = Mute,
            cursorColor = Accent,
            focusedTextColor = Fg,
            unfocusedTextColor = Fg,
        )
        AlertDialog(
            onDismissRequest = { renameTarget = null },
            title = { Text("Rename session", fontFamily = IdrSans, color = Fg) },
            text = {
                OutlinedTextField(
                    value = renameText,
                    onValueChange = { renameText = it },
                    label = { Text("folder name") },
                    singleLine = true,
                    colors = colors,
                    modifier = Modifier.fillMaxWidth(),
                )
            },
            confirmButton = {
                TextButton(onClick = {
                    scope.launch {
                        try {
                            withContext(Dispatchers.IO) {
                                SessionStore.renameSession(target.dir, renameText)
                            }
                            renameTarget = null
                            refresh()
                        } catch (e: Exception) {
                            Toast.makeText(ctx, e.message ?: "rename failed", Toast.LENGTH_LONG).show()
                        }
                    }
                }) { Text("SAVE", color = Accent, fontFamily = IdrMono) }
            },
            dismissButton = {
                TextButton(onClick = { renameTarget = null }) {
                    Text("CANCEL", color = Mute, fontFamily = IdrMono)
                }
            },
            containerColor = Bg2,
        )
    }

    deleteTarget?.let { target ->
        AlertDialog(
            onDismissRequest = { deleteTarget = null },
            title = { Text("Delete session?", fontFamily = IdrSans, color = Fg) },
            text = {
                Text(
                    "Permanently delete ${target.name} (${target.imuRows} IMU / ${target.gnssRows} GNSS).",
                    color = Mute,
                    fontFamily = IdrSans,
                )
            },
            confirmButton = {
                TextButton(onClick = {
                    scope.launch {
                        withContext(Dispatchers.IO) { SessionStore.deleteSession(target.dir) }
                        deleteTarget = null
                        refresh()
                    }
                }) { Text("DELETE", color = Danger, fontFamily = IdrMono) }
            },
            dismissButton = {
                TextButton(onClick = { deleteTarget = null }) {
                    Text("CANCEL", color = Mute, fontFamily = IdrMono)
                }
            },
            containerColor = Bg2,
        )
    }
}

@Composable
private fun SessionCard(
    s: SessionSummary,
    enabled: Boolean,
    onCheck: () -> Unit,
    onRename: () -> Unit,
    onDelete: () -> Unit,
    onShare: () -> Unit,
) {
    val q = s.quality
    val verdictColor = when (q?.verdict) {
        QualityVerdict.KEEP -> Telem
        QualityVerdict.RETRY -> Accent
        QualityVerdict.FAIL -> Danger
        null -> Mute
    }
    val whenStr = SimpleDateFormat("yyyy-MM-dd HH:mm", Locale.US).format(Date(s.modifiedMs))
    val hz = if (s.imuHz.isFinite()) "%.0f".format(s.imuHz) else "—"

    Column(
        Modifier
            .fillMaxWidth()
            .background(Bg2, RoundedCornerShape(10.dp))
            .border(1.dp, Line, RoundedCornerShape(10.dp))
            .padding(12.dp),
        verticalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        Text(s.name, fontFamily = IdrMono, color = Fg, fontSize = 13.sp)
        Text(
            "${s.rider} · ${s.vehicle} · ${s.mount} · ${s.routeId}",
            fontFamily = IdrMono,
            color = Mute,
            fontSize = 10.sp,
        )
        Text(
            "$whenStr · IMU ${s.imuRows} @ ~${hz} Hz · GNSS ${s.gnssRows}",
            fontFamily = IdrMono,
            color = Mute,
            fontSize = 10.sp,
        )
        Text(
            q?.summary ?: "NOT SCORED — tap CHECK",
            fontFamily = IdrMono,
            color = verdictColor,
            fontSize = 11.sp,
        )
        if (q != null && q.issues.isNotEmpty()) {
            Text(
                q.issues.joinToString(" · ") { it.code },
                fontFamily = IdrMono,
                color = Mute,
                fontSize = 9.sp,
            )
        }
        Spacer(Modifier.height(2.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            SmallBtn("CHECK", enabled, Telem, onCheck)
            SmallBtn("RENAME", enabled, Accent, onRename)
            SmallBtn("ZIP", enabled, Accent, onShare)
            SmallBtn("DELETE", enabled, Danger, onDelete)
        }
    }
}

@Composable
private fun SmallBtn(label: String, enabled: Boolean, color: androidx.compose.ui.graphics.Color, onClick: () -> Unit) {
    Button(
        onClick = onClick,
        enabled = enabled,
        colors = ButtonDefaults.buttonColors(containerColor = color.copy(alpha = 0.2f), contentColor = color),
        shape = RoundedCornerShape(6.dp),
        modifier = Modifier.height(36.dp),
        contentPadding = androidx.compose.foundation.layout.PaddingValues(horizontal = 10.dp, vertical = 0.dp),
    ) {
        Text(label, fontFamily = IdrMono, fontSize = 10.sp, letterSpacing = 0.8.sp)
    }
}
