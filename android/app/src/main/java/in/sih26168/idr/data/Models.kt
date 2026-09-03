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

data class TrailPoint(
    val lat: Double,
    val lon: Double,
    val fromGnss: Boolean,
    val tNs: Long,
)

data class HudState(
    val tNs: Long = 0L,
    val lat: Double = 0.0,
    val lon: Double = 0.0,
    val alt: Double = 0.0,
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
    val mode: AppMode = AppMode.IDLE,
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
)

enum class AppMode { IDLE, RECORD, NAVIGATE }
