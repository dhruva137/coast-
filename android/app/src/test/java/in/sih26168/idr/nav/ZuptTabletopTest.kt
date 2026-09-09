package `in`.sih26168.idr.nav

import `in`.sih26168.idr.data.AppMode
import `in`.sih26168.idr.data.SensorFrame
import org.junit.Assert.assertTrue
import org.junit.Test
import kotlin.math.abs

/**
 * P1-2 ZUPT tabletop: still phone → naive speed grows from physics; COAST with
 * ZUPT holds near zero. [IdrBus] exposes `zuptTabletop`, `naiveGhostSpeedMps`,
 * and `coastSpeedMps` for the side-by-side UI (not constructed here — Robolectric
 * would be needed for `Build.*` in [IdrBus]'s default config).
 *
 * Expected live behaviour (not scripted): residual IMU bias integrates so the
 * naive readout may climb through roughly 5→15→40 km/h over tens of seconds
 * while COAST stays ~0.00 m/s. Exact numbers depend on the phone's bias.
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
    fun `still bias grows naive speed while COAST ZUPT holds near zero`() {
        val ins = SimpleIns()
        val ghost = NaiveGhostEstimator()
        // 0.03 m/s² residual — typical order for a still phone on a desk.
        for (i in 0 until 1200) {
            val f = frame(i, ax = 0.03)
            ins.onImu(f)
            ghost.onImu(f)
        }
        val coast = ins.snapshot(1200L * dtNs, AppMode.NAVIGATE).speedMps
        assertTrue("COAST should hold near 0 with ZUPT, was $coast", abs(coast) < 0.15)
        assertTrue(
            "naive speed should grow from still bias, was ${ghost.speedMps}",
            ghost.speedMps > 0.25,
        )
    }
}
