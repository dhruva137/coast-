package `in`.sih26168.idr.data

import androidx.compose.runtime.Immutable

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

/**
 * What the phone is riding in.
 *
 * ## Schema compatibility
 *
 * These names are written verbatim into `meta.json` as `vehicle`, and they are
 * the second path component of every session directory
 * (`data/<rider>/<vehicle>/<timestamp>/`). The original four -- `car`,
 * `scooter`, `motorcycle`, `bicycle` -- are UNCHANGED and still spelled the
 * same way, so every log already on a phone, and every script in `lab/` that
 * reads one, keeps working. The change is purely ADDITIVE: six new values that
 * no existing log can contain.
 *
 * A reader that meets an unknown value should fall back to [other], which is
 * what [`in`.sih26168.idr.data.Prefs] does.
 *
 * The motion model behind each value lives in
 * [`in`.sih26168.idr.nav.VehicleProfile] -- this enum is only the identifier.
 */
enum class VehicleKind {
    /** Underground / elevated metro. GNSS is absent for the whole journey. */
    metro_rail,

    /** Suburban or mainline train. */
    train,

    bus,
    car,

    /** Three-wheeler. Rigid: it tips, it does not lean. */
    auto_rickshaw,

    scooter,
    motorcycle,
    bicycle,

    /** On foot. Holonomic -- no lateral constraint to violate. */
    walking,

    /** Unknown. Keeps the pre-profile estimator behaviour exactly. */
    other,
}

@Immutable
data class SessionConfig(
    val phoneModel: String,
    val mountType: MountType,
    val vehicle: VehicleKind,
    val rider: String,
    val routeId: String,
    val notes: String,
    /**
     * Whether the vehicle rolls into a turn.
     *
     * Kept as a stored field because it is a frozen `meta.json` column, but it
     * is no longer set by hand anywhere: it is derived from [vehicle] through
     * `VehicleProfile.of(vehicle).leans`. Use `IdrBus.setVehicle` so the two
     * cannot drift apart.
     */
    val leans: Boolean = true,
    val loopClosureLat: Double? = null,
    val loopClosureLon: Double? = null,
)

@Immutable
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
@Immutable
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

/**
 * The live telemetry frame. Published at [`in`.sih26168.idr.record.RecordService]'s
 * HUD rate, currently 10 Hz.
 *
 * PERFORMANCE, and the reason this is annotated: this used to carry `insTrail`
 * and `gnssTrail`. A `List` is an unstable type to the Compose compiler, so
 * `HudState` was inferred unstable and EVERY composable that took one was
 * unskippable -- the whole Drive screen, map included, recomposed on every
 * single 20 Hz telemetry frame even when the only field that moved was a
 * fraction of a metre. The track now lives in [TrackSnapshot] on its own
 * lower-rate flow, and everything left here is a primitive or an enum, so
 * `@Immutable` is a promise the compiler can actually use to skip.
 */
@Immutable
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
    /**
     * Last ONNX `OrtSession.run` wall time in ms (same source as [measuredInferMs]).
     * Kept for older call sites; prefer [measuredInferMs] in new UI.
     */
    val inferMs: Double = 0.0,
    /**
     * Measured ONNX inference wall time (ms) from [nav.OnnxSpeedModel] —
     * `System.nanoTime` around `OrtSession.run`, never a constant.
     * [Double.NaN] until the first successful inference.
     */
    val measuredInferMs: Double = Double.NaN,
    /**
     * Measured fusion / INS step wall time (ms) for the last [nav.SimpleIns.onImu]
     * call — `System.nanoTime` around that step, never a constant.
     * [Double.NaN] until the first IMU tick is processed.
     */
    val measuredFusionMs: Double = Double.NaN,
    val modelHz: Double = 0.0,
    /**
     * Inference windows skipped because the previous one had not finished.
     * Backpressure working as designed, not an error -- but a number that keeps
     * climbing means the phone cannot sustain 10 Hz.
     */
    val modelDropped: Long = 0L,
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
     * Which estimator is producing the displayed coast: MAP-PF when the native
     * graph filter is loaded, FREE-DR for [nav.SimpleIns], RELATIVE when there
     * is no Earth origin. Never treat particle-filter spread as this label.
     */
    val engineLabel: String = "FREE-DR",
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

    // ---- Vehicle profile block -------------------------------------------
    /** The profile the estimator is actually running, not the one in prefs. */
    val vehicle: VehicleKind = VehicleKind.other,
    val profileLabel: String = "",
    /**
     * True when the coordinated-turn lean solver is running. False for cars,
     * buses and rail, where a body-y gyro rate is pitch or bogie yaw and
     * feeding it to the lean solver would fabricate a turn.
     */
    val leanSolverActive: Boolean = true,

    // ---- Zero-velocity updates -------------------------------------------
    /** True while a stop is confirmed. Drives the STOPPED banner. */
    val stationary: Boolean = false,
    /** Seconds the current stop has lasted. 0 while moving. */
    val stoppedForSec: Double = 0.0,
    /** Confirmed stops that produced an update, this session. */
    val zuptCount: Long = 0L,
    /** Plain-English statement of what the last update did. */
    val zuptNote: String = "",
    /** Magnitude of the current gyro bias estimate, deg/s. */
    val gyroBiasDegS: Double = 0.0,
    /** True once at least one ZUPT has refined the bias. */
    val gyroBiasEstimated: Boolean = false,

    // ---- Profile plausibility --------------------------------------------
    /**
     * Non-null when the motion does not match the selected profile -- e.g.
     * sustained lateral acceleration a metro cannot produce. The UI shows this
     * verbatim. The estimator does NOT silently correct for it.
     */
    val profileViolation: String? = null,
    /** Low-passed lateral specific force, m/s^2. NaN when not measurable. */
    val lateralAccelMps2: Double = Double.NaN,
    /** Ticks where the yaw rate was clipped to the profile limit. */
    val yawClampCount: Long = 0L,
    /** Ticks where speed or longitudinal accel was clipped. */
    val speedClampCount: Long = 0L,

    // ---- Barometer floor change (B7) ---------------------------------------
    /** Relative floor index; 0 at first valid pressure lock. */
    val floorIndex: Int = 0,
    /** True while a recent floor step is being highlighted. */
    val floorChanged: Boolean = false,
    /** Plain-English baro / floor status for Diagnostics. */
    val floorChangeNote: String = "",
    /** Smoothed pressure last seen by the floor detector, hPa. */
    val pressureHpa: Double = Double.NaN,

    /**
     * True on the last IMU tick when outage heading was pulled toward the
     * onset-calibrated compass. False while GNSS-locked, mag-invalid, or
     * fusion is switched off.
     */
    val compassFused: Boolean = false,
    /** True while the user has asserted [Prefs.forceStationary]. */
    val forceHold: Boolean = false,
)

/**
 * The track, on its own flow and its own (slower) clock.
 *
 * Split out of [HudState] for two reasons, both measured off the code rather
 * than guessed:
 *
 *  1. The lists made [HudState] unstable to Compose -- see the note there.
 *  2. `snapshot()` used to `toList()` both deques on every HUD frame. At the old
 *     20 Hz HUD rate with the old 4000-point cap that is up to 160 000 element
 *     copies a second into a `StateFlow` the whole screen collected, purely so
 *     the speed readout could change.
 *
 * [version] increments only when a point is actually appended, so the map can
 * `remember` its built `Path` against it and rebuild once per new point instead
 * of once per animation frame. The bounding box is maintained incrementally by
 * the estimator so the camera never has to scan the whole track in composition.
 *
 * The lists inside are never mutated after construction, which is what makes
 * the `@Immutable` promise true.
 */
@Immutable
data class TrackSnapshot(
    val ins: List<TrailPoint> = emptyList(),
    val gnss: List<TrailPoint> = emptyList(),
    val version: Long = 0L,
    val minEast: Double = 0.0,
    val maxEast: Double = 0.0,
    val minNorth: Double = 0.0,
    val maxNorth: Double = 0.0,
)

@Immutable
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
@Immutable
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

@Immutable
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

@Immutable
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
@Immutable
data class MountRotation(
    val fx: Double, val fy: Double, val fz: Double,
    val rx: Double, val ry: Double, val rz: Double,
    val dx: Double, val dy: Double, val dz: Double,
)

enum class MountQuality { GOOD, WEAK, REJECTED }

@Immutable
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
