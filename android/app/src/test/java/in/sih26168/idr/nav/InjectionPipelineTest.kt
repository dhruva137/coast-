package `in`.sih26168.idr.nav

import `in`.sih26168.idr.data.AppMode
import `in`.sih26168.idr.data.SensorFrame
import `in`.sih26168.idr.sensor.IoVnbdRow
import `in`.sih26168.idr.sensor.ReplaySensorSource
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import kotlin.math.abs

/**
 * P0-3 sensor-injection proof: a scripted [ReplaySensorSource] drives the real
 * [SimpleIns]. If these fail, the pipeline is not moving on input.
 */
class InjectionPipelineTest {

    private val hz = 100
    private val dtNs = 1_000_000_000L / hz

    private fun frame(
        i: Int,
        fwdAcc: Double,
        yawRate: Double = 0.0,
        axExtra: Double = 0.0,
    ) = SensorFrame(
        tNs = i.toLong() * dtNs,
        ax = fwdAcc + axExtra,
        ay = 0.0,
        az = 9.80665,
        gx = 0.0,
        gy = 0.0,
        gz = yawRate,
        mx = 0.0, my = 0.0, mz = 0.0,
        pressureHpa = 1013.0,
        lux = 0.0,
    )

    private fun scriptedRows(): List<IoVnbdRow> {
        // 3 s still → accelerate → left yaw → right yaw → stop. 100 Hz script
        // packed into IoVnbdRow so ReplaySensorSource is on the code path.
        val rows = ArrayList<IoVnbdRow>()
        var i = 0
        fun add(seconds: Double, fwdAcc: Double, yawRate: Double) {
            val n = (seconds * hz).toInt()
            repeat(n) {
                val f = frame(i++, fwdAcc, yawRate)
                rows += IoVnbdRow(tNs = f.tNs, frame = f, fix = null)
            }
        }
        add(3.0, 0.0, 0.0)       // still — ZUPT should hold
        add(2.0, 2.5, 0.0)       // accelerate forward
        add(3.0, 0.0, 0.0)       // coast straight
        add(2.0, 0.0, 0.40)      // steady left yaw (gz > 0 → heading increases)
        add(2.0, 0.0, 0.0)       // brief straight
        add(2.0, 0.0, -0.40)     // steady right yaw
        add(2.0, 0.0, 0.0)       // stop / settle
        return rows
    }

    @Test
    fun `injection moves estimate, yaw sign is correct, still has no drift, no NaN`() {
        val ins = SimpleIns()
        val source = ReplaySensorSource(rows = scriptedRows())
        var step = 0
        var eastAfterStill = 0.0
        var northAfterStill = 0.0
        var headingBeforeLeft = 0.0
        var headingAfterLeft = 0.0
        var headingAfterRight = 0.0
        var eastAfterAccel = 0.0
        var northAfterAccel = 0.0

        source.emitAllSync(
            onFrame = { f ->
                ins.onImu(f)
                step += 1
                val hud = ins.snapshot(f.tNs, AppMode.NAVIGATE)
                assertFalse("east NaN at step $step", hud.east.isNaN())
                assertFalse("north NaN at step $step", hud.north.isNaN())
                assertFalse("speed NaN at step $step", hud.speedMps.isNaN())
                assertFalse("heading NaN at step $step", hud.headingDeg.isNaN())

                // Boundaries at 100 Hz: still=300, accel=200, coast=300,
                // left=200, straight=200, right=200, stop=200.
                when (step) {
                    300 -> {
                        eastAfterStill = hud.east
                        northAfterStill = hud.north
                    }
                    800 -> {
                        eastAfterAccel = hud.east
                        northAfterAccel = hud.north
                        headingBeforeLeft = hud.headingDeg
                    }
                    1000 -> headingAfterLeft = hud.headingDeg
                    1400 -> headingAfterRight = hud.headingDeg
                }
            },
            onGnss = {},
        )

        // Still segment: near-zero displacement (ZUPT / no integration of noise).
        assertTrue(
            "still drift east=${eastAfterStill} north=${northAfterStill}",
            abs(eastAfterStill) < 0.5 && abs(northAfterStill) < 0.5,
        )

        // Forward motion produces displacement (estimate MOVES).
        val moved = kotlin.math.hypot(eastAfterAccel - eastAfterStill, northAfterAccel - northAfterStill)
        assertTrue("forward displacement was $moved m", moved > 2.0)

        // Left yaw (gz>0) increases compass heading in this convention
        // (compassDeg wraps; use smallest signed delta).
        val leftDelta = signedHeadingDelta(headingBeforeLeft, headingAfterLeft)
        assertTrue("left yaw delta was $leftDelta (want > 0)", leftDelta > 10.0)

        val rightDelta = signedHeadingDelta(headingAfterLeft, headingAfterRight)
        assertTrue("right yaw delta was $rightDelta (want < 0)", rightDelta < -10.0)
    }

    @Test
    fun `NaN IMU frames are ignored without poisoning state`() {
        val ins = SimpleIns()
        // Arm with a clean second of motion.
        for (i in 0 until 100) ins.onImu(frame(i, 1.5))
        val before = ins.snapshot(100L * dtNs, AppMode.NAVIGATE)
        // Inject garbage — must not move or NaN the HUD.
        ins.onImu(frame(100, 1.5).copy(ax = Double.NaN))
        ins.onImu(frame(101, 1.5).copy(gz = Double.POSITIVE_INFINITY))
        val after = ins.snapshot(101L * dtNs, AppMode.NAVIGATE)
        assertTrue(after.east.isFinite() && after.north.isFinite())
        assertEquals(before.east, after.east, 1e-9)
        assertEquals(before.north, after.north, 1e-9)
    }

    private fun signedHeadingDelta(fromDeg: Double, toDeg: Double): Double {
        var d = toDeg - fromDeg
        while (d > 180.0) d -= 360.0
        while (d < -180.0) d += 360.0
        return d
    }
}

/**
 * Scripted square path → near origin. Asserts closure is finite and in a sane
 * range — documents drift honestly, does not claim a fake small error.
 */
class LoopClosureTest {

    private val hz = 100
    private val dtNs = 1_000_000_000L / hz

    @Test
    fun `square path closes with finite bounded error`() {
        val ins = SimpleIns()
        var i = 0
        fun push(seconds: Double, fwdAcc: Double, yawRate: Double) {
            val n = (seconds * hz).toInt()
            repeat(n) {
                ins.onImu(
                    SensorFrame(
                        tNs = i++.toLong() * dtNs,
                        ax = fwdAcc, ay = 0.0, az = 9.80665,
                        gx = 0.0, gy = 0.0, gz = yawRate,
                        mx = 0.0, my = 0.0, mz = 0.0,
                        pressureHpa = 1013.0, lux = 0.0,
                    ),
                )
            }
        }

        // Build speed with accel above the 10.4 m/s² stationarity dead-band
        // (see RelativeModeTest), then four sides with 90° turns.
        push(2.5, 4.0, 0.0) // accelerate to ~10 m/s
        repeat(4) {
            // Slight positive ax keeps |a| out of the stationarity bleed.
            push(2.5, 0.6, 0.0)
            push(1.0, 0.6, Math.PI / 2) // 90° left over 1 s
        }
        push(2.0, -2.0, 0.0) // brake

        val hud = ins.snapshot(i.toLong() * dtNs, AppMode.NAVIGATE)
        val err = kotlin.math.hypot(hud.east, hud.north)
        assertTrue("closure not finite: $err", err.isFinite())
        // Honest bound: pure coasting DR on a synthetic square will drift.
        // We only require the error stays in a sane envelope (< path length).
        assertTrue("path length ${hud.distanceM}", hud.distanceM > 20.0)
        assertTrue(
            "closure $err m exceeds path ${hud.distanceM} m",
            err < hud.distanceM,
        )
        // Soft upper bound so a totally broken integrator fails loudly.
        assertTrue("closure $err m absurdly large", err < 500.0)
    }
}

class SanitizeGateTest {
    @Test
    fun `holds last good across NaN and Inf`() {
        val g = SanitizeGate(1.0)
        assertEquals(2.0, g.accept(2.0), 0.0)
        assertEquals(2.0, g.accept(Double.NaN), 0.0)
        assertEquals(2.0, g.accept(Double.POSITIVE_INFINITY), 0.0)
        assertEquals(-3.0, g.accept(-3.0), 0.0)
    }

    @Test
    fun `onnx load failure stays not-ready and never crashes onImu`() {
        val model = OnnxSpeedModel("forced test failure")
        assertFalse(model.ready)
        assertEquals("forced test failure", model.error)
        val f = SensorFrame(
            tNs = 1_000_000_000L,
            ax = 0.0, ay = 0.0, az = 9.8,
            gx = 0.0, gy = 0.0, gz = 0.0,
            mx = 0.0, my = 0.0, mz = 0.0,
            pressureHpa = 1013.0, lux = 0.0,
        )
        assertEquals(null, model.onImu(f))
        // Estimator still runs in FALLBACK when model is down.
        val ins = SimpleIns()
        ins.setModelStatus(model.ready, model.error, model.droppedWindows)
        for (i in 0 until 200) {
            ins.onImu(f.copy(tNs = (i + 1) * 10_000_000L, ax = 1.5))
        }
        val hud = ins.snapshot(2_000_000_000L, AppMode.NAVIGATE)
        assertTrue(hud.distanceM > 0.5)
        assertFalse(hud.modelReady)
        model.close()
    }
}
