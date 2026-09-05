package `in`.sih26168.idr.nav

import `in`.sih26168.idr.data.SensorFrame
import `in`.sih26168.idr.data.VehicleKind
import kotlin.math.abs
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Zero-velocity updates must actually bound drift, not merely be present.
 *
 * The claim these tests exist to falsify: on a metro, where GNSS never arrives
 * and the train stops at every station, a confirmed stop lets the estimator
 * zero its velocity error and re-measure gyro bias, so heading error is bounded
 * by the interval between stations rather than by the length of the journey.
 *
 * That is a real claim about behaviour and it is cheap to check, so it is
 * checked rather than asserted in a slide.
 */
class ZuptTest {

    private val hz = 100
    private val dtNs = 1_000_000_000L / hz
    private val g = 9.80665

    /** Frames for a stationary phone: gravity on z, gyro at `bias`, small noise. */
    private fun still(
        ins: SimpleIns,
        seconds: Double,
        t0: Long,
        bias: Double,
        seed: Int = 1,
    ): Long {
        var t = t0
        val rnd = java.util.Random(seed.toLong())
        repeat((seconds * hz).toInt()) {
            ins.onImu(
                frame(
                    t,
                    ax = rnd.nextGaussian() * 0.01,
                    az = g + rnd.nextGaussian() * 0.01,
                    gz = bias + rnd.nextGaussian() * 0.0005,
                ),
            )
            t += dtNs
        }
        return t
    }

    /** Frames for straight-line travel at constant speed, same gyro bias. */
    private fun moving(
        ins: SimpleIns,
        seconds: Double,
        t0: Long,
        bias: Double,
        seed: Int = 2,
    ): Long {
        var t = t0
        val rnd = java.util.Random(seed.toLong())
        repeat((seconds * hz).toInt()) {
            // Vibration on the accel magnitude is what stops the stationary
            // detector from calling a moving train "stopped".
            ins.onImu(
                frame(
                    t,
                    ax = rnd.nextGaussian() * 0.5,
                    az = g + rnd.nextGaussian() * 0.5,
                    gz = bias + rnd.nextGaussian() * 0.02,
                ),
            )
            t += dtNs
        }
        return t
    }

    private fun frame(
        t: Long,
        ax: Double = 0.0,
        ay: Double = 0.0,
        az: Double = 9.80665,
        gx: Double = 0.0,
        gy: Double = 0.0,
        gz: Double = 0.0,
    ) = SensorFrame(
        tNs = t, ax = ax, ay = ay, az = az, gx = gx, gy = gy, gz = gz,
        mx = 0.0, my = 0.0, mz = 0.0, pressureHpa = 1013.25, lux = 0.0,
    )

    private fun metro() = SimpleIns(profile = VehicleProfile.of(VehicleKind.metro_rail))

    @Test
    fun `a sustained stop is detected`() {
        val ins = metro()
        var t = moving(ins, 3.0, 0L, bias = 0.0)
        t = still(ins, 12.0, t, bias = 0.0)
        assertTrue("12 s of stillness should register as a stop", ins.stationary)
        assertTrue("a confirmed stop should produce an update", ins.zuptCount > 0)
    }

    @Test
    fun `motion is not mistaken for a stop`() {
        val ins = metro()
        moving(ins, 20.0, 0L, bias = 0.0)
        assertTrue("a moving vehicle must never be called stopped", !ins.stationary)
        assertEquals("no ZUPT may fire while moving", 0L, ins.zuptCount)
    }

    @Test
    fun `a stop is not declared before the dwell threshold`() {
        val ins = metro()
        val t = moving(ins, 3.0, 0L, bias = 0.0)
        // Well under any sane confirmation window.
        still(ins, 0.4, t, bias = 0.0)
        assertEquals(
            "a momentary quiet patch must not zero a real velocity",
            0L,
            ins.zuptCount,
        )
    }

    @Test
    fun `a stop re-estimates gyro bias and the estimate is applied`() {
        // What this DOES test: the mechanism. A stationary window has a known
        // true rate of zero, so the measured mean is bias; the estimator must
        // capture it and subtract it from subsequent samples.
        //
        // What this does NOT test, deliberately: that ZUPT reduces end-to-end
        // drift on a real journey. An earlier version of this file asserted
        // that and the assertion was wrong -- not because the feature failed,
        // but because the synthetic generator here never actually accelerates
        // the vehicle (total distance came out at metres over simulated
        // minutes), so there was no journey to drift over. Rather than tune the
        // threshold until it passed, the claim is left unproven.
        //
        // It is measurable on the real metro ride: same line, same stations,
        // metro profile versus `other`, compare closure error. Until that is
        // done, the app must not advertise a drift-reduction figure.
        val bias = 0.01 // rad/s, ~0.57 deg/s, plausible for a phone gyro
        val ins = metro()
        var t = moving(ins, 3.0, 0L, bias)
        t = still(ins, 15.0, t, bias)

        assertTrue("a stop should have been confirmed", ins.zuptCount > 0)

        // After the stop, feed the same biased gyro while moving and confirm
        // the integrated heading advances more slowly than the raw bias would.
        val yawAtStop = ins.yaw
        moving(ins, 10.0, t, bias)
        val advanced = abs(ins.yaw - yawAtStop)
        val uncorrected = bias * 10.0 // what 10 s of raw bias would integrate to
        assertTrue(
            "bias correction must reduce post-stop heading advance: " +
                "advanced=$advanced uncorrected=$uncorrected",
            advanced < uncorrected,
        )
    }

    @Test
    fun `velocity is zeroed by a confirmed stop`() {
        val ins = metro()
        // Drive the fallback integrator up to a non-zero speed, then stop.
        var t = 0L
        repeat(200) {
            ins.onImu(frame(t, ax = 1.0, az = g))
            t += dtNs
        }
        assertTrue("setup should have produced real speed", ins.speed > 0.5)
        still(ins, 12.0, t, bias = 0.0)
        assertTrue(
            "a confirmed stop must zero velocity, got ${ins.speed}",
            ins.speed < 0.05,
        )
    }

    @Test
    fun `non-leaning profiles do not run the lean solver`() {
        // Regression guard for the bug where `leans` was derived as
        // `v != VehicleKind.car`, which silently marked metro, train, bus and
        // walking as leaning the moment the enum grew past four values.
        for (kind in listOf(
            VehicleKind.metro_rail,
            VehicleKind.train,
            VehicleKind.bus,
            VehicleKind.car,
            VehicleKind.walking,
        )) {
            assertTrue(
                "$kind must not be treated as a leaning vehicle",
                !VehicleProfile.of(kind).leans,
            )
        }
        for (kind in listOf(
            VehicleKind.scooter,
            VehicleKind.motorcycle,
            VehicleKind.bicycle,
        )) {
            assertTrue(
                "$kind leans and must keep the coordinated-turn solver",
                VehicleProfile.of(kind).leans,
            )
        }
    }
}
