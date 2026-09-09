package `in`.sih26168.idr.ui

import android.content.Intent
import android.widget.Toast
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
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
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import `in`.sih26168.idr.record.QualityVerdict
import `in`.sih26168.idr.record.SessionStore
import `in`.sih26168.idr.record.SessionSummary
import `in`.sih26168.idr.record.SessionTrackPoint
import `in`.sih26168.idr.ui.theme.Accent
import `in`.sih26168.idr.ui.theme.Bg
import `in`.sih26168.idr.ui.theme.Bg2
import `in`.sih26168.idr.ui.theme.Danger
import `in`.sih26168.idr.ui.theme.Gnss
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
import kotlin.math.max
import kotlin.math.min

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
    var detail by remember { mutableStateOf<SessionSummary?>(null) }
    var detailTrack by remember { mutableStateOf<List<SessionTrackPoint>>(emptyList()) }

    fun refresh() {
        scope.launch {
            busy = true
            sessions = withContext(Dispatchers.IO) { SessionStore.listSessions(ctx) }
            busy = false
        }
    }

    LaunchedEffect(Unit) { refresh() }

    LaunchedEffect(detail?.dir?.absolutePath) {
        val d = detail ?: return@LaunchedEffect
        detailTrack = emptyList()
        detailTrack = withContext(Dispatchers.IO) { SessionStore.loadSessionTrack(d.dir) }
    }

    val selected = detail
    if (selected != null) {
        SessionDetailScreen(
            s = selected,
            track = detailTrack,
            busy = busy,
            onBack = { detail = null },
            onCheck = {
                scope.launch {
                    busy = true
                    val (report, updated) = withContext(Dispatchers.IO) {
                        val r = SessionStore.evaluateAndPersist(selected.dir)
                        r to SessionStore.summarize(selected.dir)
                    }
                    message = report.summary
                    detail = updated
                    refresh()
                    busy = false
                }
            },
            onRename = {
                renameTarget = selected
                renameText = selected.name
            },
            onDelete = { deleteTarget = selected },
            onShare = {
                scope.launch {
                    busy = true
                    try {
                        val zip = withContext(Dispatchers.IO) {
                            SessionStore.evaluateAndPersist(selected.dir)
                            SessionStore.zipSession(selected.dir)
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
    } else {
        SessionListPane(
            sessions = sessions,
            busy = busy,
            message = message,
            onRefresh = { refresh() },
            onRescoreAll = {
                scope.launch {
                    busy = true
                    withContext(Dispatchers.IO) {
                        sessions.forEach { SessionStore.evaluateAndPersist(it.dir) }
                    }
                    refresh()
                    message = "Re-scored ${sessions.size} sessions"
                }
            },
            onOpen = { detail = it },
        )
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
                            val dest = withContext(Dispatchers.IO) {
                                SessionStore.renameSession(target.dir, renameText)
                            }
                            renameTarget = null
                            if (detail?.dir?.absolutePath == target.dir.absolutePath) {
                                detail = withContext(Dispatchers.IO) { SessionStore.summarize(dest) }
                            }
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
                        if (detail?.dir?.absolutePath == target.dir.absolutePath) detail = null
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
private fun SessionListPane(
    sessions: List<SessionSummary>,
    busy: Boolean,
    message: String?,
    onRefresh: () -> Unit,
    onRescoreAll: () -> Unit,
    onOpen: (SessionSummary) -> Unit,
) {
    val ctx = LocalContext.current
    Column(
        Modifier
            .fillMaxSize()
            .background(Bg)
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text("SESSIONS", fontFamily = IdrMono, color = Accent, letterSpacing = 3.sp, fontSize = 12.sp)
        Text(
            "Past rides — tap a session to see its track.",
            color = Mute,
            fontFamily = IdrSans,
            fontSize = 13.sp,
        )
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(
                onClick = onRefresh,
                enabled = !busy,
                colors = ButtonDefaults.buttonColors(containerColor = Accent, contentColor = Bg),
                shape = RoundedCornerShape(8.dp),
            ) {
                Text("REFRESH", fontFamily = IdrMono, fontSize = 11.sp)
            }
            Button(
                onClick = onRescoreAll,
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
                    SessionHistoryCard(s = s, onClick = { onOpen(s) })
                }
            }
        }
    }
}

@Composable
private fun SessionHistoryCard(s: SessionSummary, onClick: () -> Unit) {
    val whenStr = SimpleDateFormat("yyyy-MM-dd HH:mm", Locale.US).format(Date(s.modifiedMs))
    val duration = formatDuration(s.durationSec)
    val distance = formatDistance(s.distanceM)
    val drift = s.maxDriftSinceFixM?.let { "%.0f m".format(it) } ?: "—"
    val q = s.quality
    val verdictColor = when (q?.verdict) {
        QualityVerdict.KEEP -> Telem
        QualityVerdict.RETRY -> Accent
        QualityVerdict.FAIL -> Danger
        null -> Mute
    }

    Column(
        Modifier
            .fillMaxWidth()
            .background(Bg2, RoundedCornerShape(10.dp))
            .border(1.dp, Line, RoundedCornerShape(10.dp))
            .clickable(onClick = onClick)
            .padding(12.dp),
        verticalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        Row(
            Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(s.name, fontFamily = IdrMono, color = Fg, fontSize = 13.sp, modifier = Modifier.weight(1f))
            Text(whenStr, fontFamily = IdrMono, color = Mute, fontSize = 10.sp)
        }
        Text(
            s.vehicle.ifBlank { "—" },
            fontFamily = IdrSans,
            color = Accent,
            fontSize = 12.sp,
        )
        Row(
            Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
        ) {
            MetricChip("DURATION", duration)
            MetricChip("DISTANCE", distance)
            MetricChip("MAX DRIFT", drift)
        }
        if (q != null) {
            Text(q.summary, fontFamily = IdrMono, color = verdictColor, fontSize = 10.sp)
        }
    }
}

@Composable
private fun MetricChip(label: String, value: String) {
    Column(horizontalAlignment = Alignment.Start) {
        Text(label, fontFamily = IdrMono, color = Mute, fontSize = 8.sp, letterSpacing = 0.6.sp)
        Text(value, fontFamily = IdrMono, color = Fg, fontSize = 12.sp)
    }
}

@Composable
private fun SessionDetailScreen(
    s: SessionSummary,
    track: List<SessionTrackPoint>,
    busy: Boolean,
    onBack: () -> Unit,
    onCheck: () -> Unit,
    onRename: () -> Unit,
    onDelete: () -> Unit,
    onShare: () -> Unit,
) {
    val whenStr = SimpleDateFormat("yyyy-MM-dd HH:mm", Locale.US).format(Date(s.modifiedMs))
    val hasIdr = track.any { !it.fromGnss }
    val hasGnss = track.any { it.fromGnss }

    Column(
        Modifier
            .fillMaxSize()
            .background(Bg)
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Row(
            Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text(
                "← BACK",
                modifier = Modifier
                    .background(Bg2, RoundedCornerShape(8.dp))
                    .border(1.dp, Line, RoundedCornerShape(8.dp))
                    .clickable(onClick = onBack)
                    .padding(horizontal = 12.dp, vertical = 8.dp),
                color = Mute,
                fontFamily = IdrMono,
                fontSize = 11.sp,
            )
            Column(Modifier.weight(1f)) {
                Text(s.name, fontFamily = IdrMono, color = Fg, fontSize = 14.sp)
                Text("$whenStr · ${s.vehicle}", fontFamily = IdrSans, color = Mute, fontSize = 12.sp)
            }
        }

        Row(
            Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
        ) {
            MetricChip("DURATION", formatDuration(s.durationSec))
            MetricChip("DISTANCE", formatDistance(s.distanceM))
            MetricChip("MAX DRIFT", s.maxDriftSinceFixM?.let { "%.0f m".format(it) } ?: "—")
        }

        Box(
            Modifier
                .fillMaxWidth()
                .weight(1f)
                .background(Bg2, RoundedCornerShape(12.dp))
                .border(1.dp, Line, RoundedCornerShape(12.dp)),
        ) {
            if (track.isEmpty()) {
                Text(
                    "No track points in this session.",
                    color = Mute,
                    fontFamily = IdrSans,
                    modifier = Modifier.align(Alignment.Center).padding(16.dp),
                )
            } else {
                SessionTrackMap(track = track, modifier = Modifier.fillMaxSize().padding(8.dp))
            }
            Row(
                Modifier
                    .align(Alignment.BottomStart)
                    .padding(10.dp),
                horizontalArrangement = Arrangement.spacedBy(12.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                LegendDot(Gnss, "GNSS")
                LegendDot(Accent, if (hasIdr) "IDR" else "IDR (not logged)")
            }
        }

        if (!hasIdr && hasGnss) {
            Text(
                "Field logs store GNSS fixes only — teal IDR segments appear when trail.csv is present.",
                color = Mute,
                fontFamily = IdrSans,
                fontSize = 11.sp,
            )
        }

        Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            SmallBtn("CHECK", !busy, Telem, onCheck)
            SmallBtn("RENAME", !busy, Accent, onRename)
            SmallBtn("ZIP", !busy, Accent, onShare)
            SmallBtn("DELETE", !busy, Danger, onDelete)
        }
    }
}

@Composable
private fun LegendDot(color: androidx.compose.ui.graphics.Color, label: String) {
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
        Box(Modifier.size(8.dp).background(color, CircleShape))
        Text(label, fontFamily = IdrMono, color = Mute, fontSize = 9.sp)
    }
}

/**
 * Static session track: GNSS blue (#4FC3F7) / IDR teal (#00E0A4).
 * Local EN projection — no network, no MapLibre.
 */
@Composable
fun SessionTrackMap(
    track: List<SessionTrackPoint>,
    modifier: Modifier = Modifier,
) {
    val en = remember(track) { SessionStore.toLocalEn(track) }
    val flags = remember(track) { track.map { it.fromGnss } }
    Canvas(modifier = modifier) {
        if (en.size < 2) return@Canvas
        var minE = Float.POSITIVE_INFINITY
        var maxE = Float.NEGATIVE_INFINITY
        var minN = Float.POSITIVE_INFINITY
        var maxN = Float.NEGATIVE_INFINITY
        for ((e, n) in en) {
            minE = min(minE, e); maxE = max(maxE, e)
            minN = min(minN, n); maxN = max(maxN, n)
        }
        val pad = 24f
        val spanE = max(maxE - minE, 8f)
        val spanN = max(maxN - minN, 8f)
        val scale = min((size.width - 2 * pad) / spanE, (size.height - 2 * pad) / spanN)
        val cx = (minE + maxE) / 2f
        val cy = (minN + maxN) / 2f
        fun px(e: Float, n: Float) = Offset(
            size.width / 2f + (e - cx) * scale,
            size.height / 2f - (n - cy) * scale,
        )

        // Contiguous runs by fromGnss → GNSS blue / IDR teal.
        var i = 0
        while (i < en.size) {
            val gnss = flags.getOrElse(i) { true }
            var j = i + 1
            while (j < en.size && flags.getOrElse(j) { true } == gnss) j++
            val color = if (gnss) Gnss else Accent
            if (j - i >= 2) {
                val path = Path()
                val p0 = px(en[i].first, en[i].second)
                path.moveTo(p0.x, p0.y)
                for (k in i + 1 until j) {
                    val p = px(en[k].first, en[k].second)
                    path.lineTo(p.x, p.y)
                }
                drawPath(path, color, style = Stroke(width = if (gnss) 4f else 5.5f, cap = StrokeCap.Round))
            } else {
                drawCircle(color, 3.5f, px(en[i].first, en[i].second))
            }
            i = j
        }

        // Start / end markers.
        val start = px(en.first().first, en.first().second)
        val end = px(en.last().first, en.last().second)
        drawCircle(Mute, 5f, start)
        drawCircle(Accent, 6f, end)
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

private fun formatDuration(sec: Double?): String {
    if (sec == null || !sec.isFinite() || sec < 0) return "—"
    val s = sec.toInt()
    val m = s / 60
    val r = s % 60
    return if (m >= 60) "%dh %02dm".format(m / 60, m % 60) else "%d:%02d".format(m, r)
}

private fun formatDistance(m: Double?): String {
    if (m == null || !m.isFinite() || m < 0) return "—"
    return if (m >= 1000) "%.2f km".format(m / 1000.0) else "%.0f m".format(m)
}
