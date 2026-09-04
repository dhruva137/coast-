package `in`.sih26168.idr.data

/**
 * Frozen sensor / log types. Field names match bible §5.8 and core/ts types.
 * Do not rename columns.
 */
data class SensorFrame(
    val tNs: Long,
    val ax: Double,
    val ay: Double,
    val az: Double,
    val gx: Double,
    val gy: Double,
    val gz: Double,
    val mx: Double,
    val my: Double,
    val mz: Double,
    val pressureHpa: Double,
    val lux: Double,
)

data class GnssFix(
    val tNs: Long,
    val lat: Double,
    val lon: Double,
    val alt: Double,
    val speed: Double,
    val bearing: Double,
    val accH: Double,
    val accV: Double,
    val nSats: Int,
)

enum class MountType { handlebar, pocket, tankbag, frame, dash }

enum class VehicleKind { car, scooter, motorcycle, bicycle }

data class SessionConfig(
    val phoneModel: String,
    val mountType: MountType,
    val vehicle: VehicleKind,
    val rider: String,
    val routeId: String,
    val notes: String,
    val leans: Boolean = true,
    val loopClosureLat: Double? = null,
    val loopClosureLon: Double? = null,
)

data class SensorReport(
    val accelUncal: Boolean = false,
    val gyroUncal: Boolean = false,
    val accelFallback: Boolean = false,
    val gyroFallback: Boolean = false,
    val mag: Boolean = false,
    val pressure: Boolean = false,
    val light: Boolean = false,
    val gnss: Boolean = false,
)

/**
 * One point of a track.
 *
 * [east] / [north] are metres from the session origin and are ALWAYS valid --
 * they are what the estimator actually integrates. [lat] / [lon] are only
 * meaningful when an absolute origin exists; they are [Double.NaN] otherwise
 * and the UI must not render them as a position.
 */
data class TrailPoint(
    val east: Double,
    val north: Double,
    val lat: Double,
    val lon: Double,
    val fromGnss: Boolean,
    val tNs: Long,
) {
    val hasAbsolute: Boolean get() = !lat.isNaN() && !lon.isNaN()
}

/**
 * What actually produced the speed the HUD is showing right now.
 *
 * `GNSS` = live fix. `MODEL` = on-device AVNet-tiny ONNX head. `FALLBACK` =
 * the hand-rolled accel-integrator coast in [`in`.sih26168.idr.nav.SimpleIns].
 * Never label a tick `MODEL` unless the session really ran.
 */
enum class SpeedSource { GNSS, MODEL, FALLBACK }

/**
 * What the position on screen actually means. This is the single most
 * important honesty control in the app -- it must never say GNSS when there
 * is no fix, and never say DEAD_RECKONING when there is no absolute anchor.
 */
enum class NavMode {
    /** Live GNSS fix inside the timeout. Absolute position, OS accuracy. */
    GNSS,

    /** No fix, but an absolute origin exists. Absolute position, growing error. */
    DEAD_RECKONING,

    /** No absolute anchor at all. Displacement and track shape only. */
    RELATIVE,

    /** Estimator not armed. */
    IDLE,
}

/** Where the absolute anchor came from, if there is one. */
enum class OriginSource {
    /** No anchor -- the app is in [NavMode.RELATIVE]. */
    NONE,

    /** A real GNSS fix. Absolute error starts at the accuracy of that fix. */
    GNSS_FIX,

    /** The user long-pressed the map. User-asserted; its own error is unknown. */
    USER_MAP,

    /** The user typed coordinates. User-asserted; its own error is unknown. */
    USER_COORDS,
}

/** Whether the location subsystem can give us anything at all, and why not. */
enum class LocationStatus {
    /** ACCESS_FINE/COARSE_LOCATION not granted. */
    PERMISSION_DENIED,

    /** Permission granted, but the device location master switch is off. */
    SERVICES_OFF,

    /** Location on and permitted, but no provider is currently enabled. */
    NO_PROVIDER,

    /** Permitted and enabled, no fix yet (cold start / indoors). */
    WAITING_FOR_FIX,

    /** Fix is live and inside the staleness timeout. */
    LIVE,

    /** We had a fix and lost it -- tunnel, basement, urban canyon. */
    LOST,

    /** Not checked yet. */
    UNKNOWN,
}

data class HudState(
    val tNs: Long = 0L,
    /** [Double.NaN] whenever there is no absolute origin. Never render NaN as 0. */
    val lat: Double = Double.NaN,
    val lon: Double = Double.NaN,
    val alt: Double = Double.NaN,
    /** Metres east / north of the session origin. Always valid once armed. */
    val east: Double = 0.0,
    val north: Double = 0.0,
    val speedMps: Double = 0.0,
    val leanDeg: Double = 0.0,
    val headingDeg: Double = 0.0,
    val headingCarDeg: Double = 0.0,
    val distanceM: Double = 0.0,
    val imuHz: Double = 0.0,
    val gnssLock: Boolean = false,
    val gnssAgeSec: Double = Double.POSITIVE_INFINITY,
    val nSats: Int = 0,
    val accH: Double = Double.NaN,
    val outageSec: Double = 0.0,
    val loopMarked: Boolean = false,
    val loopClosureM: Double? = null,
    val loopDistanceM: Double = 0.0,
    val driftPct: Double? = null,
    val coordinated: Boolean = false,
    val speedSource: SpeedSource = SpeedSource.FALLBACK,
    val modelReady: Boolean = false,
    val modelSpeedMps: Double = Double.NaN,
    val modelPsiDot: Double = Double.NaN,
    val modelSpeedVar: Double = Double.NaN,
    val inferMs: Double = 0.0,
    val modelHz: Double = 0.0,
    val modelError: String? = null,
    val mode: AppMode = AppMode.IDLE,

    // ---- Honest-position block -------------------------------------------
    val navMode: NavMode = NavMode.IDLE,
    val originSource: OriginSource = OriginSource.NONE,
    /** True only when [lat]/[lon] mean something on the Earth. */
    val hasAbsolutePosition: Boolean = false,
    /**
     * Radius, metres. GNSS: the OS-reported horizontal accuracy (measured).
     * Otherwise a MODELLED growth term -- see [uncertaintyBasis]. NaN = unknown,
     * and the UI must say "unknown", not draw a circle of zero.
     */
    val uncertaintyM: Double = Double.NaN,
    /** Plain-English statement of where [uncertaintyM] came from. */
    val uncertaintyBasis: String = "",
    /** Drift constant used by the uncertainty model, as a fraction (0.10 = 10%). */
    val driftRateUsed: Double = 0.10,
    /** True when [driftRateUsed] came from the loop closure of this session. */
    val driftRateMeasured: Boolean = false,
    /** Metres dead-reckoned since the last usable absolute fix. */
    val distanceSinceFixM: Double = 0.0,
    val locationStatus: LocationStatus = LocationStatus.UNKNOWN,
    /**
     * True once heading has been tied to true north by a GNSS bearing.
     *
     * Until then [headingDeg] is integrated from an arbitrary zero -- it is the
     * angle turned since arming, NOT a compass bearing. The map must not draw a
     * north arrow while this is false, and the UI must not call it a heading.
     */
    val headingReferenced: Boolean = false,
    /** True when a validated mount rotation is being applied to the IMU. */
    val mountApplied: Boolean = false,
    val mountNote: String = "raw device axes -- not calibrated",

    val insTrail: List<TrailPoint> = emptyList(),
    val gnssTrail: List<TrailPoint> = emptyList(),
)

data class RecordStats(
    val running: Boolean = false,
    val sessionDir: String? = null,
    val imuRows: Long = 0,
    val gnssRows: Long = 0,
    val startedAtNs: Long = 0,
    val imuHz: Double = 0.0,
    val qualitySummary: String? = null,
)

enum class AppMode { IDLE, RECORD, NAVIGATE }

// ---------------------------------------------------------------------------
// Device self-check
// ---------------------------------------------------------------------------

/** One sensor as the platform actually describes it. No interpretation here. */
data class SensorSpec(
    val present: Boolean = false,
    val name: String = "",
    val vendor: String = "",
    /** Platform-advertised fastest period, microseconds. 0 = not reported. */
    val minDelayUs: Int = 0,
    /** Derived from [minDelayUs]. NaN when the platform reports nothing. */
    val advertisedHz: Double = Double.NaN,
    /** Counted by [`in`.sih26168.idr.sensor.DeviceProbe]. NaN until probed. */
    val measuredHz: Double = Double.NaN,
    val resolution: Double = Double.NaN,
    val maxRange: Double = Double.NaN,
    val powerMa: Double = Double.NaN,
)

enum class FindingLevel { OK, WARN, FAIL }

data class Finding(
    val level: FindingLevel,
    val title: String,
    val detail: String,
)

enum class DeviceVerdict {
    /** Real gyro + accel at a usable rate. Dead reckoning is supported. */
    PASS,

    /** It will run, but something material is missing or slow. */
    DEGRADED,

    /** A sensor dead reckoning cannot do without is absent. */
    FAIL,

    /** Not checked yet. */
    UNKNOWN,
}

data class DeviceCheck(
    val verdict: DeviceVerdict = DeviceVerdict.UNKNOWN,
    val probed: Boolean = false,
    val accel: SensorSpec = SensorSpec(),
    val accelUncal: SensorSpec = SensorSpec(),
    val gyro: SensorSpec = SensorSpec(),
    val gyroUncal: SensorSpec = SensorSpec(),
    val mag: SensorSpec = SensorSpec(),
    val magUncal: SensorSpec = SensorSpec(),
    val baro: SensorSpec = SensorSpec(),
    val findings: List<Finding> = emptyList(),
    /** Model as the OS reports it, for the report the judges read. */
    val device: String = "",
    val androidRelease: String = "",
)

// ---------------------------------------------------------------------------
// Mount calibration
// ---------------------------------------------------------------------------

/**
 * Phone-to-vehicle rotation, in aerospace body convention:
 * x = forward, y = right, z = down, right-handed (forward x right = down).
 *
 * Each triple is a unit vector expressed in DEVICE axes. Rotating a device
 * vector into vehicle axes is three dot products -- see
 * [`in`.sih26168.idr.nav.rotateToVehicle].
 */
data class MountRotation(
    val fx: Double, val fy: Double, val fz: Double,
    val rx: Double, val ry: Double, val rz: Double,
    val dx: Double, val dy: Double, val dz: Double,
)

enum class MountQuality { GOOD, WEAK, REJECTED }

data class MountResult(
    val quality: MountQuality,
    val rotation: MountRotation?,
    /** Speed change measured over the window, m/s. Drives the sign of forward. */
    val deltaVMps: Double,
    /** Peak gyro magnitude during the window, rad/s. High = the user turned. */
    val peakGyroRadS: Double,
    /** Tilt of the screen-up axis of the phone from vertical, degrees. */
    val tiltDeg: Double,
    val samples: Int,
    val reason: String,
)
