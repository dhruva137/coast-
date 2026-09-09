package `in`.sih26168.idr.nav

import `in`.sih26168.idr.data.AppMode
import `in`.sih26168.idr.data.SensorFrame
import org.junit.Assert.assertTrue
import org.junit.Test
import kotlin.math.abs

/**
 * ZUPT tabletop: on a pure still phone COAST holds ~0; ghost stays calm after
 * gravity LP (does not explode). Residual step growth is covered in
 * [NaiveGhostTest].
 */
class ZuptTabletopTest {

    private val hz = 100
    private val dtNs = 1_000_000_000L / hz
    private val g = 9.80665

    private fun frame(i: Int, ax: Double = 0.0) = SensorFrame(
        tNs = i.toLong() * dtNs,
        ax = ax, ay = 0.0, az = g,
        gx = 0.0, gy = 0.0, gz = 0.0,
        mx = 0.0, my = 0.0, mz = 0.0,
        pressureHpa = 1013.0, lux = 0.0,
    )

    @Test
    fun `pure still - COAST ZUPT holds zero and ghost stays calm`() {
        val ins = SimpleIns()
        val ghost = NaiveGhostEstimator()
        for (i in 0 until 1000) {
            val f = frame(i)
            ins.onImu(f)
            ghost.onImu(f)
        }
        val coast = ins.snapshot(1000L * dtNs, AppMode.NAVIGATE).speedMps
        assertTrue("COAST should hold near 0 with ZUPT, was $coast", abs(coast) < 0.15)
        assertTrue(
            "ghost on pure still must stay calm (gravity removed), was ${ghost.speedMps}",
            ghost.speedMps < 1.0,
        )
    }
}
