package `in`.sih26168.idr.nav

import `in`.sih26168.idr.data.SensorFrame
import `in`.sih26168.idr.data.VehicleKind
import kotlin.math.abs
import kotlin.math.sin
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Walking dead reckoning must actually track a walk.
 *
 * This is the demo the whole pitch rests on: a judge holds the phone, we turn
 * location off, walk a loop, and come back to a marked floor tile. If the
 * distance is wrong the demo is worthless, so it is measured here rather than
 * assumed.
 *
 * Why a step detector at all, rather than the vehicle integrator: a gait is a
 * per-step oscillation whose MEAN forward acceleration is about zero. Integrate
 * it and you get noise, not speed. Counting footsteps and multiplying by a
 * step-length model is the standard pedestrian answer.
 */
class WalkingPdrTest {

    private val hz = 100
    private val dtNs = 1_000_000_000L / hz
    private val g = 9.80665

    private fun frame(
        t: Long,
        ax: Double = 0.0,
        ay: Double = 0.0,
        az: Double = 9.80665,
        gz: Double = 0.0,
    ) = SensorFrame(
        tNs = t, ax = ax, ay = ay, az = az, gx = 0.0, gy = 0.0, gz = gz,
        mx = 0.0, my = 0.0, mz = 0.0, pressureHpa = 1013.25, lux = 0.0,
    )

    /**
     * Synthesise a walking gait.
     *
     * Real walking puts a roughly sinusoidal oscillation on the accelerometer
     * magnitude at the step rate, with a peak-to-trough range of a few m/s^2.
     * `cadenceHz` steps per second at `amp` amplitude is what the detector's
     * peak-trough logic and the Weinberg length model both key off.
     */
    private fun walk(
        ins: SimpleIns,
        seconds: Double,
        t0: Long,
        cadenceHz: Double = 1.8,
        amp: Double = 2.2,
        gz: Double = 0.0,
    ): Long {
        var t = t0
        val n = (seconds * hz).toInt()
        repeat(n) { i ->
            val phase = 2.0 * Math.PI * cadenceHz * (i.toDouble() / hz)
            ins.onImu(frame(t, az = g + amp * sin(phase), gz = gz))
            t += dtNs
        }
        return t
    }

    private fun walking() = SimpleIns(profile = VehicleProfile.of(VehicleKind.walking))

    @Test
    fun `walking profile uses steps, vehicle profiles do not`() {
        assertTrue(
            "walking must count steps",
            VehicleProfile.of(VehicleKind.walking).usesSteps,
        )
        for (kind in listOf(
            VehicleKind.scooter,
            VehicleKind.car,
            VehicleKind.metro_rail,
            VehicleKind.bicycle,
        )) {
            assertTrue(
                "$kind must not use the pedestrian step model",
                !VehicleProfile.of(kind).usesSteps,
            )
        }
    }

    @Test
    fun `steps are detected at roughly the cadence walked`() {
        val ins = walking()
        val seconds = 10.0
        val cadence = 1.8
        walk(ins, seconds, 0L, cadenceHz = cadence)

        val expected = seconds * cadence // ~18 steps
        assertTrue(
            "expected roughly $expected steps, got ${ins.stepCount}",
            ins.stepCount >= (expected * 0.6).toLong() &&
                ins.stepCount <= (expected * 1.4).toLong(),
        )
    }

    @Test
    fun `distance over a straight walk is physically plausible`() {
        // 20 s at 1.8 steps/s is ~36 steps. At a 0.6-0.8 m stride that is
        // ~22-29 m. The assertion is deliberately a wide plausibility band, not
        // a tuned number: the point is that the estimate is in the right order
        // of magnitude, which the vehicle integrator is not for a gait.
        val ins = walking()
        walk(ins, 20.0, 0L)

        val d = ins.distanceM
        assertTrue(
            "20 s of walking should cover ~15-45 m, got $d m " +
                "(${ins.stepCount} steps, last stride ${ins.lastStepLengthM} m)",
            d in 15.0..45.0,
        )
    }

    @Test
    fun `the vehicle integrator would NOT track this walk`() {
        // The control that justifies the step detector existing. Same gait, fed
        // to a profile that integrates forward acceleration instead of counting
        // steps. Mean forward accel over a gait is ~0, so it should barely move
        // -- if this ever starts matching the walking result, the step model is
        // no longer earning its place.
        val vehicle = SimpleIns(profile = VehicleProfile.of(VehicleKind.other))
        walk(vehicle, 20.0, 0L)

        val walker = walking()
        walk(walker, 20.0, 0L)

        assertTrue(
            "step model (${walker.distanceM} m) should travel much further than " +
                "the vehicle integrator (${vehicle.distanceM} m) on a gait",
            walker.distanceM > vehicle.distanceM * 2.0,
        )
    }

    @Test
    fun `standing still produces no distance`() {
        val ins = walking()
        var t = 0L
        // Dead still: gravity only, no gait oscillation.
        repeat(1500) {
            ins.onImu(frame(t))
            t += dtNs
        }
        assertEquals("standing still must not count steps", 0L, ins.stepCount)
        assertTrue(
            "standing still must not accumulate distance, got ${ins.distanceM} m",
            ins.distanceM < 1.0,
        )
    }

    @Test
    fun `turning while walking changes heading`() {
        // The loop-closure demo needs heading to respond to a turn, otherwise
        // the track is a straight line no matter where the judge walks.
        val ins = walking()
        val turnRate = 0.35 // rad/s, a gentle continuous curve
        walk(ins, 6.0, 0L, gz = turnRate)

        val turned = abs(ins.yaw)
        assertTrue(
            "6 s at $turnRate rad/s should turn ~2 rad, got $turned",
            turned > 0.5,
        )
    }
}
