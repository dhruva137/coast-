package `in`.sih26168.idr.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import `in`.sih26168.idr.IdrBus
import `in`.sih26168.idr.data.HudState
import `in`.sih26168.idr.data.SpeedSource
import `in`.sih26168.idr.ui.theme.Accent
import `in`.sih26168.idr.ui.theme.Amber
import `in`.sih26168.idr.ui.theme.Bg2
import `in`.sih26168.idr.ui.theme.Danger
import `in`.sih26168.idr.ui.theme.Gnss
import `in`.sih26168.idr.ui.theme.IdrMono
import `in`.sih26168.idr.ui.theme.Line
import `in`.sih26168.idr.ui.theme.Mute
import `in`.sih26168.idr.ui.theme.Telem
import `in`.sih26168.idr.ui.theme.Text as Fg
import kotlin.math.abs
import kotlin.math.sqrt

/**
 * Every research readout the field-logging build showed, kept intact and moved
 * off the primary screen.
 *
 * Nothing is dropped: lean angle, inference latency, sustained inference rate,
 * the drift estimate, heading disagreement between the lean-aware and car-style
 * solvers, IMU rate, satellite count, model variance, and the raw model error
 * string when the ONNX session failed to load. A judge can ask for this in one
 * tap; a rider never has to look at it.
 */
@Composable
fun DiagnosticsPanel(bus: IdrBus, hud: HudState) {
    val sensors by bus.sensors.collectAsStateWithLifecycle()
    val device by bus.device.collectAsStateWithLifecycle()

    Column(
        Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(12.dp))
            .background(Bg2)
            .border(1.dp, Line, RoundedCornerShape(12.dp))
            .padding(14.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Section("ESTIMATOR")
        Kv("nav mode", hud.navMode.name)
        Kv("origin", hud.originSource.name)
        Kv("heading referenced to north", if (hud.headingReferenced) "yes" else "no (relative to start)")
        Kv("heading", "%.1f deg".format(hud.headingDeg))
        val disagree = abs(hud.headingDeg - hud.headingCarDeg).let { d -> minOf(d, 360.0 - d) }
        Kv("car-style heading delta", "%.1f deg".format(disagree), Accent)
        Kv("lean angle", "%+.1f deg".format(hud.leanDeg), Accent)
        Kv("coordinated turn", if (hud.coordinated) "yes" else "no")
        Kv("displacement E / N", "%.1f / %.1f m".format(hud.east, hud.north))
        Kv("distance total", "%.1f m".format(hud.distanceM))
        Kv("distance since last fix", "%.1f m".format(hud.distanceSinceFixM))
        Kv("mount frame", hud.mountNote, if (hud.mountApplied) Telem else Amber)

        Section("UNCERTAINTY MODEL")
        Kv("radius", metres(hud.uncertaintyM))
        Kv(
            "drift constant",
            "%.1f%% %s".format(
                hud.driftRateUsed * 100.0,
                if (hud.driftRateMeasured) "(measured this session)" else "(benchmark target, not measured)",
            ),
            if (hud.driftRateMeasured) Telem else Amber,
        )
        Text(
            hud.uncertaintyBasis,
            fontFamily = IdrMono,
            color = Mute,
            fontSize = 10.sp,
            lineHeight = 14.sp,
        )
        hud.loopClosureM?.let { c ->
            Kv("loop closure error", "%.2f m over %.0f m".format(c, hud.loopDistanceM), Telem)
        }
        hud.driftPct?.let { d -> Kv("measured drift", "%.2f %%".format(d), Telem) }

        Section("ON-DEVICE MODEL  ·  avnet_tiny.onnx")
        val srcColor = when (hud.speedSource) {
            SpeedSource.MODEL -> Accent
            SpeedSource.GNSS -> Gnss
            SpeedSource.FALLBACK -> Amber
        }
        Kv("speed source", hud.speedSource.name, srcColor)
        Kv("session loaded", if (hud.modelReady) "yes" else "NO", if (hud.modelReady) Telem else Danger)
        Kv("inference latency", "%.2f ms".format(hud.inferMs))
        Kv(
            "sustained rate",
            "%.2f Hz (target 10.0)".format(hud.modelHz),
            if (hud.modelHz >= 9.0) Telem else Amber,
        )
        Kv(
            "model speed",
            if (hud.modelSpeedMps.isNaN()) "-- (window filling)" else "%.2f m/s".format(hud.modelSpeedMps),
        )
        Kv(
            "model sigma",
            if (hud.modelSpeedVar.isNaN()) "--" else "%.3f m/s".format(sqrt(hud.modelSpeedVar)),
        )
        Kv(
            "model yaw rate",
            if (hud.modelPsiDot.isNaN()) "--" else "%+.3f rad/s".format(hud.modelPsiDot),
        )
        hud.modelError?.let { e ->
            Text(
                "MODEL DOWN: $e",
                fontFamily = IdrMono,
                color = Danger,
                fontSize = 10.sp,
                lineHeight = 14.sp,
            )
            Text(
                "Speed is coming from the fallback integrator, not the trained model.",
                fontFamily = IdrMono,
                color = Danger,
                fontSize = 10.sp,
            )
        }

        Section("SENSORS")
        Kv("IMU rate", "%.0f Hz".format(hud.imuHz), if (hud.imuHz >= 50.0) Telem else Amber)
        Kv("accel uncalibrated", yn(sensors.accelUncal))
        Kv("gyro uncalibrated", yn(sensors.gyroUncal))
        Kv("accel calibrated fallback", yn(sensors.accelFallback))
        Kv("gyro calibrated fallback", yn(sensors.gyroFallback))
        Kv("magnetometer", yn(sensors.mag))
        Kv("barometer", yn(sensors.pressure))
        if (device.probed) {
            Kv("gyro measured rate", hzOrUnknown(device.gyroUncal.measuredHz, device.gyro.measuredHz))
            Kv("accel measured rate", hzOrUnknown(device.accelUncal.measuredHz, device.accel.measuredHz))
        }

        Section("GNSS")
        Kv("location status", hud.locationStatus.name)
        Kv("fix live", yn(hud.gnssLock), if (hud.gnssLock) Gnss else Amber)
        Kv("satellites used", if (hud.nSats > 0) hud.nSats.toString() else "-- (not reported)")
        Kv("reported accuracy", if (hud.accH.isFinite()) "%.1f m".format(hud.accH) else "-- (none)")
        Kv(
            "fix age",
            if (hud.gnssAgeSec.isFinite()) "%.1f s".format(hud.gnssAgeSec) else "no fix yet",
        )
        Kv("outage", "%.1f s".format(hud.outageSec), if (hud.outageSec > 0.0) Amber else Mute)
        Kv(
            "position",
            if (hud.hasAbsolutePosition && hud.lat.isFinite()) {
                "%.6f, %.6f".format(hud.lat, hud.lon)
            } else {
                "unknown -- relative mode"
            },
        )
    }
}

private fun yn(b: Boolean) = if (b) "yes" else "no"

private fun hzOrUnknown(vararg candidates: Double): String {
    val v = candidates.firstOrNull { it.isFinite() && it > 0.0 } ?: return "not measured"
    return "%.0f Hz".format(v)
}

@Composable
private fun Section(label: String) {
    Text(
        label,
        fontFamily = IdrMono,
        color = Telem,
        fontSize = 10.sp,
        letterSpacing = 2.sp,
        modifier = Modifier.padding(top = 4.dp),
    )
}

@Composable
private fun Kv(key: String, value: String, tint: androidx.compose.ui.graphics.Color = Fg) {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
        Text(key, fontFamily = IdrMono, color = Mute, fontSize = 11.sp)
        Text(
            value,
            fontFamily = IdrMono,
            color = tint,
            fontSize = 11.sp,
            modifier = Modifier.padding(start = 12.dp),
        )
    }
}
