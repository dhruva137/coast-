package `in`.sih26168.idr.nav

import `in`.sih26168.idr.data.AppMode
import `in`.sih26168.idr.data.GnssFix
import `in`.sih26168.idr.data.SensorFrame
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertSame
import org.junit.Assert.assertTrue
import org.junit.Test
import kotlin.math.sqrt

/**
 * Regression guards for the map-performance fix.
 *
 * The estimator used to append one trail point per IMU sample. `SensorHub` runs
 * at `SENSOR_DELAY_FASTEST`, so that is 200-500 points a second, and the map
 * rebuilt a `Path` from all of them on every animation frame. Worse, the old
 * 4000-point cap then meant the visible track was only the last few seconds of
 * the ride -- the rest had already been dropped off the front of the deque.
 *
 * These tests pin the two properties that fix depends on:
 *
 *  1. Points are retained by DISTANCE, not by sample count, so the drawn line is
 *     geometrically the same but two orders of magnitude cheaper.
 *  2. [SimpleIns.trackSnapshot] returns the SAME instance until a point is
 *     actually appended, so the map's `remember(track.version)` cache holds and
 *     nothing is copied on a HUD frame that added nothing.
 */
class TrailDecimationTest {

    private val hz = 100
    private val dtNs = 1_000_000_000L / hz

    private fun frame(i: Int, fwdAcc: Double) = SensorFrame(
        tNs = i.toLong() * dtNs,
        ax = fwdAcc, ay = 0.0, az = 9.80665,
        gx = 0.0, gy = 0.0, gz = 0.0,
        mx = 0.0, my = 0.0, mz = 0.0,
        pressureHpa = 1013.0, lux = 0.0,
    )

    private fun run(ins: SimpleIns, seconds: Double, fwdAcc: Double, from: Int = 0): Int {
        val n = (seconds * hz).toInt()
        for (i in 0 until n) ins.onImu(frame(from + i, fwdAcc))
        return from + n
    }

    @Test
    fun `the trail keeps far fewer points than there were IMU samples`() {
        val ins = SimpleIns()
        // 10 s at 100 Hz = 1000 samples. The old code kept all 1000.
        val i = run(ins, seconds = 10.0, fwdAcc = 1.5)
        val pts = ins.trackSnapshot().ins

        assertTrue("something must be tracked", pts.size >= 2)
        assertTrue(
            "kept ${pts.size} of $i samples -- decimation is not working",
            pts.size < i / 10,
        )
    }

    @Test
    fun `every retained pair earns its slot by distance or by time`() {
        val ins = SimpleIns(trailMinStepM = 2.0, trailMinStepNs = 1_000_000_000L)
        run(ins, seconds = 12.0, fwdAcc = 1.5)
        val pts = ins.trackSnapshot().ins

        assertTrue("expected a real track, got ${pts.size} points", pts.size > 5)
        for (k in 1 until pts.size) {
            val de = pts[k].east - pts[k - 1].east
            val dn = pts[k].north - pts[k - 1].north
            val d = sqrt(de * de + dn * dn)
            val dtSec = (pts[k].tNs - pts[k - 1].tNs) / 1e9
            assertTrue(
                "pair $k is %.3f m and %.3f s from the last -- neither rule justifies it"
                    .format(d, dtSec),
                d >= 1.9 || dtSec >= 0.95,
            )
        }
    }

    @Test
    fun `decimation does not distort the distance the track spans`() {
        val ins = SimpleIns()
        val i = run(ins, seconds = 10.0, fwdAcc = 1.5)
        val hud = ins.snapshot(i.toLong() * dtNs, AppMode.NAVIGATE)
        val pts = ins.trackSnapshot().ins

        // The last retained point must be within one decimation step of where
        // the estimator says it actually is.
        val last = pts.last()
        val de = last.east - hud.east
        val dn = last.north - hud.north
        assertTrue(
            "track end lags the estimator by %.2f m".format(sqrt(de * de + dn * dn)),
            sqrt(de * de + dn * dn) <= 2.5,
        )
    }

    @Test
    fun `a stationary phone still records a point on the time rule`() {
        val ins = SimpleIns()
        // No acceleration at all: displacement never reaches the 2 m step.
        run(ins, seconds = 6.0, fwdAcc = 0.0)
        val pts = ins.trackSnapshot().ins
        assertTrue("expected a few heartbeat points, got ${pts.size}", pts.size in 2..12)
    }

    @Test
    fun `the trail is capped so a long ride cannot grow without bound`() {
        val ins = SimpleIns(trailCap = 40, trailMinStepM = 0.5)
        run(ins, seconds = 30.0, fwdAcc = 2.0)
        assertTrue(ins.trackSnapshot().ins.size <= 40)
    }

    @Test
    fun `trackSnapshot returns the same instance until a point is added`() {
        val ins = SimpleIns()
        val i = run(ins, seconds = 3.0, fwdAcc = 1.5)
        val a = ins.trackSnapshot()
        val b = ins.trackSnapshot()
        // Same object: the map's remember(version) cache must survive a HUD
        // frame that appended nothing.
        assertSame(a, b)

        // A HUD snapshot must not invalidate it either -- it used to toList()
        // both deques every time.
        ins.snapshot(i.toLong() * dtNs, AppMode.NAVIGATE)
        assertSame(a, ins.trackSnapshot())

        run(ins, seconds = 3.0, fwdAcc = 1.5, from = i)
        val c = ins.trackSnapshot()
        assertNotEquals(a.version, c.version)
    }

    @Test
    fun `the snapshot carries a bounding box that matches its points`() {
        val ins = SimpleIns()
        run(ins, seconds = 8.0, fwdAcc = 1.5)
        val t = ins.trackSnapshot()

        // The camera reads these instead of rescanning the track every frame,
        // so they have to agree with it. The box always contains the origin,
        // which is drawn as the crosshair marker.
        assertEquals(minOf(0.0, t.ins.minOf { it.east }), t.minEast, 1e-9)
        assertEquals(maxOf(0.0, t.ins.maxOf { it.east }), t.maxEast, 1e-9)
        assertEquals(minOf(0.0, t.ins.minOf { it.north }), t.minNorth, 1e-9)
        assertEquals(maxOf(0.0, t.ins.maxOf { it.north }), t.maxNorth, 1e-9)
    }

    @Test
    fun `a GNSS fix is never decimated away`() {
        val ins = SimpleIns()
        val i = run(ins, seconds = 2.0, fwdAcc = 1.5)
        val before = ins.trackSnapshot().ins.size
        ins.onGnss(
            GnssFix(
                tNs = i.toLong() * dtNs,
                lat = 12.9716, lon = 77.5946, alt = 900.0,
                speed = 8.0, bearing = 0.0, accH = 5.0, accV = 8.0, nSats = 9,
            ),
        )
        val after = ins.trackSnapshot()
        assertEquals(before + 1, after.ins.size)
        assertEquals(1, after.gnss.size)
        assertTrue(after.ins.last().fromGnss)
    }

    @Test
    fun `reset clears the track and bumps the version`() {
        val ins = SimpleIns()
        run(ins, seconds = 4.0, fwdAcc = 1.5)
        val before = ins.trackSnapshot()
        assertTrue(before.ins.isNotEmpty())

        ins.reset()
        val after = ins.trackSnapshot()
        assertTrue(after.ins.isEmpty())
        assertTrue(after.gnss.isEmpty())
        assertNotEquals(before.version, after.version)
        assertEquals(0.0, after.minEast, 1e-9)
        assertEquals(0.0, after.maxNorth, 1e-9)
    }
}
