package `in`.sih26168.idr.nav

/**
 * Zero-velocity update (ZUPT): the single most valuable correction available
 * to a phone-only dead-reckoning system in an underground metro.
 *
 * ## Why it matters
 *
 * A strapdown estimator with no external reference has two error sources that
 * grow without bound. Velocity error grows linearly with the accelerometer
 * bias, and position error grows as its integral -- quadratically with time.
 * Heading error grows linearly with gyro bias, and because every metre of
 * displacement is projected through that heading, position error from a gyro
 * bias grows CUBICALLY. Nothing in the IMU can stop either one.
 *
 * A confirmed stop breaks both. It is a free, exact measurement: velocity is
 * zero, not "small", and the entire velocity state can be set to zero rather
 * than merely damped. Better, while the vehicle is still, every count the
 * gyroscope produces is bias by definition, so the mean over the stationary
 * window IS the bias and can be subtracted from everything that follows.
 *
 * A metro stops at every station for twenty to forty-five seconds. Over a
 * twelve-station journey the estimator gets a dozen exact velocity fixes and a
 * dozen fresh bias estimates, so error is bounded by the interval BETWEEN
 * stations instead of by the length of the whole journey. That is the
 * difference between a usable track and a spiral.
 *
 * ## What this is not
 *
 * This is the standard SHOE-family detector (Skog et al., IEEE TBME 2010),
 * applied to a handset in a rail carriage. The method is textbook. What is
 * ours is the per-vehicle threshold set in [ZuptProfile] -- a metro at a
 * platform is orders of magnitude stiller than a scooter idling at a light,
 * and one threshold cannot serve both.
 *
 * ## The honest limitation
 *
 * An accelerometer cannot distinguish constant velocity from rest. Both read
 * exactly gravity. The ONLY thing separating them is vibration: a moving
 * vehicle shakes and a stopped one does not. That is why gate 2 in
 * [ZuptProfile] is a variance test rather than a magnitude test, and it is why
 * a perfectly smooth ride on perfectly smooth track would defeat this detector
 * in principle. On real hardware, in a real tunnel, it will not -- but the
 * limitation is real and the UI does not pretend otherwise.
 */
class ZuptDetector(profile: VehicleProfile) {

    private var params: ZuptProfile = profile.zupt

    // Ring of recent samples. Sized for the worst case the app can produce:
    // SENSOR_DELAY_FASTEST tops out near 500 Hz on current hardware, and the
    // longest window any profile asks for is 1 s.
    private val cap = 1024
    private val tNs = LongArray(cap)
    private val aMag = DoubleArray(cap)
    private val gMag = DoubleArray(cap)
    private val gxs = DoubleArray(cap)
    private val gys = DoubleArray(cap)
    private val gzs = DoubleArray(cap)
    private var head = 0
    private var count = 0

    // Running sums, updated on push and on evict so the per-sample cost is
    // constant rather than proportional to the window. The values are O(10)
    // and the session is at most a few hundred thousand samples, so the
    // accumulated rounding in a Double sum is around 1e-11 -- far below any
    // threshold here. Recomputing from scratch at 500 Hz would not be.
    private var sumA = 0.0
    private var sumA2 = 0.0
    private var sumG = 0.0
    private var sumG2 = 0.0
    private var sumGx = 0.0
    private var sumGy = 0.0
    private var sumGz = 0.0

    private var stillSinceNs = 0L
    private var lastFireNs = 0L

    /** True once a stop has been CONFIRMED and until motion resumes. */
    var stopped: Boolean = false
        private set

    /** Confirmed stops that produced an update, this session. */
    var updates: Long = 0L
        private set

    /** Seconds the current stop has lasted. 0 when moving. */
    var stoppedForSec: Double = 0.0
        private set

    /** Last computed statistics, for Diagnostics. NaN before the first window. */
    var lastAccelVar: Double = Double.NaN
        private set
    var lastGyroMag: Double = Double.NaN
        private set

    fun setProfile(profile: VehicleProfile) {
        params = profile.zupt
        reset()
    }

    fun reset() {
        head = 0
        count = 0
        sumA = 0.0
        sumA2 = 0.0
        sumG = 0.0
        sumG2 = 0.0
        sumGx = 0.0
        sumGy = 0.0
        sumGz = 0.0
        stillSinceNs = 0L
        lastFireNs = 0L
        stopped = false
        updates = 0L
        stoppedForSec = 0.0
        lastAccelVar = Double.NaN
        lastGyroMag = Double.NaN
    }

    /**
     * Feed one IMU sample.
     *
     * [gx]/[gy]/[gz] must be the gyro AFTER the current bias estimate has been
     * subtracted, in whatever frame the caller integrates in. That makes the
     * mean this detector reports the RESIDUAL bias, so [ZuptEvent] carries a
     * delta the caller adds to what it already has, and repeated updates
     * converge instead of fighting each other.
     *
     * The accelerometer is used through its magnitude only, which is invariant
     * under the mount rotation, so an uncalibrated phone gets the same
     * stationary decision as a calibrated one.
     *
     * @return a [ZuptEvent] on the tick a stop is confirmed or refreshed, and
     *   null on every other tick.
     */
    fun update(
        tNsNow: Long,
        ax: Double,
        ay: Double,
        az: Double,
        gx: Double,
        gy: Double,
        gz: Double,
    ): ZuptEvent? {
        if (!params.enabled) return null

        push(tNsNow, hypot3(ax, ay, az), gx, gy, gz)
        evictOlderThan(tNsNow - (params.windowSec * 1e9).toLong())

        // Not enough history to say anything. Refusing to decide is correct;
        // guessing "stopped" here would zero a real velocity at every arm.
        if (count < 8 || spanSec() < params.windowSec * 0.9) return null

        val n = count.toDouble()
        val meanA = sumA / n
        val varA = maxOf(0.0, sumA2 / n - meanA * meanA)
        val meanG = sumG / n
        val varG = maxOf(0.0, sumG2 / n - meanG * meanG)
        lastAccelVar = varA
        lastGyroMag = meanG

        val still = kotlin.math.abs(meanA - G) <= params.accelBiasMax &&
            varA <= params.accelVarMax &&
            meanG <= params.gyroMagMax &&
            varG <= params.gyroVarMax

        if (!still) {
            stillSinceNs = 0L
            stopped = false
            stoppedForSec = 0.0
            return null
        }

        if (stillSinceNs == 0L) stillSinceNs = tNsNow
        val stillFor = (tNsNow - stillSinceNs) / 1e9
        if (stillFor < params.minStillSec) return null
        stoppedForSec = stillFor

        // Confirmed. Fire once on entry, then refresh no faster than rearmSec
        // so a long platform dwell keeps the bias fresh without spamming.
        val firstOfThisStop = !stopped
        if (!firstOfThisStop && (tNsNow - lastFireNs) / 1e9 < params.rearmSec) {
            return null
        }
        stopped = true
        lastFireNs = tNsNow
        updates += 1

        return ZuptEvent(
            tNs = tNsNow,
            // Every count the gyro produced while the vehicle was still is
            // bias. This is the residual, because the caller already removed
            // its running estimate before handing the samples over.
            biasDeltaX = sumGx / n,
            biasDeltaY = sumGy / n,
            biasDeltaZ = sumGz / n,
            stillForSec = stillFor,
            samples = count,
            firstOfThisStop = firstOfThisStop,
            accelVar = varA,
            gyroMag = meanG,
        )
    }

    private fun spanSec(): Double {
        if (count < 2) return 0.0
        val oldest = tNs[head]
        val newest = tNs[(head + count - 1) % cap]
        return (newest - oldest) / 1e9
    }

    private fun push(t: Long, a: Double, gx: Double, gy: Double, gz: Double) {
        // A full ring means the sample rate beat the window; drop the oldest,
        // which is exactly what the window would have done a moment later.
        if (count == cap) evictOne()
        val i = (head + count) % cap
        tNs[i] = t
        aMag[i] = a
        val g = hypot3(gx, gy, gz)
        gMag[i] = g
        gxs[i] = gx
        gys[i] = gy
        gzs[i] = gz
        sumA += a
        sumA2 += a * a
        sumG += g
        sumG2 += g * g
        sumGx += gx
        sumGy += gy
        sumGz += gz
        count += 1
    }

    private fun evictOlderThan(cutoffNs: Long) {
        // Always keep at least two samples, so a pause in the sensor stream
        // cannot empty the window and silently reset the stop timer.
        while (count > 2 && tNs[head] < cutoffNs) evictOne()
    }

    private fun evictOne() {
        val i = head
        sumA -= aMag[i]
        sumA2 -= aMag[i] * aMag[i]
        sumG -= gMag[i]
        sumG2 -= gMag[i] * gMag[i]
        sumGx -= gxs[i]
        sumGy -= gys[i]
        sumGz -= gzs[i]
        head = (head + 1) % cap
        count -= 1
    }
}

/**
 * A confirmed stop.
 *
 * The caller's job on receiving one is short and exact: set velocity to zero,
 * and add the bias deltas to its running gyro bias estimate.
 */
data class ZuptEvent(
    val tNs: Long,
    val biasDeltaX: Double,
    val biasDeltaY: Double,
    val biasDeltaZ: Double,
    val stillForSec: Double,
    val samples: Int,
    /** True on the first update of this stop, false on a periodic refresh. */
    val firstOfThisStop: Boolean,
    val accelVar: Double,
    val gyroMag: Double,
)
