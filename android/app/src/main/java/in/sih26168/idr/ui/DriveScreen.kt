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
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.defaultMinSize
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Layers
import androidx.compose.material.icons.outlined.MyLocation
import androidx.compose.material.icons.outlined.Visibility
import androidx.compose.material.icons.outlined.VisibilityOff
import androidx.compose.material3.BottomSheetDefaults
import androidx.compose.material3.BottomSheetScaffold
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.FloatingActionButtonDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.SheetValue
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberBottomSheetScaffoldState
import androidx.compose.material3.rememberStandardBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.derivedStateOf
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.runtime.snapshotFlow
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
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
import `in`.sih26168.idr.demo.TrackerHooks
import `in`.sih26168.idr.pair.PairingStore
import `in`.sih26168.idr.pair.PairingUploader
import `in`.sih26168.idr.record.RecordService
import `in`.sih26168.idr.record.SessionLastFix
import `in`.sih26168.idr.record.SessionStore
import `in`.sih26168.idr.sensor.LocationGate
import `in`.sih26168.idr.ui.theme.Accent
import `in`.sih26168.idr.ui.theme.Amber
import `in`.sih26168.idr.ui.theme.Bg
import `in`.sih26168.idr.ui.theme.Bg2
import `in`.sih26168.idr.ui.theme.Danger
import `in`.sih26168.idr.ui.theme.Ghost
import `in`.sih26168.idr.ui.theme.Gnss
import `in`.sih26168.idr.ui.theme.IdrMono
import `in`.sih26168.idr.ui.theme.IdrSans
import `in`.sih26168.idr.ui.theme.Line
import `in`.sih26168.idr.ui.theme.Mute
import `in`.sih26168.idr.ui.theme.Telem
import `in`.sih26168.idr.ui.theme.Text as Fg
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.withContext
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/** Peek height: drag handle + speed row + Start/Stop. */
private val DriveSheetPeek = 176.dp

/**
 * Map-first Drive — Google Maps / Uber-driver layout.
 *
 * Full-bleed map, centered GPS↔IDR pill, M3 FABs, and a
 * [BottomSheetScaffold] whose peek shows speed + mode + Start/Stop; expand
 * reveals diagnostics and mark/replay controls.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DriveScreen(
    bus: IdrBus,
    permsOk: Boolean,
    coarseOnly: Boolean = false,
    requestPerms: () -> Unit,
    onOpenPairing: () -> Unit = {},
    onStartDemo: (() -> Unit)? = null,
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
    val ghostTrack by bus.ghostTrack.collectAsStateWithLifecycle()
    val showGhost by bus.showGhost.collectAsStateWithLifecycle()
    val zuptTabletop by bus.zuptTabletop.collectAsStateWithLifecycle()
    val forceStationary by bus.forceStationary.collectAsStateWithLifecycle()
    val naiveGhostSpeed by bus.naiveGhostSpeedMps.collectAsStateWithLifecycle()
    val coastSpeed by bus.coastSpeedMps.collectAsStateWithLifecycle()
    val live = mode == AppMode.NAVIGATE
    val locationStatus = if (live) hud.locationStatus else idleLocation
    val navMode = if (live) hud.navMode else NavMode.IDLE
    val prefs = remember { Prefs(ctx) }
    val demoActive = prefs.demoMode || replayActive || (replayEnabled && live)
    val (notifsOk, requestNotifs) = rememberNotificationGate()
    var showOriginDialog by remember { mutableStateOf(false) }
    var lastFix by remember { mutableStateOf<SessionLastFix?>(null) }
    var basemapWanted by remember { mutableStateOf(prefs.basemapEnabled) }
    var recenterTick by remember { mutableIntStateOf(0) }
    var prevNavMode by remember { mutableStateOf(NavMode.IDLE) }
    var showHandover by remember { mutableStateOf(false) }
    var showReacquire by remember { mutableStateOf(false) }

    // Session start / end bookends. Skip the first composition so opening Drive
    // does not fake a SESSION_END while live is still false.
    var sessionBookendReady by remember { mutableStateOf(false) }
    LaunchedEffect(live) {
        if (!sessionBookendReady) {
            sessionBookendReady = true
            if (!live) return@LaunchedEffect
        }
        SignalHistory.append(
            ctx,
            SignalHistory.Event(
                kind = if (live) SignalHistory.KIND_SESSION_START else SignalHistory.KIND_SESSION_END,
                atMs = System.currentTimeMillis(),
                lat = hud.lat.takeIf { it.isFinite() },
                lon = hud.lon.takeIf { it.isFinite() },
            ),
        )
    }

    LaunchedEffect(navMode, live, blackout) {
        val coastNow = navMode == NavMode.DEAD_RECKONING || navMode == NavMode.RELATIVE
        val coastWas = prevNavMode == NavMode.DEAD_RECKONING || prevNavMode == NavMode.RELATIVE
        val enteredIdr = live && prevNavMode == NavMode.GNSS &&
            (coastNow || blackout)
        val demoColdStart = demoActive && live && blackout &&
            prevNavMode == NavMode.IDLE && navMode != NavMode.GNSS
        val reacquiredGnss = live && !blackout && navMode == NavMode.GNSS && coastWas
        when {
            enteredIdr || demoColdStart -> {
                // Persist the loss event with the last absolute fix.
                SignalHistory.append(
                    ctx,
                    SignalHistory.Event(
                        kind = SignalHistory.KIND_GNSS_LOST,
                        atMs = System.currentTimeMillis(),
                        lat = hud.lat.takeIf { it.isFinite() },
                        lon = hud.lon.takeIf { it.isFinite() },
                        nSats = hud.nSats.takeIf { it > 0 },
                        note = if (demoColdStart) "cold-start under blackout"
                            else "GNSS handover",
                    ),
                )
                showHandover = true
                showReacquire = false
                kotlinx.coroutines.delay(3200)
                showHandover = false
            }
            reacquiredGnss -> {
                SignalHistory.append(
                    ctx,
                    SignalHistory.Event(
                        kind = SignalHistory.KIND_GNSS_REACQUIRED,
                        atMs = System.currentTimeMillis(),
                        lat = hud.lat.takeIf { it.isFinite() },
                        lon = hud.lon.takeIf { it.isFinite() },
                        nSats = hud.nSats.takeIf { it > 0 },
                    ),
                )
                showReacquire = true
                showHandover = false
                kotlinx.coroutines.delay(3200)
                showReacquire = false
            }
        }
        prevNavMode = navMode
    }

    val sheetState = rememberStandardBottomSheetState(
        initialValue = if (prefs.diagnosticsOpen) SheetValue.Expanded else SheetValue.PartiallyExpanded,
        skipHiddenState = true,
    )
    val scaffoldState = rememberBottomSheetScaffoldState(bottomSheetState = sheetState)

    LaunchedEffect(sheetState) {
        snapshotFlow { sheetState.currentValue }
            .distinctUntilChanged()
            .collect { value ->
                prefs.diagnosticsOpen = value == SheetValue.Expanded
            }
    }

    LaunchedEffect(live) {
        if (!live) {
            lastFix = withContext(Dispatchers.IO) { SessionStore.lastKnownFix(ctx) }
        }
    }

    // Ghost puck only in demo contexts — never on a plain live Start.
    val drawGhost = showGhost && (blackout || replayActive || zuptTabletop)
    val motionLabel = when {
        !live -> "IDLE"
        !hud.speedMps.isFinite() -> "—"
        hud.speedMps < 0.35 -> "STILL"
        else -> "MOVING"
    }

    val useKmh = prefs.useKmh
    val speedText = if (hud.speedMps.isFinite()) {
        if (useKmh) "%.0f".format(hud.speedMps * 3.6) else "%.1f".format(hud.speedMps)
    } else {
        "--"
    }
    val speedUnit = if (useKmh) "km/h" else "m/s"
    val distText by remember { derivedStateOf { distanceValue(hud.distanceM) } }
    val distUnit by remember { derivedStateOf { distanceUnit(hud.distanceM) } }

    val view = LocalView.current
    DisposableEffect(live) {
        view.keepScreenOn = live
        onDispose { view.keepScreenOn = false }
    }

    BottomSheetScaffold(
        scaffoldState = scaffoldState,
        sheetPeekHeight = DriveSheetPeek,
        containerColor = Color.Transparent,
        contentColor = Fg,
        sheetContainerColor = Bg2.copy(alpha = 0.97f),
        sheetContentColor = Fg,
        sheetTonalElevation = 0.dp,
        sheetShadowElevation = 8.dp,
        sheetShape = RoundedCornerShape(topStart = 20.dp, topEnd = 20.dp),
        sheetDragHandle = { BottomSheetDefaults.DragHandle(color = Mute.copy(alpha = 0.65f)) },
        sheetContent = {
                DriveSheetBody(
                live = live,
                speedText = speedText,
                speedUnit = speedUnit,
                distText = distText,
                distUnit = distUnit,
                navMode = navMode,
                hud = hud,
                bus = bus,
                permsOk = permsOk,
                notifsOk = notifsOk,
                requestNotifs = requestNotifs,
                requestPerms = requestPerms,
                onShowOrigin = { showOriginDialog = true },
                onOpenPairing = onOpenPairing,
            )
        },
    ) { pad ->
        Box(Modifier.fillMaxSize()) {
            DriveMapPanel(
                bus = bus,
                track = track,
                navMode = navMode,
                modifier = Modifier.fillMaxSize(),
                mapModifier = Modifier.fillMaxSize(),
                onLongPress = { showOriginDialog = true },
                showBasemapToggle = false,
                basemapWanted = basemapWanted,
                onBasemapWantedChange = {
                    basemapWanted = it
                    prefs.basemapEnabled = it
                },
                recenterTick = recenterTick,
                showRecenterChip = false,
                ghostTrack = ghostTrack,
                showGhost = drawGhost,
            )

            if (zuptTabletop) {
                ZuptTabletopOverlay(
                    naiveMps = naiveGhostSpeed,
                    coastMps = coastSpeed,
                    modifier = Modifier
                        .align(Alignment.Center)
                        .padding(horizontal = 16.dp)
                        .padding(bottom = pad.calculateBottomPadding() / 2)
                        .fillMaxWidth(),
                )
            }

            // Top overlays — status pill centered.
            Column(
                Modifier
                    .align(Alignment.TopCenter)
                    .fillMaxWidth()
                    .statusBarsPadding()
                    .padding(horizontal = 12.dp, vertical = 8.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                // Just the mode pill at the top — no competing labels.
                // Demo mode is entered from Settings, not from the map.
                ModePill(
                    navMode = navMode,
                    nSats = hud.nSats,
                    live = live,
                    blackout = blackout,
                )

                if (live) {
                    Column(
                        horizontalAlignment = Alignment.CenterHorizontally,
                        verticalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        MotionChip(label = motionLabel, speedText = speedText, speedUnit = speedUnit)
                        HoldStillChip(
                            held = forceStationary,
                            onToggle = {
                                val next = !forceStationary
                                bus.setForceStationary(next)
                                prefs.forceStationary = next
                            },
                        )
                    }
                }

                // In-frame honesty label — same visual layer as the map.
                if (demoActive || replayActive || replayEnabled) {
                    Text(
                        DemoMode.REPLAY_LABEL,
                        modifier = Modifier
                            .fillMaxWidth()
                            .clip(RoundedCornerShape(8.dp))
                            .background(Amber.copy(alpha = 0.22f))
                            .border(2.dp, Amber, RoundedCornerShape(8.dp))
                            .padding(horizontal = 12.dp, vertical = 8.dp)
                            .semantics {
                                contentDescription = DemoMode.REPLAY_LABEL
                            },
                        color = Amber,
                        fontFamily = IdrMono,
                        fontSize = 12.sp,
                        fontWeight = FontWeight.Bold,
                        letterSpacing = 0.8.sp,
                        textAlign = TextAlign.Center,
                    )
                }

                if (demoActive || (blackout && live)) {
                    Text(
                        DemoMode.EXPLAINER,
                        modifier = Modifier
                            .fillMaxWidth()
                            .clip(RoundedCornerShape(8.dp))
                            .background(Bg2.copy(alpha = 0.94f))
                            .border(1.dp, Accent.copy(alpha = 0.55f), RoundedCornerShape(8.dp))
                            .padding(horizontal = 12.dp, vertical = 10.dp)
                            .semantics { contentDescription = DemoMode.EXPLAINER },
                        color = Fg,
                        fontFamily = IdrSans,
                        fontSize = 14.sp,
                        fontWeight = FontWeight.SemiBold,
                        textAlign = TextAlign.Center,
                        lineHeight = 18.sp,
                    )
                }

                if (showHandover) {
                    HandoverBanner(reacquire = false)
                }
                if (showReacquire) {
                    HandoverBanner(reacquire = true)
                }

                // Paired indicator — only when actively streaming to a console.
                // Not-paired state moves into the bottom sheet to keep the map clean.
                run {
                    val pairStore = remember { PairingStore(ctx) }
                    var pairTick by remember { mutableIntStateOf(0) }
                    val consolePaired = remember(pairTick) { pairStore.paired }
                    val pairLabel = remember(pairTick) {
                        pairStore.label.ifBlank { "console" }
                    }
                    if (consolePaired) {
                        Row(
                            modifier = Modifier
                                .clip(RoundedCornerShape(99.dp))
                                .background(Bg2.copy(alpha = 0.92f))
                                .border(1.dp, Danger.copy(alpha = 0.7f), RoundedCornerShape(99.dp))
                                .padding(horizontal = 12.dp, vertical = 6.dp)
                                .semantics {
                                    contentDescription =
                                        "Paired with $pairLabel. Sharing live position."
                                },
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(8.dp),
                        ) {
                            Box(
                                Modifier
                                    .size(8.dp)
                                    .clip(CircleShape)
                                    .background(Danger),
                            )
                            Text(
                                "PAIRED · $pairLabel",
                                color = Danger,
                                fontFamily = IdrMono,
                                fontSize = 10.sp,
                                fontWeight = FontWeight.Bold,
                                letterSpacing = 1.0.sp,
                            )
                        }
                    }
                }

                DeviceWarningLine(device)

                if (coarseOnly) {
                    Text(
                        "Approximate location — reduced precision",
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

                if (!live) {
                    LastLocationCard(
                        lastFix = lastFix,
                        liveHud = hud,
                    )
                }
            }

            // Map FABs — above the sheet, Maps/Uber style.
            Column(
                Modifier
                    .align(Alignment.BottomEnd)
                    .padding(end = 14.dp, bottom = pad.calculateBottomPadding() + 12.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp),
                horizontalAlignment = Alignment.End,
            ) {
                DriveFab(
                    icon = Icons.Outlined.MyLocation,
                    contentDescription = "Recenter map on vehicle",
                    onClick = { recenterTick++ },
                )
                DriveFab(
                    icon = Icons.Outlined.Layers,
                    contentDescription = if (basemapWanted) {
                        "Show metre grid instead of basemap; disables tile network"
                    } else {
                        "Show map basemap"
                    },
                    tint = if (basemapWanted) Accent else Mute,
                    onClick = {
                        basemapWanted = !basemapWanted
                        prefs.basemapEnabled = basemapWanted
                    },
                )
                DriveFab(
                    icon = if (blackout) Icons.Outlined.VisibilityOff else Icons.Outlined.Visibility,
                    contentDescription = if (blackout) {
                        "Restore GNSS — end simulated blackout"
                    } else {
                        "Simulate GNSS blackout for demo"
                    },
                    tint = if (blackout) Amber else Mute,
                    onClick = { bus.setBlackout(!blackout) },
                )
            }
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

@Composable
private fun DriveFab(
    icon: ImageVector,
    contentDescription: String,
    onClick: () -> Unit,
    tint: Color = Fg,
) {
    FloatingActionButton(
        onClick = onClick,
        modifier = Modifier
            .size(56.dp)
            .semantics { this.contentDescription = contentDescription },
        shape = CircleShape,
        containerColor = Bg2.copy(alpha = 0.94f),
        contentColor = tint,
        elevation = FloatingActionButtonDefaults.elevation(
            defaultElevation = 4.dp,
            pressedElevation = 6.dp,
        ),
    ) {
        Icon(
            imageVector = icon,
            contentDescription = contentDescription,
            modifier = Modifier.size(26.dp),
        )
    }
}

@Composable
private fun ColumnScope.DriveSheetBody(
    live: Boolean,
    speedText: String,
    speedUnit: String,
    distText: String,
    distUnit: String,
    navMode: NavMode,
    hud: HudState,
    bus: IdrBus,
    permsOk: Boolean,
    notifsOk: Boolean,
    requestNotifs: () -> Unit,
    requestPerms: () -> Unit,
    onShowOrigin: () -> Unit,
    onOpenPairing: () -> Unit = {},
) {
    val ctx = LocalContext.current
    val prefs = remember { Prefs(ctx) }
    val pairStore = remember { PairingStore(ctx) }
    var pairTick by remember { mutableIntStateOf(0) }
    val consolePaired = remember(pairTick) { pairStore.paired }
    val pairLabel = remember(pairTick) { pairStore.label.ifBlank { "console" } }
    val replayActive by bus.replayActive.collectAsStateWithLifecycle()
    val replayEnabled by bus.replayEnabled.collectAsStateWithLifecycle()
    // Replay-visible speed must never share the exact visual layer of a live
    // reading. Colour + inline REPLAY badge below make a screenshot self-labelling.
    val isReplaySpeed = prefs.demoMode || replayActive || (replayEnabled && live)
    val speedColor = if (isReplaySpeed) Amber else Fg
    Column(
        Modifier
            .fillMaxWidth()
            .navigationBarsPadding()
            .padding(horizontal = 16.dp)
            .padding(bottom = 12.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        // Peek content: speed + mode + Start/Stop
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            Column {
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    Text("SPEED", fontFamily = IdrMono, color = Mute, fontSize = 10.sp, letterSpacing = 1.4.sp)
                    if (isReplaySpeed) {
                        Text(
                            "REPLAY",
                            modifier = Modifier
                                .clip(RoundedCornerShape(4.dp))
                                .background(Amber.copy(alpha = 0.22f))
                                .border(1.dp, Amber, RoundedCornerShape(4.dp))
                                .padding(horizontal = 5.dp, vertical = 1.dp)
                                .semantics { contentDescription = "Replay speed — not live" },
                            fontFamily = IdrMono,
                            color = Amber,
                            fontSize = 9.sp,
                            fontWeight = FontWeight.Bold,
                            letterSpacing = 1.0.sp,
                        )
                    }
                }
                Row(verticalAlignment = Alignment.Bottom) {
                    Text(speedText, fontFamily = IdrMono, color = speedColor, fontSize = 34.sp, fontWeight = FontWeight.Bold)
                    Spacer(Modifier.width(4.dp))
                    Text(speedUnit, fontFamily = IdrMono, color = Mute, fontSize = 12.sp, modifier = Modifier.padding(bottom = 6.dp))
                }
            }
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Text("MODE", fontFamily = IdrMono, color = Mute, fontSize = 10.sp, letterSpacing = 1.4.sp)
                Text(
                    when (navMode) {
                        NavMode.GNSS -> "GPS"
                        NavMode.DEAD_RECKONING -> "COAST"
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

        PrimaryControls(
            live = live,
            permsOk = permsOk,
            onStartStop = {
                try {
                    if (live) {
                        RecordService.stop(ctx)
                        if (prefs.demoMode) DemoMode.clear(prefs, bus)
                    } else {
                        if (!notifsOk) requestNotifs()
                        RecordService.start(ctx, AppMode.NAVIGATE)
                    }
                } catch (_: Exception) {
                    // Foreground-service / lifecycle races must not crash the UI.
                }
            },
            onRequestPerms = requestPerms,
        )

        // Expanded diagnostics + ride controls (visible when sheet expands).
        LoopClosureLine(
            closureM = hud.loopClosureM,
            driftPct = hud.driftPct,
            loopMarked = hud.loopMarked,
            loopDistanceM = hud.loopDistanceM,
        )

        if (hud.floorChanged) {
            Text(
                "FLOOR CHANGED · relative floor ${hud.floorIndex}",
                fontFamily = IdrMono,
                color = Amber,
                fontSize = 11.sp,
                letterSpacing = 1.0.sp,
            )
        }

        if (live) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                SecondaryButton("SET START", Modifier.weight(1f), onShowOrigin)
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

        // Accuracy / uncertainty card is debug-only (broken confidence signal).
        if (prefs.showUncertaintyRadius && navMode != NavMode.IDLE) {
            AccuracyCard(hud)
        }

        // Console pairing — lives inside the sheet so the map stays clean.
        Text(
            "CONSOLE",
            fontFamily = IdrMono,
            color = Mute,
            fontSize = 11.sp,
            letterSpacing = 1.2.sp,
            modifier = Modifier.padding(top = 4.dp),
        )
        if (consolePaired) {
            Row(
                Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(10.dp))
                    .background(Bg.copy(alpha = 0.5f))
                    .border(1.dp, Line, RoundedCornerShape(10.dp))
                    .padding(horizontal = 12.dp, vertical = 10.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                Box(
                    Modifier
                        .size(10.dp)
                        .clip(CircleShape)
                        .background(Danger),
                )
                Text(
                    "PAIRED · $pairLabel",
                    modifier = Modifier.weight(1f),
                    color = Fg,
                    fontFamily = IdrMono,
                    fontSize = 12.sp,
                    fontWeight = FontWeight.Bold,
                    letterSpacing = 0.8.sp,
                )
                Text(
                    "UNPAIR",
                    modifier = Modifier
                        .defaultMinSize(minHeight = 40.dp)
                        .clip(RoundedCornerShape(6.dp))
                        .clickable {
                            PairingUploader.unpair(ctx)
                            pairTick++
                        }
                        .padding(horizontal = 10.dp, vertical = 8.dp)
                        .semantics { contentDescription = "Unpair from console" },
                    color = Danger,
                    fontFamily = IdrMono,
                    fontSize = 11.sp,
                    fontWeight = FontWeight.Bold,
                    letterSpacing = 0.8.sp,
                )
            }
        } else {
            SecondaryButton("PAIR WITH CONSOLE", Modifier.fillMaxWidth(), onOpenPairing)
        }

        Text(
            "SYSTEM HEALTH",
            fontFamily = IdrMono,
            color = Mute,
            fontSize = 11.sp,
            letterSpacing = 1.2.sp,
            modifier = Modifier.padding(top = 4.dp),
        )
        Column(
            Modifier
                .fillMaxWidth()
                .heightIn(max = 320.dp)
                .verticalScroll(rememberScrollState()),
        ) {
            DiagnosticsPanel(bus = bus, hud = hud)
        }
    }
}

// ---------------------------------------------------------------------------
// Mode pill (emotional core of the demo)
// ---------------------------------------------------------------------------

/**
 * P1-2 desk demo: still phone → naive speed climbs from IMU bias; COAST+ZUPT
 * stays near 0.00 m/s. Speeds come from the live estimators, not a script.
 */
@Composable
private fun ZuptTabletopOverlay(
    naiveMps: Double,
    coastMps: Double,
    modifier: Modifier = Modifier,
) {
    Row(
        modifier
            .clip(RoundedCornerShape(14.dp))
            .background(Bg2.copy(alpha = 0.94f))
            .border(1.dp, Line, RoundedCornerShape(14.dp))
            .padding(horizontal = 14.dp, vertical = 12.dp),
        horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text(
                "naive DR (no map)",
                fontFamily = IdrMono,
                color = Ghost,
                fontSize = 10.sp,
                letterSpacing = 0.6.sp,
            )
            Text(
                if (naiveMps.isFinite()) "%.2f".format(naiveMps) else "--",
                fontFamily = IdrMono,
                color = Ghost,
                fontSize = 28.sp,
                fontWeight = FontWeight.Bold,
            )
            Text("m/s · drifting", fontFamily = IdrSans, color = Mute, fontSize = 11.sp)
        }
        Box(
            Modifier
                .width(1.dp)
                .height(64.dp)
                .background(Line),
        )
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text(
                "COAST",
                fontFamily = IdrMono,
                color = Accent,
                fontSize = 10.sp,
                letterSpacing = 0.6.sp,
            )
            Text(
                if (coastMps.isFinite()) "%.2f".format(coastMps) else "--",
                fontFamily = IdrMono,
                color = Accent,
                fontSize = 28.sp,
                fontWeight = FontWeight.Bold,
            )
            Text("m/s · ZUPT hold", fontFamily = IdrSans, color = Mute, fontSize = 11.sp)
        }
    }
}

@Composable
private fun MotionChip(label: String, speedText: String, speedUnit: String) {
    val tint = when (label) {
        "MOVING" -> Accent
        "STILL" -> Mute
        else -> Mute
    }
    Text(
        "$label  ·  $speedText $speedUnit",
        modifier = Modifier
            .clip(RoundedCornerShape(99.dp))
            .background(Bg2.copy(alpha = 0.92f))
            .border(1.dp, tint.copy(alpha = 0.55f), RoundedCornerShape(99.dp))
            .padding(horizontal = 12.dp, vertical = 6.dp)
            .semantics { contentDescription = "Motion $label, speed $speedText $speedUnit" },
        color = tint,
        fontFamily = IdrMono,
        fontSize = 11.sp,
        letterSpacing = 1.0.sp,
    )
}

private const val ReacquireHandover = "COAST  →  GPS  ·  reacquired"
private const val ReacquireSemantics = "Coast to GPS reacquired"

@Composable
private fun HandoverBanner(reacquire: Boolean) {
    val pulse = rememberInfiniteTransition(label = "handoverPulse")
    val alpha by pulse.animateFloat(
        initialValue = 1f,
        targetValue = 0.55f,
        animationSpec = infiniteRepeatable(tween(450), RepeatMode.Reverse),
        label = "handoverAlpha",
    )
    val fill = if (reacquire) Gnss else Amber
    val headline = if (reacquire) ReacquireHandover else "◼ GPS  →  ◆ COAST"
    val sub = if (reacquire) "GNSS lock restored" else DemoMode.HANDOVER
    val desc = if (reacquire) ReacquireSemantics else DemoMode.HANDOVER
    Column(
        Modifier
            .fillMaxWidth()
            .alpha(alpha)
            .clip(RoundedCornerShape(12.dp))
            .background(fill)
            .border(3.dp, Fg, RoundedCornerShape(12.dp))
            .padding(horizontal = 14.dp, vertical = 14.dp)
            .semantics { contentDescription = desc },
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        Text(
            headline,
            color = Bg,
            fontFamily = IdrMono,
            fontSize = 18.sp,
            fontWeight = FontWeight.Bold,
            letterSpacing = 1.2.sp,
            textAlign = TextAlign.Center,
        )
        Text(
            sub,
            color = Bg,
            fontFamily = IdrSans,
            fontSize = 14.sp,
            fontWeight = FontWeight.SemiBold,
            textAlign = TextAlign.Center,
        )
    }
}

@Composable
private fun HoldStillChip(held: Boolean, onToggle: () -> Unit) {
    val tint = if (held) Amber else Mute
    val label = if (held) "I AM STATIONARY" else "HOLD STILL"
    Text(
        label,
        modifier = Modifier
            .defaultMinSize(minHeight = 44.dp)
            .clip(RoundedCornerShape(99.dp))
            .background(if (held) Amber.copy(alpha = 0.22f) else Bg2.copy(alpha = 0.92f))
            .border(1.dp, tint.copy(alpha = 0.7f), RoundedCornerShape(99.dp))
            .semantics {
                contentDescription = if (held) {
                    "I am stationary. Force hold on. Tap to resume coast."
                } else {
                    "Hold still. Force stationary hold off. Tap to zero coast."
                }
            }
            .clickable(onClick = onToggle)
            .padding(horizontal = 12.dp, vertical = 10.dp),
        color = tint,
        fontFamily = IdrMono,
        fontSize = 11.sp,
        letterSpacing = 1.0.sp,
        fontWeight = FontWeight.Bold,
    )
}

@Composable
private fun ModePill(
    navMode: NavMode,
    nSats: Int,
    live: Boolean,
    blackout: Boolean = false,
    modifier: Modifier = Modifier,
) {
    val idr = navMode == NavMode.DEAD_RECKONING || navMode == NavMode.RELATIVE || (live && blackout)
    val pulse = rememberInfiniteTransition(label = "idrPulse")
    val alpha by pulse.animateFloat(
        initialValue = 1f,
        targetValue = if (idr && live) 0.55f else 1f,
        animationSpec = infiniteRepeatable(tween(700), RepeatMode.Reverse),
        label = "idrAlpha",
    )
    val tint by animateColorAsState(
        targetValue = when {
            !live || navMode == NavMode.IDLE -> Mute
            navMode == NavMode.GNSS && !blackout -> Gnss
            else -> Amber
        },
        label = "pillTint",
    )
    // Shape + label redundancy (not colour alone): GPS = round, COAST = squared.
    val shape = if (idr) RoundedCornerShape(10.dp) else RoundedCornerShape(99.dp)
    val label = when {
        !live || navMode == NavMode.IDLE -> "READY"
        navMode == NavMode.GNSS && !blackout -> "● GPS  ·  $nSats sats"
        navMode == NavMode.DEAD_RECKONING || blackout -> "◆ COAST — sensors + map"
        else -> "◇ RELATIVE — no absolute fix"
    }
    Box(
        modifier
            .alpha(alpha)
            .widthIn(max = 280.dp)
            .clip(shape)
            .background(Bg2.copy(alpha = 0.94f))
            .border(if (idr) 2.5.dp else 1.5.dp, tint.copy(alpha = 0.9f), shape)
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

/**
 * Small overlay on Drive home: last session end-fix (or live HUD coords if idle
 * but still holding a recent absolute estimate). Does not turn Drive into a lab tool.
 */
@Composable
private fun LastLocationCard(lastFix: SessionLastFix?, liveHud: HudState) {
    val fromHud = liveHud.lat.isFinite() && liveHud.lon.isFinite() && liveHud.hasAbsolutePosition
    if (!fromHud && lastFix == null) return

    val title: String
    val coords: String
    val subtitle: String
    if (fromHud) {
        title = "LAST LOCATION"
        coords = "%.5f, %.5f".format(Locale.US, liveHud.lat, liveHud.lon)
        subtitle = "Current absolute estimate"
    } else {
        val f = lastFix!!
        title = "LAST LOCATION"
        coords = "%.5f, %.5f".format(Locale.US, f.lat, f.lon)
        val whenStr = SimpleDateFormat("MMM d · HH:mm", Locale.US).format(Date(f.modifiedMs))
        subtitle = "${f.sessionName} · ${f.vehicle} · $whenStr"
    }

    Column(
        Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(12.dp))
            .background(Bg2.copy(alpha = 0.92f))
            .border(1.dp, Line, RoundedCornerShape(12.dp))
            .padding(horizontal = 14.dp, vertical = 10.dp),
        verticalArrangement = Arrangement.spacedBy(2.dp),
    ) {
        Text(title, fontFamily = IdrMono, color = Mute, fontSize = 9.sp, letterSpacing = 1.2.sp)
        Text(coords, fontFamily = IdrMono, color = Fg, fontSize = 13.sp)
        Text(subtitle, fontFamily = IdrSans, color = Mute, fontSize = 11.sp, maxLines = 1)
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
            .height(56.dp)
            .semantics {
                contentDescription = if (live) "Stop navigation" else "Start navigation"
            },
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
            .defaultMinSize(minHeight = 44.dp)
            .heightIn(min = 44.dp)
            .clip(RoundedCornerShape(10.dp))
            .background(Bg2.copy(alpha = 0.92f))
            .border(1.dp, Line, RoundedCornerShape(10.dp))
            .semantics { contentDescription = label }
            .clickable(onClick = onClick)
            .padding(horizontal = 8.dp, vertical = 10.dp),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            label,
            fontFamily = IdrMono,
            color = Fg,
            fontSize = 11.sp,
            letterSpacing = 0.8.sp,
            textAlign = TextAlign.Center,
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
