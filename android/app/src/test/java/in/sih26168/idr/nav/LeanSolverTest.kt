package `in`.sih26168.idr.nav

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import kotlin.math.abs
import kotlin.math.cos
import kotlin.math.sin
import kotlin.math.tan

class LeanSolverTest {
    @Test
    fun recoversCoordinatedTurnLean() {
        val v = 12.0
        val phiTrue = 25.0 * Math.PI / 180.0
        val psiDot = (G * tan(phiTrue)) / v
        val gy = psiDot * sin(phiTrue)
        val gz = psiDot * cos(phiTrue)
        val sol = solveLean(LeanObservation(gy = gy, gz = gz, speed = v, phi0 = 0.0))
        assertTrue("residual ${sol.residual}", sol.residual < 1e-6)
        assertTrue("phi ${sol.phi} vs $phiTrue", abs(sol.phi - phiTrue) < 1e-6)
        assertTrue(sol.iterations <= 8)
    }

    @Test
    fun scaleErrorIsCosDeltaPhiNotCosPhi() {
        val dphi = 10.0 * Math.PI / 180.0
        val s = headingRateScaleError(dphi)
        assertEquals(cos(dphi), s, 1e-15)
        val car = cos(40.0 * Math.PI / 180.0)
        assertTrue("10° lean error → ~1.5%", abs(1.0 - s) < 0.02)
        assertTrue("car-style at 40° lean is >22%", 1.0 - car > 0.22)
    }

    @Test
    fun carStyleYawIsGz() {
        val phi = 0.4
        val psiDot = 0.5
        val gy = psiDot * sin(phi)
        val gz = psiDot * cos(phi)
        assertEquals(gz, carStyleYawRate(gz), 0.0)
        assertEquals(psiDot, yawRateFromLean(gy, gz, phi), 1e-12)
    }
}
