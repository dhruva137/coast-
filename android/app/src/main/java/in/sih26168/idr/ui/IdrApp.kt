package `in`.sih26168.idr.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.HelpOutline
import androidx.compose.material.icons.outlined.Folder
import androidx.compose.material.icons.outlined.Navigation
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
import androidx.compose.ui.unit.sp
import `in`.sih26168.idr.IdrBus
import `in`.sih26168.idr.data.Prefs
import `in`.sih26168.idr.sensor.DeviceProbe
import `in`.sih26168.idr.sensor.LocationGate
import `in`.sih26168.idr.ui.theme.Accent
import `in`.sih26168.idr.ui.theme.Bg
import `in`.sih26168.idr.ui.theme.Bg2
import `in`.sih26168.idr.ui.theme.IdrMono
import `in`.sih26168.idr.ui.theme.Mute
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

private val Tabs = listOf("DRIVE", "SESSIONS", "SETTINGS", "ABOUT")

/**
 * Shell. DRIVE is the default tab. SESSIONS lists field logs; SETTINGS holds
 * vehicle/demo/privacy; ABOUT reuses Help (onboarding replay + claims).
 * Field RECORD is reached from Settings so the bottom bar stays four items.
 *
 * Onboarding takes the whole window on first run and can be reopened from About.
 */
@Composable
fun IdrApp(bus: IdrBus) {
    val ctx = LocalContext.current
    val prefs = remember { Prefs(ctx) }
    var tab by rememberSaveable { mutableIntStateOf(0) }
    var onboarding by remember { mutableStateOf(!prefs.onboardingDone) }
    // No autoRequest argument any more: nothing asks for a permission until the
    // user presses something that explains it. See Permissions.kt.
    val (permsOk, request) = rememberPermissionGate()

    // Restore persisted demo/vehicle prefs onto the process bus once.
    LaunchedEffect(Unit) {
        bus.setVehicle(prefs.vehicleKind)
        bus.setReplayEnabled(prefs.replayMode)
        val quick = withContext(Dispatchers.Default) { DeviceProbe.inventory(ctx) }
        bus.publishDevice(quick)
        bus.publishLocation(LocationGate.status(ctx))
    }

    if (onboarding) {
        OnboardingScreen(
            bus = bus,
            permsOk = permsOk,
            requestPerms = request,
            onFinish = {
                prefs.onboardingDone = true
                onboarding = false
            },
        )
        return
    }

    Scaffold(
        containerColor = Bg,
        contentWindowInsets = WindowInsets(0, 0, 0, 0),
        bottomBar = {
            NavigationBar(
                containerColor = Bg2,
                modifier = Modifier.navigationBarsPadding(),
            ) {
                Tabs.forEachIndexed { i, label ->
                    NavigationBarItem(
                        selected = tab == i,
                        onClick = { tab = i },
                        icon = {
                            Icon(
                                when (i) {
                                    0 -> Icons.Outlined.Navigation
                                    1 -> Icons.Outlined.Folder
                                    2 -> Icons.Outlined.Settings
                                    else -> Icons.AutoMirrored.Outlined.HelpOutline
                                },
                                contentDescription = label,
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
            when (tab) {
                0 -> DriveScreen(
                    bus = bus,
                    permsOk = permsOk,
                    requestPerms = request,
                    onOpenHelp = { tab = 3 },
                )
                1 -> Column(Modifier.statusBarsPadding().fillMaxSize()) {
                    SessionsScreen()
                }
                2 -> Column(Modifier.statusBarsPadding().fillMaxSize()) {
                    SettingsScreen(
                        bus = bus,
                        permsOk = permsOk,
                        requestPerms = request,
                    )
                }
                else -> Column(Modifier.statusBarsPadding().fillMaxSize()) {
                    HelpScreen(bus = bus, onReplayOnboarding = { onboarding = true })
                }
            }
        }
    }
}
