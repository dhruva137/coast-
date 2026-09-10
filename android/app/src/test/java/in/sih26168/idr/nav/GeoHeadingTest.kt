package `in`.sih26168.idr.nav

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import kotlin.math.abs

class GeoHeadingTest {

    @Test
    fun `zeros are not a magnetic field`() {
        assertFalse(magFieldValid(0.0, 0.0, 0.0))
        assertFalse(magFieldValid(Double.NaN, 30.0, -40.0))
        assertTrue(magFieldValid(0.0, 30.0, -40.0))
    }

    @Test
    fun `device plus-y north reads heading 0`() {
        // Flat phone, gravity on +z (Android at rest). Mag north along +y.
        val h = tiltCompensatedHeadingDeg(
            ax = 0.0, ay = 0.0, az = 9.80665,
            mx = 0.0, my = 30.0, mz = -40.0,
        )
        assertTrue(h.isFinite())
        assertEquals(0.0, h, 1e-6)
    }

    @Test
    fun `device plus-y east reads heading 90`() {
        // Mag north along +x ⇒ device +y points east.
        val h = tiltCompensatedHeadingDeg(
            ax = 0.0, ay = 0.0, az = 9.80665,
            mx = 30.0, my = 0.0, mz = -40.0,
        )
        assertTrue(h.isFinite())
        val err = abs(wrap180(h - 90.0))
        assertTrue("heading was $h", err < 1e-4)
    }

    @Test
    fun `wrap180 stays in minus 180 to 180`() {
        assertEquals(0.0, wrap180(0.0), 1e-9)
        assertEquals(-10.0, wrap180(350.0), 1e-9)
        assertEquals(10.0, wrap180(-350.0), 1e-9)
    }
}
