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
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
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
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import `in`.sih26168.idr.IdrBus
import `in`.sih26168.idr.data.Prefs
import `in`.sih26168.idr.data.VehicleKind
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
 * Demo / privacy / vehicle controls. Everything here persists through [Prefs]
 * (and bus setters where the nav pipeline already listens).
 */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun SettingsScreen(
    bus: IdrBus,
    permsOk: Boolean,
    requestPerms: () -> Unit,
    onOpenAccount: () -> Unit = {},
) {
    val ctx = LocalContext.current
    val prefs = remember { Prefs(ctx) }
    val cfg by bus.config.collectAsStateWithLifecycle()
    val blackout by bus.gnssBlackout.collectAsStateWithLifecycle()
    val replayEnabled by bus.replayEnabled.collectAsStateWithLifecycle()

    var basemap by remember { mutableStateOf(prefs.basemapEnabled) }
    var mapDark by remember { mutableStateOf(prefs.mapDarkTheme) }
    var useKmh by remember { mutableStateOf(prefs.useKmh) }
    var showGhost by remember { mutableStateOf(prefs.showGhostCar) }
    var zuptTabletop by remember { mutableStateOf(prefs.zuptTabletop) }
    var trackerOptIn by remember { mutableStateOf(prefs.trackerOptIn) }
    var trackerIp by remember { mutableStateOf(prefs.trackerLanIp) }
    var showRecord by remember { mutableStateOf(false) }
    val displayName = prefs.displayName

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

    val fieldColors = OutlinedTextFieldDefaults.colors(
        focusedBorderColor = Accent,
        unfocusedBorderColor = Line,
        focusedLabelColor = Accent,
        unfocusedLabelColor = Mute,
        cursorColor = Accent,
        focusedTextColor = Fg,
        unfocusedTextColor = Fg,
    )

    Column(
        Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        Text("SETTINGS", fontFamily = IdrMono, color = Accent, letterSpacing = 3.sp, fontSize = 12.sp)
        Text(
            if (displayName.isBlank()) "Signed in as guest"
            else "Signed in as $displayName",
            color = Mute,
            fontFamily = IdrSans,
            fontSize = 13.sp,
        )
        SecondaryButton("ACCOUNT", Modifier.fillMaxWidth(), onOpenAccount)

        Section("VEHICLE")
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

        Section("MAP")
        SettingsToggle(
            title = "Dark map",
            subtitle = if (mapDark) {
                "Night chrome (default). Light theme not wired yet — preference still saved."
            } else {
                "Light preference saved; UI stays dark until a light theme ships."
            },
            checked = mapDark,
            onCheckedChange = {
                mapDark = it
                prefs.mapDarkTheme = it
            },
        )
        SettingsToggle(
            title = "Basemap",
            subtitle = "Off → metre grid, zero tile traffic.",
            checked = basemap,
            onCheckedChange = {
                basemap = it
                prefs.basemapEnabled = it
            },
        )
        SettingsToggle(
            title = "Speed in km/h",
            subtitle = "Off shows m/s.",
            checked = useKmh,
            onCheckedChange = {
                useKmh = it
                prefs.useKmh = it
            },
        )

        Section("DEMO")
        SettingsToggle(
            title = "Replay mode",
            subtitle = "Next drive uses the bundled IO-VNBD-style stream.",
            checked = replayEnabled,
            onCheckedChange = {
                bus.setReplayEnabled(it)
                prefs.replayMode = it
            },
        )
        SettingsToggle(
            title = "Show ghost car",
            subtitle = "Red naive-DR puck + trail beside COAST (same IMU, no ZUPT / map lock).",
            checked = showGhost,
            onCheckedChange = {
                showGhost = it
                prefs.showGhostCar = it
                bus.setShowGhost(it)
            },
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
        )
        Button(
            onClick = { bus.setBlackout(!blackout) },
            modifier = Modifier.fillMaxWidth().height(48.dp),
            colors = ButtonDefaults.buttonColors(
                containerColor = if (blackout) Amber else Bg2,
                contentColor = if (blackout) Bg else Fg,
            ),
            shape = RoundedCornerShape(8.dp),
        ) {
            Text(
                if (blackout) "RESTORE GNSS" else "SIMULATE GNSS BLACKOUT",
                fontFamily = IdrMono,
                fontSize = 12.sp,
                letterSpacing = 1.sp,
            )
        }

        Section("PRIVACY")
        Text(
            // Honest F8: INTERNET exists for public OSM tiles; user data never leaves.
            "No user data leaves the device · basemap-off = zero network",
            color = Telem,
            fontFamily = IdrSans,
            fontSize = 14.sp,
            lineHeight = 20.sp,
        )
        Text(
            "Position, sensors, and sessions stay on this phone. The only optional " +
                "outbound traffic is public map tiles when basemap is on.",
            color = Mute,
            fontFamily = IdrSans,
            fontSize = 12.sp,
            lineHeight = 17.sp,
        )

        Section("PHONE TRACKER (OPT-IN)")
        SettingsToggle(
            title = "Stream to laptop",
            subtitle = "Off by default. Prefs only for now — uploader comes later.",
            checked = trackerOptIn,
            onCheckedChange = {
                trackerOptIn = it
                prefs.trackerOptIn = it
            },
        )
        OutlinedTextField(
            value = trackerIp,
            onValueChange = {
                trackerIp = it
                prefs.trackerLanIp = it.trim()
            },
            label = { Text("Laptop LAN IP") },
            placeholder = { Text("192.168.1.10") },
            singleLine = true,
            enabled = trackerOptIn,
            modifier = Modifier.fillMaxWidth(),
            colors = fieldColors,
        )

        Section("FIELD LOGGING")
        SecondaryButton("OPEN RECORD SCREEN", Modifier.fillMaxWidth()) { showRecord = true }

        Spacer(Modifier.height(24.dp))
    }
}

@Composable
private fun Section(title: String) {
    Text(
        title,
        fontFamily = IdrMono,
        color = Mute,
        fontSize = 10.sp,
        letterSpacing = 1.5.sp,
        modifier = Modifier.padding(top = 4.dp),
    )
}

@Composable
private fun SettingsToggle(
    title: String,
    subtitle: String,
    checked: Boolean,
    onCheckedChange: (Boolean) -> Unit,
) {
    Row(
        Modifier
            .fillMaxWidth()
            .heightIn(min = 48.dp)
            .clip(RoundedCornerShape(12.dp))
            .background(Bg2)
            .border(1.dp, Line, RoundedCornerShape(12.dp))
            .semantics {
                contentDescription = "$title. $subtitle. ${if (checked) "On" else "Off"}"
            }
            .clickable { onCheckedChange(!checked) }
            .padding(horizontal = 14.dp, vertical = 12.dp),
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
