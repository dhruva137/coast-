package `in`.sih26168.idr.ui

import android.content.Intent
import android.provider.Settings
import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectVerticalDragGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
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
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.pointer.pointerInput
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
 * Full-screen Uber-black drive map. The basemap is the bottom layer; HUD,
 * controls, and the bottom sheet float over it. Nothing steals height from the
 * map (the old 300.dp box is gone).
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
    val track by bus.track.collectAsStateWithLifecycle()
    val mode by bus.mode.collectAsStateWithLifecycle()
    val idleLocation by bus.location.collectAsStateWithLifecycle()
    val device by bus.device.collectAsStateWithLifecycle()
    val blackout by bus.gnssBlackout.collectAsStateWithLifecycle()
    val replayEnabled by bus.replayEnabled.collectAsStateWithLifecycle()
    val replayActive by bus.replayActive.collectAsStateWithLifecycle()
    val live = mode == AppMode.NAVIGATE
    val locationStatus = if (live) hud.locationStatus else idleLocation
    val navMode = if (live) hud.navMode else NavMode.IDLE
    val prefs = remember { Prefs(ctx) }
    val (notifsOk, requestNotifs) = rememberNotificationGate()
    var sheetExpanded by remember { mutableStateOf(prefs.diagnosticsOpen) }
    var showOriginDialog by remember { mutableStateOf(false) }

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

    Box(Modifier.fillMaxSize()) {
        // Bottom layer: map fills the entire drive viewport.
        DriveMapPanel(
            hud = hud,
            track = track,
            navMode = navMode,
            modifier = Modifier.fillMaxSize(),
            mapModifier = Modifier.fillMaxSize(),
            onLongPress = { showOriginDialog = true },
            showBasemapToggle = true,
        )

        // Top overlays (status-bar safe).
        Column(
            Modifier
                .align(Alignment.TopCenter)
                .fillMaxWidth()
                .statusBarsPadding()
                .padding(horizontal = 12.dp, vertical = 8.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Row(
                Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    "HELP",
                    modifier = Modifier
                        .clip(RoundedCornerShape(99.dp))
                        .background(Bg2.copy(alpha = 0.88f))
                        .border(1.dp, Line, RoundedCornerShape(99.dp))
                        .clickable(onClick = onOpenHelp)
                        .padding(horizontal = 14.dp, vertical = 10.dp),
                    color = Mute,
                    fontFamily = IdrMono,
                    fontSize = 11.sp,
                )
                ModePill(navMode = navMode, nSats = hud.nSats, live = live)
                // Balance the HELP chip so the pill stays visually centred.
                Spacer(Modifier.width(64.dp))
            }

            if (replayActive || replayEnabled) {
                Text(
                    "REPLAY — real dataset, real estimator",
                    modifier = Modifier
                        .clip(RoundedCornerShape(99.dp))
                        .background(Bg2.copy(alpha = 0.92f))
                        .border(1.dp, Amber.copy(alpha = 0.45f), RoundedCornerShape(99.dp))
                        .padding(horizontal = 12.dp, vertical = 6.dp),
                    color = Amber,
                    fontFamily = IdrMono,
                    fontSize = 10.sp,
                    letterSpacing = 1.0.sp,
                )
            }

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
                    }
                },
                onSetStart = { showOriginDialog = true },
            )
        }

        // Bottom sheet + primary controls.
        Column(
            Modifier
                .align(Alignment.BottomCenter)
                .fillMaxWidth()
                .padding(horizontal = 12.dp)
                .padding(bottom = 10.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            if (live) {
                DemoControls(
                    blackout = blackout,
                    replayEnabled = replayEnabled,
                    onToggleBlackout = { bus.setBlackout(!blackout) },
                    onToggleReplay = { bus.setReplayEnabled(!replayEnabled) },
                )
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    SecondaryButton("SET START", Modifier.weight(1f)) { showOriginDialog = true }
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

            DriveBottomSheet(
                expanded = sheetExpanded,
                onToggle = {
                    sheetExpanded = !sheetExpanded
                    prefs.diagnosticsOpen = sheetExpanded
                },
                speedText = speedText,
                distText = distText,
                distUnit = distUnit,
                navMode = navMode,
                hud = hud,
                bus = bus,
            )

            PrimaryControls(
                live = live,
                permsOk = permsOk,
                onStartStop = {
                    if (live) {
                        RecordService.stop(ctx)
                    } else {
                        if (!notifsOk) requestNotifs()
                        RecordService.start(ctx, AppMode.NAVIGATE)
                    }
                },
                onRequestPerms = requestPerms,
            )
        }
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
// Mode pill (emotional core of the demo)
// ---------------------------------------------------------------------------

@Composable
private fun ModePill(navMode: NavMode, nSats: Int, live: Boolean) {
    val idr = navMode == NavMode.DEAD_RECKONING || navMode == NavMode.RELATIVE
    val pulse = rememberInfiniteTransition(label = "idrPulse")
    val alpha by pulse.animateFloat(
        initialValue = 1f,
        targetValue = if (idr && live) 0.55f else 1f,
        animationSpec = infiniteRepeatable(tween(900), RepeatMode.Reverse),
        label = "idrAlpha",
    )
    val tint by animateColorAsState(
        targetValue = when {
            !live || navMode == NavMode.IDLE -> Mute
            navMode == NavMode.GNSS -> Gnss
            else -> Amber
        },
        label = "pillTint",
    )
    val label = when {
        !live || navMode == NavMode.IDLE -> "READY"
        navMode == NavMode.GNSS -> "GPS  ·  $nSats sats"
        navMode == NavMode.DEAD_RECKONING -> "IDR MODE — AI speed + road lock"
        else -> "RELATIVE — no absolute fix"
    }
    Box(
        Modifier
            .alpha(alpha)
            .widthIn(max = 260.dp)
            .clip(RoundedCornerShape(99.dp))
            .background(Bg2.copy(alpha = 0.92f))
            .border(1.5.dp, tint.copy(alpha = 0.85f), RoundedCornerShape(99.dp))
            .padding(horizontal = 16.dp, vertical = 10.dp),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            label,
            color = tint,
            fontFamily = IdrMono,
            fontSize = 12.sp,
            fontWeight = FontWeight.Bold,
            letterSpacing = 0.8.sp,
            textAlign = TextAlign.Center,
            maxLines = 2,
        )
    }
}

@Composable
private fun DemoControls(
    blackout: Boolean,
    replayEnabled: Boolean,
    onToggleBlackout: () -> Unit,
    onToggleReplay: () -> Unit,
) {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        SecondaryButton(
            if (replayEnabled) "REPLAY ON" else "REPLAY",
            Modifier.weight(1f),
            onToggleReplay,
        )
        SecondaryButton(
            if (blackout) "RESTORE GNSS" else "SIMULATE BLACKOUT",
            Modifier.weight(1.4f),
            onToggleBlackout,
        )
    }
}

@Composable
private fun DriveBottomSheet(
    expanded: Boolean,
    onToggle: () -> Unit,
    speedText: String,
    distText: String,
    distUnit: String,
    navMode: NavMode,
    hud: HudState,
    bus: IdrBus,
) {
    Column(
        Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(topStart = 18.dp, topEnd = 18.dp, bottomStart = 14.dp, bottomEnd = 14.dp))
            .background(Bg2.copy(alpha = 0.94f))
            .border(1.dp, Line, RoundedCornerShape(topStart = 18.dp, topEnd = 18.dp, bottomStart = 14.dp, bottomEnd = 14.dp))
            .pointerInput(Unit) {
                detectVerticalDragGestures { _, drag ->
                    if (drag < -20f && !expanded) onToggle()
                    if (drag > 20f && expanded) onToggle()
                }
            }
            .padding(14.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Box(
            Modifier
                .align(Alignment.CenterHorizontally)
                .width(36.dp)
                .height(4.dp)
                .clip(RoundedCornerShape(99.dp))
                .background(Mute.copy(alpha = 0.45f))
                .clickable(onClick = onToggle),
        )
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            Column {
                Text("SPEED", fontFamily = IdrMono, color = Mute, fontSize = 10.sp, letterSpacing = 1.4.sp)
                Row(verticalAlignment = Alignment.Bottom) {
                    Text(speedText, fontFamily = IdrMono, color = Fg, fontSize = 34.sp, fontWeight = FontWeight.Bold)
                    Spacer(Modifier.width(4.dp))
                    Text("km/h", fontFamily = IdrMono, color = Mute, fontSize = 12.sp, modifier = Modifier.padding(bottom = 6.dp))
                }
            }
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Text("MODE", fontFamily = IdrMono, color = Mute, fontSize = 10.sp, letterSpacing = 1.4.sp)
                Text(
                    when (navMode) {
                        NavMode.GNSS -> "GPS"
                        NavMode.DEAD_RECKONING -> "IDR"
                        NavMode.RELATIVE -> "REL"
                        NavMode.IDLE -> "—"
                    },
                    fontFamily = IdrMono,
                    color = modeColor(navMode),
                    fontSize = 22.sp,
                    fontWeight = FontWeight.Bold,
                )
            }
            Column(horizontalAlignment = Alignment.End) {
                Text("SINCE FIX", fontFamily = IdrMono, color = Mute, fontSize = 10.sp, letterSpacing = 1.4.sp)
                Row(verticalAlignment = Alignment.Bottom) {
                    Text(
                        if (hud.distanceSinceFixM.isFinite()) "%.0f".format(hud.distanceSinceFixM) else distText,
                        fontFamily = IdrMono,
                        color = Fg,
                        fontSize = 34.sp,
                        fontWeight = FontWeight.Bold,
                    )
                    Spacer(Modifier.width(4.dp))
                    Text(
                        if (hud.distanceSinceFixM.isFinite()) "m" else distUnit,
                        fontFamily = IdrMono,
                        color = Mute,
                        fontSize = 12.sp,
                        modifier = Modifier.padding(bottom = 6.dp),
                    )
                }
            }
        }

        LoopClosureLine(
            closureM = hud.loopClosureM,
            driftPct = hud.driftPct,
            loopMarked = hud.loopMarked,
            loopDistanceM = hud.loopDistanceM,
        )

        // Accuracy / uncertainty card is debug-only (broken confidence signal).
        val prefs = Prefs(LocalContext.current)
        if (prefs.showUncertaintyRadius && navMode != NavMode.IDLE) {
            AccuracyCard(hud)
        }

        TextButton(onClick = onToggle, modifier = Modifier.fillMaxWidth()) {
            Text(
                if (expanded) "HIDE SYSTEM HEALTH" else "SYSTEM HEALTH",
                fontFamily = IdrMono,
                color = Mute,
                fontSize = 11.sp,
                letterSpacing = 1.2.sp,
            )
        }
        if (expanded) {
            Column(
                Modifier
                    .fillMaxWidth()
                    .heightIn(max = 280.dp)
                    .verticalScroll(rememberScrollState()),
            ) {
                DiagnosticsPanel(bus = bus, hud = hud)
            }
        }
    }
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
    if (status == LocationStatus.LIVE) return
    if (status == LocationStatus.UNKNOWN && permsOk) return
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
            .background(Bg2.copy(alpha = 0.92f))
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
// Accuracy (debug flag only)
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
            .background(Bg.copy(alpha = 0.55f))
            .border(1.dp, tint.copy(alpha = 0.35f), RoundedCornerShape(12.dp))
            .padding(14.dp),
        verticalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        Text(
            when {
                !known -> "ACCURACY UNKNOWN"
                hud.navMode == NavMode.RELATIVE -> "SHAPE ACCURATE TO ± " + metres(r)
                else -> "ACCURATE TO ± " + metres(r)
            },
            fontFamily = IdrMono,
            color = tint,
            fontSize = 14.sp,
            fontWeight = FontWeight.Bold,
        )
        Text(
            "DEBUG — confidence radius is not shown by default (broken signal).",
            fontFamily = IdrSans,
            color = Mute,
            fontSize = 11.sp,
        )
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
        fontSize = 12.sp,
        lineHeight = 16.sp,
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
            .height(56.dp),
        colors = ButtonDefaults.buttonColors(
            containerColor = if (live) Danger else Accent,
            contentColor = Bg,
        ),
        shape = RoundedCornerShape(14.dp),
    ) {
        Text(
            if (live) "STOP" else "START",
            fontFamily = IdrMono,
            fontSize = 18.sp,
            fontWeight = FontWeight.Bold,
            letterSpacing = 2.sp,
        )
    }
    if (!permsOk && !live) {
        Text(
            "You can start without location. Tracking runs from motion sensors in relative mode.",
            fontFamily = IdrSans,
            color = Mute,
            fontSize = 11.sp,
            lineHeight = 15.sp,
            modifier = Modifier.clickable(onClick = onRequestPerms),
        )
    }
}

@Composable
fun SecondaryButton(label: String, modifier: Modifier = Modifier, onClick: () -> Unit) {
    Box(
        modifier
            .height(44.dp)
            .clip(RoundedCornerShape(10.dp))
            .background(Bg2.copy(alpha = 0.92f))
            .border(1.dp, Line, RoundedCornerShape(10.dp))
            .clickable(onClick = onClick),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            label,
            fontFamily = IdrMono,
            color = Fg,
            fontSize = 11.sp,
            letterSpacing = 0.8.sp,
            textAlign = TextAlign.Center,
            modifier = Modifier.padding(horizontal = 8.dp),
        )
    }
}

private fun modeColor(mode: NavMode) = when (mode) {
    NavMode.GNSS -> Gnss
    NavMode.DEAD_RECKONING -> Accent
    NavMode.RELATIVE -> Amber
    NavMode.IDLE -> Mute
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
