package `in`.sih26168.idr.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.defaultMinSize
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
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
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import `in`.sih26168.idr.IdrBus
import `in`.sih26168.idr.data.Prefs
import `in`.sih26168.idr.data.ThemePreference
import `in`.sih26168.idr.data.VehicleKind
import `in`.sih26168.idr.pair.PairingStore
import `in`.sih26168.idr.ui.theme.Accent
import `in`.sih26168.idr.ui.theme.Amber
import `in`.sih26168.idr.ui.theme.Bg
import `in`.sih26168.idr.ui.theme.Bg2
import `in`.sih26168.idr.ui.theme.IdrMono
import `in`.sih26168.idr.ui.theme.IdrSans
import `in`.sih26168.idr.ui.theme.Line
import `in`.sih26168.idr.ui.theme.Mute
import `in`.sih26168.idr.ui.theme.Telem
import `in`.sih26168.idr.ui.theme.Text as Fg

/**
 * Privacy / vehicle / map controls. Replay and tabletop tools live under Advanced.
 * Everything here persists through [Prefs]
 * (and bus setters where the nav pipeline already listens).
 */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun SettingsScreen(
    bus: IdrBus,
    permsOk: Boolean,
    requestPerms: () -> Unit,
    onOpenAccount: () -> Unit = {},
    onStartDemo: (() -> Unit)? = null,
    onOpenVehicleCheck: (() -> Unit)? = null,
    onOpenHelp: (() -> Unit)? = null,
    onOpenHistory: (() -> Unit)? = null,
    themePref: ThemePreference = ThemePreference.Dark,
    onThemePref: (ThemePreference) -> Unit = {},
) {
    val ctx = LocalContext.current
    val prefs = remember { Prefs(ctx) }
    val cfg by bus.config.collectAsStateWithLifecycle()
    val blackout by bus.gnssBlackout.collectAsStateWithLifecycle()
    val replayEnabled by bus.replayEnabled.collectAsStateWithLifecycle()
    val forceStationary by bus.forceStationary.collectAsStateWithLifecycle()

    var basemap by remember { mutableStateOf(prefs.basemapEnabled) }
    var useKmh by remember { mutableStateOf(prefs.useKmh) }
    var showGhost by remember { mutableStateOf(prefs.showGhostCar) }
    var zuptTabletop by remember { mutableStateOf(prefs.zuptTabletop) }
    var fuseCompass by remember { mutableStateOf(prefs.fuseCompass) }
    var showRecord by remember { mutableStateOf(false) }
    var showAbout by remember { mutableStateOf(false) }
    val displayName = prefs.displayName
    val pairStore = remember { PairingStore(ctx) }

    if (showAbout) {
        AboutScreen(onBack = { showAbout = false })
        return
    }

    if (showRecord) {
        Column(Modifier.fillMaxSize()) {
            Text(
                "← SETTINGS",
                modifier = Modifier
                    .defaultMinSize(minHeight = 44.dp)
                    .semantics { contentDescription = "Back to settings" }
                    .clickable { showRecord = false }
                    .padding(horizontal = 16.dp, vertical = 14.dp),
                fontFamily = IdrMono,
                color = Accent,
                fontSize = 11.sp,
                letterSpacing = 1.sp,
            )
            RecordScreen(bus, permsOk, requestPerms)
        }
        return
    }

    Column(
        Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 16.dp, vertical = 12.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text(
            "Settings",
            fontFamily = IdrSans,
            color = Fg,
            fontSize = 22.sp,
            fontWeight = FontWeight.SemiBold,
        )
        Text(
            if (displayName.isBlank()) "Signed in as guest"
            else "Signed in as $displayName",
            color = Mute,
            fontFamily = IdrSans,
            fontSize = 13.sp,
        )

        SettingsCard {
            SecondaryButton("ACCOUNT", Modifier.fillMaxWidth(), onOpenAccount)
            if (onOpenHelp != null) {
                SecondaryButton("HELP", Modifier.fillMaxWidth(), onOpenHelp)
            }
            if (onOpenHistory != null) {
                SecondaryButton("SIGNAL HISTORY", Modifier.fillMaxWidth(), onOpenHistory)
            }
            SecondaryButton("ABOUT", Modifier.fillMaxWidth()) { showAbout = true }
        }

        Section("VEHICLE")
        SettingsCard {
            FlowRow(
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                VehicleKind.entries.forEach { v ->
                    SettingsChip(v.name, cfg.vehicle == v) {
                        bus.setVehicle(v)
                        prefs.vehicleKind = v
                    }
                }
            }
            if (onOpenVehicleCheck != null) {
                Spacer(Modifier.height(4.dp))
                SecondaryButton("VEHICLE CHECK", Modifier.fillMaxWidth(), onOpenVehicleCheck)
                Text(
                    "Pre-flight sensor checklist — rates, compass disclosure, mount.",
                    fontFamily = IdrSans,
                    color = Mute,
                    fontSize = 12.sp,
                    lineHeight = 16.sp,
                )
            }
        }

        Section("MAP")
        SettingsCard {
            Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text(
                    "APPEARANCE",
                    modifier = Modifier.padding(horizontal = 4.dp, vertical = 4.dp),
                    color = Mute,
                    fontFamily = IdrMono,
                    fontSize = 10.sp,
                    letterSpacing = 1.sp,
                )
                FlowRow(
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                    modifier = Modifier.padding(bottom = 8.dp),
                ) {
                    ThemePreference.entries.forEach { mode ->
                        SettingsChip(mode.name.uppercase(), themePref == mode) {
                            onThemePref(mode)
                        }
                    }
                }
                Text(
                    "Dark is the demo default. Light switches Material + basemap tiles; " +
                        "many chrome colours still use dark tokens.",
                    modifier = Modifier.padding(horizontal = 4.dp, vertical = 2.dp),
                    color = Mute,
                    fontFamily = IdrSans,
                    fontSize = 12.sp,
                )
                SettingsToggle(
                    title = "Basemap",
                    subtitle = "OpenStreetMap (the map PS 26168 names). No Google key. Off → metre grid, zero tile traffic.",
                    checked = basemap,
                    onCheckedChange = {
                        basemap = it
                        prefs.basemapEnabled = it
                    },
                    bordered = false,
                )
                SettingsToggle(
                    title = "Speed in km/h",
                    subtitle = "Off shows m/s.",
                    checked = useKmh,
                    onCheckedChange = {
                        useKmh = it
                        prefs.useKmh = it
                    },
                    bordered = false,
                )
            }
        }

        Section("STATIONARY")
        SettingsCard {
            SettingsToggle(
                title = "I am not moving (force hold)",
                subtitle = "Zeros coast until off. ZUPT still auto-detects stops; this is the user override for tabletop.",
                checked = forceStationary,
                onCheckedChange = {
                    bus.setForceStationary(it)
                    prefs.forceStationary = it
                },
                bordered = false,
            )
        }

        Section("ADVANCED")
        SettingsCard {
            Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                // Demo mode is a laptop-only path now. Cleared here defensively
                // so an older Prefs value can't leave the app in blackout.
                if (prefs.demoMode || blackout) {
                    DemoMode.clear(prefs, bus)
                }
                SettingsToggle(
                    title = "Show ghost car",
                    subtitle = "Red naive-DR puck — visible only when the ZUPT tabletop demo is on.",
                    checked = showGhost,
                    onCheckedChange = {
                        showGhost = it
                        prefs.showGhostCar = it
                        bus.setShowGhost(it)
                    },
                    bordered = false,
                )
                SettingsToggle(
                    title = "ZUPT tabletop",
                    subtitle = "Still phone: side-by-side naive vs COAST speed (naive drifts, COAST ~0).",
                    checked = zuptTabletop,
                    onCheckedChange = {
                        zuptTabletop = it
                        prefs.zuptTabletop = it
                        bus.setZuptTabletop(it)
                    },
                    bordered = false,
                )
                SettingsToggle(
                    title = "Fuse compass during GNSS outage",
                    subtitle = "Onset-calibrated heading. Lab heading-induced drift 16.87%→7.22%. Map-in-loop still locks the road.",
                    checked = fuseCompass,
                    onCheckedChange = {
                        fuseCompass = it
                        prefs.fuseCompass = it
                        bus.setFuseCompass(it)
                    },
                    bordered = false,
                )
            }
        }

        Section("PRIVACY")
        SettingsCard {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(
                    "No cloud account. Position stays on this phone unless you pair a console. " +
                        "Basemap-off and unpaired = zero network.",
                    color = Telem,
                    fontFamily = IdrSans,
                    fontSize = 14.sp,
                    lineHeight = 20.sp,
                )
                Text(
                    "Position and sessions stay on this phone unless you pair with a console. " +
                        "Optional outbound: public map tiles when basemap is on; console ingest " +
                        "only while paired (token + fix, never a device ID).",
                    color = Mute,
                    fontFamily = IdrSans,
                    fontSize = 12.sp,
                    lineHeight = 17.sp,
                )
            }
        }

        Section("CONSOLE")
        SettingsCard {
            Text(
                if (pairStore.paired) {
                    val who = pairStore.label.ifBlank { "console" }
                    "Paired with $who. Open the CONNECT tab to unpair or copy the session code."
                } else {
                    "Pairing lives on the CONNECT tab — scan the console QR, paste a " +
                        "token, or show a code the laptop can type. Never sends IMEI " +
                        "or advertising ID."
                },
                color = Mute,
                fontFamily = IdrSans,
                fontSize = 13.sp,
                lineHeight = 18.sp,
            )
        }

        Section("FIELD LOGGING")
        SettingsCard {
            SecondaryButton("OPEN RECORD SCREEN", Modifier.fillMaxWidth()) { showRecord = true }
        }

        Spacer(Modifier.height(24.dp))
    }
}

@Composable
private fun SettingsCard(content: @Composable () -> Unit) {
    Column(
        Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(16.dp))
            .background(Bg2)
            .border(1.dp, Line, RoundedCornerShape(16.dp))
            .padding(14.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        content()
    }
}

@Composable
private fun Section(title: String) {
    Text(
        title,
        fontFamily = IdrMono,
        color = Accent,
        fontSize = 11.sp,
        letterSpacing = 1.5.sp,
        modifier = Modifier.padding(top = 8.dp, bottom = 2.dp),
    )
}

@Composable
private fun SettingsToggle(
    title: String,
    subtitle: String,
    checked: Boolean,
    onCheckedChange: (Boolean) -> Unit,
    bordered: Boolean = true,
) {
    val shape = RoundedCornerShape(12.dp)
    Row(
        Modifier
            .fillMaxWidth()
            .heightIn(min = 48.dp)
            .then(
                if (bordered) {
                    Modifier
                        .clip(shape)
                        .background(Bg2)
                        .border(1.dp, Line, shape)
                } else {
                    Modifier
                },
            )
            .semantics {
                contentDescription = "$title. $subtitle. ${if (checked) "On" else "Off"}"
            }
            .clickable { onCheckedChange(!checked) }
            .padding(horizontal = if (bordered) 14.dp else 2.dp, vertical = 12.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text(title, fontFamily = IdrSans, color = Fg, fontSize = 15.sp)
            Text(subtitle, fontFamily = IdrSans, color = Mute, fontSize = 12.sp, lineHeight = 16.sp)
        }
        Switch(
            checked = checked,
            onCheckedChange = null,
            colors = SwitchDefaults.colors(
                checkedThumbColor = Bg,
                checkedTrackColor = Accent,
                uncheckedThumbColor = Mute,
                uncheckedTrackColor = Line,
            ),
        )
    }
}

@Composable
private fun SettingsChip(label: String, selected: Boolean, onClick: () -> Unit) {
    val bg = if (selected) Accent.copy(alpha = 0.18f) else Bg2
    val fg = if (selected) Accent else Mute
    Text(
        text = label.uppercase(),
        modifier = Modifier
            .defaultMinSize(minHeight = 44.dp)
            .clip(RoundedCornerShape(99.dp))
            .background(bg)
            .border(1.dp, if (selected) Accent.copy(alpha = 0.5f) else Line, RoundedCornerShape(99.dp))
            .semantics {
                contentDescription = if (selected) {
                    "Vehicle $label, selected"
                } else {
                    "Vehicle $label"
                }
            }
            .clickable(onClick = onClick)
            .padding(horizontal = 14.dp, vertical = 12.dp),
        color = fg,
        fontFamily = IdrMono,
        fontSize = 11.sp,
    )
}
