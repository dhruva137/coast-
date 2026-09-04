package `in`.sih26168.idr.nav

import `in`.sih26168.idr.data.MountQuality
import `in`.sih26168.idr.data.MountResult
import `in`.sih26168.idr.data.MountRotation
import `in`.sih26168.idr.data.SensorFrame
import kotlin.math.abs
import kotlin.math.acos

/**
 * Estimate the phone-to-vehicle rotation from one short straight-line start.
 *
 * ## Why this exists
 *
 * Everything downstream assumes the gyro axes are the axes of the VEHICLE:
 * [solveLean] reads `gy` as the lateral rate and `gz` as the yaw rate, and the
 * coast integrator reads forward acceleration. A phone in a pocket, or clamped
 * at any angle other than perfectly upright and square, violates all of that.
 * Without this step the app is silently solving the wrong problem.
 *
 * ## The method
 *
 * The user stands still, starts the capture, then moves straight forward.
 *
 *  * **Down.** Over the stationary lead-in the accelerometer reads nothing but
 *    the reaction to gravity, so the mean of that window points UP.
 *    `down = -normalise(mean(a) over the still window)`.
 *  * **Forward.** Subtract that fixed gravity vector from every sample and
 *    integrate the remainder over the whole capture. The result is the velocity
 *    change of the phone. Project it into the horizontal plane and normalise:
 *    that is the direction the user moved. Because the user started from rest
 *    and moved forward, the SIGN is resolved too -- which is the part a
 *    principal-axis fit cannot give you.
 *  * **Right.** `right = down x forward`, completing the right-handed
 *    aerospace body frame (x forward, y right, z down) that [solveLean] and
 *    [stepHeading] are written against.
 *
 * Gravity MUST come from the still window rather than from the mean of the whole
 * capture. Subtracting the overall mean would also subtract the average forward
 * acceleration, which is precisely the signal being measured: a run at constant
 * acceleration would integrate to exactly zero and look like standing still.
 * That is why the user is asked to stop before pressing start, and why the
 * lead-in is checked for stillness rather than assumed.
 *
 * ## When it refuses
 *
 * A turn during the window rotates the device frame mid-capture and makes the
 * whole thing meaningless, so a large peak gyro rejects the run. So does a
 * lead-in that was not actually still, because then the gravity estimate is
 * polluted by motion. So does too little movement: if the velocity change is
 * small the forward direction is just integrated noise. Rejection returns
 * [MountQuality.REJECTED] with a reason for the user -- it never returns a
 * rotation it does not believe.
 */
class MountCalibration(
    /** Reject the run if the device turned faster than this at any point. */
    private val maxGyroRadS: Double = 0.60,
    /** Below this speed change the forward direction is not observable. */
    private val minDeltaVMps: Double = 1.0,
    /** Above this, treat the direction as well determined. */
    private val goodDeltaVMps: Double = 2.0,
    private val minSamples: Int = 100,
    /** Seconds at the start assumed stationary, used to measure gravity. */
    private val stillSec: Double = 1.0,
    /** Largest deviation from the gravity mean tolerated inside the still window. */
    private val stillAccelTol: Double = 1.2,
    /** Largest turn rate tolerated inside the still window. */
    private val stillGyroTol: Double = 0.25,
) {
    private var n = 0
    private var peakGyro = 0.0
    private var lastTNs = 0L
    private var firstTNs = 0L

    // Raw samples are kept so the second pass can subtract the measured gravity;
    // a straight-line start is a few seconds at a few hundred Hz, so this is a
    // few thousand doubles and bounded by [cap].
    private val ax = ArrayList<Double>()
    private val ay = ArrayList<Double>()
    private val az = ArrayList<Double>()
    private val dt = ArrayList<Double>()
    private val gyroMag = ArrayList<Double>()

    /** Seconds since the first sample, per stored sample. */
    private val at = ArrayList<Double>()
    private var clock = 0.0

    private val cap = 20_000

    val samples: Int get() = n

    /** Seconds of data collected so far. */
    val elapsedSec: Double
        get() = if (firstTNs == 0L) 0.0 else (lastTNs - firstTNs) / 1e9

    fun reset() {
        n = 0
        peakGyro = 0.0
        lastTNs = 0L
        firstTNs = 0L
        clock = 0.0
        ax.clear()
        ay.clear()
        az.clear()
        dt.clear()
        gyroMag.clear()
        at.clear()
    }

    fun add(frame: SensorFrame) {
        if (n >= cap) return
        if (firstTNs == 0L) {
            firstTNs = frame.tNs
            lastTNs = frame.tNs
            return
        }
        val step = (frame.tNs - lastTNs) / 1e9
        lastTNs = frame.tNs
        // Drop absurd gaps (thread stall, clock change) rather than integrating them.
        if (step <= 0.0 || step > 0.25) return

        val gmag = hypot3(frame.gx, frame.gy, frame.gz)
        if (gmag > peakGyro) peakGyro = gmag

        clock += step
        ax.add(frame.ax)
        ay.add(frame.ay)
        az.add(frame.az)
        dt.add(step)
        gyroMag.add(gmag)
        at.add(clock)
        n += 1
    }

    fun solve(): MountResult {
        if (n < minSamples) {
            return reject(
                "Only $n samples in ${"%.1f".format(elapsedSec)} s. Hold the capture " +
                    "for the full countdown.",
            )
        }

        // ---- Gravity, from the stationary lead-in only ----------------------
        var still = 0
        while (still < n && at[still] <= stillSec) still += 1
        if (still < 20) {
            return reject(
                "The first ${"%.1f".format(stillSec)} s held only $still samples, which " +
                    "is not enough to measure which way is down. Try again.",
            )
        }
        var sx = 0.0
        var sy = 0.0
        var sz = 0.0
        for (i in 0 until still) {
            sx += ax[i]
            sy += ay[i]
            sz += az[i]
        }
        val mx = sx / still
        val my = sy / still
        val mz = sz / still
        val gNorm = hypot3(mx, my, mz)
        if (gNorm < 1.0) {
            return reject(
                "Mean acceleration over the still window is only " +
                    "${"%.2f".format(gNorm)} m/s2, so gravity could not be located. Was " +
                    "the phone in free fall or the sensor stuck?",
            )
        }

        // The lead-in has to have actually been still, or the gravity vector is
        // polluted by motion and everything built on it is wrong.
        var worstDev = 0.0
        var worstSpin = 0.0
        for (i in 0 until still) {
            val d = hypot3(ax[i] - mx, ay[i] - my, az[i] - mz)
            if (d > worstDev) worstDev = d
            if (gyroMag[i] > worstSpin) worstSpin = gyroMag[i]
        }
        if (worstDev > stillAccelTol || worstSpin > stillGyroTol) {
            return MountResult(
                quality = MountQuality.REJECTED,
                rotation = null,
                deltaVMps = Double.NaN,
                peakGyroRadS = peakGyro,
                tiltDeg = Double.NaN,
                samples = n,
                reason = "The phone was already moving when the capture started " +
                    "(wobble ${"%.2f".format(worstDev)} m/s2, spin " +
                    "${"%.2f".format(worstSpin)} rad/s). Come to a complete stop first, " +
                    "then press start and move off.",
            )
        }

        // Accelerometer reads specific force: at rest it points UP.
        val ux = mx / gNorm
        val uy = my / gNorm
        val uz = mz / gNorm
        // Tilt of the screen-normal (+Z in Android device axes) from vertical.
        val tiltDeg = rad2deg(acos(clamp(uz, -1.0, 1.0)))

        // Velocity change = integral of (a - gravity) over the whole capture.
        // Gravity is the fixed vector just measured, NOT the mean of the run --
        // see the class comment for why that distinction is load-bearing.
        var vx = 0.0
        var vy = 0.0
        var vz = 0.0
        for (i in 0 until n) {
            val h = dt[i]
            vx += (ax[i] - mx) * h
            vy += (ay[i] - my) * h
            vz += (az[i] - mz) * h
        }
        // Keep only the horizontal part: vertical velocity here is integrated noise.
        val vDotU = vx * ux + vy * uy + vz * uz
        val hx = vx - vDotU * ux
        val hy = vy - vDotU * uy
        val hz = vz - vDotU * uz
        val deltaV = hypot3(hx, hy, hz)

        if (peakGyro > maxGyroRadS) {
            return MountResult(
                quality = MountQuality.REJECTED,
                rotation = null,
                deltaVMps = deltaV,
                peakGyroRadS = peakGyro,
                tiltDeg = tiltDeg,
                samples = n,
                reason = "The phone turned during the capture (peak " +
                    "${"%.2f".format(peakGyro)} rad/s). Go straight, without turning " +
                    "or reaching for the phone, and try again.",
            )
        }

        if (deltaV < minDeltaVMps) {
            return MountResult(
                quality = MountQuality.REJECTED,
                rotation = null,
                deltaVMps = deltaV,
                peakGyroRadS = peakGyro,
                tiltDeg = tiltDeg,
                samples = n,
                reason = "Only ${"%.2f".format(deltaV)} m/s of speed change was " +
                    "detected, which is not enough to tell which way is forward. " +
                    "Start from a standstill and accelerate away in a straight line.",
            )
        }

        // forward = normalised horizontal velocity change
        val fx = hx / deltaV
        val fy = hy / deltaV
        val fz = hz / deltaV
        // down = -up
        val dxv = -ux
        val dyv = -uy
        val dzv = -uz
        // right = down x forward, giving right-handed (forward, right, down)
        var rx = dyv * fz - dzv * fy
        var ry = dzv * fx - dxv * fz
        var rz = dxv * fy - dyv * fx
        val rNorm = hypot3(rx, ry, rz)
        if (rNorm < 1e-6) {
            return reject(
                "Forward and vertical came out parallel, so the frame is degenerate. " +
                    "Try again on level ground.",
            )
        }
        rx /= rNorm
        ry /= rNorm
        rz /= rNorm

        val quality = if (deltaV >= goodDeltaVMps) MountQuality.GOOD else MountQuality.WEAK
        return MountResult(
            quality = quality,
            rotation = MountRotation(
                fx = fx, fy = fy, fz = fz,
                rx = rx, ry = ry, rz = rz,
                dx = dxv, dy = dyv, dz = dzv,
            ),
            deltaVMps = deltaV,
            peakGyroRadS = peakGyro,
            tiltDeg = tiltDeg,
            samples = n,
            reason = if (quality == MountQuality.GOOD) {
                "Forward axis found from ${"%.2f".format(deltaV)} m/s of speed change " +
                    "over $n samples."
            } else {
                "Forward axis found, but from only ${"%.2f".format(deltaV)} m/s of " +
                    "speed change. It will be used; a faster straight start would pin " +
                    "it down better."
            },
        )
    }

    private fun reject(reason: String) = MountResult(
        quality = MountQuality.REJECTED,
        rotation = null,
        deltaVMps = Double.NaN,
        peakGyroRadS = peakGyro,
        tiltDeg = Double.NaN,
        samples = n,
        reason = reason,
    )
}

/** Device-frame vector to vehicle frame (x forward, y right, z down). */
fun rotateToVehicle(r: MountRotation, x: Double, y: Double, z: Double): Triple<Double, Double, Double> =
    Triple(
        x * r.fx + y * r.fy + z * r.fz,
        x * r.rx + y * r.ry + z * r.rz,
        x * r.dx + y * r.dy + z * r.dz,
    )

/**
 * Human-readable description of where the phone is pointing, for the card the
 * user reads after calibrating.
 */
fun describeMount(result: MountResult): String {
    val r = result.rotation ?: return "not calibrated"
    // Which device axis is closest to vehicle-forward tells the user, in terms
    // they can picture, how the phone is sitting.
    val axes = listOf(
        "top edge" to r.fy,
        "bottom edge" to -r.fy,
        "right edge" to r.fx,
        "left edge" to -r.fx,
        "screen" to -r.fz,
        "back" to r.fz,
    )
    val best = axes.maxByOrNull { it.second } ?: return "not calibrated"
    val alignment = rad2deg(acos(clamp(best.second, -1.0, 1.0)))
    val tilt = if (result.tiltDeg.isFinite()) ", tilted %.0f deg from flat".format(result.tiltDeg) else ""
    return "${best.first} points forward (within %.0f deg)".format(alignment) + tilt
}

/** Round-trip check used by the unit test: the frame must stay orthonormal. */
fun orthonormalError(r: MountRotation): Double {
    val ff = r.fx * r.fx + r.fy * r.fy + r.fz * r.fz
    val rr = r.rx * r.rx + r.ry * r.ry + r.rz * r.rz
    val dd = r.dx * r.dx + r.dy * r.dy + r.dz * r.dz
    val fr = r.fx * r.rx + r.fy * r.ry + r.fz * r.rz
    val fd = r.fx * r.dx + r.fy * r.dy + r.fz * r.dz
    val rd = r.rx * r.dx + r.ry * r.dy + r.rz * r.dz
    return maxOf(
        abs(ff - 1.0), abs(rr - 1.0), abs(dd - 1.0),
        abs(fr), abs(fd), abs(rd),
    )
}
