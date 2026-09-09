package `in`.sih26168.idr.ui

import androidx.compose.runtime.Immutable
import `in`.sih26168.idr.data.NavMode
import `in`.sih26168.idr.data.TrailPoint
import `in`.sih26168.idr.nav.metersPerDeg
import kotlin.math.abs
import kotlin.math.cos
import kotlin.math.exp
import kotlin.math.sqrt

/**
 * Everything the map needs to decide and to draw itself, with no Android and no
 * Compose in it, so all of it is covered by plain JVM unit tests.
 *
 * The composables that use this live in [MapLibreDriveMap] (the OpenStreetMap
 * basemap) and [DriveMap] (the metre-grid Canvas that is still the fallback).
 */

/** Which map surface is on screen right now. */
enum class MapBackend {
    /**
     * MapLibre Native + an OpenStreetMap raster style, real tiles, the COAST
     * layer drawn on top. No API key, no billing account, no Play services --
     * OSM's public tile server needs none of that. See [MapLibreDriveMap].
     */
    OSM,

    /** The hand-drawn metre grid in [DriveMap]. Always works, needs nothing. */
    CANVAS,
}

@Immutable
data class MapChoice(
    val backend: MapBackend,
    /**
     * One honest line saying why there is no basemap, shown on the Canvas.
     * Null when [backend] is [MapBackend.OSM] -- there is nothing to explain.
     */
    val reason: String?,
)

/**
 * Pick the map surface.
 *
 * The rule this encodes: **never show a blank basemap.** Every condition below
 * produces a map that would be empty, broken or a lie, and each one falls back
 * to the Canvas with a sentence a stranger can act on.
 *
 * MapLibre + OpenStreetMap removed two of the old conditions outright: OSM's
 * tile server needs **no API key** (a fresh clone and CI draw a real map), and
 * MapLibre is a plain Android view, **not** a Play-services client, so a
 * de-Googled phone draws a real map too. What remains are the three reasons a
 * basemap genuinely cannot help:
 *
 *  1. The user asked for the grid.
 *  2. No absolute position. In [NavMode.RELATIVE] there is no anchor on the
 *     Earth at all, so the track cannot be georeferenced. Drawing it over a
 *     basemap would put a real-looking route on real streets it was never on.
 *  3. Offline, with nothing cached yet. Once tiles HAVE loaded, going offline
 *     keeps the map: MapLibre serves what it cached, which is the whole point
 *     of a tunnel demo.
 */
fun chooseMapBackend(
    basemapWanted: Boolean,
    online: Boolean,
    tilesEverLoaded: Boolean,
    navMode: NavMode,
    hasAbsolutePosition: Boolean,
): MapChoice = when {
    !basemapWanted ->
        MapChoice(MapBackend.CANVAS, "Basemap off — showing track only")

    navMode == NavMode.RELATIVE || !hasAbsolutePosition ->
        MapChoice(MapBackend.CANVAS, "No absolute position — showing displacement only")

    !online && !tilesEverLoaded ->
        MapChoice(MapBackend.CANVAS, "Offline, no tiles cached — showing track only")

    else -> MapChoice(MapBackend.OSM, null)
}

// ---------------------------------------------------------------------------
// Projection
// ---------------------------------------------------------------------------

/** A point on the Earth, in degrees. Kept out of `LatLng` so this file is pure. */
@Immutable
data class GeoPoint(val lat: Double, val lon: Double)

/**
 * Quantise a coordinate to ~1 cm.
 *
 * PERFORMANCE. The session origin is recovered from the HUD every frame (see
 * [originFrom]) and the arithmetic that recovers it is not bit-for-bit stable as
 * the vehicle moves -- the last couple of digits wobble. Those digits are the
 * `remember` key the projected polyline cache hangs off, so without this the map
 * would rebuild every polyline ten times a second. 1e-7 degrees is about 1.1 cm,
 * far below any error this app can claim, and the wobble is around 1e-13.
 */
fun quantiseDeg(d: Double): Double =
    if (!d.isFinite()) d else Math.round(d * 1e7) / 1e7

/**
 * Metres east/north of an origin, placed on the Earth. Mirrors the projection
 * `SimpleIns` uses for `lat`/`lon`, so the two cannot disagree.
 */
fun projectFromOrigin(originLat: Double, originLon: Double, east: Double, north: Double): GeoPoint {
    val mpd = metersPerDeg(originLat)
    return GeoPoint(originLat + north / mpd.mLat, originLon + east / mpd.mLon)
}

/**
 * Recover the session origin from a HUD frame.
 *
 * Every [TrailPoint] carries `lat`/`lon` already, but only the ones pushed AFTER
 * an origin existed -- points laid down in [NavMode.RELATIVE] before the user
 * set a start point are `NaN` forever. Projecting east/north through the CURRENT
 * origin instead means the whole track, including everything recorded before the
 * anchor arrived, lands on the map the moment there is somewhere to put it.
 *
 * Returns null when there is no absolute position, which is the caller's cue to
 * fall back to the Canvas.
 */
fun originFrom(lat: Double, lon: Double, east: Double, north: Double): GeoPoint? {
    if (!lat.isFinite() || !lon.isFinite()) return null
    if (!east.isFinite() || !north.isFinite()) return null
    // metersPerDeg is a function of the ORIGIN's latitude, which is what we are
    // solving for, so take one refinement step. The residual is micrometres.
    val first = lat - north / metersPerDeg(lat).mLat
    val refined = lat - north / metersPerDeg(first).mLat
    return GeoPoint(refined, lon - east / metersPerDeg(refined).mLon)
}

/**
 * Ground resolution of the Web Mercator tile pyramid OSM (and every slippy-map
 * basemap) uses, in metres per screen pixel. Used to turn "the user dragged the
 * map a long way" into a decision that is the same at every zoom.
 */
fun metresPerPixel(zoom: Double, latDeg: Double): Double =
    156_543.03392 * cos(latDeg * Math.PI / 180.0) / Math.pow(2.0, zoom)

/**
 * Should the camera stop following the vehicle?
 *
 * A pinch-zoom leaves the map centred on roughly what it was centred on, so
 * following continues -- fighting a user who only wanted a closer look is
 * obnoxious. A pan drags the centre away, and past a quarter of the shorter
 * screen edge we take that as "I am looking at something else" and hand control
 * over, with a RE-CENTRE button to take it back.
 */
fun shouldBreakFollow(
    offsetM: Double,
    metresPerPixel: Double,
    viewportMinPx: Int,
    fraction: Double = 0.25,
): Boolean {
    if (!offsetM.isFinite() || !metresPerPixel.isFinite()) return false
    if (viewportMinPx <= 0 || metresPerPixel <= 0.0) return false
    return offsetM > fraction * viewportMinPx * metresPerPixel
}

// ---------------------------------------------------------------------------
// GNSS / dead-reckoned segmentation
// ---------------------------------------------------------------------------

/**
 * A run of the track that was produced the same way.
 *
 * This is the single most important visual in the demo: a judge has to be able
 * to SEE the moment the fix died and the estimate carried on, without being told
 * where to look.
 */
@Immutable
data class TrackSegment(
    /** True while a live fix was anchoring the track. False = dead reckoned. */
    val gnss: Boolean,
    val points: List<TrailPoint>,
)

/**
 * Split a trail into GNSS-tracked and dead-reckoned runs.
 *
 * A point counts as GNSS-tracked when it either IS a fix, or a fix landed within
 * [gnssHoldNs] before it. That is deliberately the same 2 s staleness window
 * `SimpleIns.gnssLock` uses to decide [NavMode], so the colour of the line and
 * the badge at the top of the screen can never disagree -- a green line under a
 * DEAD RECKONING badge would be worse than no colour at all.
 *
 * Consecutive runs SHARE their boundary point, so the polylines join instead of
 * leaving a gap at the exact instant the story is about.
 */
fun segmentTrail(
    points: List<TrailPoint>,
    gnssHoldNs: Long = 2_000_000_000L,
): List<TrackSegment> {
    if (points.size < 2) return emptyList()

    val out = ArrayList<TrackSegment>(4)
    var lastFixNs = if (points[0].fromGnss) points[0].tNs else Long.MIN_VALUE
    var runStart = 0
    var runIsGnss = points[0].fromGnss

    for (i in 1 until points.size) {
        val p = points[i]
        val isGnss = p.fromGnss ||
            (lastFixNs != Long.MIN_VALUE && p.tNs - lastFixNs in 0..gnssHoldNs)
        if (p.fromGnss) lastFixNs = p.tNs
        if (isGnss != runIsGnss) {
            // Close the run ON this point so the next one starts from it.
            out.add(TrackSegment(runIsGnss, points.subList(runStart, i + 1)))
            runStart = i
            runIsGnss = isGnss
        }
    }
    if (points.size - runStart >= 2) {
        out.add(TrackSegment(runIsGnss, points.subList(runStart, points.size)))
    }
    return out
}

// ---------------------------------------------------------------------------
// Vehicle smoothing
// ---------------------------------------------------------------------------

/**
 * Renders the estimator's position smoothly without pretending it is smooth.
 *
 * The problem statement asks for "a smooth, uninterrupted vehicle icon". The
 * estimator publishes at 10 Hz and a GNSS re-acquisition moves the position by a
 * real, discontinuous jump. Two different things, and they must be drawn
 * differently:
 *
 *  * **Between updates** the icon slides, first-order, toward the newest
 *    estimate. At [tauSec] = 0.25 s it is 98% of the way there in 1 s, which is
 *    invisible as lag and removes every 10 Hz step.
 *  * **A jump bigger than [teleportM]** is not interpolated at all. That jump is
 *    a correction -- the fix came back and the coast was wrong by that much --
 *    and sliding the icon across it would draw a path the vehicle never took,
 *    for several seconds, right at the moment a judge is watching. It snaps, and
 *    [lastStepWasJump] says so.
 *
 * Everything is in metres east/north, the frame the estimator actually
 * integrates, and projected to lat/lon once per frame afterwards. Interpolating
 * degrees instead would distort near the poles and does not simplify anything.
 */
class VehicleSmoother(
    private val tauSec: Double = 0.25,
    private val teleportM: Double = 30.0,
) {
    var east: Double = 0.0
        private set
    var north: Double = 0.0
        private set

    /** Compass degrees, 0 = north, clockwise. Interpolated the short way round. */
    var bearingDeg: Double = 0.0
        private set

    var started: Boolean = false
        private set

    /** True when the last [step] snapped rather than slid. */
    var lastStepWasJump: Boolean = false
        private set

    fun reset() {
        east = 0.0
        north = 0.0
        bearingDeg = 0.0
        started = false
        lastStepWasJump = false
    }

    fun step(dtSec: Double, targetEast: Double, targetNorth: Double, targetBearingDeg: Double) {
        if (!targetEast.isFinite() || !targetNorth.isFinite()) return
        val bearing = if (targetBearingDeg.isFinite()) targetBearingDeg else bearingDeg

        val de = targetEast - east
        val dn = targetNorth - north
        if (!started || sqrt(de * de + dn * dn) > teleportM) {
            east = targetEast
            north = targetNorth
            bearingDeg = wrap360Deg(bearing)
            started = true
            lastStepWasJump = true
            return
        }

        lastStepWasJump = false
        val a = approachAlpha(dtSec, tauSec)
        east += de * a
        north += dn * a
        bearingDeg = stepBearing(bearingDeg, bearing, a)
    }
}

/**
 * Fraction of the remaining distance to cover in [dtSec], for an exponential
 * approach with time constant [tauSec]. Frame-rate independent on purpose: a
 * fixed per-frame fraction moves at a different speed on a 60 Hz and a 120 Hz
 * display, and phones are both.
 */
fun approachAlpha(dtSec: Double, tauSec: Double): Double = when {
    !dtSec.isFinite() || dtSec <= 0.0 -> 0.0
    tauSec <= 0.0 -> 1.0
    else -> (1.0 - exp(-dtSec / tauSec)).coerceIn(0.0, 1.0)
}

fun wrap360Deg(d: Double): Double = ((d % 360.0) + 360.0) % 360.0

/** Signed difference from [from] to [to], in (-180, 180]. */
fun bearingDelta(from: Double, to: Double): Double {
    var d = (to - from) % 360.0
    if (d > 180.0) d -= 360.0
    if (d <= -180.0) d += 360.0
    return d
}

/**
 * Step a bearing toward another one the SHORT way round, so an icon crossing
 * north turns 2 degrees rather than spinning 358 the other way.
 */
fun stepBearing(fromDeg: Double, toDeg: Double, alpha: Double): Double =
    wrap360Deg(fromDeg + bearingDelta(fromDeg, toDeg) * alpha.coerceIn(0.0, 1.0))

/** Straight-line distance between two east/north pairs, metres. */
fun planarDistanceM(e1: Double, n1: Double, e2: Double, n2: Double): Double {
    val de = e2 - e1
    val dn = n2 - n1
    return sqrt(de * de + dn * dn)
}

/** True when a radius is a number worth drawing as a circle on a map. */
fun uncertaintyDrawable(radiusM: Double): Boolean =
    radiusM.isFinite() && radiusM > 0.0 && abs(radiusM) < 1_000_000.0
