package `in`.sih26168.idr.ui

import android.content.Intent
import android.provider.Settings
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.derivedStateOf
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import `in`.sih26168.idr.IdrBus
import `in`.sih26168.idr.data.AppMode
import `in`.sih26168.idr.data.HudState
import `in`.sih26168.idr.data.LocationStatus
import `in`.sih26168.idr.data.NavMode
import `in`.sih26168.idr.data.OriginSource
import `in`.sih26168.idr.data.Prefs
import `in`.sih26168.idr.record.RecordService
import `in`.sih26168.idr.sensor.LocationGate
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
import `in`.sih26168.idr.ui.theme.Telem
import `in`.sih26168.idr.ui.theme.Text as Fg

/**
 * The screen a stranger picks up and uses.
 *
 * Priority order on screen, top to bottom: what mode we are in and how much to
 * trust it, the map, the two numbers that matter (speed and distance), the
 * button. Everything a developer wants is real and still available, one tap
 * away behind Diagnostics.
 */
@Composable
fun DriveScreen(
    bus: IdrBus,
    permsOk: Boolean,
    requestPerms: () -> Unit,
    onOpenHelp: () -> Unit,
) {
    val ctx = LocalContext.current
    val hud by bus.hud.collectAsStateWithLifecycle()
    // Separate flow: see the note on TrackSnapshot. The map's geometry must not
    // be re-delivered every time the speed readout ticks.
    val track by bus.track.collectAsStateWithLifecycle()
    val mode by bus.mode.collectAsStateWithLifecycle()
    // Before arming, the HUD carries no location state, so fall back to the
    // standalone gate reading. Otherwise a denied permission would show as
    // "checking" until the user pressed START.
    val idleLocation by bus.location.collectAsStateWithLifecycle()
    val device by bus.device.collectAsStateWithLifecycle()
    val live = mode == AppMode.NAVIGATE
    val locationStatus = if (live) hud.locationStatus else idleLocation
    // navMode is only meaningful while armed; after STOP the last value lingers
    // on the HUD and must not be presented as the current state.
    val navMode = if (live) hud.navMode else NavMode.IDLE
    val prefs = remember { Prefs(ctx) }
    // Asked for at START, where the reason is visible: tracking continues with
    // the screen off, and the ongoing notice is how the user sees that.
    val (notifsOk, requestNotifs) = rememberNotificationGate()
    var showDiagnostics by remember { mutableStateOf(prefs.diagnosticsOpen) }
    var showOriginDialog by remember { mutableStateOf(false) }

    // PERFORMANCE. The big readouts are strings rounded to the nearest whole
    // km/h and metre, so their VALUE changes perhaps twice a second even though
    // the underlying double changes ten times a second. derivedStateOf means
    // BigStat is only recomposed when the text it would print actually differs;
    // formatting in the call arguments recomposed it on every frame.
    val speedText by remember {
        derivedStateOf { if (hud.speedMps.isFinite()) "%.0f".format(hud.speedMps * 3.6) else "--" }
    }
    val distText by remember { derivedStateOf { distanceValue(hud.distanceM) } }
    val distUnit by remember { derivedStateOf { distanceUnit(hud.distanceM) } }

    val view = LocalView.current
    DisposableEffect(live) {
        view.keepScreenOn = live
        onDispose { view.keepScreenOn = false }
    }

    Column(
        Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 16.dp)
            .padding(top = 8.dp, bottom = 16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        // Narrow parameters, so this skips on every frame where the mode did
        // not change -- which is nearly all of them.
        ModeHeader(navMode = navMode, origin = hud.originSource, onOpenHelp = onOpenHelp)

        // A missing or software-fused gyroscope is surfaced on the primary
        // screen, not buried in Help. Failures are shown, never hidden.
        DeviceWarningLine(device)

        LocationBanner(
            status = locationStatus,
            hasAbsolutePosition = hud.hasAbsolutePosition,
            live = live,
            permsOk = permsOk,
            onRequestPerms = requestPerms,
            onOpenSettings = {
                try {
                    ctx.startActivity(
                        Intent(Settings.ACTION_LOCATION_SOURCE_SETTINGS)
                            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK),
                    )
                } catch (_: Exception) {
                    // Some OEM builds hide this activity; the banner text still
                    // tells the user where to go.
                }
            },
            onSetStart = { showOriginDialog = true },
        )

        // DriveMapPanel picks the surface: Google basemap when there is a key,
        // Play services, an absolute position and tiles; the Canvas grid with a
        // one-line reason otherwise. It never shows a blank grey tile.
        DriveMapPanel(
            hud = hud,
            track = track,
            // The completed track stays on screen after STOP, but the mode
            // badge on it must read IDLE rather than the last live mode. This
            // used to be `hud.copy(navMode = ...)`, which allocated a whole
            // HudState on every recomposition of this screen.
            navMode = navMode,
            modifier = Modifier
                .fillMaxWidth()
                .height(300.dp)
                .clip(RoundedCornerShape(16.dp))
                .border(1.dp, Line, RoundedCornerShape(16.dp)),
            onLongPress = { showOriginDialog = true },
        )

        if (live) AccuracyCard(hud)

        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            BigStat(
                label = "SPEED",
                value = speedText,
                unit = "km/h",
                modifier = Modifier.weight(1f),
            )
            BigStat(
                label = "DISTANCE",
                value = distText,
                unit = distUnit,
                modifier = Modifier.weight(1f),
            )
        }

        PrimaryControls(
            live = live,
            permsOk = permsOk,
            onStartStop = {
                if (live) {
                    RecordService.stop(ctx)
                } else {
                    // Deliberately does NOT gate on the location permission. The
                    // whole product claim is that it runs without it. The
                    // notification ask is fire-and-forget for the same reason:
                    // tracking starts either way, the notice is just visible.
                    if (!notifsOk) requestNotifs()
                    RecordService.start(ctx, AppMode.NAVIGATE)
                }
            },
            onRequestPerms = requestPerms,
        )

        if (live) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                SecondaryButton("SET START POINT", Modifier.weight(1f)) { showOriginDialog = true }
                SecondaryButton(
                    if (hud.loopMarked) "CLOSE LOOP" else "MARK HERE",
                    Modifier.weight(1f),
                ) { bus.markRequested = true }
            }
            if (hud.loopMarked) {
                TextButton(onClick = { bus.clearMarkRequested = true }) {
                    Text("Clear mark", fontFamily = IdrSans, color = Mute, fontSize = 12.sp)
                }
            }
        }

        LoopClosureLine(
            closureM = hud.loopClosureM,
            driftPct = hud.driftPct,
            loopMarked = hud.loopMarked,
            loopDistanceM = hud.loopDistanceM,
        )

        TextButton(
            onClick = {
                showDiagnostics = !showDiagnostics
                prefs.diagnosticsOpen = showDiagnostics
            },
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text(
                if (showDiagnostics) "HIDE DIAGNOSTICS" else "DIAGNOSTICS",
                fontFamily = IdrMono,
                color = Mute,
                fontSize = 12.sp,
                letterSpacing = 1.4.sp,
            )
        }
        if (showDiagnostics) DiagnosticsPanel(bus = bus, hud = hud)

        Spacer(Modifier.height(8.dp))
    }

    if (showOriginDialog) {
        StartPointDialog(
            hud = hud,
            onDismiss = { showOriginDialog = false },
            onSet = { lat, lon ->
                bus.requestOrigin(lat, lon, OriginSource.USER_COORDS)
                showOriginDialog = false
            },
            onUseFix = {
                if (hud.lat.isFinite() && hud.lon.isFinite()) {
                    bus.requestOrigin(hud.lat, hud.lon, OriginSource.USER_MAP)
                }
                showOriginDialog = false
            },
            onClear = {
                bus.clearOriginRequested = true
                showOriginDialog = false
            },
        )
    }
}

// ---------------------------------------------------------------------------
// Mode + trust
// ---------------------------------------------------------------------------

@Composable
private fun ModeHeader(navMode: NavMode, origin: OriginSource, onOpenHelp: () -> Unit) {
    Row(
        Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(Modifier.weight(1f)) {
            Text(
                modeTitle(navMode),
                fontFamily = IdrMono,
                color = modeColor(navMode),
                fontSize = 20.sp,
                fontWeight = FontWeight.Bold,
                letterSpacing = 1.5.sp,
            )
            Text(
                modeSubtitle(navMode, origin),
                fontFamily = IdrSans,
                color = Mute,
                fontSize = 13.sp,
                lineHeight = 17.sp,
            )
        }
        Text(
            "HELP",
            modifier = Modifier
                .clip(RoundedCornerShape(99.dp))
                .border(1.dp, Line, RoundedCornerShape(99.dp))
                .clickable(onClick = onOpenHelp)
                .padding(horizontal = 16.dp, vertical = 12.dp),
            color = Mute,
            fontFamily = IdrMono,
            fontSize = 12.sp,
        )
    }
}

private fun modeTitle(mode: NavMode): String = when (mode) {
    NavMode.GNSS -> "GNSS"
    NavMode.DEAD_RECKONING -> "DEAD RECKONING"
    NavMode.RELATIVE -> "RELATIVE"
    NavMode.IDLE -> "READY"
}

private fun modeColor(mode: NavMode) = when (mode) {
    NavMode.GNSS -> Gnss
    NavMode.DEAD_RECKONING -> Accent
    NavMode.RELATIVE -> Amber
    NavMode.IDLE -> Mute
}

private fun modeSubtitle(mode: NavMode, origin: OriginSource): String = when (mode) {
    NavMode.GNSS -> "Live satellite fix. Your position on the map is absolute."
    NavMode.DEAD_RECKONING ->
        "No satellite fix. Position is carried forward from the motion sensors, " +
            "anchored to " + when (origin) {
                OriginSource.GNSS_FIX -> "your last real fix."
                OriginSource.USER_MAP, OriginSource.USER_COORDS -> "the start point you set by hand."
                OriginSource.NONE -> "nothing."
            }
    NavMode.RELATIVE ->
        "No absolute position. Distance travelled and the shape of your route are " +
            "real; where they are on the Earth is not known."
    NavMode.IDLE -> "Press START. The app runs on the motion sensors, with or without GPS."
}

// ---------------------------------------------------------------------------
// Location banner
// ---------------------------------------------------------------------------

@Composable
private fun LocationBanner(
    status: LocationStatus,
    hasAbsolutePosition: Boolean,
    live: Boolean,
    permsOk: Boolean,
    onRequestPerms: () -> Unit,
    onOpenSettings: () -> Unit,
    onSetStart: () -> Unit,
) {
    // Nothing to say once a fix is live and everything is normal.
    if (status == LocationStatus.LIVE) return
    if (status == LocationStatus.UNKNOWN && permsOk) return
    // Before arming, WAITING_FOR_FIX just means "not started yet".
    if (!live && status == LocationStatus.WAITING_FOR_FIX) return

    val tint = when (status) {
        LocationStatus.PERMISSION_DENIED, LocationStatus.SERVICES_OFF -> Danger
        LocationStatus.NO_PROVIDER, LocationStatus.LOST -> Amber
        else -> Mute
    }
    Column(
        Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(12.dp))
            .background(tint.copy(alpha = 0.10f))
            .border(1.dp, tint.copy(alpha = 0.35f), RoundedCornerShape(12.dp))
            .padding(14.dp),
        verticalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        Text(
            LocationGate.headline(status).uppercase(),
            fontFamily = IdrMono,
            color = tint,
            fontSize = 12.sp,
            letterSpacing = 1.2.sp,
        )
        Text(
            LocationGate.explain(status),
            fontFamily = IdrSans,
            color = Fg,
            fontSize = 13.sp,
            lineHeight = 18.sp,
        )
        Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            if (LocationGate.permissionWouldHelp(status)) {
                SecondaryButton("ALLOW LOCATION", Modifier.weight(1f), onRequestPerms)
            }
            if (LocationGate.settingsWouldHelp(status)) {
                SecondaryButton("OPEN SETTINGS", Modifier.weight(1f), onOpenSettings)
            }
            if (live && !hasAbsolutePosition) {
                SecondaryButton("SET START POINT", Modifier.weight(1f), onSetStart)
            }
        }
    }
}

// ---------------------------------------------------------------------------
// Accuracy
// ---------------------------------------------------------------------------

@Composable
private fun AccuracyCard(hud: HudState) {
    val r = hud.uncertaintyM
    val known = r.isFinite() && hud.navMode != NavMode.IDLE
    val tint = when {
        !known -> Mute
        hud.navMode == NavMode.GNSS -> Gnss
        r < 25.0 -> Telem
        r < 100.0 -> Amber
        else -> Danger
    }
    Column(
        Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(12.dp))
            .background(Bg2)
            .border(1.dp, tint.copy(alpha = 0.35f), RoundedCornerShape(12.dp))
            .padding(14.dp),
        verticalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(
                when {
                    !known -> "ACCURACY UNKNOWN"
                    hud.navMode == NavMode.RELATIVE -> "SHAPE ACCURATE TO ± " + metres(r)
                    else -> "ACCURATE TO ± " + metres(r)
                },
                fontFamily = IdrMono,
                color = tint,
                fontSize = 17.sp,
                fontWeight = FontWeight.Bold,
            )
            Spacer(Modifier.weight(1f))
            Text(
                if (hud.navMode == NavMode.GNSS) "MEASURED" else if (known) "MODELLED" else "--",
                fontFamily = IdrMono,
                color = Mute,
                fontSize = 10.sp,
                letterSpacing = 1.2.sp,
            )
        }
        Text(
            if (known) {
                hud.uncertaintyBasis.replaceFirstChar { it.uppercase() } + "."
            } else {
                "Nothing has been measured yet, so no honest figure can be given."
            },
            fontFamily = IdrSans,
            color = Mute,
            fontSize = 12.sp,
            lineHeight = 16.sp,
        )
        if (hud.navMode != NavMode.GNSS && known) {
            Text(
                if (hud.driftRateMeasured) {
                    "Growth rate is this session own measured loop-closure drift."
                } else {
                    "Growth rate is the project benchmark target, not a measurement " +
                        "from this ride. Close a loop with MARK to replace it with a real one."
                },
                fontFamily = IdrSans,
                color = Amber,
                fontSize = 11.sp,
                lineHeight = 15.sp,
            )
        }
    }
}

@Composable
private fun LoopClosureLine(
    closureM: Double?,
    driftPct: Double?,
    loopMarked: Boolean,
    loopDistanceM: Double,
) {
    val closure = closureM
    val text = when {
        closure != null && driftPct != null ->
            "Returned to your mark %.1f m away after %.0f m travelled: %.1f%% drift."
                .format(closure, loopDistanceM, driftPct)
        loopMarked ->
            "Mark set. Ride back to it and press CLOSE LOOP to measure real drift. " +
                "%.0f m out so far.".format(loopDistanceM)
        else -> ""
    }
    if (text.isBlank()) return
    Text(
        text,
        fontFamily = IdrSans,
        color = if (closure != null) Telem else Mute,
        fontSize = 13.sp,
        lineHeight = 18.sp,
    )
}

// ---------------------------------------------------------------------------
// Controls
// ---------------------------------------------------------------------------

@Composable
private fun PrimaryControls(
    live: Boolean,
    permsOk: Boolean,
    onStartStop: () -> Unit,
    onRequestPerms: () -> Unit,
) {
    Button(
        onClick = onStartStop,
        modifier = Modifier
            .fillMaxWidth()
            .height(64.dp),
        colors = ButtonDefaults.buttonColors(
            containerColor = if (live) Danger else Accent,
            contentColor = Bg,
        ),
        shape = RoundedCornerShape(12.dp),
    ) {
        Text(
            if (live) "STOP" else "START",
            fontFamily = IdrMono,
            fontSize = 20.sp,
            fontWeight = FontWeight.Bold,
            letterSpacing = 2.sp,
        )
    }
    if (!permsOk && !live) {
        Text(
            "You can start without granting location. The app will track your route " +
                "from the motion sensors and tell you plainly that the position is relative.",
            fontFamily = IdrSans,
            color = Mute,
            fontSize = 12.sp,
            lineHeight = 16.sp,
            modifier = Modifier.clickable(onClick = onRequestPerms),
        )
    }
}

@Composable
fun SecondaryButton(label: String, modifier: Modifier = Modifier, onClick: () -> Unit) {
    Box(
        modifier
            .height(48.dp)
            .clip(RoundedCornerShape(10.dp))
            .background(Bg2)
            .border(1.dp, Line, RoundedCornerShape(10.dp))
            .clickable(onClick = onClick),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            label,
            fontFamily = IdrMono,
            color = Fg,
            fontSize = 12.sp,
            letterSpacing = 1.sp,
            textAlign = TextAlign.Center,
            modifier = Modifier.padding(horizontal = 8.dp),
        )
    }
}

@Composable
private fun BigStat(label: String, value: String, unit: String, modifier: Modifier = Modifier) {
    Column(
        modifier
            .clip(RoundedCornerShape(12.dp))
            .background(Bg2)
            .border(1.dp, Line, RoundedCornerShape(12.dp))
            .padding(14.dp),
    ) {
        Text(label, fontFamily = IdrMono, color = Mute, fontSize = 10.sp, letterSpacing = 1.6.sp)
        Row(verticalAlignment = Alignment.Bottom) {
            Text(
                value,
                fontFamily = IdrMono,
                color = Fg,
                fontSize = 38.sp,
                fontWeight = FontWeight.Bold,
            )
            Spacer(Modifier.width(6.dp))
            Text(
                unit,
                fontFamily = IdrMono,
                color = Mute,
                fontSize = 13.sp,
                modifier = Modifier.padding(bottom = 7.dp),
            )
        }
    }
}

// ---------------------------------------------------------------------------
// Formatting
// ---------------------------------------------------------------------------

fun metres(r: Double): String = when {
    !r.isFinite() -> "unknown"
    r >= 1000.0 -> "%.1f km".format(r / 1000.0)
    r >= 100.0 -> "%.0f m".format(r)
    r >= 10.0 -> "%.0f m".format(r)
    else -> "%.1f m".format(r)
}

private fun distanceValue(m: Double): String = when {
    !m.isFinite() -> "--"
    m >= 1000.0 -> "%.2f".format(m / 1000.0)
    else -> "%.0f".format(m)
}

private fun distanceUnit(m: Double): String = if (m.isFinite() && m >= 1000.0) "km" else "m"
