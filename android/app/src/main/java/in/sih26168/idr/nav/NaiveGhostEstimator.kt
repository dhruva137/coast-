package `in`.sih26168.idr.nav

import `in`.sih26168.idr.data.SensorFrame
import `in`.sih26168.idr.data.TrackSnapshot
import `in`.sih26168.idr.data.TrailPoint
import kotlin.math.cos
import kotlin.math.hypot
import kotlin.math.sin

/**
 * Deliberately naive dead-reckoning for the demo "ghost car".
 *
 * Pure double integration `s = ∬a dt` with heading from raw gyro. No map lock,
 * no ZUPT, no gyro-bias estimate, no speed model. Same [SensorFrame] stream as
 * [SimpleIns] — divergence is physics, not a scripted bad path.
 *
 * ## Expected still-phone behaviour (ZUPT tabletop)
 *
 * Any residual horizontal specific force (sensor bias, imperfect gravity
 * removal, tiny tilt) integrates into velocity that grows roughly linearly with
 * time. Do **not** script 5→15→40 km/h — leave the phone still and let this
 * integrator produce the drift; COAST with ZUPT should hold near 0 m/s beside it.
 */
class NaiveGhostEstimator(
    private val trailCap: Int = 1500,
    private val trailMinStepM: Double = 2.0,
    private val trailMinStepNs: Long = 1_000_000_000L,
) {
    /** Metres east of session start (relative). */
    var east: Double = 0.0
        private set

    /** Metres north of session start. */
    var north: Double = 0.0
        private set

    /** Radians, 0 = north, positive toward east — same convention as [SimpleIns]. */
    var yaw: Double = 0.0
        private set

    /** Horizontal speed from the naive velocity state, m/s. */
    var speedMps: Double = 0.0
        private set

    var armed: Boolean = false
        private set

    private var ve: Double = 0.0
    private var vn: Double = 0.0
    private var lastTns: Long = 0L

    private val trail = ArrayDeque<TrailPoint>()
    private var trackVersion: Long = 0L
    private var lastTrackVersion: Long = -1L
    private var cachedTrack: TrackSnapshot = TrackSnapshot()
    private var lastKeptEast: Double = Double.NaN
    private var lastKeptNorth: Double = Double.NaN
    private var lastKeptNs: Long = 0L
    private var minEast = 0.0
    private var maxEast = 0.0
    private var minNorth = 0.0
    private var maxNorth = 0.0

    private val sanitizeEast = SanitizeGate()
    private val sanitizeNorth = SanitizeGate()
    private val sanitizeSpeed = SanitizeGate()
    private val sanitizeYaw = SanitizeGate()

    fun reset() {
        east = 0.0
        north = 0.0
        yaw = 0.0
        speedMps = 0.0
        armed = false
        ve = 0.0
        vn = 0.0
        lastTns = 0L
        trail.clear()
        trackVersion = 0L
        lastTrackVersion = -1L
        cachedTrack = TrackSnapshot()
        lastKeptEast = Double.NaN
        lastKeptNorth = Double.NaN
        lastKeptNs = 0L
        minEast = 0.0
        maxEast = 0.0
        minNorth = 0.0
        maxNorth = 0.0
        sanitizeEast.reset()
        sanitizeNorth.reset()
        sanitizeSpeed.reset()
        sanitizeYaw.reset()
    }

    fun onImu(frame: SensorFrame) {
        if (!sensorFrameChannelsFinite(
                frame.ax, frame.ay, frame.az, frame.gx, frame.gy, frame.gz,
            )
        ) {
            return
        }
        if (lastTns == 0L) {
            lastTns = frame.tNs
            return
        }
        val dt = (frame.tNs - lastTns) / 1e9
        lastTns = frame.tNs
        if (dt <= 0.0 || dt > 0.5) return
        armed = true

        // Raw yaw only — no bias subtraction, no lean solver.
        yaw = sanitizeYaw.accept(yaw + frame.gz * dt)

        // Horizontal specific force only. Gravity on body-z is assumed, not
        // estimated — any tilt or accel bias becomes unbounded velocity.
        val fx = frame.ax
        val fy = frame.ay

        // Yaw-only body→EN (roll/pitch ignored — naive).
        val ae = fx * sin(yaw) + fy * cos(yaw)
        val an = fx * cos(yaw) - fy * sin(yaw)

        ve += ae * dt
        vn += an * dt
        east = sanitizeEast.accept(east + ve * dt)
        north = sanitizeNorth.accept(north + vn * dt)
        speedMps = sanitizeSpeed.accept(hypot(ve, vn))

        pushDecimated(east, north, frame.tNs)
    }

    fun trackSnapshot(): TrackSnapshot {
        if (trackVersion != lastTrackVersion) {
            lastTrackVersion = trackVersion
            cachedTrack = TrackSnapshot(
                ins = trail.toList(),
                gnss = emptyList(),
                version = trackVersion,
                minEast = minEast,
                maxEast = maxEast,
                minNorth = minNorth,
                maxNorth = maxNorth,
            )
        }
        return cachedTrack
    }

    private fun pushDecimated(e: Double, n: Double, tNs: Long) {
        if (!shouldKeep(e, n, tNs)) return
        lastKeptEast = e
        lastKeptNorth = n
        lastKeptNs = tNs
        trail.addLast(
            TrailPoint(
                east = e,
                north = n,
                lat = Double.NaN,
                lon = Double.NaN,
                fromGnss = false,
                tNs = tNs,
            ),
        )
        while (trail.size > trailCap) trail.removeFirst()
        trackVersion += 1
        if (e < minEast) minEast = e
        if (e > maxEast) maxEast = e
        if (n < minNorth) minNorth = n
        if (n > maxNorth) maxNorth = n
    }

    private fun shouldKeep(e: Double, n: Double, tNs: Long): Boolean {
        if (lastKeptEast.isNaN() || lastKeptNorth.isNaN()) return true
        val de = e - lastKeptEast
        val dn = n - lastKeptNorth
        if (de * de + dn * dn >= trailMinStepM * trailMinStepM) return true
        return lastKeptNs != 0L && tNs - lastKeptNs >= trailMinStepNs
    }

}
