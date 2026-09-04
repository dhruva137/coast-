package `in`.sih26168.idr.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import `in`.sih26168.idr.IdrBus
import `in`.sih26168.idr.data.MountQuality
import `in`.sih26168.idr.data.MountResult
import `in`.sih26168.idr.data.Prefs
import `in`.sih26168.idr.nav.MountCalibration
import `in`.sih26168.idr.nav.describeMount
import `in`.sih26168.idr.sensor.SensorHub
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
import kotlinx.coroutines.delay

private const val CAPTURE_SECONDS = 8

/**
 * The straight-line calibration step.
 *
 * The user stands still, presses start, then moves forward in a straight line
 * for [CAPTURE_SECONDS] seconds. [MountCalibration] turns that into the
 * phone-to-vehicle rotation; see that class for the derivation and for the
 * conditions under which it refuses to produce one.
 *
 * A refusal is shown as a refusal. The app never stores a rotation it does not
 * believe, because a wrong mount frame is worse than no mount frame: it would
 * feed the lean solver axes that are confidently incorrect.
 */
@Composable
fun CalibrationCard(bus: IdrBus) {
    val ctx = LocalContext.current
    val prefs = remember { Prefs(ctx) }
    var running by remember { mutableStateOf(false) }
    var elapsed by remember { mutableStateOf(0) }
    var result by remember { mutableStateOf<MountResult?>(null) }
    var saved by remember { mutableStateOf(prefs.mount != null) }
    var savedNote by remember { mutableStateOf(prefs.mountNote) }

    val calibration = remember { MountCalibration() }
    var hub by remember { mutableStateOf<SensorHub?>(null) }

    DisposableEffect(Unit) {
        onDispose {
            hub?.stop()
            hub = null
        }
    }

    LaunchedEffect(running) {
        if (!running) return@LaunchedEffect
        elapsed = 0
        while (elapsed < CAPTURE_SECONDS && running) {
            delay(1000)
            elapsed += 1
        }
        if (running) {
            hub?.stop()
            hub = null
            val r = calibration.solve()
            result = r
            running = false
            if (r.rotation != null && r.quality != MountQuality.REJECTED) {
                prefs.mount = r.rotation
                prefs.mountNote = describeMount(r)
                savedNote = prefs.mountNote
                saved = true
                // Tell a live NAVIGATE session to reload the frame.
                bus.mountDirty = true
            }
        }
    }

    Column(
        Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(14.dp))
            .background(Bg2)
            .border(1.dp, Line, RoundedCornerShape(14.dp))
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Text(
            "Teach it how your phone is mounted",
            fontFamily = IdrSans,
            color = Fg,
            fontSize = 18.sp,
            fontWeight = FontWeight.SemiBold,
        )
        Text(
            "The app measures turning and acceleration in the phone axes. It needs to " +
                "know how those line up with the vehicle. One short straight run tells it.",
            fontFamily = IdrSans,
            color = Mute,
            fontSize = 13.sp,
            lineHeight = 18.sp,
        )
        Text(
            "1. Mount or hold the phone exactly as you will use it.\n" +
                "2. Come to a complete stop.\n" +
                "3. Press START, then move straight forward for $CAPTURE_SECONDS seconds.\n" +
                "4. Do not turn, and do not move the phone.",
            fontFamily = IdrSans,
            color = Fg,
            fontSize = 13.sp,
            lineHeight = 20.sp,
        )

        if (running) {
            LinearProgressIndicator(
                progress = { elapsed.toFloat() / CAPTURE_SECONDS },
                modifier = Modifier.fillMaxWidth(),
                color = Accent,
                trackColor = Line,
            )
            Text(
                "Keep going straight — ${CAPTURE_SECONDS - elapsed} s left",
                fontFamily = IdrMono,
                color = Accent,
                fontSize = 14.sp,
            )
        }

        Button(
            onClick = {
                if (running) {
                    running = false
                    hub?.stop()
                    hub = null
                    result = null
                } else {
                    result = null
                    calibration.reset()
                    val h = SensorHub(ctx) { frame -> calibration.add(frame) }
                    hub = h
                    h.start()
                    running = true
                }
            },
            modifier = Modifier.fillMaxWidth(),
            colors = ButtonDefaults.buttonColors(
                containerColor = if (running) Danger else Accent,
                contentColor = Bg,
            ),
            shape = RoundedCornerShape(10.dp),
        ) {
            Text(
                if (running) "CANCEL" else if (saved) "CALIBRATE AGAIN" else "START CALIBRATION",
                fontFamily = IdrMono,
                letterSpacing = 1.4.sp,
            )
        }

        result?.let { r ->
            val tint = when (r.quality) {
                MountQuality.GOOD -> Telem
                MountQuality.WEAK -> Amber
                MountQuality.REJECTED -> Danger
            }
            Text(
                when (r.quality) {
                    MountQuality.GOOD -> "CALIBRATED"
                    MountQuality.WEAK -> "CALIBRATED, WEAKLY"
                    MountQuality.REJECTED -> "NOT CALIBRATED"
                },
                fontFamily = IdrMono,
                color = tint,
                fontSize = 13.sp,
                letterSpacing = 1.6.sp,
                fontWeight = FontWeight.Bold,
            )
            Text(r.reason, fontFamily = IdrSans, color = Fg, fontSize = 13.sp, lineHeight = 18.sp)
            if (r.rotation != null) {
                Text(
                    describeMount(r),
                    fontFamily = IdrMono,
                    color = Mute,
                    fontSize = 11.sp,
                )
            }
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Text(
                    "speed change %.2f m/s".format(r.deltaVMps),
                    fontFamily = IdrMono, color = Mute, fontSize = 10.sp,
                )
                Text(
                    "peak turn %.2f rad/s".format(r.peakGyroRadS),
                    fontFamily = IdrMono, color = Mute, fontSize = 10.sp,
                )
                Text(
                    "${r.samples} samples",
                    fontFamily = IdrMono, color = Mute, fontSize = 10.sp,
                )
            }
        }

        if (result == null && saved) {
            Text(
                "Saved from an earlier run: $savedNote",
                fontFamily = IdrMono,
                color = Telem,
                fontSize = 11.sp,
                lineHeight = 15.sp,
            )
        }
        if (result == null && !saved) {
            Text(
                "Not calibrated. The app still works — it falls back to the raw phone " +
                    "axes, which is right only if the phone is upright and square to the " +
                    "direction of travel.",
                fontFamily = IdrSans,
                color = Amber,
                fontSize = 12.sp,
                lineHeight = 16.sp,
            )
        }

        Text(
            "You can skip this and do it later from Help.",
            fontFamily = IdrSans,
            color = Mute,
            fontSize = 12.sp,
            modifier = Modifier.padding(top = 2.dp),
        )
        if (saved) {
            Text(
                "Clear it if you move the phone to a different mount.",
                fontFamily = IdrSans,
                color = Mute,
                fontSize = 12.sp,
            )
            SecondaryButton("CLEAR CALIBRATION", Modifier.fillMaxWidth()) {
                prefs.mount = null
                prefs.mountNote = ""
                saved = false
                savedNote = ""
                result = null
                bus.mountDirty = true
            }
        }
    }
}
