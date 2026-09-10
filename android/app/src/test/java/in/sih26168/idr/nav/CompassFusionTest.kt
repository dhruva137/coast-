package `in`.sih26168.idr.nav

import `in`.sih26168.idr.data.AppMode
import `in`.sih26168.idr.data.GnssFix
import `in`.sih26168.idr.data.SensorFrame
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import kotlin.math.abs

/**
 * Onset-calibrated compass during GNSS outage — the heading policy measured in
 * `lab/stress/results/heading_fusion/summary.md` (16.87% → 7.22% heading-induced
 * drift). These tests check the phone estimator, not the map-in-loop headline.
 */
class CompassFusionTest {

    private val hz = 100
    private val dtNs = 1_000_000_000L / hz
    private val g = 9.80665

    private fun frame(
        i: Int,
        gz: Double,
        mx: Double = 0.0,
        my: Double = 30.0,
        mz: Double = -40.0,
        ax: Double = 0.0,
    ) = SensorFrame(
        tNs = i.toLong() * dtNs,
        ax = ax, ay = 0.0, az = g,
        gx = 0.0, gy = 0.0, gz = gz,
        mx = mx, my = my, mz = mz,
        pressureHpa = 1013.0, lux = 0.0,
    )

    private fun gnss(i: Int, bearing: Double, speed: Double = 8.0) = GnssFix(
        tNs = i.toLong() * dtNs,
        lat = 52.4,
        lon = -1.5,
        alt = 80.0,
        speed = speed,
        bearing = bearing,
        accH = 4.0,
        accV = 6.0,
        nSats = 10,
    )

    /** Mag + GNSS lock so the onset offset is captured, then GNSS dies. */
    private fun lockThenOutage(ins: SimpleIns, magOn: Boolean): Int {
        var i = 0
        repeat(20) {
            ins.onImu(frame(i++, gz = 0.0, my = if (magOn) 30.0 else 0.0, mz = if (magOn) -40.0 else 0.0))
        }
        ins.onGnss(gnss(i, bearing = 0.0))
        repeat(hz) {
            ins.onImu(
                frame(
                    i++,
                    gz = 0.0,
                    my = if (magOn) 30.0 else 0.0,
                    mz = if (magOn) -40.0 else 0.0,
                    ax = 0.4 + 0.5 * kotlin.math.sin(i * 0.37),
                ),
            )
            if (i % 20 == 0) ins.onGnss(gnss(i, bearing = 0.0))
        }
        // Wait out gnssTimeout (2 s) so the coast is actually an outage.
        repeat((2.5 * hz).toInt()) {
            ins.onImu(
                frame(
                    i++,
                    gz = 0.0,
                    my = if (magOn) 30.0 else 0.0,
                    mz = if (magOn) -40.0 else 0.0,
                    ax = 0.4 + 0.5 * kotlin.math.sin(i * 0.37),
                ),
            )
        }
        return i
    }

    @Test
    fun `zero mag does not pull heading — existing logs stay gyro-only`() {
        val ins = SimpleIns()
        ins.setFuseCompass(true)
        var i = lockThenOutage(ins, magOn = false)
        val gz = deg2rad(45.0)
        repeat(hz) { ins.onImu(frame(i++, gz = gz, my = 0.0, mz = 0.0, ax = 0.5)) }
        repeat(5 * hz) { ins.onImu(frame(i++, gz = 0.0, my = 0.0, mz = 0.0, ax = 0.5)) }
        val h = ins.snapshot(i.toLong() * dtNs, AppMode.NAVIGATE).headingDeg
        val err = abs(wrap180(h))
        assertTrue("heading $h should keep the gyro step, not snap to mag", err > 25.0)
        assertFalse(ins.snapshot(i.toLong() * dtNs, AppMode.NAVIGATE).compassFused)
    }

    @Test
    fun `onset-calibrated compass pulls heading back after a gyro step`() {
        val gyro = SimpleIns()
        gyro.setFuseCompass(false)
        val fused = SimpleIns()
        fused.setFuseCompass(true)
        val gz = deg2rad(45.0)

        fun coast(ins: SimpleIns, magOn: Boolean): Double {
            var i = lockThenOutage(ins, magOn)
            repeat(hz) {
                ins.onImu(
                    frame(
                        i++,
                        gz = gz,
                        my = if (magOn) 30.0 else 0.0,
                        mz = if (magOn) -40.0 else 0.0,
                        ax = 0.5,
                    ),
                )
            }
            // Gyro silent: complementary filter should bleed the step out (tau=6s).
            repeat(15 * hz) {
                ins.onImu(
                    frame(
                        i++,
                        gz = 0.0,
                        my = if (magOn) 30.0 else 0.0,
                        mz = if (magOn) -40.0 else 0.0,
                        ax = 0.4 + 0.5 * kotlin.math.sin(i * 0.37),
                    ),
                )
            }
            return ins.snapshot(i.toLong() * dtNs, AppMode.NAVIGATE).headingDeg
        }

        val hGyro = coast(gyro, magOn = true)
        val hFused = coast(fused, magOn = true)
        val eGyro = abs(wrap180(hGyro))
        val eFused = abs(wrap180(hFused))
        assertTrue("gyro-only heading was $hGyro (want the 45° step to remain)", eGyro > 25.0)
        assertTrue("fused heading $hFused should relax toward mag/GNSS 0 vs gyro $hGyro", eFused < 15.0)
        assertTrue("fused $eFused should beat gyro $eGyro", eFused < 0.5 * eGyro)
    }

    @Test
    fun `force hold zeros coast from accel`() {
        val moving = SimpleIns()
        val held = SimpleIns()
        held.setForceHold(true)
        repeat(5 * hz) { i ->
            val f = frame(i, gz = 0.0, mx = 0.0, my = 0.0, mz = 0.0, ax = 1.0)
            moving.onImu(f)
            held.onImu(f)
        }
        val t = (5L * hz) * dtNs
        val dMove = moving.snapshot(t, AppMode.NAVIGATE).distanceM
        val dHold = held.snapshot(t, AppMode.NAVIGATE).distanceM
        assertTrue("unheld distance was $dMove", dMove > 5.0)
        assertEquals(0.0, dHold, 0.05)
        assertTrue(held.snapshot(t, AppMode.NAVIGATE).forceHold)
    }
}
