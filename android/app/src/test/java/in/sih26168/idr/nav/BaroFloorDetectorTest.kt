package `in`.sih26168.idr.nav

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * B7 barometer floor-change detector. Synthetic pressure steps only —
 * no real multi-storey baro field log in-repo yet (data pending).
 */
class BaroFloorDetectorTest {

    private val ns = 100_000_000L // 10 Hz

    @Test
    fun `ignores missing pressure`() {
        val d = BaroFloorDetector()
        assertFalse(d.onPressure(0L, Double.NaN))
        assertFalse(d.onPressure(ns, 0.0))
        assertFalse(d.onPressure(2 * ns, -1.0))
        assertEquals(0, d.floorIndex)
        assertFalse(d.changedThisSession)
    }

    @Test
    fun `locks baseline without a false floor change`() {
        val d = BaroFloorDetector(stepHpa = 0.40, smoothAlpha = 1.0, holdNs = 200_000_000L)
        // Flat pressure for a few seconds.
        for (i in 0 until 50) {
            assertFalse(d.onPressure(i * ns, 1013.0))
        }
        assertEquals(0, d.floorIndex)
        assertFalse(d.changedThisSession)
        assertFalse(d.recentlyChanged(50 * ns))
    }

    @Test
    fun `sustained pressure drop increments floor index`() {
        val d = BaroFloorDetector(stepHpa = 0.40, smoothAlpha = 1.0, holdNs = 300_000_000L)
        // Lock at ground.
        for (i in 0 until 10) d.onPressure(i * ns, 1013.0)
        // Climb one storey (~0.5 hPa drop) and hold past confirm window.
        var accepted = false
        for (i in 10 until 40) {
            if (d.onPressure(i * ns, 1012.5)) accepted = true
        }
        assertTrue("expected a floor step on pressure drop", accepted)
        assertEquals(1, d.floorIndex)
        assertTrue(d.changedThisSession)
        assertTrue(d.recentlyChanged(40 * ns))
    }

    @Test
    fun `sustained pressure rise decrements floor index`() {
        val d = BaroFloorDetector(stepHpa = 0.40, smoothAlpha = 1.0, holdNs = 300_000_000L)
        for (i in 0 until 10) d.onPressure(i * ns, 1013.0)
        for (i in 10 until 40) d.onPressure(i * ns, 1012.5) // up one
        assertEquals(1, d.floorIndex)
        var accepted = false
        for (i in 40 until 70) {
            if (d.onPressure(i * ns, 1013.0)) accepted = true // back down
        }
        assertTrue(accepted)
        assertEquals(0, d.floorIndex)
    }

    @Test
    fun `brief spike does not count as a floor`() {
        val d = BaroFloorDetector(stepHpa = 0.40, smoothAlpha = 1.0, holdNs = 500_000_000L)
        for (i in 0 until 10) d.onPressure(i * ns, 1013.0)
        // One sample past threshold, then back — shorter than holdNs.
        assertFalse(d.onPressure(10 * ns, 1012.5))
        assertFalse(d.onPressure(11 * ns, 1013.0))
        assertEquals(0, d.floorIndex)
        assertFalse(d.changedThisSession)
    }
}
