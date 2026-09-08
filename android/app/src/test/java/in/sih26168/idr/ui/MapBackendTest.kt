package `in`.sih26168.idr.ui

import `in`.sih26168.idr.data.NavMode
import `in`.sih26168.idr.data.TrailPoint
import kotlin.math.abs
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The map layer's pure logic.
 *
 * Two rules here are demo-critical and are the reason these tests exist:
 *
 *  1. **Never show a blank grey Google tile.** Every condition that would
 *     produce an empty or misleading basemap has to fall back to the Canvas
 *     with a sentence the user can act on.
 *  2. **Never draw a georeferenced track we do not have.** In RELATIVE mode
 *     there is no anchor on the Earth, so putting the trace over real streets
 *     would show a route the vehicle was never on.
 */
class MapBackendTest {

    private fun choose(
        hasApiKey: Boolean = true,
        playServicesOk: Boolean = true,
        basemapWanted: Boolean = true,
        online: Boolean = true,
        tilesEverLoaded: Boolean = true,
        navMode: NavMode = NavMode.GNSS,
        hasAbsolutePosition: Boolean = true,
    ) = chooseMapBackend(
        hasApiKey, playServicesOk, basemapWanted, online,
        tilesEverLoaded, navMode, hasAbsolutePosition,
    )

    @Test
    fun `google is used when everything is available`() {
        val c = choose()
        assertEquals(MapBackend.GOOGLE, c.backend)
        assertNull("nothing to explain when the basemap works", c.reason)
    }

    @Test
    fun `no api key falls back to canvas with a reason`() {
        // The shipped default: this repo contains no key and never will.
        val c = choose(hasApiKey = false)
        assertEquals(MapBackend.CANVAS, c.backend)
        assertNotNull("the user must be told why", c.reason)
    }

    @Test
    fun `missing play services falls back`() {
        val c = choose(playServicesOk = false)
        assertEquals(MapBackend.CANVAS, c.backend)
        assertNotNull(c.reason)
    }

    @Test
    fun `relative mode never draws over a basemap`() {
        // No anchor on the Earth: a real-looking route on real streets it was
        // never on is worse than an honest grid.
        val c = choose(navMode = NavMode.RELATIVE)
        assertEquals(MapBackend.CANVAS, c.backend)
        assertNotNull(c.reason)

        val d = choose(hasAbsolutePosition = false)
        assertEquals(MapBackend.CANVAS, d.backend)
    }

    @Test
    fun `offline keeps the map once tiles have been cached`() {
        // The whole point of a tunnel demo: the map must survive losing the
        // radio, because that is the moment the demo is about.
        assertEquals(
            MapBackend.GOOGLE,
            choose(online = false, tilesEverLoaded = true).backend,
        )
        assertEquals(
            MapBackend.CANVAS,
            choose(online = false, tilesEverLoaded = false).backend,
        )
    }

    @Test
    fun `every fallback carries an explanation`() {
        val fallbacks = listOf(
            choose(hasApiKey = false),
            choose(playServicesOk = false),
            choose(basemapWanted = false),
            choose(navMode = NavMode.RELATIVE),
            choose(online = false, tilesEverLoaded = false),
        )
        for (c in fallbacks) {
            assertEquals(MapBackend.CANVAS, c.backend)
            assertTrue(
                "a fallback with no reason leaves the user guessing",
                !c.reason.isNullOrBlank(),
            )
        }
    }

    // ---- trail segmentation ------------------------------------------------

    private fun pt(tSec: Double, fromGnss: Boolean) = TrailPoint(
        east = tSec, north = 0.0, lat = Double.NaN, lon = Double.NaN,
        tNs = (tSec * 1e9).toLong(), fromGnss = fromGnss,
    )

    @Test
    fun `a trail that loses gnss splits into two runs`() {
        // This split IS the demo: a judge has to see where the fix died.
        val pts = listOf(
            pt(0.0, true), pt(1.0, true), pt(2.0, true),
            // fix stops here; 2 s hold then dead reckoning
            pt(3.0, false), pt(6.0, false), pt(9.0, false), pt(12.0, false),
        )
        val segs = segmentTrail(pts)
        assertTrue("expected at least two runs, got ${segs.size}", segs.size >= 2)
        assertTrue("first run should be GNSS", segs.first().gnss)
        assertTrue("last run should be dead reckoned", !segs.last().gnss)
    }

    @Test
    fun `runs share their boundary point so the line does not gap`() {
        val pts = listOf(
            pt(0.0, true), pt(1.0, true),
            pt(5.0, false), pt(6.0, false),
        )
        val segs = segmentTrail(pts)
        if (segs.size >= 2) {
            val endOfFirst = segs[0].points.last()
            val startOfSecond = segs[1].points.first()
            assertEquals(
                "a gap at the exact instant the story is about",
                endOfFirst.tNs,
                startOfSecond.tNs,
            )
        }
    }

    @Test
    fun `an all-gnss trail is one run`() {
        val pts = (0..5).map { pt(it.toDouble(), true) }
        val segs = segmentTrail(pts)
        assertEquals(1, segs.size)
        assertTrue(segs[0].gnss)
    }

    // ---- vehicle smoothing -------------------------------------------------

    @Test
    fun `the icon slides toward the estimate rather than stepping`() {
        val s = VehicleSmoother(tauSec = 0.25, teleportM = 30.0)
        s.step(0.1, 0.0, 0.0, 0.0) // first step snaps to establish position
        s.step(0.1, 10.0, 0.0, 0.0)
        assertTrue("should have moved", s.east > 0.0)
        assertTrue("should not have arrived in one 100 ms frame", s.east < 10.0)
    }

    @Test
    fun `a large correction snaps instead of sliding`() {
        // A GNSS re-acquisition after a long coast is a real discontinuity.
        // Sliding across it would draw a path the vehicle never took, for
        // seconds, exactly when a judge is watching.
        val s = VehicleSmoother(tauSec = 0.25, teleportM = 30.0)
        s.step(0.1, 0.0, 0.0, 0.0)
        s.step(0.1, 500.0, 0.0, 0.0)
        assertEquals(500.0, s.east, 1e-9)
        assertTrue("the jump must be reported, not hidden", s.lastStepWasJump)
    }

    @Test
    fun `smoothing is frame rate independent`() {
        // A fixed per-frame fraction moves at different speeds on 60 Hz and
        // 120 Hz displays, and phones are both.
        val slow = VehicleSmoother(tauSec = 0.25, teleportM = 1e9)
        val fast = VehicleSmoother(tauSec = 0.25, teleportM = 1e9)
        slow.step(0.1, 0.0, 0.0, 0.0)
        fast.step(0.1, 0.0, 0.0, 0.0)

        // One second of travel toward the same target, at 10 Hz vs 100 Hz.
        repeat(10) { slow.step(0.1, 100.0, 0.0, 0.0) }
        repeat(100) { fast.step(0.01, 100.0, 0.0, 0.0) }

        assertTrue(
            "10 Hz reached ${slow.east}, 100 Hz reached ${fast.east}",
            abs(slow.east - fast.east) < 2.0,
        )
    }

    @Test
    fun `bearing turns the short way round north`() {
        // 350 -> 10 degrees is a 20 degree right turn, not 340 the other way.
        val d = bearingDelta(350.0, 10.0)
        assertEquals(20.0, d, 1e-9)
        assertEquals(-20.0, bearingDelta(10.0, 350.0), 1e-9)

        val stepped = stepBearing(350.0, 10.0, 0.5)
        assertEquals(0.0, wrap360Deg(stepped), 1e-9)
    }

    @Test
    fun `camera follow breaks on a pan but not on a pinch`() {
        val mpp = metresPerPixel(zoom = 17.0, latDeg = 12.97) // Bengaluru
        // A pinch leaves the centre roughly where it was.
        assertTrue(!shouldBreakFollow(2.0, mpp, viewportMinPx = 1080))
        // A deliberate drag across a quarter of the screen hands over control.
        assertTrue(shouldBreakFollow(0.30 * 1080 * mpp, mpp, viewportMinPx = 1080))
    }

    @Test
    fun `uncertainty is only drawable when it is a sane number`() {
        assertTrue(uncertaintyDrawable(12.5))
        assertTrue(!uncertaintyDrawable(0.0))
        assertTrue(!uncertaintyDrawable(Double.NaN))
        assertTrue(!uncertaintyDrawable(Double.POSITIVE_INFINITY))
    }
}
