package `in`.sih26168.idr.nav

import kotlin.math.pow

/**
 * Pedestrian step detector for walking dead reckoning.
 *
 * Peak-trough on |a|, then Weinberg step length
 * `L = k (a_max − a_min)^{1/4}` (Weinberg 2002). The method is textbook; we
 * use it as the speed source when Walking is selected, because the vehicle
 * accel-integrator assumes a forward launch a gait never produces.
 */
class StepDetector(
    private val kWeinberg: Double = 0.41,
    private val minIntervalSec: Double = 0.28,
    private val maxIntervalSec: Double = 1.40,
    private val minPeakMps2: Double = G + 0.55,
    private val minRangeMps2: Double = 0.70,
    private val minLengthM: Double = 0.35,
    private val maxLengthM: Double = 1.05,
    private val defaultCadenceHz: Double = 1.7,
) {
    data class Step(val tNs: Long, val lengthM: Double, val cadenceHz: Double)

    private var ema: Double = Double.NaN
    private var prev: Double = Double.NaN
    private var climbing: Boolean = false
    private var peak: Double = Double.NEGATIVE_INFINITY
    private var trough: Double = Double.POSITIVE_INFINITY
    private var lastNs: Long = 0L

    var count: Long = 0L
        private set
    var lastLengthM: Double = Double.NaN
        private set
    var lastCadenceHz: Double = Double.NaN
        private set

    fun reset() {
        ema = Double.NaN
        prev = Double.NaN
        climbing = false
        peak = Double.NEGATIVE_INFINITY
        trough = Double.POSITIVE_INFINITY
        lastNs = 0L
        count = 0L
        lastLengthM = Double.NaN
        lastCadenceHz = Double.NaN
    }

    fun update(tNs: Long, ax: Double, ay: Double, az: Double): Step? {
        val mag = hypot3(ax, ay, az)
        ema = if (!ema.isFinite()) mag else 0.40 * mag + 0.60 * ema
        if (!prev.isFinite()) {
            prev = ema
            trough = ema
            return null
        }
        if (ema > prev) {
            climbing = true
            peak = maxOf(peak, ema)
        } else if (ema < prev && climbing) {
            val step = maybeAccept(tNs)
            climbing = false
            trough = ema
            peak = Double.NEGATIVE_INFINITY
            prev = ema
            return step
        } else {
            trough = minOf(trough, ema)
        }
        prev = ema
        return null
    }

    fun coastSpeedMps(nowNs: Long): Double {
        if (lastNs == 0L || !lastLengthM.isFinite()) return 0.0
        val age = (nowNs - lastNs) / 1e9
        if (age > maxIntervalSec) return 0.0
        val cadence = if (lastCadenceHz.isFinite() && lastCadenceHz > 0.3) {
            lastCadenceHz
        } else {
            defaultCadenceHz
        }
        val fadeStart = maxIntervalSec - 0.35
        val fade = if (age > fadeStart) {
            ((maxIntervalSec - age) / 0.35).coerceIn(0.0, 1.0)
        } else {
            1.0
        }
        return lastLengthM * cadence * fade
    }

    private fun maybeAccept(tNs: Long): Step? {
        val range = peak - trough
        if (peak < minPeakMps2 || range < minRangeMps2) return null
        val dt = if (lastNs == 0L) Double.NaN else (tNs - lastNs) / 1e9
        if (dt.isFinite() && dt < minIntervalSec) return null
        val cadence = if (dt.isFinite() && dt in minIntervalSec..maxIntervalSec) {
            1.0 / dt
        } else {
            defaultCadenceHz
        }
        val length = clamp(kWeinberg * range.pow(0.25), minLengthM, maxLengthM)
        lastNs = tNs
        lastLengthM = length
        lastCadenceHz = cadence
        count += 1
        return Step(tNs, length, cadence)
    }
}

/** Horizontal yaw rate as rotation about gravity (handheld / pocket). */
fun yawRateAroundGravity(
    ax: Double,
    ay: Double,
    az: Double,
    gx: Double,
    gy: Double,
    gz: Double,
): Double {
    val n = hypot3(ax, ay, az)
    if (n < 1.0) return gz
    return (gx * ax + gy * ay + gz * az) / n
}

fun vehicleLeans(kind: `in`.sih26168.idr.data.VehicleKind): Boolean =
    kind == `in`.sih26168.idr.data.VehicleKind.scooter ||
        kind == `in`.sih26168.idr.data.VehicleKind.motorcycle ||
        kind == `in`.sih26168.idr.data.VehicleKind.bicycle
