package `in`.sih26168.idr.nav

import kotlin.math.abs
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Unit tests for [SensorMath]. The goal is to catch the two calibration bugs
 * that shipped in an earlier build:
 *
 *   1. Compass needle rotating with the phone instead of against it
 *      (rotating right made "north" swing right, not left).
 *   2. Pitch and roll formulas that returned zero when the phone was
 *      actually tilted vertically.
 *
 * All values are chosen so a person can eyeball whether the number should
 * be positive, negative, or zero.
 */
class SensorMathTest {

    private val tolDeg = 0.5f
    private val tolPx = 0.01f

    // ----- Compass needle direction ------------------------------------------

    @Test
    fun `needle points up when heading is zero`() {
        val (x, y) = SensorMath.needleTip(headingDeg = 0f, radius = 100f)
        assertClose(0f, x, tolPx)
        assertClose(-100f, y, tolPx) // screen +y is DOWN, so up is negative
    }

    @Test
    fun `needle points left when phone points east`() {
        // Phone rotated so its top points east — true north is now to the left
        // of the screen. This is the bug the earlier build had backwards.
        val (x, y) = SensorMath.needleTip(headingDeg = 90f, radius = 100f)
        assertClose(-100f, x, tolPx)
        assertClose(0f, y, tolPx)
    }

    @Test
    fun `needle points down when phone points south`() {
        val (x, y) = SensorMath.needleTip(headingDeg = 180f, radius = 100f)
        assertClose(0f, x, tolPx)
        assertClose(100f, y, tolPx)
    }

    @Test
    fun `needle points right when phone points west`() {
        val (x, y) = SensorMath.needleTip(headingDeg = 270f, radius = 100f)
        assertClose(100f, x, tolPx)
        assertClose(0f, y, tolPx)
    }

    // ----- Short-way delta ----------------------------------------------------

    @Test
    fun `short way delta across wrap prefers the short side`() {
        // 350 → 10 is a +20 step through north, not a -340 sweep.
        assertClose(20f, SensorMath.shortWayDelta(350f, 10f), tolDeg)
        // 10 → 350 is a -20 step.
        assertClose(-20f, SensorMath.shortWayDelta(10f, 350f), tolDeg)
    }

    @Test
    fun `short way delta on already close values is the raw diff`() {
        assertClose(15f, SensorMath.shortWayDelta(20f, 35f), tolDeg)
        assertClose(-30f, SensorMath.shortWayDelta(90f, 60f), tolDeg)
    }

    // ----- Pitch from gravity -------------------------------------------------

    @Test
    fun `pitch is zero when phone lies face up`() {
        // Face-up flat: g = (0, 0, +9.8).
        val pitch = SensorMath.pitchFromGravity(0f, 0f, 9.8f)
        assertClose(0f, pitch, tolDeg)
    }

    @Test
    fun `pitch is plus 90 when phone stands upright`() {
        // Top of phone up: gravity aligns with -Y in phone frame.
        val pitch = SensorMath.pitchFromGravity(0f, -9.8f, 0f)
        assertClose(90f, pitch, tolDeg)
    }

    @Test
    fun `pitch is minus 90 when phone is nose down`() {
        // Bottom of phone up: gravity aligns with +Y in phone frame.
        val pitch = SensorMath.pitchFromGravity(0f, 9.8f, 0f)
        assertClose(-90f, pitch, tolDeg)
    }

    // ----- Roll from gravity --------------------------------------------------

    @Test
    fun `roll is zero when phone lies face up`() {
        val roll = SensorMath.rollFromGravity(0f, 0f, 9.8f)
        assertClose(0f, roll, tolDeg)
    }

    @Test
    fun `roll is positive when right edge is down`() {
        // Right-side down: gravity in phone frame = (+9.8, 0, 0).
        val roll = SensorMath.rollFromGravity(9.8f, 0f, 0f)
        assertClose(90f, roll, tolDeg)
    }

    @Test
    fun `roll is negative when left edge is down`() {
        val roll = SensorMath.rollFromGravity(-9.8f, 0f, 0f)
        assertClose(-90f, roll, tolDeg)
    }

    // ----- Cardinal naming ----------------------------------------------------

    @Test
    fun `cardinal names cover the eight sectors`() {
        assertEquals("north", SensorMath.cardinal(0f))
        assertEquals("north-east", SensorMath.cardinal(45f))
        assertEquals("east", SensorMath.cardinal(90f))
        assertEquals("south-east", SensorMath.cardinal(135f))
        assertEquals("south", SensorMath.cardinal(180f))
        assertEquals("south-west", SensorMath.cardinal(225f))
        assertEquals("west", SensorMath.cardinal(270f))
        assertEquals("north-west", SensorMath.cardinal(315f))
        // Wraps.
        assertEquals("north", SensorMath.cardinal(360f))
        assertEquals("north", SensorMath.cardinal(-1f))
    }

    // ----- Helpers ------------------------------------------------------------

    private fun assertClose(expected: Float, actual: Float, tol: Float) {
        assertTrue(
            "expected $expected ± $tol, got $actual",
            abs(actual - expected) <= tol,
        )
    }
}
