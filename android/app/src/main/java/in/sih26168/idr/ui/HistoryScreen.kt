package `in`.sih26168.idr.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.defaultMinSize
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import `in`.sih26168.idr.ui.theme.Accent
import `in`.sih26168.idr.ui.theme.Amber
import `in`.sih26168.idr.ui.theme.Bg
import `in`.sih26168.idr.ui.theme.Bg2
import `in`.sih26168.idr.ui.theme.Danger
import `in`.sih26168.idr.ui.theme.Gnss
import `in`.sih26168.idr.ui.theme.IdrMono
import `in`.sih26168.idr.ui.theme.IdrSans
import `in`.sih26168.idr.ui.theme.Line
import `in`.sih26168.idr.ui.theme.Mute
import `in`.sih26168.idr.ui.theme.Text as Fg
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

@Composable
fun HistoryScreen(onBack: (() -> Unit)? = null) {
    val ctx = LocalContext.current
    var reloadTick by remember { mutableIntStateOf(0) }
    val events = remember(reloadTick) { SignalHistory.read(ctx) }
    val df = remember { SimpleDateFormat("dd MMM · HH:mm:ss", Locale.US) }

    Column(
        Modifier
            .fillMaxSize()
            .background(Bg)
            .padding(horizontal = 16.dp, vertical = 12.dp),
    ) {
        if (onBack != null) {
            Text(
                "← BACK",
                modifier = Modifier
                    .semantics { contentDescription = "Back" }
                    .clickable(onClick = onBack)
                    .padding(vertical = 6.dp),
                fontFamily = IdrMono,
                color = Accent,
                fontSize = 11.sp,
                letterSpacing = 1.sp,
            )
        }

        Row(
            Modifier.fillMaxWidth().padding(top = 6.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(Modifier.weight(1f)) {
                Text(
                    "Signal history",
                    fontFamily = IdrSans,
                    color = Fg,
                    fontSize = 22.sp,
                    fontWeight = FontWeight.SemiBold,
                )
                Text(
                    "GNSS loss and regain events, session starts and ends. " +
                        "Coordinates are the last absolute fix the estimator held.",
                    fontFamily = IdrSans,
                    color = Mute,
                    fontSize = 12.sp,
                )
            }
            if (events.isNotEmpty()) {
                Text(
                    "CLEAR",
                    modifier = Modifier
                        .defaultMinSize(minHeight = 44.dp)
                        .clip(RoundedCornerShape(8.dp))
                        .clickable {
                            SignalHistory.clear(ctx)
                            reloadTick++
                        }
                        .padding(horizontal = 10.dp, vertical = 10.dp)
                        .semantics { contentDescription = "Clear history" },
                    fontFamily = IdrMono,
                    color = Danger,
                    fontSize = 11.sp,
                    letterSpacing = 1.0.sp,
                    fontWeight = FontWeight.Bold,
                )
            }
        }

        Spacer(Modifier.size(12.dp))

        if (events.isEmpty()) {
            Column(
                Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(12.dp))
                    .background(Bg2)
                    .border(1.dp, Line, RoundedCornerShape(12.dp))
                    .padding(20.dp),
                verticalArrangement = Arrangement.spacedBy(4.dp),
            ) {
                Text(
                    "Nothing yet.",
                    fontFamily = IdrSans,
                    color = Fg,
                    fontSize = 15.sp,
                    fontWeight = FontWeight.Medium,
                )
                Text(
                    "Start a drive from DRIVE. Every time GNSS drops or reacquires, " +
                        "the event lands here with the last known coordinates.",
                    fontFamily = IdrSans,
                    color = Mute,
                    fontSize = 12.sp,
                    lineHeight = 17.sp,
                )
            }
            return@Column
        }

        LazyColumn(
            Modifier.fillMaxSize(),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            items(events) { ev ->
                EventRow(event = ev, timestamp = df.format(Date(ev.atMs)))
            }
        }
    }
}

@Composable
private fun EventRow(event: SignalHistory.Event, timestamp: String) {
    val (label, tint) = when (event.kind) {
        SignalHistory.KIND_GNSS_LOST -> "GNSS LOST" to Amber
        SignalHistory.KIND_GNSS_REACQUIRED -> "GNSS REACQUIRED" to Gnss
        SignalHistory.KIND_SESSION_START -> "SESSION START" to Accent
        SignalHistory.KIND_SESSION_END -> "SESSION END" to Mute
        SignalHistory.KIND_SHAKE_RECORDING -> "SHAKE TRACE" to Accent
        else -> event.kind.uppercase() to Mute
    }
    Row(
        Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(10.dp))
            .background(Bg2)
            .border(1.dp, Line, RoundedCornerShape(10.dp))
            .padding(horizontal = 12.dp, vertical = 10.dp),
        verticalAlignment = Alignment.Top,
        horizontalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Box(
            Modifier
                .padding(top = 4.dp)
                .size(10.dp)
                .clip(CircleShape)
                .background(tint),
        )
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text(
                label,
                fontFamily = IdrMono,
                color = tint,
                fontSize = 11.sp,
                letterSpacing = 1.0.sp,
                fontWeight = FontWeight.Bold,
            )
            Text(
                timestamp,
                fontFamily = IdrMono,
                color = Fg,
                fontSize = 13.sp,
            )
            val lat = event.lat
            val lon = event.lon
            if (lat != null && lon != null && lat.isFinite() && lon.isFinite()) {
                Text(
                    "%.5f, %.5f".format(Locale.US, lat, lon) +
                        (event.nSats?.let { " · $it sats" } ?: ""),
                    fontFamily = IdrMono,
                    color = Mute,
                    fontSize = 11.sp,
                )
            } else {
                Text(
                    "no absolute fix at this moment" +
                        (event.nSats?.let { " · $it sats" } ?: ""),
                    fontFamily = IdrSans,
                    color = Mute,
                    fontSize = 11.sp,
                )
            }
            event.note?.let {
                Text(it, fontFamily = IdrSans, color = Mute, fontSize = 11.sp)
            }
        }
    }
}
