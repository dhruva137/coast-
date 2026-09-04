package `in`.sih26168.idr.nav

import `in`.sih26168.idr.data.MountQuality
import `in`.sih26168.idr.data.SensorFrame
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import kotlin.math.abs
import kotlin.math.cos
import kotlin.math.sin

/**
 * Synthetic-motion tests for the mount solver.
 *
 * Each test builds an IMU stream for a phone at a KNOWN orientation and checks
 * that the solver recovers that orientation. The point is to prove the frame
 * convention (x forward, y right, z down) is actually what comes out, because a
 * sign error there silently corrupts every heading downstream.
 */
class MountCalibrationTest {

    private val g = 9.80665
    private val hz = 200
    private val dtNs = 1_000_000_000L / hz

    /**
     * Build a stationary lead-in followed by a straight-line start, which is
     * exactly the protocol the calibration screen asks the user to perform.
     *
     * @param up unit vector, in DEVICE axes, that points up in the world
     * @param fwd unit vector, in DEVICE axes, of travel; must be perpendicular to [up]
     * @param accel forward acceleration in m/s2 during the moving phase
     * @param moveSeconds duration of the moving phase
     * @param stillSeconds stationary lead-in before it
     */
    private fun straightRun(
        up: Triple<Double, Double, Double>,
        fwd: Triple<Double, Double, Double>,
        accel: Double = 1.5,
        moveSeconds: Double = 6.0,
        stillSeconds: Double = 1.5,
        gyro: Triple<Double, Double, Double> = Triple(0.0, 0.0, 0.0),
        gyroDuringStill: Boolean = false,
    ): List<SensorFrame> {
        val nStill = (stillSeconds * hz).toInt()
        val nMove = (moveSeconds * hz).toInt()
        val out = ArrayList<SensorFrame>(nStill + nMove)
        for (i in 0 until nStill + nMove) {
            val moving = i >= nStill
            val a = if (moving) accel else 0.0
            // Specific force = gravity reaction (along up) + forward acceleration.
            val ax = up.first * g + fwd.first * a
            val ay = up.second * g + fwd.second * a
            val az = up.third * g + fwd.third * a
            val spin = if (moving || gyroDuringStill) gyro else Triple(0.0, 0.0, 0.0)
            out += SensorFrame(
                tNs = i.toLong() * dtNs,
                ax = ax, ay = ay, az = az,
                gx = spin.first, gy = spin.second, gz = spin.third,
                mx = 0.0, my = 0.0, mz = 0.0,
                pressureHpa = 1013.0, lux = 0.0,
            )
        }
        return out
    }

    private fun solve(frames: List<SensorFrame>): `in`.sih26168.idr.data.MountResult {
        val c = MountCalibration()
        frames.forEach { c.add(it) }
        return c.solve()
    }

    @Test
    fun `phone flat on a dash facing forward recovers the identity-ish frame`() {
        // Android device axes: +X right of screen, +Y top of screen, +Z out of screen.
        // Phone lying face-up: up = +Z. Travelling toward the top edge: fwd = +Y.
        val r = solve(straightRun(up = Triple(0.0, 0.0, 1.0), fwd = Triple(0.0, 1.0, 0.0)))
        assertEquals(MountQuality.GOOD, r.quality)
        val m = r.rotation
        assertNotNull(m)
        m!!
        // forward is +Y
        assertEquals(0.0, m.fx, 1e-3)
        assertEquals(1.0, m.fy, 1e-3)
        assertEquals(0.0, m.fz, 1e-3)
        // down is -Z
        assertEquals(-1.0, m.dz, 1e-3)
        // right = down x forward = (-Z) x (+Y) = +X
        assertEquals(1.0, m.rx, 1e-3)
    }

    @Test
    fun `frame stays orthonormal for an arbitrary awkward mount`() {
        // Phone in a pocket: tilted 35 degrees, travelling along an odd axis.
        val t = Math.toRadians(35.0)
        val up = normalise(Triple(sin(t), 0.3, cos(t)))
        // Any vector perpendicular to up works as the direction of travel.
        val fwd = normalise(orthogonalTo(up))
        val r = solve(straightRun(up = up, fwd = fwd))
        assertEquals(MountQuality.GOOD, r.quality)
        val err = orthonormalError(r.rotation!!)
        assertTrue("frame not orthonormal, error $err", err < 1e-6)
    }

    @Test
    fun `recovered forward matches the true direction of travel`() {
        val up = normalise(Triple(0.1, -0.2, 1.0))
        val fwd = normalise(orthogonalTo(up))
        val r = solve(straightRun(up = up, fwd = fwd))
        val m = r.rotation!!
        val dot = m.fx * fwd.first + m.fy * fwd.second + m.fz * fwd.third
        assertTrue("forward dot true forward = $dot", dot > 0.999)
    }

    @Test
    fun `rotating a device vector into the vehicle frame gives forward on x`() {
        val r = solve(straightRun(up = Triple(0.0, 0.0, 1.0), fwd = Triple(0.0, 1.0, 0.0))).rotation!!
        // A pure +Y device vector is pure forward, so x = 1 and y = z = 0.
        val v = rotateToVehicle(r, 0.0, 1.0, 0.0)
        assertEquals(1.0, v.first, 1e-3)
        assertEquals(0.0, v.second, 1e-3)
        assertEquals(0.0, v.third, 1e-3)
        // Gravity reaction points up, so in the vehicle frame it is -Z (up = -down).
        val gv = rotateToVehicle(r, 0.0, 0.0, g)
        assertEquals(-g, gv.third, 1e-3)
    }

    @Test
    fun `yaw about the world vertical lands on the vehicle z axis`() {
        // This is the property the lean solver depends on: a pure turn must show
        // up as gz in the vehicle frame, whatever angle the phone sits at.
        val up = normalise(Triple(0.25, -0.1, 1.0))
        val fwd = normalise(orthogonalTo(up))
        val r = solve(straightRun(up = up, fwd = fwd)).rotation!!
        // A 0.4 rad/s left turn is a rotation about world-up, i.e. -down.
        val rate = 0.4
        val omega = Triple(up.first * rate, up.second * rate, up.third * rate)
        val v = rotateToVehicle(r, omega.first, omega.second, omega.third)
        assertEquals("roll rate should be zero", 0.0, v.first, 1e-6)
        assertEquals("pitch rate should be zero", 0.0, v.second, 1e-6)
        // Turning about world-up is -rate about vehicle-down.
        assertEquals(-rate, v.third, 1e-6)
    }

    @Test
    fun `a turn during the capture is rejected rather than fitted`() {
        val r = solve(
            straightRun(
                up = Triple(0.0, 0.0, 1.0),
                fwd = Triple(0.0, 1.0, 0.0),
                gyro = Triple(0.0, 0.0, 1.2),
            ),
        )
        assertEquals(MountQuality.REJECTED, r.quality)
        assertNull(r.rotation)
        assertTrue(r.reason.contains("turned"))
    }

    @Test
    fun `standing still is rejected because forward is not observable`() {
        val r = solve(
            straightRun(up = Triple(0.0, 0.0, 1.0), fwd = Triple(0.0, 1.0, 0.0), accel = 0.0),
        )
        assertEquals(MountQuality.REJECTED, r.quality)
        assertNull(r.rotation)
    }

    @Test
    fun `too short a capture is rejected`() {
        val r = solve(
            straightRun(
                up = Triple(0.0, 0.0, 1.0),
                fwd = Triple(0.0, 1.0, 0.0),
                moveSeconds = 0.1,
                stillSeconds = 0.1,
            ),
        )
        assertEquals(MountQuality.REJECTED, r.quality)
    }

    @Test
    fun `a gentle start is accepted but flagged weak`() {
        // 6 s at 0.25 m/s2 is 1.5 m/s: over the observability floor, under the
        // threshold where the direction is well pinned down.
        val r = solve(
            straightRun(up = Triple(0.0, 0.0, 1.0), fwd = Triple(0.0, 1.0, 0.0), accel = 0.25),
        )
        assertEquals(MountQuality.WEAK, r.quality)
        assertNotNull(r.rotation)
    }

    @Test
    fun `a lead-in that was not still is rejected rather than fitted`() {
        // Gravity would be measured while the phone was already turning, which
        // would tilt the whole frame. Refuse instead.
        val r = solve(
            straightRun(
                up = Triple(0.0, 0.0, 1.0),
                fwd = Triple(0.0, 1.0, 0.0),
                gyro = Triple(0.0, 0.0, 0.4),
                gyroDuringStill = true,
            ),
        )
        assertEquals(MountQuality.REJECTED, r.quality)
        assertNull(r.rotation)
    }

    @Test
    fun `constant acceleration is still recovered`() {
        // Regression guard. Estimating gravity from the mean of the WHOLE capture
        // cancels a constant forward acceleration exactly, making a real straight
        // start look identical to standing still. Gravity must come from the
        // stationary lead-in only.
        val r = solve(
            straightRun(
                up = Triple(0.0, 0.0, 1.0),
                fwd = Triple(0.0, 1.0, 0.0),
                accel = 1.5,
                moveSeconds = 6.0,
            ),
        )
        assertEquals(MountQuality.GOOD, r.quality)
        assertEquals(9.0, r.deltaVMps, 0.2)
    }

    // ---- helpers ----------------------------------------------------------

    private fun normalise(v: Triple<Double, Double, Double>): Triple<Double, Double, Double> {
        val n = hypot3(v.first, v.second, v.third)
        return Triple(v.first / n, v.second / n, v.third / n)
    }

    /** Any unit vector perpendicular to [v]. */
    private fun orthogonalTo(v: Triple<Double, Double, Double>): Triple<Double, Double, Double> {
        // Cross with whichever axis is least parallel to v.
        val seed = if (abs(v.first) < 0.9) Triple(1.0, 0.0, 0.0) else Triple(0.0, 1.0, 0.0)
        val c = Triple(
            v.second * seed.third - v.third * seed.second,
            v.third * seed.first - v.first * seed.third,
            v.first * seed.second - v.second * seed.first,
        )
        return normalise(c)
    }

    @Suppress("unused")
    private fun cosDeg(d: Double) = cos(Math.toRadians(d))
}
