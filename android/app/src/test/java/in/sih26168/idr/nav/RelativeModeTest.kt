package `in`.sih26168.idr.nav

import `in`.sih26168.idr.data.AppMode
import `in`.sih26168.idr.data.GnssFix
import `in`.sih26168.idr.data.LocationStatus
import `in`.sih26168.idr.data.NavMode
import `in`.sih26168.idr.data.OriginSource
import `in`.sih26168.idr.data.SensorFrame
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import kotlin.math.abs

/**
 * The behaviour the problem statement is actually about: what happens with no
 * GNSS at all, and what happens when a fix arrives and then goes away.
 *
 * These are pure-JVM tests of [SimpleIns]; no Android framework is involved.
 */
class RelativeModeTest {

    private val hz = 100
    private val dtNs = 1_000_000_000L / hz

    /**
     * Straight, level, forward acceleration; the phone is upright and square.
     *
     * [fwdAcc] is deliberately large in the coasting tests. The fallback speed
     * integrator applies a stationarity decay whenever the total specific force
     * is under 10.4 m/s2 and the yaw rate is near zero, so a gentle synthetic
     * push sits inside that dead band and is bled away. A real launch does not.
     */
    private fun frame(i: Int, fwdAcc: Double, yawRate: Double = 0.0) = SensorFrame(
        tNs = i.toLong() * dtNs,
        // Raw device axes are used when no mount is calibrated: ax is forward.
        ax = fwdAcc, ay = 0.0, az = 9.80665,
        gx = 0.0, gy = 0.0, gz = yawRate,
        mx = 0.0, my = 0.0, mz = 0.0,
        pressureHpa = 1013.0, lux = 0.0,
    )

    private fun run(ins: SimpleIns, seconds: Double, fwdAcc: Double, from: Int = 0): Int {
        val n = (seconds * hz).toInt()
        for (i in 0 until n) ins.onImu(frame(from + i, fwdAcc))
        return from + n
    }

    // ---- No location at all ------------------------------------------------

    @Test
    fun `with no fix ever the estimator still moves and reports RELATIVE`() {
        val ins = SimpleIns()
        ins.setLocationStatus(LocationStatus.PERMISSION_DENIED)
        val i = run(ins, seconds = 5.0, fwdAcc = 1.0)
        val hud = ins.snapshot(i.toLong() * dtNs, AppMode.NAVIGATE)

        assertEquals(NavMode.RELATIVE, hud.navMode)
        assertEquals(OriginSource.NONE, hud.originSource)
        assertFalse(hud.hasAbsolutePosition)
        // The icon must NOT be frozen: real displacement was integrated.
        assertTrue("distance was ${hud.distanceM}", hud.distanceM > 5.0)
        assertTrue("north was ${hud.north}", abs(hud.north) > 5.0)
    }

    @Test
    fun `relative mode never fabricates a latitude or longitude`() {
        val ins = SimpleIns()
        val i = run(ins, seconds = 3.0, fwdAcc = 1.0)
        val hud = ins.snapshot(i.toLong() * dtNs, AppMode.NAVIGATE)
        assertTrue("lat should be NaN, was ${hud.lat}", hud.lat.isNaN())
        assertTrue("lon should be NaN, was ${hud.lon}", hud.lon.isNaN())
        ins.trackSnapshot().ins.forEach {
            assertTrue("trail point leaked a coordinate", it.lat.isNaN() && it.lon.isNaN())
        }
    }

    @Test
    fun `relative mode does not claim a north reference`() {
        val ins = SimpleIns()
        val i = run(ins, seconds = 2.0, fwdAcc = 1.0)
        val hud = ins.snapshot(i.toLong() * dtNs, AppMode.NAVIGATE)
        // Heading is the angle turned since arming, not a compass bearing.
        assertFalse(hud.headingReferenced)
    }

    @Test
    fun `relative uncertainty grows with distance and says it is modelled`() {
        val ins = SimpleIns()
        val a = run(ins, seconds = 3.0, fwdAcc = 1.0)
        val early = ins.snapshot(a.toLong() * dtNs, AppMode.NAVIGATE)
        val b = run(ins, seconds = 6.0, fwdAcc = 1.0, from = a)
        val late = ins.snapshot(b.toLong() * dtNs, AppMode.NAVIGATE)

        assertTrue(early.uncertaintyM.isFinite())
        assertTrue("must grow", late.uncertaintyM > early.uncertaintyM)
        assertEquals(SimpleIns.DEFAULT_DRIFT_RATE, late.driftRateUsed, 1e-9)
        assertFalse("not measured until a loop closes", late.driftRateMeasured)
        assertTrue(late.uncertaintyBasis.contains("relative displacement only"))
    }

    // ---- User-supplied start point ----------------------------------------

    @Test
    fun `a hand-set start point anchors the track without claiming its own accuracy`() {
        val ins = SimpleIns()
        var i = run(ins, seconds = 4.0, fwdAcc = 1.0)
        ins.setUserOrigin(12.9716, 77.5946, OriginSource.USER_COORDS)
        i = run(ins, seconds = 1.0, fwdAcc = 0.0, from = i)
        val hud = ins.snapshot(i.toLong() * dtNs, AppMode.NAVIGATE)

        assertEquals(NavMode.DEAD_RECKONING, hud.navMode)
        assertEquals(OriginSource.USER_COORDS, hud.originSource)
        assertTrue(hud.hasAbsolutePosition)
        assertTrue(hud.lat.isFinite() && hud.lon.isFinite())
        // Moving north of the anchor must increase latitude.
        assertTrue("lat ${hud.lat} should be north of the anchor", hud.lat > 12.9716)
        // The error of the anchor itself is explicitly excluded.
        assertTrue(hud.uncertaintyBasis.contains("NOT included"))
    }

    @Test
    fun `a rejected coordinate leaves the estimator in relative mode`() {
        val ins = SimpleIns()
        val i = run(ins, seconds = 2.0, fwdAcc = 1.0)
        ins.setUserOrigin(999.0, 77.0, OriginSource.USER_COORDS)
        ins.setUserOrigin(Double.NaN, 77.0, OriginSource.USER_COORDS)
        val hud = ins.snapshot(i.toLong() * dtNs, AppMode.NAVIGATE)
        assertEquals(NavMode.RELATIVE, hud.navMode)
    }

    @Test
    fun `clearing a hand-set start point returns to relative`() {
        val ins = SimpleIns()
        val i = run(ins, seconds = 2.0, fwdAcc = 1.0)
        ins.setUserOrigin(12.0, 77.0, OriginSource.USER_COORDS)
        ins.clearUserOrigin()
        val hud = ins.snapshot(i.toLong() * dtNs, AppMode.NAVIGATE)
        assertEquals(NavMode.RELATIVE, hud.navMode)
        assertTrue(hud.lat.isNaN())
    }

    // ---- Fix acquired, then lost ------------------------------------------

    private fun fix(i: Int, lat: Double, lon: Double, acc: Double = 5.0, speed: Double = 8.0) =
        GnssFix(
            tNs = i.toLong() * dtNs,
            lat = lat, lon = lon, alt = 900.0,
            speed = speed, bearing = 0.0,
            accH = acc, accV = 8.0, nSats = 9,
        )

    @Test
    fun `a fix upgrades a relative session to absolute in place`() {
        val ins = SimpleIns()
        var i = run(ins, seconds = 3.0, fwdAcc = 1.0)
        assertEquals(NavMode.RELATIVE, ins.snapshot(i.toLong() * dtNs, AppMode.NAVIGATE).navMode)

        ins.onGnss(fix(i, 12.9716, 77.5946))
        val hud = ins.snapshot(i.toLong() * dtNs, AppMode.NAVIGATE)
        assertEquals(NavMode.GNSS, hud.navMode)
        assertEquals(OriginSource.GNSS_FIX, hud.originSource)
        // The OS accuracy is used verbatim, and it is labelled as measured.
        assertEquals(5.0, hud.uncertaintyM, 1e-9)
        assertTrue(hud.uncertaintyBasis.contains("reported by the OS"))
        // A bearing at speed is what ties heading to north.
        assertTrue(hud.headingReferenced)
        i = i
    }

    @Test
    fun `losing the fix switches to dead reckoning and keeps moving`() {
        val ins = SimpleIns()
        var i = run(ins, seconds = 1.0, fwdAcc = 4.0)
        ins.onGnss(fix(i, 12.9716, 77.5946, acc = 4.0))
        val locked = ins.snapshot(i.toLong() * dtNs, AppMode.NAVIGATE)
        assertEquals(NavMode.GNSS, locked.navMode)

        // Feed IMU for well past the 2 s GNSS staleness timeout, with no fixes.
        i = run(ins, seconds = 8.0, fwdAcc = 4.0, from = i)
        val coasting = ins.snapshot(i.toLong() * dtNs, AppMode.NAVIGATE)

        assertEquals(NavMode.DEAD_RECKONING, coasting.navMode)
        assertEquals(LocationStatus.LOST, coasting.locationStatus)
        assertTrue("still absolute", coasting.hasAbsolutePosition)
        assertTrue("position must keep advancing", coasting.distanceSinceFixM > 5.0)
        // Error model: last fix accuracy plus growth. Strictly bigger than the fix.
        assertTrue(coasting.uncertaintyM > 4.0)
        assertEquals(
            4.0 + SimpleIns.DEFAULT_DRIFT_RATE * coasting.distanceSinceFixM,
            coasting.uncertaintyM,
            1e-6,
        )
        assertTrue(coasting.uncertaintyBasis.contains("modelled"))
        // Outage is measured from when the fix went away, not from when a
        // snapshot first noticed, so a single call after a long coast is right.
        assertEquals(8.0, coasting.outageSec, 0.15)
    }

    @Test
    fun `re-acquiring a fix resets the accumulated error`() {
        val ins = SimpleIns()
        var i = run(ins, seconds = 1.0, fwdAcc = 4.0)
        ins.onGnss(fix(i, 12.9716, 77.5946, acc = 4.0))
        i = run(ins, seconds = 8.0, fwdAcc = 4.0, from = i)
        val coasting = ins.snapshot(i.toLong() * dtNs, AppMode.NAVIGATE)
        assertTrue(coasting.uncertaintyM > 10.0)

        ins.onGnss(fix(i, 12.9720, 77.5946, acc = 6.0))
        val reacquired = ins.snapshot(i.toLong() * dtNs, AppMode.NAVIGATE)
        assertEquals(NavMode.GNSS, reacquired.navMode)
        assertEquals(6.0, reacquired.uncertaintyM, 1e-9)
        assertEquals(0.0, reacquired.distanceSinceFixM, 1e-9)
    }

    @Test
    fun `a low-quality fix does not anchor the session`() {
        val ins = SimpleIns()
        val i = run(ins, seconds = 1.0, fwdAcc = 1.0)
        // 60 m accuracy is past the usability gate.
        ins.onGnss(fix(i, 12.9716, 77.5946, acc = 60.0))
        val hud = ins.snapshot(i.toLong() * dtNs, AppMode.NAVIGATE)
        assertEquals(NavMode.RELATIVE, hud.navMode)
        assertFalse(hud.hasAbsolutePosition)
    }

    // ---- Loop closure ------------------------------------------------------

    @Test
    fun `a closed loop replaces the modelled drift rate with a measured one`() {
        val ins = SimpleIns()
        var i = run(ins, seconds = 2.0, fwdAcc = 1.0)
        ins.mark()
        // Out and back: accelerate away, then reverse heading and return.
        i = run(ins, seconds = 4.0, fwdAcc = 0.5, from = i)
        val hud = ins.snapshot(i.toLong() * dtNs, AppMode.NAVIGATE)
        assertTrue(hud.loopMarked)

        ins.mark()
        val closed = ins.snapshot(i.toLong() * dtNs, AppMode.NAVIGATE)
        assertTrue("closure must be measured", closed.loopClosureM != null)
        assertTrue("drift must be measured", closed.driftPct != null)
        assertTrue(closed.driftRateMeasured)
        assertEquals(closed.driftPct!! / 100.0, closed.driftRateUsed, 1e-9)
    }

    @Test
    fun `the estimator reports IDLE when it is not armed`() {
        val ins = SimpleIns()
        val hud = ins.snapshot(0L, AppMode.IDLE)
        assertEquals(NavMode.IDLE, hud.navMode)
        assertTrue(hud.uncertaintyM.isNaN())
        assertTrue(hud.lat.isNaN())
    }
}
