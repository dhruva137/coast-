package `in`.sih26168.idr.nav

import `in`.sih26168.idr.data.AppMode
import `in`.sih26168.idr.data.GnssFix
import `in`.sih26168.idr.data.HudState
import `in`.sih26168.idr.data.SensorFrame
import `in`.sih26168.idr.data.SpeedSource
import `in`.sih26168.idr.data.TrailPoint
import kotlin.math.cos
import kotlin.math.sin

/**
 * Lean-aware strapdown coast: integrate gyro yaw-rate + speed, no magnetometer.
 *
 * GNSS when locked seeds (lat, lon, alt, speed, bearing). During outage speed
 * comes from the on-device AVNet-tiny ONNX head ([OnnxSpeedModel]) when a
 * window is fresh, and from the accel-integrator coast otherwise — [speedSource]
 * says which, every tick. The coordinated-turn solver supplies ψ̇; car-style
 * ψ̇ = ω_z is kept only so the HUD can show heading disagreement.
 */
class SimpleIns(
    private val trailCap: Int = 4000,
    private val gnssTimeoutNs: Long = 2_000_000_000L,
    private val modelStaleNs: Long = 500_000_000L,
) {
    var lat: Double = 0.0
        private set
    var lon: Double = 0.0
        private set
    var alt: Double = 0.0
        private set
    /** Radians, 0 = north, positive toward east. */
    var yaw: Double = 0.0
        private set
    var yawCar: Double = 0.0
        private set
    var speed: Double = 0.0
        private set
    var lean: Double = 0.0
        private set
    var distanceM: Double = 0.0
        private set
    var coordinated: Boolean = false
        private set
    var seeded: Boolean = false
        private set
    var speedSource: SpeedSource = SpeedSource.FALLBACK
        private set

    private var modelSpeed: Double = Double.NaN
    private var modelPsiDot: Double = Double.NaN
    private var modelSpeedVar: Double = Double.NaN
    private var modelTNs: Long = 0L
    private var modelLatencyMs: Double = 0.0
    private var modelHz: Double = 0.0
    private var modelReady: Boolean = false
    private var modelError: String? = null

    private var lastTns: Long = 0L
    private var lastGnssNs: Long = 0L
    private var lastAccH: Double = Double.NaN
    private var lastSats: Int = 0
    private var outageStartNs: Long = 0L
    private var imuCount: Int = 0
    private var imuWindowStartNs: Long = 0L
    private var imuHz: Double = 0.0

    private var markLat: Double? = null
    private var markLon: Double? = null
    private var markDistance: Double = 0.0
    private var lastClosureM: Double? = null

    private val insTrail = ArrayDeque<TrailPoint>()
    private val gnssTrail = ArrayDeque<TrailPoint>()

    fun reset() {
        lat = 0.0
        lon = 0.0
        alt = 0.0
        yaw = 0.0
        yawCar = 0.0
        speed = 0.0
        lean = 0.0
        distanceM = 0.0
        coordinated = false
        seeded = false
        speedSource = SpeedSource.FALLBACK
        modelSpeed = Double.NaN
        modelPsiDot = Double.NaN
        modelSpeedVar = Double.NaN
        modelTNs = 0L
        modelLatencyMs = 0.0
        modelHz = 0.0
        lastTns = 0L
        lastGnssNs = 0L
        lastAccH = Double.NaN
        lastSats = 0
        outageStartNs = 0L
        imuCount = 0
        imuWindowStartNs = 0L
        imuHz = 0.0
        markLat = null
        markLon = null
        markDistance = 0.0
        lastClosureM = null
        insTrail.clear()
        gnssTrail.clear()
    }

    fun onImu(frame: SensorFrame) {
        noteHz(frame.tNs)
        if (lastTns == 0L) {
            lastTns = frame.tNs
            return
        }
        val dt = (frame.tNs - lastTns) / 1e9
        lastTns = frame.tNs
        if (dt <= 0.0 || dt > 0.5) return

        val lock = gnssLock(frame.tNs)
        val modelFresh = modelSpeed.isFinite() &&
            modelTNs != 0L &&
            frame.tNs - modelTNs in 0 until modelStaleNs
        if (lock) {
            // onGnss already wrote speed from the fix.
            speedSource = SpeedSource.GNSS
        } else if (modelFresh) {
            // Trained AVNet-tiny head drives the coast.
            speed = maxOf(0.0, modelSpeed)
            speedSource = SpeedSource.MODEL
        } else {
            // Labelled fallback: physics-informed coast, FrequencyDecoupledOdo stand-in.
            speed = maxOf(0.0, speed + frame.ax * dt)
            val aMean = hypot3(frame.ax, frame.ay, frame.az)
            if (aMean < 10.4 && kotlin.math.abs(frame.gz) < 0.05) {
                speed *= 0.995
            }
            speedSource = SpeedSource.FALLBACK
        }

        val sol = solveLean(
            LeanObservation(
                gy = frame.gy,
                gz = frame.gz,
                gx = frame.gx,
                speed = speed,
                phi0 = lean,
            ),
        )
        lean = sol.phi
        coordinated = sol.coordinated
        yaw = stepHeading(yaw, dt, frame.gy, frame.gz, lean, leanAware = true)
        yawCar = stepHeading(yawCar, dt, frame.gy, frame.gz, 0.0, leanAware = false)

        if (!seeded) return

        val ve = speed * sin(yaw)
        val vn = speed * cos(yaw)
        val mpd = metersPerDeg(lat)
        if (mpd.mLat != 0.0 && mpd.mLon != 0.0) {
            lat += (vn * dt) / mpd.mLat
            lon += (ve * dt) / mpd.mLon
        }
        distanceM += speed * dt
        push(insTrail, TrailPoint(lat, lon, fromGnss = false, tNs = frame.tNs))
    }

    /**
     * Newest on-device inference. ψ̇ is stored for the HUD only — heading stays
     * on the coordinated-turn solver, which is the validated path; swapping it
     * for the model head is a separate, separately-evidenced change.
     */
    fun onModel(est: SpeedEstimate, hz: Double) {
        modelSpeed = est.speed
        modelPsiDot = est.psiDot
        modelSpeedVar = est.speedVar
        modelTNs = est.tNs
        modelLatencyMs = est.latencyMs
        modelHz = hz
    }

    /** Session health from [OnnxSpeedModel]; `error` non-null means no model ran. */
    fun setModelStatus(ready: Boolean, error: String?) {
        modelReady = ready
        modelError = error
    }

    fun onGnss(fix: GnssFix) {
        lastGnssNs = fix.tNs
        lastAccH = fix.accH
        lastSats = fix.nSats
        val usable = fix.accH < 25.0 && (fix.nSats == 0 || fix.nSats >= 4)
        if (!usable) return

        lat = fix.lat
        lon = fix.lon
        alt = fix.alt
        speed = maxOf(0.0, fix.speed)
        if (fix.speed > 1.0 && !fix.bearing.isNaN()) {
            yaw = deg2rad(fix.bearing)
            yawCar = yaw
        }
        seeded = true
        outageStartNs = 0L
        push(gnssTrail, TrailPoint(fix.lat, fix.lon, fromGnss = true, tNs = fix.tNs))
        push(insTrail, TrailPoint(fix.lat, fix.lon, fromGnss = true, tNs = fix.tNs))
    }

    /**
     * First tap stores the loop-closure origin. Later taps measure
     * |p_now − p_mark| against distance travelled since the mark.
     */
    fun mark(): HudState {
        if (!seeded) return snapshot(lastTns, AppMode.NAVIGATE)
        if (markLat == null || markLon == null) {
            markLat = lat
            markLon = lon
            markDistance = distanceM
            lastClosureM = null
        } else {
            lastClosureM = haversineM(markLat!!, markLon!!, lat, lon)
        }
        return snapshot(lastTns, AppMode.NAVIGATE)
    }

    fun clearMark() {
        markLat = null
        markLon = null
        markDistance = 0.0
        lastClosureM = null
    }

    fun snapshot(nowNs: Long, mode: AppMode): HudState {
        val lock = gnssLock(nowNs)
        val age = if (lastGnssNs == 0L) Double.POSITIVE_INFINITY else (nowNs - lastGnssNs) / 1e9
        val outage = if (lock) {
            outageStartNs = 0L
            0.0
        } else {
            if (outageStartNs == 0L) outageStartNs = nowNs
            (nowNs - outageStartNs) / 1e9
        }
        val loopDist = if (markLat != null) maxOf(0.0, distanceM - markDistance) else 0.0
        val drift = lastClosureM?.let { err ->
            if (loopDist > 1.0) 100.0 * err / loopDist else null
        }
        return HudState(
            tNs = nowNs,
            lat = lat,
            lon = lon,
            alt = alt,
            speedMps = speed,
            leanDeg = rad2deg(lean),
            headingDeg = compassDeg(yaw),
            headingCarDeg = compassDeg(yawCar),
            distanceM = distanceM,
            imuHz = imuHz,
            gnssLock = lock,
            gnssAgeSec = age,
            nSats = lastSats,
            accH = lastAccH,
            outageSec = outage,
            loopMarked = markLat != null,
            loopClosureM = lastClosureM,
            loopDistanceM = loopDist,
            driftPct = drift,
            coordinated = coordinated,
            speedSource = speedSource,
            modelReady = modelReady,
            modelSpeedMps = modelSpeed,
            modelPsiDot = modelPsiDot,
            modelSpeedVar = modelSpeedVar,
            inferMs = modelLatencyMs,
            modelHz = modelHz,
            modelError = modelError,
            mode = mode,
            insTrail = insTrail.toList(),
            gnssTrail = gnssTrail.toList(),
        )
    }

    private fun gnssLock(nowNs: Long): Boolean {
        if (lastGnssNs == 0L) return false
        if (nowNs - lastGnssNs > gnssTimeoutNs) return false
        if (lastAccH.isFinite() && lastAccH > 25.0) return false
        if (lastSats in 1..3) return false
        return true
    }

    private fun noteHz(tNs: Long) {
        if (imuWindowStartNs == 0L) imuWindowStartNs = tNs
        imuCount += 1
        val dt = (tNs - imuWindowStartNs) / 1e9
        if (dt >= 1.0) {
            imuHz = imuCount / dt
            imuCount = 0
            imuWindowStartNs = tNs
        }
    }

    private fun push(buf: ArrayDeque<TrailPoint>, p: TrailPoint) {
        buf.addLast(p)
        while (buf.size > trailCap) buf.removeFirst()
    }
}
