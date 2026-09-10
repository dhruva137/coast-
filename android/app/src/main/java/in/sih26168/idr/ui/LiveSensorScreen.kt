package `in`.sih26168.idr.ui

import android.content.Context
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text as M3Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
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
import kotlin.math.abs
import kotlin.math.atan2
import kotlin.math.hypot
import kotlin.math.roundToInt
import kotlin.math.sqrt
import kotlinx.coroutines.delay

/**
 * Live sensor screen — the "hold the phone and see the estimator respond" demo.
 *
 * This is the causal-response screen a judge performs themselves: tilt → the
 * spirit-level ball rolls; shake → the shake meter jumps and the event chip
 * fires; hold still → ZUPT engages. Nothing here is drawn on a map; the label
 * "RELATIVE MOTION — no GNSS" sits in the same visual layer as the numbers so
 * no glance can mistake this for an absolute fix.
 */
@Composable
fun LiveSensorScreen(onBack: (() -> Unit)? = null) {
    val ctx = LocalContext.current
    val sm = remember { ctx.getSystemService(Context.SENSOR_SERVICE) as SensorManager }

    // Live sensor state (updated at sensor rate, ~50–200 Hz on most devices).
    var pitchDeg by remember { mutableStateOf(0f) }   // + = nose up
    var rollDeg by remember { mutableStateOf(0f) }    // + = right-side up
    var shakeMag by remember { mutableStateOf(0f) }   // m/s^2, linear |a|
    var gyroMag by remember { mutableStateOf(0f) }    // rad/s |ω|
    var lastEvent by remember { mutableStateOf<LiveEvent?>(null) }

    // Rolling stats for event detection.
    val ringSize = 30
    val shakeRing = remember { FloatArray(ringSize) }
    var ringIdx by remember { mutableStateOf(0) }
    var ringFilled by remember { mutableStateOf(false) }
    var stationarySinceMs by remember { mutableStateOf(0L) }
    var lastBumpMs by remember { mutableStateOf(0L) }
    var lastVibMs by remember { mutableStateOf(0L) }
    var lastZuptMs by remember { mutableStateOf(0L) }

    DisposableEffect(Unit) {
        val accel = sm.getDefaultSensor(Sensor.TYPE_LINEAR_ACCELERATION)
            ?: sm.getDefaultSensor(Sensor.TYPE_ACCELEROMETER)
        val gravity = sm.getDefaultSensor(Sensor.TYPE_GRAVITY)
            ?: sm.getDefaultSensor(Sensor.TYPE_ACCELEROMETER)
        val gyro = sm.getDefaultSensor(Sensor.TYPE_GYROSCOPE)

        val listener = object : SensorEventListener {
            override fun onSensorChanged(e: SensorEvent) {
                when (e.sensor?.type) {
                    Sensor.TYPE_LINEAR_ACCELERATION -> {
                        val (ax, ay, az) = Triple(e.values[0], e.values[1], e.values[2])
                        val mag = sqrt(ax * ax + ay * ay + az * az)
                        shakeMag = 0.7f * shakeMag + 0.3f * mag
                        shakeRing[ringIdx] = mag
                        ringIdx = (ringIdx + 1) % ringSize
                        if (ringIdx == 0) ringFilled = true

                        val now = System.currentTimeMillis()
                        // Bump: sharp single spike above 8 m/s^2 and 300ms since last.
                        if (mag > 8f && now - lastBumpMs > 300) {
                            lastBumpMs = now
                            lastEvent = LiveEvent(
                                kind = LiveEventKind.BUMP,
                                trigger = "|a_linear| = %.1f m/s^2".format(mag),
                                atMs = now,
                            )
                        }
                        // Sustained vibration: ring average above 3 m/s^2.
                        if (ringFilled) {
                            var sum = 0f
                            for (v in shakeRing) sum += v
                            val avg = sum / ringSize
                            if (avg > 3f && now - lastVibMs > 800) {
                                lastVibMs = now
                                lastEvent = LiveEvent(
                                    kind = LiveEventKind.VIB,
                                    trigger = "avg |a| over 30 samples = %.1f".format(avg),
                                    atMs = now,
                                )
                            }
                        }
                        // Stationary: |a_linear| < 0.15 for >800ms → ZUPT.
                        if (mag < 0.15f) {
                            if (stationarySinceMs == 0L) stationarySinceMs = now
                            else if (now - stationarySinceMs > 800 &&
                                now - lastZuptMs > 1500
                            ) {
                                lastZuptMs = now
                                lastEvent = LiveEvent(
                                    kind = LiveEventKind.ZUPT,
                                    trigger = "held < 0.15 m/s^2 for > 800 ms",
                                    atMs = now,
                                )
                            }
                        } else {
                            stationarySinceMs = 0L
                        }
                    }
                    Sensor.TYPE_GRAVITY, Sensor.TYPE_ACCELEROMETER -> {
                        val (gx, gy, gz) = Triple(e.values[0], e.values[1], e.values[2])
                        val pitch = Math.toDegrees(
                            atan2((-gx).toDouble(), hypot(gy.toDouble(), gz.toDouble()))
                        ).toFloat()
                        val roll = Math.toDegrees(
                            atan2(gy.toDouble(), gz.toDouble())
                        ).toFloat()
                        pitchDeg = 0.85f * pitchDeg + 0.15f * pitch
                        rollDeg = 0.85f * rollDeg + 0.15f * roll
                    }
                    Sensor.TYPE_GYROSCOPE -> {
                        val (wx, wy, wz) = Triple(e.values[0], e.values[1], e.values[2])
                        val m = sqrt(wx * wx + wy * wy + wz * wz)
                        gyroMag = 0.7f * gyroMag + 0.3f * m
                    }
                }
            }

            override fun onAccuracyChanged(sensor: Sensor?, accuracy: Int) = Unit
        }

        // Register only what exists. UI rate (~60Hz) is enough for the demo and
        // saves battery vs GAME rate.
        accel?.let { sm.registerListener(listener, it, SensorManager.SENSOR_DELAY_UI) }
        if (gravity !== accel) {
            gravity?.let { sm.registerListener(listener, it, SensorManager.SENSOR_DELAY_UI) }
        }
        gyro?.let { sm.registerListener(listener, it, SensorManager.SENSOR_DELAY_UI) }

        onDispose { sm.unregisterListener(listener) }
    }

    // Dismiss event chip after 2.5 s.
    LaunchedEffect(lastEvent?.atMs) {
        val ev = lastEvent ?: return@LaunchedEffect
        val at = ev.atMs
        delay(2500)
        if (lastEvent?.atMs == at) lastEvent = null
    }

    val motion = when {
        shakeMag < 0.20f -> MotionState.STILL
        shakeMag < 1.0f -> MotionState.LIGHT
        shakeMag < 4.0f -> MotionState.WALKING
        else -> MotionState.STRONG
    }

    Column(
        Modifier
            .fillMaxSize()
            .background(Bg)
            .statusBarsPadding()
            .padding(horizontal = 16.dp, vertical = 12.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        if (onBack != null) {
            M3Text(
                "← BACK",
                modifier = Modifier
                    .semantics { contentDescription = "Back" }
                    .clickable(onClick = onBack)
                    .padding(vertical = 6.dp),
                fontFamily = IdrMono,
                color = Accent,
                fontSize = 11.sp,
                letterSpacing = 1.sp,
            )
        }

        M3Text(
            "Live sensor",
            fontFamily = IdrSans,
            color = Fg,
            fontSize = 26.sp,
            fontWeight = FontWeight.SemiBold,
        )
        M3Text(
            "RELATIVE MOTION — no GNSS, no map. Tilt, walk, tap — the estimator responds in real time.",
            fontFamily = IdrSans,
            color = Mute,
            fontSize = 13.sp,
        )

        // Spirit level — the thing a judge actually reacts to.
        SpiritLevel(pitchDeg = pitchDeg, rollDeg = rollDeg)

        // Live numeric readouts.
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            ReadoutCard(
                label = "PITCH",
                value = "%+.0f°".format(pitchDeg),
                sub = "nose up / down",
                modifier = Modifier.weight(1f),
            )
            ReadoutCard(
                label = "ROLL",
                value = "%+.0f°".format(rollDeg),
                sub = "left / right tilt",
                modifier = Modifier.weight(1f),
            )
        }
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            ReadoutCard(
                label = "SHAKE",
                value = "%.1f".format(shakeMag),
                sub = "m/s² · linear accel",
                tint = shakeTint(shakeMag),
                modifier = Modifier.weight(1f),
            )
            ReadoutCard(
                label = "SPIN",
                value = "%.2f".format(gyroMag),
                sub = "rad/s · gyro magnitude",
                modifier = Modifier.weight(1f),
            )
        }

        // Motion state chip.
        MotionStateChip(state = motion)

        // Live shake bar.
        ShakeBar(mag = shakeMag)

        // Event chip.
        Box(Modifier.fillMaxWidth().height(60.dp), contentAlignment = Alignment.Center) {
            lastEvent?.let { EventChip(event = it) }
                ?: M3Text(
                    "Bump the phone, hold it still, or shake it.",
                    color = Mute,
                    fontFamily = IdrSans,
                    fontSize = 12.sp,
                )
        }
    }
}

// ---------------------------------------------------------------------------
// Spirit level — the causal element
// ---------------------------------------------------------------------------

@Composable
private fun SpiritLevel(pitchDeg: Float, rollDeg: Float) {
    // Ball position: map ±45° → ±1.0 (clamped).
    val nx = (rollDeg / 45f).coerceIn(-1f, 1f)
    val ny = (pitchDeg / 45f).coerceIn(-1f, 1f)

    val ballX = remember { Animatable(0f) }
    val ballY = remember { Animatable(0f) }
    LaunchedEffect(nx, ny) {
        ballX.animateTo(nx, animationSpec = tween(120))
        ballY.animateTo(ny, animationSpec = tween(120))
    }

    val level = hypot(nx, ny) < 0.05f

    Box(
        Modifier
            .fillMaxWidth()
            .aspectRatio(1f)
            .clip(RoundedCornerShape(16.dp))
            .background(Bg2)
            .border(1.dp, Line, RoundedCornerShape(16.dp)),
        contentAlignment = Alignment.Center,
    ) {
        Canvas(Modifier.fillMaxSize()) {
            val w = size.width
            val h = size.height
            val cx = w / 2f
            val cy = h / 2f
            val r = minOf(w, h) * 0.42f

            // Outer ring.
            drawCircle(color = Line, radius = r, center = Offset(cx, cy), style = Stroke(width = 2f))
            // Inner rings for scale (15°, 30°).
            drawCircle(color = Line.copy(alpha = 0.45f), radius = r * (15f / 45f), center = Offset(cx, cy), style = Stroke(width = 1f))
            drawCircle(color = Line.copy(alpha = 0.45f), radius = r * (30f / 45f), center = Offset(cx, cy), style = Stroke(width = 1f))
            // Crosshair.
            drawLine(Line.copy(alpha = 0.6f), Offset(cx - r, cy), Offset(cx + r, cy), 1f)
            drawLine(Line.copy(alpha = 0.6f), Offset(cx, cy - r), Offset(cx, cy + r), 1f)

            // Ball.
            val bx = cx + ballX.value * r
            val by = cy + ballY.value * r
            val ballColor: Color = if (level) Accent else Amber
            drawCircle(color = ballColor.copy(alpha = 0.22f), radius = 34f, center = Offset(bx, by))
            drawCircle(color = ballColor, radius = 18f, center = Offset(bx, by))
        }

        // Center label.
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            M3Text(
                if (level) "LEVEL" else "TILTED",
                fontFamily = IdrMono,
                color = if (level) Accent else Amber,
                fontSize = 12.sp,
                letterSpacing = 1.2.sp,
                fontWeight = FontWeight.Bold,
            )
            M3Text(
                "gravity vector → tilt",
                fontFamily = IdrSans,
                color = Mute,
                fontSize = 10.sp,
            )
        }
    }
}

// ---------------------------------------------------------------------------
// Small components
// ---------------------------------------------------------------------------

@Composable
private fun ReadoutCard(
    label: String,
    value: String,
    sub: String,
    modifier: Modifier = Modifier,
    tint: Color = Fg,
) {
    Column(
        modifier
            .clip(RoundedCornerShape(12.dp))
            .background(Bg2)
            .border(1.dp, Line, RoundedCornerShape(12.dp))
            .padding(horizontal = 12.dp, vertical = 10.dp)
            .semantics { contentDescription = "$label $value $sub" },
        verticalArrangement = Arrangement.spacedBy(2.dp),
    ) {
        M3Text(label, fontFamily = IdrMono, color = Mute, fontSize = 10.sp, letterSpacing = 1.2.sp)
        M3Text(value, fontFamily = IdrMono, color = tint, fontSize = 26.sp, fontWeight = FontWeight.Bold)
        M3Text(sub, fontFamily = IdrSans, color = Mute, fontSize = 11.sp)
    }
}

@Composable
private fun MotionStateChip(state: MotionState) {
    val (label, tint) = when (state) {
        MotionState.STILL -> "STILL · zero-velocity update armed" to Accent
        MotionState.LIGHT -> "LIGHT motion" to Telem
        MotionState.WALKING -> "WALKING" to Amber
        MotionState.STRONG -> "STRONG SHAKE" to Danger
    }
    M3Text(
        label,
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(10.dp))
            .background(tint.copy(alpha = 0.14f))
            .border(1.dp, tint.copy(alpha = 0.55f), RoundedCornerShape(10.dp))
            .padding(vertical = 10.dp),
        color = tint,
        fontFamily = IdrMono,
        fontSize = 12.sp,
        letterSpacing = 1.2.sp,
        fontWeight = FontWeight.Bold,
    )
}

@Composable
private fun ShakeBar(mag: Float) {
    val pct = (mag / 12f).coerceIn(0f, 1f)
    val tint = shakeTint(mag)
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            M3Text("SHAKE METER", fontFamily = IdrMono, color = Mute, fontSize = 10.sp, letterSpacing = 1.2.sp)
            M3Text(
                "%.1f m/s²".format(mag),
                fontFamily = IdrMono,
                color = tint,
                fontSize = 10.sp,
            )
        }
        Box(
            Modifier
                .fillMaxWidth()
                .height(10.dp)
                .clip(RoundedCornerShape(6.dp))
                .background(Line.copy(alpha = 0.35f)),
        ) {
            Canvas(Modifier.fillMaxSize()) {
                drawRect(
                    color = tint,
                    size = androidx.compose.ui.geometry.Size(size.width * pct, size.height),
                )
            }
        }
    }
}

@Composable
private fun EventChip(event: LiveEvent) {
    val (label, tint) = when (event.kind) {
        LiveEventKind.BUMP -> "Bump detected" to Amber
        LiveEventKind.VIB -> "High vibration — filtering" to Amber
        LiveEventKind.ZUPT -> "Stationary — zero-velocity update applied" to Accent
    }
    Column(
        Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(10.dp))
            .background(tint.copy(alpha = 0.18f))
            .border(2.dp, tint, RoundedCornerShape(10.dp))
            .padding(horizontal = 12.dp, vertical = 8.dp)
            .semantics { contentDescription = "$label. Trigger: ${event.trigger}." },
        verticalArrangement = Arrangement.spacedBy(2.dp),
    ) {
        M3Text(label, color = tint, fontFamily = IdrMono, fontSize = 13.sp, fontWeight = FontWeight.Bold, letterSpacing = 0.8.sp)
        M3Text(event.trigger, color = Mute, fontFamily = IdrMono, fontSize = 11.sp)
    }
}

private fun shakeTint(mag: Float): Color = when {
    mag < 0.20f -> Accent
    mag < 1.0f -> Telem
    mag < 4.0f -> Amber
    else -> Danger
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

private enum class MotionState { STILL, LIGHT, WALKING, STRONG }

private enum class LiveEventKind { BUMP, VIB, ZUPT }

private data class LiveEvent(
    val kind: LiveEventKind,
    val trigger: String,
    val atMs: Long,
)
