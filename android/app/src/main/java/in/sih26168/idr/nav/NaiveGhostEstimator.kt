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
 * ## Gravity
 *
 * Phone accelerometers report **specific force** (includes gravity). Integrating
 * raw `ax`/`ay` while the phone is tilted leaks ~9.8 m/s² into the horizontal
 * axes and the puck teleports in under a second. This estimator keeps a
 * low-pass gravity estimate per axis and integrates `a − g`, matching the lab
 * free-DR baseline's honesty (still phone → slow bias drift, not an explosion).
 */
class NaiveGhostEstimator(
    private val trailCap: Int = 1500,
    private val trailMinStepM: Double = 2.0,
    private val trailMinStepNs: Long = 1_000_000_000L,
    /** Low-pass coefficient for gravity: `g ← (1−α)g + α a`. */
    private val gravityAlpha: Double = 0.02,
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

    private var gxEst: Double = 0.0
    private var gyEst: Double = 0.0
    private var gzEst: Double = 9.80665
    private var gravityReady: Boolean = false

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
        gxEst = 0.0
        gyEst = 0.0
        gzEst = 9.80665
        gravityReady = false
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
            // Seed gravity from the first sample so a tilted start does not
            // dump a full g into velocity on the second tick.
            gxEst = frame.ax
            gyEst = frame.ay
            gzEst = frame.az
            gravityReady = true
            lastTns = frame.tNs
            return
        }
        val dt = (frame.tNs - lastTns) / 1e9
        lastTns = frame.tNs
        if (dt <= 0.0 || dt > 0.5) return
        armed = true

        // Low-pass gravity (specific-force mean). Absorbs slow tilt/bias so a
        // still phone does not explode; residual noise still drifts slowly.
        val a = gravityAlpha.coerceIn(0.001, 1.0)
        gxEst = (1.0 - a) * gxEst + a * frame.ax
        gyEst = (1.0 - a) * gyEst + a * frame.ay
        gzEst = (1.0 - a) * gzEst + a * frame.az
        gravityReady = true

        // Raw yaw only — no bias subtraction, no lean solver.
        yaw = sanitizeYaw.accept(yaw + frame.gz * dt)

        val fx = frame.ax - gxEst
        val fy = frame.ay - gyEst

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
