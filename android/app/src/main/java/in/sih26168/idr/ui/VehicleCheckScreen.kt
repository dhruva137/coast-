package `in`.sih26168.idr.ui

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.location.LocationManager
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.slideInVertically
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
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import `in`.sih26168.idr.IdrBus
import `in`.sih26168.idr.data.DeviceCheck
import `in`.sih26168.idr.data.DeviceVerdict
import `in`.sih26168.idr.data.MountRotation
import `in`.sih26168.idr.data.Prefs
import `in`.sih26168.idr.data.SensorSpec
import `in`.sih26168.idr.nav.rotateToVehicle
import `in`.sih26168.idr.sensor.DeviceProbe
import `in`.sih26168.idr.sensor.LocationGate
import `in`.sih26168.idr.ui.theme.Accent
import `in`.sih26168.idr.ui.theme.Amber
import `in`.sih26168.idr.ui.theme.Bg
import `in`.sih26168.idr.ui.theme.Bg2
import `in`.sih26168.idr.ui.theme.Danger
import `in`.sih26168.idr.ui.theme.IdrMono
import `in`.sih26168.idr.ui.theme.IdrSans
import `in`.sih26168.idr.ui.theme.Line
import `in`.sih26168.idr.ui.theme.Mute
import `in`.sih26168.idr.ui.theme.Telem
import `in`.sih26168.idr.ui.theme.Text as Fg
import kotlin.math.atan2
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext

private const val ROW_STAGGER_MS = 150L
private const val CHECKLIST_ROWS = 7

/**
 * Aircraft-style pre-flight check. Surfaces [DeviceProbe] inventory + measured
 * rates one row at a time so cold-start time feels like the system arming.
 *
 * No gyroscope → designed degraded explanation, never a crash.
 */
@Composable
fun VehicleCheckScreen(
    bus: IdrBus,
    onFinished: () -> Unit,
    allowSkip: Boolean = true,
) {
    val ctx = LocalContext.current
    val prefs = remember { Prefs(ctx) }
    var check by remember { mutableStateOf(DeviceCheck()) }
    var probing by remember { mutableStateOf(true) }
    var rowsRevealed by remember { mutableIntStateOf(0) }
    var showMagInfo by remember { mutableStateOf(false) }
    var showCalibrate by remember { mutableStateOf(false) }
    var mountEpoch by remember { mutableIntStateOf(0) }
    var gnssDetail by remember { mutableStateOf("checking…") }
    var gnssOk by remember { mutableStateOf(false) }

    LaunchedEffect(Unit) {
        val quick = withContext(Dispatchers.Default) { DeviceProbe.inventory(ctx) }
        check = quick
        bus.publishDevice(quick)
        gnssDetail = gnssLine(ctx)
        gnssOk = gnssLooksReady(ctx)
        val full = withContext(Dispatchers.Default) { DeviceProbe.probe(ctx, quick) }
        check = full
        bus.publishDevice(full)
        probing = false
        // Stagger row reveals after the burst so rates are already known.
        for (i in 1..CHECKLIST_ROWS) {
            rowsRevealed = i
            delay(ROW_STAGGER_MS)
        }
    }

    val noGyro = !check.gyro.present && !check.gyroUncal.present && check.verdict != DeviceVerdict.UNKNOWN
    val allRowsShown = !probing && rowsRevealed >= CHECKLIST_ROWS
    val mount = remember(mountEpoch) { prefs.mount }
    val mountNote = remember(mountEpoch) { prefs.mountNote }

    Column(
        Modifier
            .fillMaxSize()
            .background(Bg)
            .statusBarsPadding()
            .padding(horizontal = 20.dp)
            .padding(top = 12.dp, bottom = 16.dp),
    ) {
        Row(
            Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                "VEHICLE CHECK",
                fontFamily = IdrMono,
                color = Accent,
                fontSize = 13.sp,
                fontWeight = FontWeight.Bold,
                letterSpacing = 2.sp,
            )
            if (allowSkip) {
                TextButton(onClick = {
                    prefs.vehicleCheckDone = true
                    onFinished()
                }) {
                    Text("SKIP", fontFamily = IdrMono, color = Mute, fontSize = 12.sp)
                }
            }
        }

        Text(
            "${check.device.ifBlank { "this phone" }} · ${check.androidRelease.ifBlank { "…" }}",
            fontFamily = IdrMono,
            color = Mute,
            fontSize = 10.sp,
            modifier = Modifier.padding(top = 4.dp, bottom = 16.dp),
        )

        if (noGyro && allRowsShown) {
            NoGyroscopePanel(
                Modifier
                    .weight(1f)
                    .verticalScroll(rememberScrollState()),
            )
        } else {
            Column(
                Modifier
                    .weight(1f)
                    .verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(4.dp),
            ) {
                if (probing && rowsRevealed == 0) {
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(10.dp),
                        modifier = Modifier.padding(vertical = 8.dp),
                    ) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(18.dp),
                            strokeWidth = 2.dp,
                            color = Mute,
                        )
                        Text(
                            "Measuring sensor rates (${DeviceProbe.PROBE_MS / 1000}s)…",
                            fontFamily = IdrSans,
                            color = Mute,
                            fontSize = 13.sp,
                        )
                    }
                }

                ChecklistItem(
                    visible = rowsRevealed >= 1,
                    label = "Accelerometer",
                    status = accelStatus(check),
                    detail = measuredHzDetail(bestAccel(check)),
                )
                ChecklistItem(
                    visible = rowsRevealed >= 2,
                    label = "Gyroscope",
                    status = gyroStatus(check),
                    detail = measuredHzDetail(bestGyro(check)),
                )
                ChecklistItem(
                    visible = rowsRevealed >= 3,
                    label = "Magnetometer",
                    status = if (check.mag.present || check.magUncal.present) {
                        CheckStatus.OK
                    } else {
                        CheckStatus.WARN
                    },
                    detail = if (check.mag.present || check.magUncal.present) {
                        "captured · fused in GNSS outage"
                    } else {
                        "absent · not required"
                    },
                    showInfo = check.mag.present || check.magUncal.present,
                    onInfo = { showMagInfo = true },
                )
                ChecklistItem(
                    visible = rowsRevealed >= 4,
                    label = "Barometer",
                    status = if (check.baro.present) CheckStatus.OK else CheckStatus.WARN,
                    detail = if (check.baro.present) {
                        listOfNotNull(
                            "floor-change detection",
                            measuredHzSuffix(check.baro),
                        ).joinToString(" · ")
                    } else {
                        "optional · horizontal nav unaffected"
                    },
                )
                ChecklistItem(
                    visible = rowsRevealed >= 5,
                    label = "GNSS",
                    status = if (gnssOk) CheckStatus.OK else CheckStatus.WARN,
                    detail = gnssDetail,
                )
                ChecklistItem(
                    visible = rowsRevealed >= 6,
                    label = "Mount alignment",
                    status = if (mount != null) CheckStatus.OK else CheckStatus.WARN,
                    detail = mountDetail(mount, mountNote),
                )
                ChecklistItem(
                    visible = rowsRevealed >= 7,
                    label = "Yaw vs vehicle",
                    status = CheckStatus.WARN,
                    detail = "open — lab alignment was a wash (32%→32%)",
                )

                if (allRowsShown) {
                    Spacer(Modifier.height(12.dp))
                    MountAlignmentCard(
                        mount = mount,
                        mountNote = mountNote,
                        showCalibrate = showCalibrate,
                        onShowCalibrate = { showCalibrate = true },
                        onCalibrateDone = {
                            showCalibrate = false
                            mountEpoch += 1
                        },
                        bus = bus,
                    )
                    Spacer(Modifier.height(16.dp))
                    ReadyBanner(check)
                }
            }
        }

        Spacer(Modifier.height(12.dp))
        Button(
            onClick = {
                prefs.vehicleCheckDone = true
                onFinished()
            },
            enabled = allRowsShown || allowSkip,
            modifier = Modifier
                .fillMaxWidth()
                .height(52.dp),
            colors = ButtonDefaults.buttonColors(containerColor = Accent, contentColor = Bg),
            shape = RoundedCornerShape(10.dp),
        ) {
            Text(
                when {
                    noGyro && allRowsShown -> "CONTINUE ANYWAY"
                    allRowsShown && DeviceProbe.usable(check) -> "READY"
                    allRowsShown -> "CONTINUE"
                    else -> "CHECKING…"
                },
                fontFamily = IdrMono,
                fontSize = 15.sp,
                letterSpacing = 1.6.sp,
                fontWeight = FontWeight.Bold,
            )
        }
    }

    if (showMagInfo) {
        MagnetometerInfoDialog(onDismiss = { showMagInfo = false })
    }
}

@Composable
private fun NoGyroscopePanel(modifier: Modifier = Modifier) {
    Column(
        modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(14.dp))
            .background(Bg2)
            .border(1.dp, Danger.copy(alpha = 0.45f), RoundedCornerShape(14.dp))
            .padding(18.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text(
            "NO GYROSCOPE",
            fontFamily = IdrMono,
            color = Danger,
            fontSize = 13.sp,
            fontWeight = FontWeight.Bold,
            letterSpacing = 2.sp,
        )
        Text(
            "This phone reports no gyroscope.",
            fontFamily = IdrSans,
            color = Fg,
            fontSize = 20.sp,
            fontWeight = FontWeight.SemiBold,
            lineHeight = 26.sp,
        )
        Text(
            "Dead reckoning needs turn rate to keep heading when GPS drops. Without a " +
                "gyro, the app cannot track turns and will not produce a usable " +
                "dead-reckoned path on this device.",
            fontFamily = IdrSans,
            color = Mute,
            fontSize = 14.sp,
            lineHeight = 20.sp,
        )
        Text(
            "What still works",
            fontFamily = IdrSans,
            color = Telem,
            fontSize = 14.sp,
            fontWeight = FontWeight.SemiBold,
        )
        Text(
            "· Live GNSS navigation while satellites are visible\n" +
                "· Session logging and replay of recorded tracks\n" +
                "· Bundled IO-VNBD replay from Settings → Advanced (not a live ride)",
            fontFamily = IdrSans,
            color = Fg,
            fontSize = 13.sp,
            lineHeight = 20.sp,
        )
        Text(
            "What is degraded",
            fontFamily = IdrSans,
            color = Amber,
            fontSize = 14.sp,
            fontWeight = FontWeight.SemiBold,
        )
        Text(
            "· GNSS outages (tunnels, basements, urban canyons) — the marker will not " +
                "coast on motion sensors\n" +
                "· This is a hardware limit, not a setting you can flip.",
            fontFamily = IdrSans,
            color = Fg,
            fontSize = 13.sp,
            lineHeight = 20.sp,
        )
    }
}

@Composable
private fun ReadyBanner(check: DeviceCheck) {
    val (tint, line) = when (check.verdict) {
        DeviceVerdict.PASS -> Telem to "Ready. Dead reckoning available."
        DeviceVerdict.DEGRADED -> Amber to "Ready, with limits. ${DeviceProbe.headline(check)}"
        DeviceVerdict.FAIL -> Danger to DeviceProbe.headline(check)
        DeviceVerdict.UNKNOWN -> Mute to "Checking sensors…"
    }
    Text(
        line,
        fontFamily = IdrSans,
        color = tint,
        fontSize = 16.sp,
        fontWeight = FontWeight.SemiBold,
        lineHeight = 22.sp,
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(12.dp))
            .background(tint.copy(alpha = 0.12f))
            .border(1.dp, tint.copy(alpha = 0.35f), RoundedCornerShape(12.dp))
            .padding(14.dp),
    )
}

private enum class CheckStatus { OK, WARN, FAIL, PENDING }

@Composable
private fun ChecklistItem(
    visible: Boolean,
    label: String,
    status: CheckStatus,
    detail: String,
    showInfo: Boolean = false,
    onInfo: (() -> Unit)? = null,
) {
    AnimatedVisibility(
        visible = visible,
        enter = fadeIn() + slideInVertically { it / 3 },
    ) {
        val tint = when (status) {
            CheckStatus.OK -> Telem
            CheckStatus.WARN -> Amber
            CheckStatus.FAIL -> Danger
            CheckStatus.PENDING -> Mute
        }
        val mark = when (status) {
            CheckStatus.OK -> "✓"
            CheckStatus.WARN -> "!"
            CheckStatus.FAIL -> "×"
            CheckStatus.PENDING -> "·"
        }
        Row(
            Modifier
                .fillMaxWidth()
                .padding(vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                label,
                fontFamily = IdrSans,
                color = Fg,
                fontSize = 15.sp,
                modifier = Modifier.weight(1.15f),
            )
            Box(
                Modifier
                    .padding(end = 8.dp)
                    .size(22.dp)
                    .clip(CircleShape)
                    .background(tint.copy(alpha = 0.18f))
                    .border(1.dp, tint.copy(alpha = 0.45f), CircleShape),
                contentAlignment = Alignment.Center,
            ) {
                Text(mark, fontFamily = IdrMono, color = tint, fontSize = 12.sp, fontWeight = FontWeight.Bold)
            }
            Text(
                detail,
                fontFamily = IdrMono,
                color = Mute,
                fontSize = 12.sp,
                modifier = Modifier.weight(1.35f),
                lineHeight = 16.sp,
            )
            if (showInfo && onInfo != null) {
                Text(
                    "ⓘ",
                    modifier = Modifier
                        .padding(start = 6.dp)
                        .semantics { contentDescription = "Magnetometer details" }
                        .clickable(onClick = onInfo)
                        .padding(4.dp),
                    fontFamily = IdrSans,
                    color = Accent,
                    fontSize = 16.sp,
                )
            }
        }
    }
}

@Composable
fun MagnetometerInfoDialog(onDismiss: () -> Unit) {
    AlertDialog(
        onDismissRequest = onDismiss,
        containerColor = Bg2,
        title = {
            Text("Magnetometer — onset-calibrated fuse in outage", fontFamily = IdrSans, color = Fg, fontSize = 18.sp)
        },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Text(
                    "We now fuse an onset-calibrated compass during GNSS outage. " +
                        "The offset is taken from the last GNSS bearing before the signal died — " +
                        "no oracle, implementable on this phone.",
                    fontFamily = IdrSans,
                    color = Mute,
                    fontSize = 13.sp,
                    lineHeight = 18.sp,
                )
                Text(
                    "Lab heading_fusion: heading-induced drift falls from 16.87% (gyro alone) " +
                        "to 7.22% (onset-calibrated compass) across 655 outage windows. " +
                        "That is still not good enough to navigate on alone — a heading error " +
                        "held over distance puts you sideways. Map-in-loop remains the road lock.",
                    fontFamily = IdrSans,
                    color = Fg,
                    fontSize = 13.sp,
                    lineHeight = 18.sp,
                )
                Text(
                    "The older magnetometer study (perfect per-drive offset) still shows " +
                        "~16.6° median compass error vs GPS course. Fusing the compass is a " +
                        "measured gain, not a replacement for the map.",
                    fontFamily = IdrSans,
                    color = Mute,
                    fontSize = 13.sp,
                    lineHeight = 18.sp,
                )
                Text(
                    "Sources: lab/stress/results/heading_fusion/summary.md · " +
                        "lab/stress/results/magnetometer/summary.md",
                    fontFamily = IdrMono,
                    color = Mute,
                    fontSize = 10.sp,
                    lineHeight = 14.sp,
                )
            }
        },
        confirmButton = {
            TextButton(onClick = onDismiss) {
                Text("GOT IT", fontFamily = IdrMono, color = Accent, fontSize = 12.sp)
            }
        },
    )
}

@Composable
private fun MountAlignmentCard(
    mount: MountRotation?,
    mountNote: String,
    showCalibrate: Boolean,
    onShowCalibrate: () -> Unit,
    onCalibrateDone: () -> Unit,
    bus: IdrBus,
) {
    Column(
        Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(14.dp))
            .background(Bg2)
            .border(1.dp, Amber.copy(alpha = 0.35f), RoundedCornerShape(14.dp))
            .padding(14.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Text(
            "MOUNT · GRAVITY FRAME",
            fontFamily = IdrMono,
            color = Accent,
            fontSize = 10.sp,
            letterSpacing = 1.4.sp,
        )
        val angles = if (mount != null) {
            val (pitch, roll) = pitchRollDeg(mount)
            "Pitch %.0f°  ·  roll %.0f°  (from last calibration gravity frame)"
                .format(pitch, roll)
        } else {
            "Pitch/roll unknown — no stored mount. Recalibrate to measure gravity."
        }
        Text(
            angles,
            fontFamily = IdrSans,
            color = Fg,
            fontSize = 14.sp,
            lineHeight = 20.sp,
        )
        if (mountNote.isNotBlank()) {
            Text(mountNote, fontFamily = IdrSans, color = Mute, fontSize = 12.sp, lineHeight = 16.sp)
        }
        Text(
            "Yaw vs vehicle: open — lab alignment was a wash (32%→32%). Recalibrate.",
            fontFamily = IdrSans,
            color = Amber,
            fontSize = 13.sp,
            lineHeight = 18.sp,
        )
        if (showCalibrate) {
            Text(
                "Same 8-second straight run as onboarding. Stand still, then walk forward.",
                fontFamily = IdrSans,
                color = Mute,
                fontSize = 12.sp,
                lineHeight = 16.sp,
            )
            CalibrationCard(bus = bus)
            SecondaryButton("DONE", Modifier.fillMaxWidth(), onCalibrateDone)
        } else {
            SecondaryButton("RECALIBRATE", Modifier.fillMaxWidth(), onShowCalibrate)
        }
    }
}

private fun bestAccel(c: DeviceCheck): SensorSpec =
    if (c.accelUncal.present) c.accelUncal else c.accel

private fun bestGyro(c: DeviceCheck): SensorSpec =
    if (c.gyroUncal.present) c.gyroUncal else c.gyro

private fun accelStatus(c: DeviceCheck): CheckStatus = when {
    !c.accel.present && !c.accelUncal.present -> CheckStatus.FAIL
    else -> CheckStatus.OK
}

private fun gyroStatus(c: DeviceCheck): CheckStatus = when {
    !c.gyro.present && !c.gyroUncal.present -> CheckStatus.FAIL
    else -> CheckStatus.OK
}

private fun measuredHzDetail(spec: SensorSpec): String {
    if (!spec.present) return "not present"
    val m = spec.measuredHz
    return if (m.isFinite() && m > 0.0) {
        "%.0f Hz measured".format(m)
    } else if (spec.advertisedHz.isFinite()) {
        "%.0f Hz advertised".format(spec.advertisedHz)
    } else {
        "present · rate unknown"
    }
}

private fun measuredHzSuffix(spec: SensorSpec): String? {
    val m = spec.measuredHz
    return if (m.isFinite() && m > 0.0) "%.0f Hz".format(m) else null
}

private fun mountDetail(mount: MountRotation?, note: String): String {
    if (mount == null) return "not calibrated · run from onboarding"
    val (pitch, roll) = pitchRollDeg(mount)
    val angles = "pitch %.0f° roll %.0f°".format(pitch, roll)
    return if (note.isNotBlank()) "calibrated · $angles" else "calibrated · $angles"
}

/**
 * Approximate phone pitch/roll from the calibrated mount: device +Z (out of
 * screen) expressed in vehicle axes (forward, right, down).
 */
private fun pitchRollDeg(r: MountRotation): Pair<Double, Double> {
    val (fwd, right, down) = rotateToVehicle(r, 0.0, 0.0, 1.0)
    val pitch = Math.toDegrees(atan2(fwd, -down))
    val roll = Math.toDegrees(atan2(right, -down))
    return pitch to roll
}

private fun gnssLooksReady(ctx: Context): Boolean {
    if (LocationGate.blockingStatus(ctx) != null) return false
    return lastKnownAccuracyM(ctx) != null || LocationGate.hasPermission(ctx)
}

private fun gnssLine(ctx: Context): String {
    LocationGate.blockingStatus(ctx)?.let { return LocationGate.headline(it) }
    val acc = lastKnownAccuracyM(ctx)
    return if (acc != null) {
        "%.1f m accuracy".format(acc)
    } else if (LocationGate.hasPermission(ctx)) {
        "ready · waiting for first fix"
    } else {
        "permission not granted"
    }
}

@Suppress("MissingPermission")
private fun lastKnownAccuracyM(ctx: Context): Double? {
    val fine = ContextCompat.checkSelfPermission(ctx, Manifest.permission.ACCESS_FINE_LOCATION) ==
        PackageManager.PERMISSION_GRANTED
    val coarse = ContextCompat.checkSelfPermission(ctx, Manifest.permission.ACCESS_COARSE_LOCATION) ==
        PackageManager.PERMISSION_GRANTED
    if (!fine && !coarse) return null
    val lm = ctx.getSystemService(Context.LOCATION_SERVICE) as? LocationManager ?: return null
    val providers = listOf(
        LocationManager.GPS_PROVIDER,
        LocationManager.NETWORK_PROVIDER,
        LocationManager.PASSIVE_PROVIDER,
    )
    var best: Float? = null
    for (p in providers) {
        val loc = try {
            if (lm.isProviderEnabled(p)) lm.getLastKnownLocation(p) else null
        } catch (_: SecurityException) {
            null
        } catch (_: Exception) {
            null
        } ?: continue
        if (loc.hasAccuracy()) {
            val a = loc.accuracy
            if (best == null || a < best) best = a
        }
    }
    return best?.toDouble()
}
