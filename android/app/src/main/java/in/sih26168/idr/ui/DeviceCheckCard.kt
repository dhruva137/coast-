package `in`.sih26168.idr.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
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
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import `in`.sih26168.idr.IdrBus
import `in`.sih26168.idr.data.DeviceCheck
import `in`.sih26168.idr.data.DeviceVerdict
import `in`.sih26168.idr.data.FindingLevel
import `in`.sih26168.idr.sensor.DeviceProbe
import `in`.sih26168.idr.ui.theme.Amber
import `in`.sih26168.idr.ui.theme.Bg2
import `in`.sih26168.idr.ui.theme.Danger
import `in`.sih26168.idr.ui.theme.IdrMono
import `in`.sih26168.idr.ui.theme.IdrSans
import `in`.sih26168.idr.ui.theme.Line
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
 * If the verdict is FAIL the card says so in as many words. It does not offer a
 * reduced mode and pretend everything is fine.
 */
@Composable
fun DeviceCheckCard(bus: IdrBus, compact: Boolean = false) {
    val ctx = LocalContext.current
    var check by remember { mutableStateOf(DeviceCheck()) }
    var probing by remember { mutableStateOf(true) }

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
                Box(dotColor = c)
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
                    "not a setting.",
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
}

/** Small status dot. Named Box to keep the call sites short and aligned. */
@Composable
private fun Box(dotColor: Color) {
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
