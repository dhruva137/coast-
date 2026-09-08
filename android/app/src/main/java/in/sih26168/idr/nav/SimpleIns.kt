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
import `in`.sih26168.idr.data.TrackSnapshot
import `in`.sih26168.idr.data.TrailPoint
import `in`.sih26168.idr.data.VehicleKind
import kotlin.math.abs
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
 *
 * ## Vehicle profile
 *
 * Everything above is shaped by [VehicleProfile]. The profile decides whether
 * the lean solver runs at all, how fast the vehicle may plausibly go, turn and
 * accelerate, how much sideways motion it is physically capable of, and how
 * still it has to be before a stop counts. The default is
 * [VehicleKind.other], which leaves every limit wide and the lean solver on --
 * i.e. exactly the behaviour that shipped before profiles existed.
 *
 * ## Zero-velocity updates
 *
 * See [ZuptDetector]. A confirmed stop zeroes velocity outright and refreshes
 * the gyro bias from the stationary mean, which bounds drift by the interval
 * between stops rather than by the length of the journey. In a metro that
 * interval is one station.
 */
class SimpleIns(
    profile: VehicleProfile = VehicleProfile.default(),
    private val trailCap: Int = 1500,
    private val gnssTimeoutNs: Long = 2_000_000_000L,
    private val modelStaleNs: Long = 500_000_000L,
    /**
     * Minimum spacing between retained INS trail points, metres.
     *
     * PERFORMANCE + CORRECTNESS. The old code appended one point per IMU sample.
     * `SensorHub` runs at `SENSOR_DELAY_FASTEST`, so on a real phone that is
     * 200-500 points a second, and the 4000-point cap it kept meant the entire
     * visible track was the last 8-20 SECONDS of the ride -- the rest was
     * silently dropped off the front. Decimating by distance keeps the drawn
     * line geometrically identical to the eye (2 m is well under a pixel at any
     * zoom that fits a route) while making the cap mean roughly 3 km of track,
     * and cuts the map's per-frame path work by two orders of magnitude.
     */
    private val trailMinStepM: Double = 2.0,
    /**
     * Retain a point at least this often even when standing still, so a
     * stationary pause is still visible in the track's timing.
     */
    private val trailMinStepNs: Long = 1_000_000_000L,
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

    // ---- Vehicle profile ---------------------------------------------------
    var profile: VehicleProfile = profile
        private set

    /** True when the coordinated-turn solver is running for this profile. */
    val leanSolverActive: Boolean get() = profile.leans

    private var yawClampCount: Long = 0L
    private var speedClampCount: Long = 0L
    /** Fraction of recent ticks where the yaw rate hit the profile limit. */
    private var yawClampDuty: Double = 0.0
    /** Low-passed |lateral specific force|, m/s^2. NaN until measurable. */
    private var lateralFiltered: Double = Double.NaN
    private var lateralViolation: String? = null
    private var turnViolation: String? = null

    // ---- Pedestrian dead reckoning -----------------------------------------
    //
    // A gait produces a per-step oscillation whose MEAN forward acceleration is
    // about zero, so the vehicle integrator below reads a walk as "not moving"
    // and then accumulates noise. Counting footsteps and multiplying by a
    // step-length model is the standard answer. Used only when the profile says
    // so -- see VehicleProfile.usesSteps.
    private val steps = StepDetector()

    /** Footsteps counted this session. 0 unless the profile uses steps. */
    val stepCount: Long get() = steps.count

    /** Most recent Weinberg step length, metres. NaN before the first step. */
    val lastStepLengthM: Double get() = steps.lastLengthM

    // ---- Zero-velocity updates ---------------------------------------------
    private val zupt = ZuptDetector(profile)
    /** Gyro bias estimate in the integration frame, rad/s. */
    private var biasX: Double = 0.0
    private var biasY: Double = 0.0
    private var biasZ: Double = 0.0
    private var gyroBiasEstimated: Boolean = false
    private var zuptNote: String = ""

    /** True while a stop is confirmed. */
    var stationary: Boolean = false

        private set

    /** Confirmed stops that produced an update, this session. */
    val zuptCount: Long get() = zupt.updates

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
    private var modelDropped: Long = 0L
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

    // ---- Track publishing --------------------------------------------------
    /** Bumped only when a point is actually appended. Drives the map's cache. */
    private var trackVersion: Long = 0L
    private var lastTrackVersion: Long = -1L
    private var cachedTrack: TrackSnapshot = TrackSnapshot()
    private var lastKeptEast: Double = Double.NaN
    private var lastKeptNorth: Double = Double.NaN
    private var lastKeptNs: Long = 0L
    // Bounds maintained incrementally: the map used to rescan every point in
    // composition, every frame, just to place the camera.
    private var minEast = 0.0
    private var maxEast = 0.0
    private var minNorth = 0.0
    private var maxNorth = 0.0

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
        modelDropped = 0L
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
        trackVersion += 1
        lastTrackVersion = -1L
        cachedTrack = TrackSnapshot()
        lastKeptEast = Double.NaN
        lastKeptNorth = Double.NaN
        lastKeptNs = 0L
        minEast = 0.0
        maxEast = 0.0
        minNorth = 0.0
        maxNorth = 0.0
        zupt.reset()
        steps.reset()
        biasX = 0.0
        biasY = 0.0
        biasZ = 0.0
        gyroBiasEstimated = false
        stationary = false
        zuptNote = ""
        yawClampCount = 0L
        speedClampCount = 0L
        yawClampDuty = 0.0
        lateralFiltered = Double.NaN
        lateralViolation = null
        turnViolation = null
    }

    /**
     * Choose the motion model.
     *
     * The gyro bias is deliberately NOT cleared: it is a property of the phone,
     * not of the vehicle, and throwing away a good estimate because the user
     * corrected the vehicle picker would be a regression. The stationary
     * detector IS reset, because its thresholds have just changed and the
     * statistics in its window were gathered under the old ones.
     */
    fun setProfile(p: VehicleProfile) {
        if (p.kind == profile.kind) return
        profile = p
        zupt.setProfile(p)
        stationary = false
        zuptNote = ""
        lateralFiltered = Double.NaN
        lateralViolation = null
        turnViolation = null
        yawClampDuty = 0.0
        // A non-leaning profile must not carry a lean angle forward from a
        // leaning one; it would bias every subsequent yaw-rate projection.
        if (!p.leans) lean = 0.0
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
        var gxV: Double
        var gyV: Double
        var gzV: Double
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

        // Subtract the ZUPT-estimated gyro bias before anything integrates it.
        // Estimating a bias and then not applying it would be worse than not
        // estimating one, because Diagnostics would report a correction that
        // never reached the heading. The bias is measured in the same frame the
        // detector saw, so it is removed here, after rotation, only once a stop
        // has actually produced an estimate.
        if (gyroBiasEstimated) {
            gxV -= biasX
            gyV -= biasY
            gzV -= biasZ
        }

        // ---- Zero-velocity update ------------------------------------------
        //
        // A confirmed stop is free information and the only bounded correction
        // available with no GNSS: velocity is exactly zero, so whatever the
        // integrator currently holds is pure accumulated error, and the gyro
        // mean over a stationary window is pure bias. Applying both caps drift
        // at every station instead of letting it compound across the journey.
        //
        // This runs on the *raw* device axes deliberately: the accelerometer is
        // used through its magnitude, which no mount rotation can change, so an
        // uncalibrated phone gets the same stationary decision as a calibrated
        // one. It also runs before the speed branch below, so a stop overrides
        // the model and the fallback alike.
        // The gyro handed over is the BIAS-CORRECTED signal, because
        // ZuptEvent's deltas are defined as a residual on top of whatever the
        // caller has already removed. Feeding raw samples here makes each stop
        // re-report the full bias, so the running estimate double-counts and
        // grows without limit -- measured as heading drift getting worse, not
        // better, after a stop. The accelerometer stays raw: the detector uses
        // it through its magnitude, which no correction or rotation changes.
        val zev = zupt.update(
            frame.tNs, frame.ax, frame.ay, frame.az, gxV, gyV, gzV,
        )
        stationary = zupt.stopped
        if (zev != null) {
            speed = 0.0
            biasX += zev.biasDeltaX
            biasY += zev.biasDeltaY
            biasZ += zev.biasDeltaZ
            gyroBiasEstimated = true
            zuptNote = if (zev.firstOfThisStop) {
                "STOPPED - velocity zeroed, gyro bias re-estimated"
            } else {
                "STOPPED %.0f s - bias refreshed".format(zev.stillForSec)
            }
        } else if (!stationary) {
            zuptNote = ""
        }

        val lock = gnssLock(frame.tNs)
        val modelFresh = modelSpeed.isFinite() &&
            modelTNs != 0L &&
            frame.tNs - modelTNs in 0 until modelStaleNs
        if (lock) {
            // onGnss already wrote speed from the fix.
            speedSource = SpeedSource.GNSS
        } else if (profile.usesSteps) {
            // Pedestrian: speed is step length x cadence, held between steps and
            // faded out if a step is overdue, so a stop reads as a stop rather
            // than as a phantom constant walk.
            steps.update(frame.tNs, frame.ax, frame.ay, frame.az)
            speed = steps.coastSpeedMps(frame.tNs)
            speedSource = SpeedSource.FALLBACK
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
        pushInsDecimated(east, north, frame.tNs, fromGnss = false)
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
    fun setModelStatus(ready: Boolean, error: String?, dropped: Long = 0L) {
        modelReady = ready
        modelError = error
        modelDropped = dropped
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
        // A fix is a real discontinuity in the track and is never decimated
        // away: it is the point a judge is looking for on the map.
        push(gnssTrail, point(east, north, fromGnss = true, tNs = fix.tNs))
        pushInsDecimated(east, north, fix.tNs, fromGnss = true)
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
            modelDropped = modelDropped,
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
        trackVersion += 1
        if (p.east < minEast) minEast = p.east
        if (p.east > maxEast) maxEast = p.east
        if (p.north < minNorth) minNorth = p.north
        if (p.north > maxNorth) maxNorth = p.north
    }

    /**
     * True when this sample is far enough from the last retained one to be
     * worth keeping. Pure and side-effect free so it can be unit tested.
     */
    internal fun shouldKeepTrailPoint(e: Double, n: Double, tNs: Long): Boolean {
        if (lastKeptEast.isNaN() || lastKeptNorth.isNaN()) return true
        val de = e - lastKeptEast
        val dn = n - lastKeptNorth
        if (de * de + dn * dn >= trailMinStepM * trailMinStepM) return true
        return lastKeptNs != 0L && tNs - lastKeptNs >= trailMinStepNs
    }

    /** Append to the INS trail only if [shouldKeepTrailPoint] says it earns a slot. */
    private fun pushInsDecimated(e: Double, n: Double, tNs: Long, fromGnss: Boolean) {
        if (!fromGnss && !shouldKeepTrailPoint(e, n, tNs)) return
        lastKeptEast = e
        lastKeptNorth = n
        lastKeptNs = tNs
        push(insTrail, point(e, n, fromGnss = fromGnss, tNs = tNs))
    }

    /**
     * The track for the map, as an immutable snapshot.
     *
     * Rebuilt only when [trackVersion] moved. The previous design copied both
     * deques into fresh lists inside every HUD frame whether or not a point had
     * been added, which is the single largest allocation source the app had.
     */
    fun trackSnapshot(): TrackSnapshot {
        if (trackVersion != lastTrackVersion) {
            lastTrackVersion = trackVersion
            cachedTrack = TrackSnapshot(
                ins = insTrail.toList(),
                gnss = gnssTrail.toList(),
                version = trackVersion,
                minEast = minEast,
                maxEast = maxEast,
                minNorth = minNorth,
                maxNorth = maxNorth,
            )
        }
        return cachedTrack
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
