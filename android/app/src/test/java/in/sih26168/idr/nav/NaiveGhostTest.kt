package `in`.sih26168.idr.nav

import `in`.sih26168.idr.data.AppMode
import `in`.sih26168.idr.data.SensorFrame
import org.junit.Assert.assertTrue
import org.junit.Test
import kotlin.math.PI
import kotlin.math.abs
import kotlin.math.cos
import kotlin.math.hypot
import kotlin.math.sin

/**
 * Ghost car: gravity-removed naive DR must stay bounded on a still/tilted phone
 * and still diverge from COAST under sustained bias/yaw.
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
    fun `tilted still phone - ghost speed stays bounded after 10s`() {
        val ghost = NaiveGhostEstimator()
        // ~15° tilt: without gravity removal this dumps ~2.5 m/s² into ax and
        // explodes past hundreds of m/s in 10 s.
        val tilt = 15.0 * PI / 180.0
        val ax = g * sin(tilt)
        val az = g * cos(tilt)
        for (i in 0 until 1000) {
            ghost.onImu(frame(i, ax = ax, az = az))
        }
        assertTrue(
            "tilted-still ghost speed ${ghost.speedMps} m/s must stay < 8 (not explode)",
            ghost.speedMps < 8.0,
        )
        assertTrue(
            "displacement ${hypot(ghost.east, ghost.north)} m must stay finite/sane",
            hypot(ghost.east, ghost.north) < 200.0,
        )
    }

    @Test
    fun `still then yaw - ghost displaces differently from COAST`() {
        val ins = SimpleIns()
        val ghost = NaiveGhostEstimator()
        var i = 0

        // Warm up gravity LP on pure g, then apply a sudden horizontal step that
        // the LP has not fully absorbed — ghost integrates residual; COAST ZUPTs.
        repeat(200) {
            val f = frame(i++)
            ins.onImu(f)
            ghost.onImu(f)
        }
        repeat(400) {
            val f = frame(i++, ax = 0.8)
            ins.onImu(f)
            ghost.onImu(f)
        }
        repeat(300) {
            val f = frame(i++, ax = 0.8, gz = 0.50)
            ins.onImu(f)
            ghost.onImu(f)
        }

        val separation = hypot(ghost.east - ins.east, ghost.north - ins.north)
        assertTrue("ghost yaw ${ghost.yaw} should be clearly positive", ghost.yaw > 1.0)
        assertTrue(
            "ghost should have moved under residual accel (e=${ghost.east} n=${ghost.north})",
            hypot(ghost.east, ghost.north) > 1.0,
        )
        assertTrue(
            "ghost/COAST separation $separation m",
            separation > 0.5,
        )
    }

    @Test
    fun `sudden horizontal step makes naive speed grow while LP catches up`() {
        val ghost = NaiveGhostEstimator()
        for (i in 0 until 150) ghost.onImu(frame(i))
        for (i in 150 until 650) ghost.onImu(frame(i, ax = 0.4))
        assertTrue(
            "naive speed should grow under a step residual, was ${ghost.speedMps} m/s",
            ghost.speedMps > 0.15,
        )
        assertTrue(
            "speed ${ghost.speedMps} must stay bounded (not gravity-leak thousands)",
            ghost.speedMps < 30.0,
        )
    }

    @Test
    fun `COAST ZUPT holds near zero on still frames`() {
        val ins = SimpleIns()
        val ghost = NaiveGhostEstimator()
        for (i in 0 until 800) {
            val f = frame(i)
            ins.onImu(f)
            ghost.onImu(f)
        }
        val coastHud = ins.snapshot(800L * dtNs, AppMode.NAVIGATE)
        assertTrue(
            "COAST speed should stay near zero with ZUPT, was ${coastHud.speedMps}",
            abs(coastHud.speedMps) < 0.15,
        )
        // After gravity LP converges, pure still → ghost also calm (no explode).
        assertTrue(
            "ghost on pure still must stay calm, was ${ghost.speedMps}",
            ghost.speedMps < 1.0,
        )
    }
}
