package `in`.sih26168.idr.nav

import `in`.sih26168.idr.data.AppMode
import `in`.sih26168.idr.data.SensorFrame
import org.junit.Assert.assertTrue
import org.junit.Test
import kotlin.math.abs
import kotlin.math.hypot

/**
 * P1-1 ghost car: naive double-integration on the same IMU as COAST must
 * diverge, and still input with a realistic accel bias must grow speed
 * (the contrast ZUPT tabletop relies on).
 */
class NaiveGhostTest {

    private val hz = 100
    private val dtNs = 1_000_000_000L / hz
    private val g = 9.80665

    private fun frame(
        i: Int,
        ax: Double = 0.0,
        ay: Double = 0.0,
        az: Double = g,
        gz: Double = 0.0,
    ) = SensorFrame(
        tNs = i.toLong() * dtNs,
        ax = ax, ay = ay, az = az,
        gx = 0.0, gy = 0.0, gz = gz,
        mx = 0.0, my = 0.0, mz = 0.0,
        pressureHpa = 1013.0, lux = 0.0,
    )

    @Test
    fun `still then yaw - ghost displaces differently from COAST`() {
        val ins = SimpleIns()
        val ghost = NaiveGhostEstimator()
        var i = 0

        // Long still with a realistic accel bias. COAST ZUPT zeros speed; ghost
        // double-integrates so position/speed run away before any yaw.
        repeat(600) {
            val f = frame(i++, ax = 0.06)
            ins.onImu(f)
            ghost.onImu(f)
        }

        // Sustained yaw — ghost keeps the unbounded EN velocity; COAST stays
        // near a stop (or coasts with a different heading model).
        repeat(300) {
            val f = frame(i++, ax = 0.06, gz = 0.50)
            ins.onImu(f)
            ghost.onImu(f)
        }

        val separation = hypot(ghost.east - ins.east, ghost.north - ins.north)
        val coastHud = ins.snapshot(i.toLong() * dtNs, AppMode.NAVIGATE)

        assertTrue("ghost yaw ${ghost.yaw} should be clearly positive", ghost.yaw > 1.0)
        assertTrue(
            "ghost should have drifted far under bias (e=${ghost.east} n=${ghost.north})",
            hypot(ghost.east, ghost.north) > 2.0,
        )
        assertTrue(
            "ghost/COAST separation $separation m (coast e=${ins.east} n=${ins.north})",
            separation > 1.0,
        )
        // Honest: paths are not identical on the same IMU.
        assertTrue(
            "estimators should not share the same east",
            abs(ghost.east - coastHud.east) > 0.2 || abs(ghost.north - coastHud.north) > 0.2,
        )
    }

    @Test
    fun `still input with bias makes naive speed grow`() {
        val ghost = NaiveGhostEstimator()
        // Constant horizontal bias, phone otherwise still — physics, not a script.
        for (i in 0 until 1000) {
            ghost.onImu(frame(i, ax = 0.05))
        }
        assertTrue(
            "naive speed should grow under still+bias, was ${ghost.speedMps} m/s",
            ghost.speedMps > 0.3,
        )
        // After 10 s at 0.05 m/s², v ≈ 0.5 m/s (ideal). Allow some slack.
        assertTrue("speed ${ghost.speedMps} absurdly large for 10 s of 0.05 m/s²", ghost.speedMps < 2.0)
    }

    @Test
    fun `COAST ZUPT holds near zero while ghost speed grows on same still frames`() {
        val ins = SimpleIns()
        val ghost = NaiveGhostEstimator()
        // Tiny bias + gravity: enough for ghost to integrate, small enough that
        // ZUPT still classifies the phone as stopped (accel ≈ g).
        for (i in 0 until 800) {
            val f = frame(i, ax = 0.02)
            ins.onImu(f)
            ghost.onImu(f)
        }
        val coastHud = ins.snapshot(800L * dtNs, AppMode.NAVIGATE)
        assertTrue(
            "COAST speed should stay near zero with ZUPT, was ${coastHud.speedMps}",
            abs(coastHud.speedMps) < 0.15,
        )
        assertTrue(
            "ghost speed should grow on the same still frames, was ${ghost.speedMps}",
            ghost.speedMps > 0.1,
        )
    }
}
