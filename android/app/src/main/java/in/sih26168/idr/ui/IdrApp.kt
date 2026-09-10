package `in`.sih26168.idr.ui

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Navigation
import androidx.compose.material.icons.outlined.QrCode
import androidx.compose.material.icons.outlined.Sensors
import androidx.compose.material.icons.outlined.Settings
import androidx.compose.material3.Icon
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationBarItemDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import `in`.sih26168.idr.IdrBus
import `in`.sih26168.idr.data.Prefs
import `in`.sih26168.idr.data.ThemePreference
import `in`.sih26168.idr.sensor.DeviceProbe
import `in`.sih26168.idr.sensor.LocationGate
import `in`.sih26168.idr.ui.theme.Accent
import `in`.sih26168.idr.ui.theme.Bg
import `in`.sih26168.idr.ui.theme.Bg2
import `in`.sih26168.idr.ui.theme.IdrMono
import `in`.sih26168.idr.ui.theme.IdrTheme
import `in`.sih26168.idr.ui.theme.Mute
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/** Product tabs. About and Sessions are not tabs. */
internal val IdrShellTabs = listOf("DRIVE", "SENSE", "CONNECT", "SETTINGS")

internal const val TAB_DRIVE = 0
internal const val TAB_SENSE = 1
internal const val TAB_CONNECT = 2
internal const val TAB_SETTINGS = 3

/**
 * Shell. DRIVE is the map. CONNECT hosts console pairing. SETTINGS holds
 * vehicle, privacy, Help, and About. Sessions are not in the product nav.
 *
 * Local profile gate runs once until guest/sign-in; reopenable from Settings.
 * Onboarding takes the whole window on first run and can be reopened from Help.
 * Vehicle Check runs once after onboarding (prefs flag) and from Settings.
 * Demo Mode skips auth/onboarding/vehicle-check and starts the blackout replay.
 */
@Composable
fun IdrApp(bus: IdrBus) {
    val ctx = LocalContext.current
    val prefs = remember { Prefs(ctx) }
    var themePref by remember { mutableStateOf(prefs.themePreference) }
    IdrTheme(preference = themePref) {
        IdrAppContent(
            bus = bus,
            prefs = prefs,
            themePref = themePref,
            onThemePref = {
                themePref = it
                prefs.themePreference = it
            },
        )
    }
}

@Composable
private fun IdrAppContent(
    bus: IdrBus,
    prefs: Prefs,
    themePref: ThemePreference,
    onThemePref: (ThemePreference) -> Unit,
) {
    val ctx = LocalContext.current
    var tab by rememberSaveable { mutableIntStateOf(TAB_DRIVE) }
    var authDone by remember { mutableStateOf(prefs.authDone) }
    var showAuthOverlay by remember { mutableStateOf(false) }
    var onboarding by remember { mutableStateOf(!prefs.onboardingDone) }
    var vehicleCheck by remember { mutableStateOf(!prefs.vehicleCheckDone) }
    var showVehicleCheckOverlay by remember { mutableStateOf(false) }
    var pendingDemoStart by rememberSaveable { mutableStateOf(false) }
    // Location-only gate for banners/onboarding. Notifications stay a separate
    // ask at START (see rememberNotificationGate). Refresh bus.location as soon
    // as the system dialog returns so the banner clears without needing Start.
    // granted = FINE or COARSE; coarseOnly surfaces reduced precision separately.
    val locPerm = rememberLocationPermissionGate { _ ->
        bus.publishLocation(LocationGate.status(ctx))
    }
    val permsOk = locPerm.granted
    val coarseOnly = locPerm.coarseOnly
    val request = locPerm.request
    val pendingPair by bus.pendingPairRaw.collectAsStateWithLifecycle()
    var helpOverlay by rememberSaveable { mutableStateOf(false) }
    var historyOverlay by rememberSaveable { mutableStateOf(false) }

    LaunchedEffect(pendingPair) {
        if (!pendingPair.isNullOrBlank()) {
            helpOverlay = false
            historyOverlay = false
            tab = TAB_CONNECT
        }
    }

    fun enterDemoMode() {
        DemoMode.arm(prefs, bus)
        authDone = true
        showAuthOverlay = false
        onboarding = false
        vehicleCheck = false
        showVehicleCheckOverlay = false
        helpOverlay = false
        historyOverlay = false
        tab = TAB_DRIVE
        pendingDemoStart = true
    }

    // Restore persisted demo/vehicle prefs onto the process bus once.
    LaunchedEffect(Unit) {
        bus.setVehicle(prefs.vehicleKind)
        bus.setReplayEnabled(prefs.replayMode)
        bus.setShowGhost(prefs.showGhostCar)
        bus.setZuptTabletop(prefs.zuptTabletop)
        bus.setForceStationary(prefs.forceStationary)
        bus.setFuseCompass(prefs.fuseCompass)
        if (prefs.demoMode) {
            bus.setBlackout(true)
        }
        val quick = withContext(Dispatchers.Default) { DeviceProbe.inventory(ctx) }
        bus.publishDevice(quick)
        bus.publishLocation(LocationGate.status(ctx))
    }

    LaunchedEffect(pendingDemoStart, authDone, onboarding, vehicleCheck) {
        if (pendingDemoStart && authDone && !onboarding && !vehicleCheck) {
            DemoMode.start(ctx, prefs, bus)
            pendingDemoStart = false
        }
    }

    if (!authDone || showAuthOverlay) {
        AuthScreen(
            allowDismiss = showAuthOverlay && authDone,
            onDismiss = { showAuthOverlay = false },
            onFinished = {
                authDone = true
                showAuthOverlay = false
            },
            onDemoMode = { enterDemoMode() },
        )
        return
    }

    if (onboarding) {
        OnboardingScreen(
            permsOk = permsOk,
            coarseOnly = coarseOnly,
            requestPerms = request,
            onFinish = {
                prefs.onboardingDone = true
                onboarding = false
            },
            onDemoMode = { enterDemoMode() },
        )
        return
    }

    if (vehicleCheck || showVehicleCheckOverlay) {
        VehicleCheckScreen(
            bus = bus,
            allowSkip = true,
            onFinished = {
                prefs.vehicleCheckDone = true
                vehicleCheck = false
                showVehicleCheckOverlay = false
            },
        )
        return
    }

    BackHandler(enabled = helpOverlay) { helpOverlay = false }
    BackHandler(enabled = historyOverlay && !helpOverlay) { historyOverlay = false }
    BackHandler(enabled = !helpOverlay && !historyOverlay && tab == TAB_CONNECT) { tab = TAB_DRIVE }

    Scaffold(
        containerColor = Bg,
        contentWindowInsets = WindowInsets(0, 0, 0, 0),
        bottomBar = {
            NavigationBar(
                containerColor = Bg2,
                modifier = Modifier.navigationBarsPadding(),
            ) {
                IdrShellTabs.forEachIndexed { i, label ->
                    val iconDesc = when (i) {
                        TAB_DRIVE -> "Drive — navigation map"
                        TAB_SENSE -> "Sense — live sensor demo"
                        TAB_CONNECT -> "Connect — pair with console"
                        else -> "Settings"
                    }
                    NavigationBarItem(
                        selected = tab == i && !helpOverlay && !historyOverlay,
                        onClick = {
                            helpOverlay = false
                            historyOverlay = false
                            tab = i
                        },
                        icon = {
                            Icon(
                                when (i) {
                                    TAB_DRIVE -> Icons.Outlined.Navigation
                                    TAB_SENSE -> Icons.Outlined.Sensors
                                    TAB_CONNECT -> Icons.Outlined.QrCode
                                    else -> Icons.Outlined.Settings
                                },
                                contentDescription = iconDesc,
                                modifier = Modifier.size(24.dp),
                            )
                        },
                        label = {
                            Text(label, fontFamily = IdrMono, fontSize = 10.sp, letterSpacing = 1.sp)
                        },
                        colors = NavigationBarItemDefaults.colors(
                            selectedIconColor = Accent,
                            selectedTextColor = Accent,
                            unselectedIconColor = Mute,
                            unselectedTextColor = Mute,
                            indicatorColor = Accent.copy(alpha = 0.16f),
                        ),
                    )
                }
            }
        },
    ) { pad ->
        Box(
            Modifier
                .fillMaxSize()
                .background(Bg)
                .padding(pad),
        ) {
            when {
                helpOverlay -> Column(Modifier.statusBarsPadding().fillMaxSize()) {
                    HelpScreen(
                        bus = bus,
                        onReplayOnboarding = {
                            helpOverlay = false
                            onboarding = true
                        },
                        onBack = { helpOverlay = false },
                    )
                }
                historyOverlay -> Column(Modifier.statusBarsPadding().fillMaxSize()) {
                    HistoryScreen(onBack = { historyOverlay = false })
                }
                tab == TAB_DRIVE -> DriveScreen(
                    bus = bus,
                    permsOk = permsOk,
                    coarseOnly = coarseOnly,
                    requestPerms = request,
                    onOpenPairing = { tab = TAB_CONNECT },
                    onStartDemo = { enterDemoMode() },
                )
                tab == TAB_SENSE -> LiveSensorScreen()
                tab == TAB_CONNECT -> Column(Modifier.statusBarsPadding().fillMaxSize()) {
                    PairingScreen(bus = bus)
                }
                else -> Column(Modifier.statusBarsPadding().fillMaxSize()) {
                    SettingsScreen(
                        bus = bus,
                        permsOk = permsOk,
                        requestPerms = request,
                        onOpenAccount = { showAuthOverlay = true },
                        onStartDemo = { enterDemoMode() },
                        onOpenVehicleCheck = { showVehicleCheckOverlay = true },
                        onOpenHelp = { helpOverlay = true },
                        onOpenHistory = { historyOverlay = true },
                        themePref = themePref,
                        onThemePref = onThemePref,
                    )
                }
            }
        }
    }
}
