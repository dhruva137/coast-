package `in`.sih26168.idr.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
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
import `in`.sih26168.idr.IdrBus
import `in`.sih26168.idr.data.DeviceCheck
import `in`.sih26168.idr.data.DeviceVerdict
import `in`.sih26168.idr.data.FindingLevel
import `in`.sih26168.idr.data.SensorSpec
import `in`.sih26168.idr.sensor.DeviceProbe
import `in`.sih26168.idr.ui.theme.Amber
import `in`.sih26168.idr.ui.theme.Bg2
import `in`.sih26168.idr.ui.theme.Danger
import `in`.sih26168.idr.ui.theme.IdrMono
import `in`.sih26168.idr.ui.theme.IdrSans
import `in`.sih26168.idr.ui.theme.Mute
import `in`.sih26168.idr.ui.theme.Telem
import `in`.sih26168.idr.ui.theme.Text as Fg
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/**
 * Runs the hardware self-check and shows the result as a pass/fail card.
 *
 * The inventory is instant; the measured-rate probe takes about two and a half
 * seconds and runs off the main thread. Both results go on the bus so the
 * Diagnostics panel can quote the measured rates later.
 *
 * Non-compact mode includes a short pre-flight row strip (rates + magnetometer
 * ⓘ) matching Vehicle Check. FAIL still says so plainly — no silent reduce mode.
 */
@Composable
fun DeviceCheckCard(bus: IdrBus, compact: Boolean = false) {
    val ctx = LocalContext.current
    var check by remember { mutableStateOf(DeviceCheck()) }
    var probing by remember { mutableStateOf(true) }
    var showMagInfo by remember { mutableStateOf(false) }

    LaunchedEffect(Unit) {
        val quick = withContext(Dispatchers.Default) { DeviceProbe.inventory(ctx) }
        check = quick
        bus.publishDevice(quick)
        val full = withContext(Dispatchers.Default) { DeviceProbe.probe(ctx, quick) }
        check = full
        bus.publishDevice(full)
        probing = false
    }

    val tint = when (check.verdict) {
        DeviceVerdict.PASS -> Telem
        DeviceVerdict.DEGRADED -> Amber
        DeviceVerdict.FAIL -> Danger
        DeviceVerdict.UNKNOWN -> Mute
    }

    Column(
        Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(14.dp))
            .background(Bg2)
            .border(1.dp, tint.copy(alpha = 0.4f), RoundedCornerShape(14.dp))
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(
                check.verdict.name,
                fontFamily = IdrMono,
                color = tint,
                fontSize = 13.sp,
                fontWeight = FontWeight.Bold,
                letterSpacing = 2.sp,
            )
            Spacer(Modifier.weight(1f))
            if (probing) {
                CircularProgressIndicator(
                    modifier = Modifier.size(16.dp),
                    strokeWidth = 2.dp,
                    color = Mute,
                )
            }
        }
        Text(
            DeviceProbe.headline(check),
            fontFamily = IdrSans,
            color = Fg,
            fontSize = 18.sp,
            fontWeight = FontWeight.SemiBold,
            lineHeight = 23.sp,
        )
        Text(
            "${check.device} · ${check.androidRelease}",
            fontFamily = IdrMono,
            color = Mute,
            fontSize = 10.sp,
        )
        if (probing) {
            Text(
                "Measuring how fast the sensors actually deliver data " +
                    "(${DeviceProbe.PROBE_MS / 1000} seconds). Advertised rates and real " +
                    "rates often differ on mid-range hardware.",
                fontFamily = IdrSans,
                color = Mute,
                fontSize = 12.sp,
                lineHeight = 16.sp,
            )
        }

        if (!compact && !probing) {
            SensorRateStrip(check = check, onMagInfo = { showMagInfo = true })
        }

        val findings = if (compact) {
            check.findings.filter { it.level != FindingLevel.OK }.ifEmpty { check.findings.take(2) }
        } else {
            check.findings
        }
        findings.forEach { f ->
            val c: Color = when (f.level) {
                FindingLevel.OK -> Telem
                FindingLevel.WARN -> Amber
                FindingLevel.FAIL -> Danger
            }
            Row(Modifier.fillMaxWidth().padding(top = 4.dp)) {
                StatusDot(dotColor = c)
                Column(Modifier.padding(start = 10.dp)) {
                    Text(
                        f.title,
                        fontFamily = IdrSans,
                        color = c,
                        fontSize = 14.sp,
                        fontWeight = FontWeight.Medium,
                        lineHeight = 18.sp,
                    )
                    Text(
                        f.detail,
                        fontFamily = IdrSans,
                        color = Mute,
                        fontSize = 12.sp,
                        lineHeight = 17.sp,
                    )
                }
            }
        }

        if (check.verdict == DeviceVerdict.FAIL) {
            Text(
                "The app will still open and still log data, but it will not produce a " +
                    "usable dead-reckoned track on this phone. That is a hardware limit, " +
                    "not a setting. Open Vehicle Check from Settings for the full explanation.",
                fontFamily = IdrSans,
                color = Danger,
                fontSize = 13.sp,
                lineHeight = 18.sp,
                modifier = Modifier.padding(top = 4.dp),
            )
        }
        Text(
            "Rates shown as measured were counted by this app on this phone just now. " +
                "Rates shown as advertised are what the driver claims.",
            fontFamily = IdrMono,
            color = Mute,
            fontSize = 9.sp,
            lineHeight = 13.sp,
            modifier = Modifier.padding(top = 4.dp),
        )
    }

    if (showMagInfo) {
        MagnetometerInfoDialog(onDismiss = { showMagInfo = false })
    }
}

/** Compact rate rows mirroring Vehicle Check — used on the About/Help card. */
@Composable
private fun SensorRateStrip(check: DeviceCheck, onMagInfo: () -> Unit) {
    Column(
        Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(10.dp))
            .background(Color(0xFF0B0E11).copy(alpha = 0.55f))
            .padding(horizontal = 12.dp, vertical = 10.dp),
        verticalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        RateLine("Accelerometer", rateLabel(if (check.accelUncal.present) check.accelUncal else check.accel))
        RateLine("Gyroscope", rateLabel(if (check.gyroUncal.present) check.gyroUncal else check.gyro))
        Row(
            Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                "Magnetometer",
                fontFamily = IdrSans,
                color = Fg,
                fontSize = 13.sp,
                modifier = Modifier.weight(1f),
            )
            Text(
                if (check.mag.present || check.magUncal.present) {
                    "captured · fused in outage"
                } else {
                    "absent"
                },
                fontFamily = IdrMono,
                color = Mute,
                fontSize = 11.sp,
            )
            if (check.mag.present || check.magUncal.present) {
                Text(
                    "ⓘ",
                    modifier = Modifier
                        .padding(start = 6.dp)
                        .semantics { contentDescription = "Magnetometer details" }
                        .clickable(onClick = onMagInfo)
                        .padding(2.dp),
                    fontFamily = IdrSans,
                    color = Telem,
                    fontSize = 14.sp,
                )
            }
        }
        RateLine(
            "Barometer",
            if (check.baro.present) {
                rateLabel(check.baro).ifBlank { "present" }
            } else {
                "optional"
            },
        )
    }
}

@Composable
private fun RateLine(label: String, value: String) {
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
        Text(label, fontFamily = IdrSans, color = Fg, fontSize = 13.sp, modifier = Modifier.weight(1f))
        Text(value, fontFamily = IdrMono, color = Mute, fontSize = 11.sp)
    }
}

private fun rateLabel(spec: SensorSpec): String {
    if (!spec.present) return "not present"
    val m = spec.measuredHz
    return if (m.isFinite() && m > 0.0) "%.0f Hz measured".format(m)
    else if (spec.advertisedHz.isFinite()) "%.0f Hz advertised".format(spec.advertisedHz)
    else "present"
}

/** Small status dot. */
@Composable
private fun StatusDot(dotColor: Color) {
    androidx.compose.foundation.layout.Box(
        Modifier
            .padding(top = 5.dp)
            .size(8.dp)
            .clip(CircleShape)
            .background(dotColor),
    )
}

/** Line used on the Drive screen when the device check found something bad. */
@Composable
fun DeviceWarningLine(check: DeviceCheck) {
    if (check.verdict == DeviceVerdict.PASS || check.verdict == DeviceVerdict.UNKNOWN) return
    val tint = if (check.verdict == DeviceVerdict.FAIL) Danger else Amber
    Text(
        DeviceProbe.headline(check),
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(10.dp))
            .background(tint.copy(alpha = 0.12f))
            .border(1.dp, tint.copy(alpha = 0.35f), RoundedCornerShape(10.dp))
            .padding(12.dp),
        fontFamily = IdrSans,
        color = tint,
        fontSize = 13.sp,
    )
}
