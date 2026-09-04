package `in`.sih26168.idr.nav

import `in`.sih26168.idr.data.AppMode
import `in`.sih26168.idr.data.GnssFix
import `in`.sih26168.idr.data.HudState
import `in`.sih26168.idr.data.LocationStatus
import `in`.sih26168.idr.data.MountRotation
import `in`.sih26168.idr.data.NavMode
import `in`.sih26168.idr.data.OriginSource
import `in`.sih26168.idr.data.SensorFrame
import `in`.sih26168.idr.data.SpeedSource
import `in`.sih26168.idr.data.TrailPoint
import kotlin.math.cos
import kotlin.math.sin

/**
 * Lean-aware strapdown coast: integrate gyro yaw-rate + speed, no magnetometer.
 *
 * ## Frames
 *
 * The estimator always integrates displacement in a local **east/north** frame
 * in metres. That is the quantity the IMU actually gives us, and it is defined
 * with or without GNSS. Latitude and longitude are a PROJECTION of that
 * displacement onto the Earth, and only exist once an absolute origin has been
 * supplied -- by a GNSS fix, or by the user placing one by hand. When there is
 * no origin, [HudState.lat] and [HudState.lon] are [Double.NaN] and
 * [HudState.navMode] is [NavMode.RELATIVE]. The app never invents a coordinate.
 *
 * ## Modes
 *
 *  * [NavMode.GNSS] -- a fix arrived inside [gnssTimeoutNs] and passed the
 *    quality gate. Position is absolute and its error is the accuracy the OS
 *    reported.
 *  * [NavMode.DEAD_RECKONING] -- no live fix, but an origin exists, so position
 *    is still absolute. Error is modelled, and grows with distance travelled
 *    since the last fix.
 *  * [NavMode.RELATIVE] -- no origin at all. Displacement and track shape are
 *    real; absolute position is unknown and is reported as unknown.
 *
 * ## Speed
 *
 * GNSS when locked. During outage the on-device AVNet-tiny ONNX head
 * ([OnnxSpeedModel]) drives the coast when a window is fresh, and the
 * accel-integrator fallback otherwise -- [speedSource] says which, every tick.
 * The coordinated-turn solver supplies the yaw rate; car-style yaw = omega_z is
 * kept only so Diagnostics can show the heading disagreement.
 */
class SimpleIns(
    private val trailCap: Int = 4000,
    private val gnssTimeoutNs: Long = 2_000_000_000L,
    private val modelStaleNs: Long = 500_000_000L,
) {
    // ---- Absolute anchor ---------------------------------------------------
    private var originLat: Double = Double.NaN
    private var originLon: Double = Double.NaN
    var originSource: OriginSource = OriginSource.NONE
        private set

    val hasOrigin: Boolean get() = originSource != OriginSource.NONE

    // ---- Local displacement, always valid ----------------------------------
    /** Metres east of the origin. Integrated from the IMU regardless of GNSS. */
    var east: Double = 0.0
        private set

    /** Metres north of the origin. */
    var north: Double = 0.0
        private set

    val lat: Double
        get() = if (!hasOrigin) Double.NaN else originLat + north / metersPerDeg(originLat).mLat

    val lon: Double
        get() = if (!hasOrigin) Double.NaN else originLon + east / metersPerDeg(originLat).mLon

    var alt: Double = Double.NaN
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

    /** Metres dead-reckoned since the last usable fix. Drives the error model. */
    var distanceSinceFixM: Double = 0.0
        private set

    var coordinated: Boolean = false
        private set
    var speedSource: SpeedSource = SpeedSource.FALLBACK
        private set

    /** True once anything at all has been integrated -- used to gate the UI. */
    var armed: Boolean = false
        private set

    /**
     * True once a GNSS bearing has tied [yaw] to true north. Until then yaw is
     * the angle turned since arming, measured from an arbitrary zero, and the
     * UI must not present it as a compass heading.
     */
    var headingReferenced: Boolean = false
        private set

    // ---- Mount rotation ----------------------------------------------------
    private var mount: MountRotation? = null
    private var mountNote: String = "raw device axes -- not calibrated"

    // ---- Model status ------------------------------------------------------
    private var modelSpeed: Double = Double.NaN
    private var modelPsiDot: Double = Double.NaN
    private var modelSpeedVar: Double = Double.NaN
    private var modelTNs: Long = 0L
    private var modelLatencyMs: Double = 0.0
    private var modelHz: Double = 0.0
    private var modelReady: Boolean = false
    private var modelError: String? = null

    // ---- GNSS bookkeeping --------------------------------------------------
    private var lastTns: Long = 0L
    private var lastGnssNs: Long = 0L
    private var lastAccH: Double = Double.NaN
    /** Accuracy of the fix that last anchored us. Base of the error model. */
    private var anchorAccH: Double = Double.NaN
    private var lastSats: Int = 0
    private var everHadFix: Boolean = false
    /** elapsedRealtime of the first integrated IMU tick; base for outage when no fix ever arrived. */
    private var armedAtNs: Long = 0L
    private var imuCount: Int = 0
    private var imuWindowStartNs: Long = 0L
    private var imuHz: Double = 0.0
    private var locationStatus: LocationStatus = LocationStatus.UNKNOWN

    // ---- Loop closure ------------------------------------------------------
    private var markEast: Double? = null
    private var markNorth: Double? = null
    private var markDistance: Double = 0.0
    private var lastClosureM: Double? = null

    private val insTrail = ArrayDeque<TrailPoint>()
    private val gnssTrail = ArrayDeque<TrailPoint>()

    fun reset() {
        originLat = Double.NaN
        originLon = Double.NaN
        originSource = OriginSource.NONE
        east = 0.0
        north = 0.0
        alt = Double.NaN
        yaw = 0.0
        yawCar = 0.0
        speed = 0.0
        lean = 0.0
        distanceM = 0.0
        distanceSinceFixM = 0.0
        coordinated = false
        armed = false
        headingReferenced = false
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
        anchorAccH = Double.NaN
        lastSats = 0
        everHadFix = false
        armedAtNs = 0L
        imuCount = 0
        imuWindowStartNs = 0L
        imuHz = 0.0
        markEast = null
        markNorth = null
        markDistance = 0.0
        lastClosureM = null
        insTrail.clear()
        gnssTrail.clear()
    }

    /**
     * Install the phone-to-vehicle rotation measured by [MountCalibration].
     * Null restores raw device axes, which is what every uncalibrated run uses.
     */
    fun setMount(rotation: MountRotation?, note: String) {
        mount = rotation
        mountNote = note
    }

    fun setLocationStatus(status: LocationStatus) {
        locationStatus = status
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
        armed = true
        if (armedAtNs == 0L) armedAtNs = frame.tNs

        // Rotate into the vehicle frame when the mount has been calibrated.
        // Uncalibrated runs keep the historical raw-axis behaviour rather than
        // silently switching to a different, untested convention.
        val m = mount
        val fwdAcc: Double
        val gxV: Double
        val gyV: Double
        val gzV: Double
        if (m != null) {
            val a = rotateToVehicle(m, frame.ax, frame.ay, frame.az)
            val g = rotateToVehicle(m, frame.gx, frame.gy, frame.gz)
            // Forward is perpendicular to the calibrated vertical, so gravity
            // projects onto it as ~0 and no explicit subtraction is needed.
            fwdAcc = a.first
            gxV = g.first
            gyV = g.second
            gzV = g.third
        } else {
            fwdAcc = frame.ax
            gxV = frame.gx
            gyV = frame.gy
            gzV = frame.gz
        }

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
            speed = maxOf(0.0, speed + fwdAcc * dt)
            val aMean = hypot3(frame.ax, frame.ay, frame.az)
            if (aMean < 10.4 && kotlin.math.abs(gzV) < 0.05) {
                speed *= 0.995
            }
            speedSource = SpeedSource.FALLBACK
        }

        val sol = solveLean(
            LeanObservation(
                gy = gyV,
                gz = gzV,
                gx = gxV,
                speed = speed,
                phi0 = lean,
            ),
        )
        lean = sol.phi
        coordinated = sol.coordinated
        yaw = stepHeading(yaw, dt, gyV, gzV, lean, leanAware = true)
        yawCar = stepHeading(yawCar, dt, gyV, gzV, 0.0, leanAware = false)

        // Displacement is integrated unconditionally. This is the whole point:
        // with no fix and no origin we still know how far and in what shape.
        val ve = speed * sin(yaw)
        val vn = speed * cos(yaw)
        east += ve * dt
        north += vn * dt
        distanceM += speed * dt
        if (!lock) distanceSinceFixM += speed * dt
        push(insTrail, point(east, north, fromGnss = false, tNs = frame.tNs))
    }

    /**
     * Newest on-device inference. The yaw rate is stored for Diagnostics only --
     * heading stays on the coordinated-turn solver, which is the validated path;
     * swapping it for the model head is a separate, separately-evidenced change.
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

        everHadFix = true
        alt = fix.alt
        if (!hasOrigin) {
            // First absolute anchor. Pin the origin here and treat the
            // displacement accumulated so far in RELATIVE mode as measured from
            // this point -- it is, the origin is simply now known.
            originLat = fix.lat
            originLon = fix.lon
            originSource = OriginSource.GNSS_FIX
            east = 0.0
            north = 0.0
        } else {
            // Snap local displacement to the fix. This is a real discontinuity
            // and Diagnostics reports it; the UI smooths only the rendering.
            val mpd = metersPerDeg(originLat)
            east = (fix.lon - originLon) * mpd.mLon
            north = (fix.lat - originLat) * mpd.mLat
        }
        speed = maxOf(0.0, fix.speed)
        if (fix.speed > 1.0 && !fix.bearing.isNaN()) {
            yaw = deg2rad(fix.bearing)
            yawCar = yaw
            // Only now is heading a true compass bearing rather than an angle
            // turned since arming.
            headingReferenced = true
        }
        anchorAccH = fix.accH
        distanceSinceFixM = 0.0
        armed = true
        if (armedAtNs == 0L) armedAtNs = fix.tNs
        push(gnssTrail, point(east, north, fromGnss = true, tNs = fix.tNs))
        push(insTrail, point(east, north, fromGnss = true, tNs = fix.tNs))
    }

    /**
     * Anchor the track to a point the USER supplied -- long-press or typed
     * coordinates. The accumulated displacement is kept and the whole relative
     * track is placed on the map from here.
     *
     * The anchor is an assertion, not a measurement: [anchorAccH] stays NaN so
     * the error model reports growth only and the UI says the absolute error is
     * unknown.
     */
    fun setUserOrigin(lat: Double, lon: Double, source: OriginSource) {
        if (!lat.isFinite() || !lon.isFinite()) return
        if (lat < -90.0 || lat > 90.0 || lon < -180.0 || lon > 180.0) return
        originLat = lat
        originLon = lon
        originSource = source
        anchorAccH = Double.NaN
    }

    /** Drop the user-set anchor and fall back to relative mode. */
    fun clearUserOrigin() {
        if (originSource == OriginSource.USER_MAP || originSource == OriginSource.USER_COORDS) {
            originLat = Double.NaN
            originLon = Double.NaN
            originSource = OriginSource.NONE
            anchorAccH = Double.NaN
        }
    }

    /**
     * First tap stores the loop-closure origin. Later taps measure the distance
     * back to the mark against the distance travelled since it. Works in
     * relative mode too, because it is measured in the local frame.
     */
    fun mark(): HudState {
        if (!armed) return snapshot(lastTns, AppMode.NAVIGATE)
        if (markEast == null || markNorth == null) {
            markEast = east
            markNorth = north
            markDistance = distanceM
            lastClosureM = null
        } else {
            val de = east - markEast!!
            val dn = north - markNorth!!
            lastClosureM = kotlin.math.sqrt(de * de + dn * dn)
        }
        return snapshot(lastTns, AppMode.NAVIGATE)
    }

    fun clearMark() {
        markEast = null
        markNorth = null
        markDistance = 0.0
        lastClosureM = null
    }

    fun snapshot(nowNs: Long, mode: AppMode): HudState {
        val lock = gnssLock(nowNs)
        val age = if (lastGnssNs == 0L) Double.POSITIVE_INFINITY else (nowNs - lastGnssNs) / 1e9
        // Outage is derived from when the fix actually went away, not from when
        // a snapshot first noticed. The previous version started the clock on
        // the first observing call, so a single snapshot after a long coast
        // reported an outage of zero -- exactly the case that matters.
        val outage = when {
            lock -> 0.0
            lastGnssNs != 0L -> maxOf(0.0, (nowNs - lastGnssNs) / 1e9)
            armedAtNs != 0L -> maxOf(0.0, (nowNs - armedAtNs) / 1e9)
            else -> 0.0
        }
        val loopDist = if (markEast != null) maxOf(0.0, distanceM - markDistance) else 0.0
        val drift = lastClosureM?.let { err ->
            if (loopDist > 1.0) 100.0 * err / loopDist else null
        }

        val navMode = when {
            mode != AppMode.NAVIGATE -> NavMode.IDLE
            lock -> NavMode.GNSS
            hasOrigin -> NavMode.DEAD_RECKONING
            else -> NavMode.RELATIVE
        }

        // Drift constant: the benchmark target until this session measures its
        // own on a closed loop, at which point we use the measured number.
        val measuredDrift = drift != null && drift > 0.0
        val k = if (measuredDrift) drift!! / 100.0 else DEFAULT_DRIFT_RATE

        val uncertainty: Double
        val basis: String
        when (navMode) {
            NavMode.GNSS -> {
                uncertainty = lastAccH
                basis = if (lastAccH.isFinite()) {
                    "horizontal accuracy reported by the OS for the live fix"
                } else {
                    "the OS did not report an accuracy for this fix"
                }
            }
            NavMode.DEAD_RECKONING -> {
                val growth = k * distanceSinceFixM
                if (originSource == OriginSource.GNSS_FIX) {
                    uncertainty = if (anchorAccH.isFinite()) anchorAccH + growth else growth
                    basis = if (anchorAccH.isFinite()) {
                        "modelled: %.0f m accuracy of the last fix + %.0f%% of the %.0f m dead-reckoned since"
                            .format(anchorAccH, k * 100.0, distanceSinceFixM)
                    } else {
                        "modelled growth only: %.0f%% of the %.0f m dead-reckoned since the last fix, whose own accuracy was not reported"
                            .format(k * 100.0, distanceSinceFixM)
                    }
                } else {
                    uncertainty = growth
                    basis = "modelled growth only: %.0f%% of the %.0f m travelled. The error of the start point you set by hand is unknown and is NOT included"
                        .format(k * 100.0, distanceSinceFixM)
                }
            }
            NavMode.RELATIVE -> {
                uncertainty = k * distanceM
                basis = "relative displacement only: %.0f%% of the %.0f m travelled. There is no absolute position to be uncertain about"
                    .format(k * 100.0, distanceM)
            }
            NavMode.IDLE -> {
                uncertainty = Double.NaN
                basis = "not armed"
            }
        }

        val status = when {
            locationStatus == LocationStatus.PERMISSION_DENIED ||
                locationStatus == LocationStatus.SERVICES_OFF ||
                locationStatus == LocationStatus.NO_PROVIDER -> locationStatus
            lock -> LocationStatus.LIVE
            everHadFix -> LocationStatus.LOST
            locationStatus == LocationStatus.UNKNOWN -> LocationStatus.UNKNOWN
            else -> LocationStatus.WAITING_FOR_FIX
        }

        return HudState(
            tNs = nowNs,
            lat = lat,
            lon = lon,
            alt = alt,
            east = east,
            north = north,
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
            loopMarked = markEast != null,
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
            navMode = navMode,
            originSource = originSource,
            hasAbsolutePosition = hasOrigin,
            uncertaintyM = uncertainty,
            uncertaintyBasis = basis,
            driftRateUsed = k,
            driftRateMeasured = measuredDrift,
            distanceSinceFixM = distanceSinceFixM,
            locationStatus = status,
            headingReferenced = headingReferenced,
            mountApplied = mount != null,
            mountNote = mountNote,
            insTrail = insTrail.toList(),
            gnssTrail = gnssTrail.toList(),
        )
    }

    private fun point(e: Double, n: Double, fromGnss: Boolean, tNs: Long): TrailPoint {
        val hasAbs = hasOrigin
        val mpd = if (hasAbs) metersPerDeg(originLat) else null
        return TrailPoint(
            east = e,
            north = n,
            lat = if (hasAbs && mpd != null) originLat + n / mpd.mLat else Double.NaN,
            lon = if (hasAbs && mpd != null) originLon + e / mpd.mLon else Double.NaN,
            fromGnss = fromGnss,
            tNs = tNs,
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

    companion object {
        /**
         * Fraction of distance travelled, used as the error growth rate until a
         * loop closure measures the real one. This is the benchmark TARGET the
         * project states (under 10% drift), not a measured result -- the UI
         * labels it "modelled" wherever it is shown.
         */
        const val DEFAULT_DRIFT_RATE = 0.10
    }
}
