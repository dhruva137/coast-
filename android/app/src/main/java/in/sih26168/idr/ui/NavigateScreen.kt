package `in`.sih26168.idr.ui

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
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import `in`.sih26168.idr.IdrBus
import `in`.sih26168.idr.data.AppMode
import `in`.sih26168.idr.record.RecordService
import `in`.sih26168.idr.ui.theme.Accent
import `in`.sih26168.idr.ui.theme.Amber
import `in`.sih26168.idr.ui.theme.Bg
import `in`.sih26168.idr.ui.theme.Bg2
import `in`.sih26168.idr.ui.theme.Danger
import `in`.sih26168.idr.ui.theme.Gnss
import `in`.sih26168.idr.ui.theme.IdrMono
import `in`.sih26168.idr.ui.theme.Line
import `in`.sih26168.idr.ui.theme.Mute
import `in`.sih26168.idr.ui.theme.Telem
import `in`.sih26168.idr.ui.theme.Text as Fg
import kotlin.math.abs

@Composable
fun NavigateScreen(bus: IdrBus, permsOk: Boolean, requestPerms: () -> Unit) {
    val ctx = LocalContext.current
    val hud by bus.hud.collectAsStateWithLifecycle()
    val mode by bus.mode.collectAsStateWithLifecycle()
    val live = mode == AppMode.NAVIGATE
    val view = LocalView.current
    DisposableEffect(live) {
        view.keepScreenOn = live
        onDispose { view.keepScreenOn = false }
    }

    Column(
        Modifier
            .fillMaxSize()
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            Column {
                Text("NAVIGATE", fontFamily = IdrMono, color = Accent, letterSpacing = 3.sp, fontSize = 12.sp)
                Text("lean-aware INS  ·  gyro + speed", color = Mute, fontFamily = IdrMono, fontSize = 11.sp)
            }
            val lockColor = if (hud.gnssLock) Gnss else Amber
            val lockText = if (hud.gnssLock) "GNSS LOCK  ${hud.nSats} SAT" else "GNSS OUT"
            Text(
                lockText,
                modifier = Modifier
                    .clip(RoundedCornerShape(99.dp))
                    .border(1.dp, lockColor.copy(alpha = 0.45f), RoundedCornerShape(99.dp))
                    .padding(horizontal = 10.dp, vertical = 6.dp),
                color = lockColor,
                fontFamily = IdrMono,
                fontSize = 11.sp,
            )
        }

        TrailMap(
            hud = hud,
            modifier = Modifier
                .fillMaxWidth()
                .height(240.dp)
                .clip(RoundedCornerShape(12.dp))
                .border(1.dp, Line, RoundedCornerShape(12.dp)),
        )

        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            HudCell("SPEED", "%.1f".format(hud.speedMps * 3.6), "km/h", Modifier.weight(1f))
            HudCell("LEAN", "%+.1f".format(hud.leanDeg), "deg", Modifier.weight(1f), accent = true)
        }
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            HudCell("HDG", "%.0f".format(hud.headingDeg), "deg N", Modifier.weight(1f))
            HudCell("DIST", "%.0f".format(hud.distanceM), "m", Modifier.weight(1f))
        }
        val disagree = abs(hud.headingDeg - hud.headingCarDeg).let { d -> minOf(d, 360.0 - d) }
        Text(
            "car-style heading Δ ${"%.1f".format(disagree)}°   ·   IMU ${"%.0f".format(hud.imuHz)} Hz   ·   ${if (hud.coordinated) "coordinated" else "not coordinated"}",
            fontFamily = IdrMono,
            color = Mute,
            fontSize = 10.sp,
        )

        val closure = hud.loopClosureM
        val closureLine = when {
            closure != null && hud.driftPct != null ->
                "closure ${"%.1f".format(closure)} m over ${"%.0f".format(hud.loopDistanceM)} m = ${"%.1f".format(hud.driftPct)}%"
            hud.loopMarked ->
                "MARK origin set  ·  tap again at return  ·  ${"%.0f".format(hud.loopDistanceM)} m out"
            else -> "tap MARK at the start point — loop closure is the score"
        }
        Text(closureLine, fontFamily = IdrMono, color = if (closure != null) Telem else Mute, fontSize = 12.sp)

        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(
                onClick = {
                    if (!permsOk) {
                        requestPerms()
                        return@Button
                    }
                    if (live) RecordService.stop(ctx) else RecordService.start(ctx, AppMode.NAVIGATE)
                },
                modifier = Modifier
                    .weight(1f)
                    .height(48.dp),
                colors = ButtonDefaults.buttonColors(
                    containerColor = if (live) Danger else Accent,
                    contentColor = Bg,
                ),
                shape = RoundedCornerShape(8.dp),
            ) {
                Text(if (live) "STOP" else "ARM", fontFamily = IdrMono, letterSpacing = 1.2.sp)
            }
            Button(
                onClick = {
                    if (live) {
                        bus.markRequested = true
                    } else if (permsOk) {
                        RecordService.start(ctx, AppMode.NAVIGATE)
                    } else {
                        requestPerms()
                    }
                },
                modifier = Modifier
                    .weight(1f)
                    .height(48.dp),
                colors = ButtonDefaults.buttonColors(containerColor = Telem, contentColor = Bg),
                shape = RoundedCornerShape(8.dp),
                enabled = live || permsOk,
            ) {
                Text("MARK", fontFamily = IdrMono, letterSpacing = 1.2.sp)
            }
        }
        TextButton(onClick = { bus.clearMarkRequested = true }) {
            Text("RESET MARK", fontFamily = IdrMono, color = Mute, fontSize = 11.sp)
        }
        if (!permsOk) {
            Text("Grant location to arm the estimator.", color = Danger, fontSize = 12.sp)
        }
    }
}

@Composable
private fun HudCell(
    label: String,
    value: String,
    unit: String,
    modifier: Modifier = Modifier,
    accent: Boolean = false,
) {
    Column(
        modifier
            .clip(RoundedCornerShape(10.dp))
            .background(Bg2)
            .border(1.dp, Line, RoundedCornerShape(10.dp))
            .padding(12.dp),
    ) {
        Text(label, fontFamily = IdrMono, color = Mute, fontSize = 10.sp, letterSpacing = 1.6.sp)
        Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            Text(value, fontFamily = IdrMono, color = if (accent) Accent else Fg, fontSize = 28.sp)
            Text(unit, fontFamily = IdrMono, color = Mute, fontSize = 12.sp, modifier = Modifier.padding(top = 12.dp))
        }
    }
}
