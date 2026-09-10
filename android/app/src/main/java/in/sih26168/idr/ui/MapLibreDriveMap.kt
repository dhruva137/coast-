package `in`.sih26168.idr.ui

import android.content.Context
import android.graphics.Bitmap
import android.graphics.Paint
import android.graphics.Path
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.defaultMinSize
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.State
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.runtime.withFrameNanos
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import `in`.sih26168.idr.IdrBus
import `in`.sih26168.idr.data.NavMode
import `in`.sih26168.idr.data.Prefs
import `in`.sih26168.idr.data.TrackSnapshot
import `in`.sih26168.idr.nav.haversineM
import `in`.sih26168.idr.nav.metersPerDeg
import `in`.sih26168.idr.ui.theme.Accent
import `in`.sih26168.idr.ui.theme.Amber
import `in`.sih26168.idr.ui.theme.Bg
import `in`.sih26168.idr.ui.theme.Ghost
import `in`.sih26168.idr.ui.theme.Gnss
import `in`.sih26168.idr.ui.theme.IdrMono
import `in`.sih26168.idr.ui.theme.Mute
import `in`.sih26168.idr.ui.theme.Text as Fg
import java.io.File
import kotlin.math.cos
import kotlin.math.min
import kotlin.math.roundToInt
import kotlin.math.sin
import kotlin.math.sqrt
import org.maplibre.android.MapLibre
import org.maplibre.android.camera.CameraPosition
import org.maplibre.android.camera.CameraUpdateFactory
import org.maplibre.android.geometry.LatLng
import org.maplibre.android.gestures.MoveGestureDetector
import org.maplibre.android.maps.MapLibreMap
import org.maplibre.android.maps.MapView
import org.maplibre.android.maps.Style
import org.maplibre.android.style.layers.FillLayer
import org.maplibre.android.style.layers.LineLayer
import org.maplibre.android.style.layers.Property
import org.maplibre.android.style.layers.PropertyFactory
import org.maplibre.android.style.layers.SymbolLayer
import org.maplibre.android.style.sources.GeoJsonSource
import org.maplibre.geojson.Feature
import org.maplibre.geojson.FeatureCollection
import org.maplibre.geojson.LineString
import org.maplibre.geojson.Point
import org.maplibre.geojson.Polygon/**
 * The map panel: a real OpenStreetMap basemap when one is possible, and the
 * metre-grid Canvas ([DriveMap]) when it is not.
 *
 * ## Why both exist
 *
 * The problem statement asks for a UI "displaying a smooth, uninterrupted
 * vehicle icon showing seamless navigation", and it names the basemap
 * explicitly: "overlaying the inertial trajectory onto an offline map database
 * (e.g., OpenStreetMap)". So the basemap here is **MapLibre Native** drawing
 * **OpenStreetMap** raster tiles. That stack needs no API key, no billing
 * account and no Google Play services -- the public OSM tile server is open,
 * and MapLibre is a plain Android `View`.
 *
 * But the basemap is still the one part of this screen that can fail for
 * reasons outside the app: no network at the venue, or no anchor on the Earth
 * to georeference the track against. Each of those falls back to the Canvas
 * with a line saying which, because a blank tile in front of a judge is worse
 * than an honest metre grid. [chooseMapBackend] holds that decision and is unit
 * tested.
 */
@Composable
fun DriveMapPanel(
    bus: IdrBus,
    track: TrackSnapshot,
    navMode: NavMode,
    modifier: Modifier = Modifier,
    mapModifier: Modifier = Modifier,
    onLongPress: () -> Unit = {},
    /**
     * When true, draw the legacy text chip for map↔grid. Drive now uses an M3
     * FAB instead — leave this false from [DriveScreen].
     */
    showBasemapToggle: Boolean = true,
    /** External basemap preference; null = own Prefs-backed state. */
    basemapWanted: Boolean? = null,
    onBasemapWantedChange: ((Boolean) -> Unit)? = null,
    /** Increment to force camera follow + animate to the vehicle. */
    recenterTick: Int = 0,
    /** When false, hide the on-map RE-CENTRE chip (Drive FAB handles it). */
    showRecenterChip: Boolean = true,
    ghostTrack: TrackSnapshot = TrackSnapshot(),
    showGhost: Boolean = false,
) {
    val ctx = LocalContext.current
    val prefs = remember { Prefs(ctx) }
    var internalBasemap by remember { mutableStateOf(prefs.basemapEnabled) }
    val basemapOn = basemapWanted ?: internalBasemap
    fun setBasemap(v: Boolean) {
        if (basemapWanted == null) {
            internalBasemap = v
            prefs.basemapEnabled = v
        }
        onBasemapWantedChange?.invoke(v)
    }
    val showUncertainty = prefs.showUncertaintyRadius
    val online by rememberOnline()
    // Survives rotation deliberately: once tiles have arrived, MapLibre serves
    // them from its own cache, so dropping the network must NOT tear the map
    // down. That case -- moving map, no signal -- is the entire demo.
    var tilesEverLoaded by rememberSaveable { mutableStateOf(false) }
    // P0-4: bundled neighbourhood .mbtiles → MapLibre even with airplane on
    // and an empty HTTP tile cache. Copied out of assets once (mbtiles://
    // cannot read APK assets directly — maplibre-native#3559).
    val bundledMbtilesPath = remember(ctx) { ensureBundledMbtilesOnDisk(ctx)?.absolutePath }
    val hasBundledMbtiles = bundledMbtilesPath != null

    // MapLibre needs its native library, and the build ships arm64-v8a and
    // armeabi-v7a only. On an x86/x86_64 emulator libmaplibre.so is simply
    // absent, so getInstance throws UnsatisfiedLinkError during composition --
    // on the default tab, which reads as "the app crashes on launch". ONNX
    // degrades gracefully here; MapLibre does not, so probe it once and fall
    // back to the Canvas map rather than taking the process down.
    val mapLibreUsable = remember(ctx) {
        runCatching { MapLibre.getInstance(ctx) }.isSuccess
    }

    val chrome = rememberVehicleChrome(bus.hud)
    val origin = chrome.origin
    val insidePack = chrome.insideBundledBounds
    // Prefer live light OSM whenever the radio is up — the bundled pack is
    // dark Carto and looks like a black map. Keep mbtiles only for airplane /
    // offline demos inside the Coventry bbox.
    val useBundledMbtiles = hasBundledMbtiles && insidePack && !online
    val choice = chooseMapBackend(
        basemapWanted = basemapOn,
        online = online,
        tilesEverLoaded = tilesEverLoaded,
        navMode = navMode,
        hasAbsolutePosition = chrome.hasAbsolutePosition && origin != null,
        bundledMbtilesAvailable = hasBundledMbtiles,
        insideBundledBounds = insidePack,
    )

    Box(modifier) {
        if (choice.backend == MapBackend.OSM && origin != null && mapLibreUsable) {
            MapLibreDriveMap(
                bus = bus,
                track = track,
                navMode = navMode,
                origin = origin,
                modifier = mapModifier.fillMaxSize(),
                onLongPress = onLongPress,
                onMapLoaded = { tilesEverLoaded = true },
                showUncertaintyRadius = showUncertainty,
                bundledMbtilesAbsolutePath = if (useBundledMbtiles) bundledMbtilesPath else null,
                ghostTrack = ghostTrack,
                showGhost = showGhost,
                recenterTick = recenterTick,
                showRecenterChip = showRecenterChip,
                // Always light OSM chrome — matches the console Fleet map.
                darkBasemap = false,
            )
        } else {
            DriveMap(
                bus = bus,
                track = track,
                navMode = navMode,
                modifier = mapModifier.fillMaxSize(),
                onLongPress = onLongPress,
                // Nothing to explain before the user has pressed START: the
                // Canvas already says "Press START to begin tracking".
                caption = if (navMode == NavMode.IDLE && track.ins.isEmpty()) null else choice.reason,
                showUncertaintyRadius = showUncertainty,
                ghostTrack = ghostTrack,
                showGhost = showGhost,
            )
        }

        // Privacy control: basemap off → Canvas grid, no tile traffic.
        if (showBasemapToggle) {
            val toggleLabel = if (basemapOn) "SHOW GRID" else "SHOW MAP"
            Text(
                toggleLabel,
                modifier = Modifier
                    .align(Alignment.TopEnd)
                    .padding(12.dp)
                    .defaultMinSize(minWidth = 44.dp, minHeight = 44.dp)
                    .clip(RoundedCornerShape(8.dp))
                    .background(Bg.copy(alpha = 0.72f))
                    .semantics {
                        contentDescription = if (basemapOn) {
                            "Show metre grid instead of basemap; disables tile network"
                        } else {
                            "Show map basemap"
                        }
                    }
                    .clickable { setBasemap(!basemapOn) }
                    .padding(horizontal = 12.dp, vertical = 12.dp),
                color = Mute,
                fontFamily = IdrMono,
                fontSize = 10.sp,
                letterSpacing = 1.2.sp,
                textAlign = TextAlign.Center,
            )
        }
    }
}

/** Follow zoom. 17 is "you can see which street you are on" without hunting. */
private const val FOLLOW_ZOOM = 17.0

private const val VEHICLE_IMG = "coast-vehicle"
private const val GHOST_IMG = "coast-ghost"
private const val SRC_GNSS = "coast-gnss"
private const val SRC_DR = "coast-dr"
private const val SRC_GHOST = "coast-ghost-trail"
private const val SRC_GHOST_VEHICLE = "coast-ghost-vehicle-src"
private const val SRC_VEHICLE = "coast-vehicle-src"
private const val SRC_UNC = "coast-uncertainty"
private const val LYR_GNSS = "coast-gnss-line"
private const val LYR_DR = "coast-dr-line"
private const val LYR_GHOST = "coast-ghost-line"
private const val LYR_GHOST_VEHICLE = "coast-ghost-vehicle-layer"
private const val LYR_VEHICLE = "coast-vehicle-layer"
private const val LYR_UNC_FILL = "coast-uncertainty-fill"
private const val LYR_UNC_LINE = "coast-uncertainty-line"

/** Asset path for the P0-4 offline neighbourhood pack (see assets/maps/README.md). */
internal const val BUNDLED_MBTILES_ASSET = "maps/demo_neighbourhood.mbtiles"

/**
 * Public OSM raster basemap — the same tile source the console Fleet map uses,
 * so the phone and console look identical. No API key, no billing, no watermark.
 * The `dark` argument is kept for signature stability but the same OSM tiles are
 * used in both modes — the surrounding UI carries the light/dark theme.
 * Prefer [bundledMbtilesStyleJson] when the neighbourhood `.mbtiles` is on disk.
 */
private fun osmStyleJson(dark: Boolean): String {
    // Light paper-map background. `dark` kept for call-site stability; demo
    // always wants white OSM (same tiles as the console Fleet "OSM" style).
    val bg = if (dark) "#0B0E11" else "#F5F5F0"
    return """
{
  "version": 8,
  "sources": {
    "osm": {
      "type": "raster",
      "tiles": [
        "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
      ],
      "tileSize": 256,
      "minzoom": 0,
      "maxzoom": 19,
      "attribution": "© OpenStreetMap"
    }
  },
  "layers": [
    { "id": "bg", "type": "background", "paint": { "background-color": "$bg" } },
    { "id": "osm", "type": "raster", "source": "osm" }
  ]
}
""".trimIndent()
}

/**
 * Style that reads a local raster MBTiles file via MapLibre's `mbtiles://` scheme.
 * [absolutePath] must be a real filesystem path (assets must be copied first).
 * Bundled tiles are dark cartography; [dark] only adjusts the background fill.
 */
internal fun bundledMbtilesStyleJson(absolutePath: String, dark: Boolean = true): String {
    // MapLibre expects mbtiles:///<abs-path> (three slashes + absolute Unix path).
    val uri = "mbtiles://" + absolutePath
    val bg = if (dark) "#0B0E11" else "#E8ECF0"
    return """
{
  "version": 8,
  "sources": {
    "osm": {
      "type": "raster",
      "url": "$uri",
      "tileSize": 256,
      "minzoom": 13,
      "maxzoom": 17,
      "attribution": "© OpenStreetMap contributors © CARTO (bundled demo neighbourhood)"
    }
  },
  "layers": [
    { "id": "bg", "type": "background", "paint": { "background-color": "$bg" } },
    { "id": "osm", "type": "raster", "source": "osm", "paint": { "raster-opacity": 0.92 } }
  ]
}
""".trimIndent()
}

/**
 * Copy the bundled `.mbtiles` from APK assets into [Context.getFilesDir] once.
 * Returns null when the asset is absent or the copy fails.
 */
internal fun ensureBundledMbtilesOnDisk(context: Context): File? {
    val present = runCatching {
        context.assets.open(BUNDLED_MBTILES_ASSET).close()
        true
    }.getOrDefault(false)
    if (!present) return null

    val dest = File(context.filesDir, BUNDLED_MBTILES_ASSET)
    if (dest.exists() && dest.length() > 0L) return dest
    return runCatching {
        dest.parentFile?.mkdirs()
        context.assets.open(BUNDLED_MBTILES_ASSET).use { input ->
            dest.outputStream().use { output -> input.copyTo(output) }
        }
        if (dest.exists() && dest.length() > 0L) dest else null
    }.getOrNull()
}
/** Live references into the map, filled once the style is ready. */
private class MapRefs {
    var map: MapLibreMap? = null
    var style: Style? = null
    var gnss: GeoJsonSource? = null
    var dr: GeoJsonSource? = null
    var ghost: GeoJsonSource? = null
    var ghostVehicle: GeoJsonSource? = null
    var ghostLine: LineLayer? = null
    var ghostVehicleLayer: SymbolLayer? = null
    var vehicle: GeoJsonSource? = null
    var unc: GeoJsonSource? = null
    var vehicleLayer: SymbolLayer? = null
    var uncFill: FillLayer? = null
    var uncLine: LineLayer? = null
    var ready = false
    var iconDirectional: Boolean? = null
    var uncShown: Boolean? = null
    var uncModelled: Boolean? = null
    var ghostVisible: Boolean? = null
}

/**
 * The COAST layer on a real OpenStreetMap basemap, MapLibre Native wrapped in an
 * [AndroidView] because MapLibre is a classic Android `View`, not Compose.
 *
 * ## What is drawn, and what each thing means
 *
 *  * **Green line** -- the track while a live GNSS fix was anchoring it.
 *  * **Orange line, thicker** -- the track while it was dead reckoned from the
 *    IMU alone. Colour AND width differ, so the distinction survives a
 *    colour-blind reader and a projector. These are the same two colours the
 *    mode badge at the top of the screen uses, and the split is computed with
 *    the same 2 s staleness window the estimator uses to choose the mode, so
 *    the line and the badge cannot contradict each other. See [segmentTrail].
 *  * **Circle** -- the uncertainty from `HudState.uncertaintyM`, which is the
 *    OS-reported accuracy under GNSS (solid) and the distance-and-drift model
 *    otherwise (dashed). It is NOT a particle-filter spread: `docs/
 *    ARCHITECTURE_V2.md` measured that spread against true error at **-0.23**,
 *    i.e. slightly anti-correlated, and drawing it as a confidence radius would
 *    tell the user "trust me" exactly when the filter is most wrong.
 *  * **Vehicle icon** -- a chevron when heading has been tied to true north by a
 *    GNSS bearing, and a plain dot when it has not. Before that reference
 *    exists `headingDeg` is the angle turned since arming from an arbitrary
 *    zero; pointing a chevron with it on a north-up map would be a fabrication.
 *
 * ## Performance
 *
 *  * The projected polylines are rebuilt only when a point is appended
 *    (`LaunchedEffect(track.version, ...)`), never per frame. The origin is
 *    quantised (see [quantiseDeg]) because it is recovered from the HUD by
 *    arithmetic whose last digits wobble as the vehicle moves.
 *  * The 60 Hz vehicle animation: east/north/bearing live in [Animatable]s
 *    (not Compose UI state). Each ~10 Hz fix calls `animateTo`; a
 *    `withFrameNanos` loop reads those values and writes the GeoJSON source
 *    so interpolated frames never recompose the Compose tree.
 *  * Theme / style swaps call [MapLibreMap.setStyle], which tears down layers —
 *    trail sources are re-registered inside the style-loaded callback so the
 *    path does not vanish.
 */
@Composable
fun MapLibreDriveMap(
    bus: IdrBus,
    track: TrackSnapshot,
    navMode: NavMode,
    origin: GeoPoint,
    modifier: Modifier = Modifier,
    onLongPress: () -> Unit = {},
    onMapLoaded: () -> Unit = {},
    /** Off by default — uncertainty correlates −0.23 with true error. */
    showUncertaintyRadius: Boolean = false,
    /**
     * Absolute filesystem path to the bundled neighbourhood `.mbtiles`, or null
     * to use live Carto tiles. Caller must pass non-null **only** when the fix
     * is inside the pack's Coventry bbox — otherwise MapLibre paints an empty
     * dark basemap (no streets, no error).
     */
    bundledMbtilesAbsolutePath: String? = null,
    ghostTrack: TrackSnapshot = TrackSnapshot(),
    showGhost: Boolean = false,
    /** Increment from Drive FAB to re-enable follow and animate to the vehicle. */
    recenterTick: Int = 0,
    showRecenterChip: Boolean = true,
    /** Dark Carto / dark chrome background; false → light_all tiles. */
    darkBasemap: Boolean = true,
) {
    val ctx = LocalContext.current
    val density = LocalDensity.current
    val lifecycleOwner = LocalLifecycleOwner.current

    val oLat = quantiseDeg(origin.lat)
    val oLon = quantiseDeg(origin.lon)
    val styleJson = remember(bundledMbtilesAbsolutePath, darkBasemap) {
        val path = bundledMbtilesAbsolutePath
        if (!path.isNullOrBlank()) {
            bundledMbtilesStyleJson(path, dark = darkBasemap)
        } else {
            osmStyleJson(darkBasemap)
        }
    }

    val motion = remember(bus) { VehicleMotionSource(bus) }
    val vehicle = subscribeVehicleMotion(motion.hud)
    val chrome by vehicle.chrome
    val eastAnim = vehicle.east
    val northAnim = vehicle.north
    val bearingAnim = vehicle.bearing

    val refs = remember { MapRefs() }
    // Plain array, not state: the gesture watcher needs the last drawn position
    // and must not be woken up by it.
    val rendered = remember { doubleArrayOf(oLat, oLon) }

    val following = remember { mutableStateOf(true) }
    val gesturing = remember { mutableStateOf(false) }
    var viewportMinPx by remember { mutableIntStateOf(0) }
    var followTick by remember { mutableIntStateOf(0) }

    val trackLatest = rememberUpdatedState(track)
    val ghostLatest = rememberUpdatedState(ghostTrack)
    val showGhostLatest = rememberUpdatedState(showGhost)
    val oLatLatest = rememberUpdatedState(oLat)
    val oLonLatest = rememberUpdatedState(oLon)
    val onMapLoadedLatest = rememberUpdatedState(onMapLoaded)
    val onLongPressLatest = rememberUpdatedState(onLongPress)

    // Drive FAB / external recenter request.
    LaunchedEffect(recenterTick) {
        if (recenterTick == 0) return@LaunchedEffect
        following.value = true
        followTick++
        val map = refs.map ?: return@LaunchedEffect
        runCatching {
            map.animateCamera(
                CameraUpdateFactory.newLatLngZoom(
                    LatLng(rendered[0], rendered[1]),
                    maxOf(map.cameraPosition.zoom, FOLLOW_ZOOM),
                ),
                500,
            )
        }
    }

    // MapLibre.getInstance MUST run before a MapView is constructed. No key is
    // passed -- the style carries its own tile URLs, so none is needed.
    // DriveMapPanel already probed ABI usability; call again (idempotent) so a
    // MapView is never constructed without a successful init on this process.
    val mapView = remember {
        MapLibre.getInstance(ctx)
        MapView(ctx)
    }

    // Classic View lifecycle, driven from the composition's lifecycle owner.
    // addObserver replays the current state, so a MapView created while the
    // activity is already RESUMED still gets onCreate/onStart/onResume.
    DisposableEffect(lifecycleOwner, mapView) {
        val observer = LifecycleEventObserver { _, event ->
            when (event) {
                Lifecycle.Event.ON_CREATE -> mapView.onCreate(null)
                Lifecycle.Event.ON_START -> mapView.onStart()
                Lifecycle.Event.ON_RESUME -> mapView.onResume()
                Lifecycle.Event.ON_PAUSE -> mapView.onPause()
                Lifecycle.Event.ON_STOP -> mapView.onStop()
                else -> {}
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose {
            lifecycleOwner.lifecycle.removeObserver(observer)
            refs.ready = false
            mapView.onDestroy()
        }
    }

    var mapReadyTick by remember { mutableIntStateOf(0) }

    // One-time map wiring: gestures + camera. Style/layers live in a separate
    // effect keyed on styleJson so theme swaps re-register the track polyline.
    DisposableEffect(mapView) {
        mapView.getMapAsync { map ->
            refs.map = map
            map.uiSettings.apply {
                isRotateGesturesEnabled = false
                isTiltGesturesEnabled = false
                isCompassEnabled = true
                isAttributionEnabled = true
                isLogoEnabled = true
            }
            map.cameraPosition = CameraPosition.Builder()
                .target(LatLng(oLat, oLon))
                .zoom(FOLLOW_ZOOM)
                .build()

            map.addOnMapLongClickListener {
                onLongPressLatest.value()
                true
            }

            map.addOnMoveListener(object : MapLibreMap.OnMoveListener {
                override fun onMoveBegin(detector: MoveGestureDetector) {
                    gesturing.value = true
                }

                override fun onMove(detector: MoveGestureDetector) {}

                override fun onMoveEnd(detector: MoveGestureDetector) {
                    gesturing.value = false
                    val pos = map.cameraPosition
                    val tgt = pos.target
                    if (tgt != null) {
                        val offsetM = haversineM(
                            tgt.latitude, tgt.longitude, rendered[0], rendered[1],
                        )
                        following.value = !shouldBreakFollow(
                            offsetM = offsetM,
                            metresPerPixel = metresPerPixel(pos.zoom, tgt.latitude),
                            viewportMinPx = viewportMinPx,
                        )
                        followTick++
                    }
                }
            })
            mapReadyTick++
        }
        onDispose { }
    }

    // setStyle tears down sources/layers — always re-install COAST overlays and
    // pushTrail inside the style-loaded callback (Phase 5.4 gotcha).
    LaunchedEffect(mapReadyTick, styleJson) {
        if (mapReadyTick == 0) return@LaunchedEffect
        val m = refs.map ?: return@LaunchedEffect
        refs.ready = false
        val directional = chrome.headingReferenced
        m.setStyle(Style.Builder().fromJson(styleJson)) { style ->
            installCoastLayers(refs, style, density.density, directional)
            onMapLoadedLatest.value()
            pushTrail(refs, trackLatest.value, oLatLatest.value, oLonLatest.value)
            pushGhost(
                refs,
                ghostLatest.value,
                oLatLatest.value,
                oLonLatest.value,
                showGhostLatest.value,
            )
        }
    }

    // Rebuild the two coloured polylines only when a point is appended.
    LaunchedEffect(track.version, oLat, oLon) {
        pushTrail(refs, track, oLat, oLon)
    }

    LaunchedEffect(ghostTrack.version, showGhost, oLat, oLon) {
        pushGhost(refs, ghostTrack, oLat, oLon, showGhost)
    }

    // Pose Animatables come from subscribeVehicleMotion (bus), not HUD recomposition.

    val directional by rememberUpdatedState(chrome.headingReferenced)
    val modelled by rememberUpdatedState(navMode != NavMode.GNSS)
    val drawUncertainty by rememberUpdatedState(showUncertaintyRadius)

    LaunchedEffect(Unit) {
        while (true) {
            withFrameNanos {
                if (!refs.ready) return@withFrameNanos

                val e = eastAnim.value.toDouble()
                val n = northAnim.value.toDouble()
                val bearing = bearingAnim.value.toDouble()
                val g = projectFromOrigin(oLatLatest.value, oLonLatest.value, e, n)
                rendered[0] = g.lat
                rendered[1] = g.lon

                val dir = directional
                if (refs.iconDirectional != dir) {
                    refs.style?.addImage(VEHICLE_IMG, vehicleBitmap(density.density, dir))
                    refs.iconDirectional = dir
                }
                refs.vehicle?.setGeoJson(Point.fromLngLat(g.lon, g.lat))
                refs.vehicleLayer?.setProperties(
                    PropertyFactory.iconRotate(if (dir) wrap360Deg(bearing).toFloat() else 0f),
                )

                val r = vehicle.extras.uncertaintyM
                if (drawUncertainty && uncertaintyDrawable(r)) {
                    refs.unc?.setGeoJson(circlePolygonFeature(g.lat, g.lon, r))
                    val mdl = modelled
                    if (refs.uncShown != true || refs.uncModelled != mdl) {
                        val tint = (if (mdl) Amber else Gnss).toArgb()
                        refs.uncFill?.setProperties(
                            PropertyFactory.visibility(Property.VISIBLE),
                            PropertyFactory.fillColor(tint),
                        )
                        val dash = if (mdl) arrayOf(2f, 1.5f) else arrayOf(1f)
                        refs.uncLine?.setProperties(
                            PropertyFactory.visibility(Property.VISIBLE),
                            PropertyFactory.lineColor(tint),
                            PropertyFactory.lineDasharray(dash),
                        )
                        refs.uncShown = true
                        refs.uncModelled = mdl
                    }
                } else if (refs.uncShown != false) {
                    refs.uncFill?.setProperties(PropertyFactory.visibility(Property.NONE))
                    refs.uncLine?.setProperties(PropertyFactory.visibility(Property.NONE))
                    refs.uncShown = false
                    refs.uncModelled = null
                }

                if (following.value && !gesturing.value) {
                    refs.map?.moveCamera(CameraUpdateFactory.newLatLng(LatLng(g.lat, g.lon)))
                }
            }
        }
    }

    Box(
        modifier
            .background(Bg)
            .onSizeChanged { viewportMinPx = min(it.width, it.height) },
    ) {
        AndroidView(factory = { mapView }, modifier = Modifier.fillMaxSize())

        MapLegend(
            navMode = navMode,
            headingReferenced = chrome.headingReferenced,
            showGhost = showGhost,
            modifier = Modifier
                .align(Alignment.TopStart)
                .padding(10.dp),
        )

        // OSM's tile policy requires visible attribution. MapLibre's attribution
        // control also carries it, but this states it outright on the map.
        Text(
            "© OpenStreetMap contributors",
            modifier = Modifier
                .align(Alignment.BottomStart)
                .padding(8.dp)
                .clip(RoundedCornerShape(4.dp))
                .background(Bg.copy(alpha = 0.7f))
                .padding(horizontal = 6.dp, vertical = 3.dp),
            color = Mute,
            fontFamily = IdrMono,
            fontSize = 8.sp,
        )

        // Read followTick so this leaf recomposes when follow flips.
        followTick
        if (showRecenterChip && !following.value) {
            Text(
                "RE-CENTRE",
                modifier = Modifier
                    .align(Alignment.BottomEnd)
                    .padding(12.dp)
                    .clip(RoundedCornerShape(99.dp))
                    .background(Bg.copy(alpha = 0.85f))
                    .clickable {
                        val map = refs.map
                        if (map != null) {
                            runCatching {
                                map.animateCamera(
                                    CameraUpdateFactory.newLatLngZoom(
                                        LatLng(rendered[0], rendered[1]),
                                        maxOf(map.cameraPosition.zoom, FOLLOW_ZOOM),
                                    ),
                                    500,
                                )
                            }
                        }
                        following.value = true
                        followTick++
                    }
                    .padding(horizontal = 14.dp, vertical = 9.dp),
                color = Accent,
                fontFamily = IdrMono,
                fontSize = 11.sp,
                letterSpacing = 1.2.sp,
            )
        }
    }
}


/**
 * Install COAST GeoJSON sources + layers on a freshly loaded MapLibre [style].
 * Must run after every [MapLibreMap.setStyle] — style swaps wipe prior layers.
 */
private fun installCoastLayers(
    refs: MapRefs,
    style: Style,
    density: Float,
    directional: Boolean,
) {
    refs.style = style
    refs.ghostVisible = null
    refs.uncShown = null
    refs.uncModelled = null

    style.addImage(VEHICLE_IMG, vehicleBitmap(density, directional))
    style.addImage(GHOST_IMG, ghostBitmap(density))

    val gnssSrc = GeoJsonSource(SRC_GNSS)
    val drSrc = GeoJsonSource(SRC_DR)
    val ghostSrc = GeoJsonSource(SRC_GHOST)
    val ghostVehSrc = GeoJsonSource(SRC_GHOST_VEHICLE)
    val vehSrc = GeoJsonSource(SRC_VEHICLE)
    val uncSrc = GeoJsonSource(SRC_UNC)
    style.addSource(gnssSrc)
    style.addSource(drSrc)
    style.addSource(ghostSrc)
    style.addSource(ghostVehSrc)
    style.addSource(vehSrc)
    style.addSource(uncSrc)

    val uncFill = FillLayer(LYR_UNC_FILL, SRC_UNC).withProperties(
        PropertyFactory.fillColor(Amber.toArgb()),
        PropertyFactory.fillOpacity(0.10f),
        PropertyFactory.visibility(Property.NONE),
    )
    val uncLine = LineLayer(LYR_UNC_LINE, SRC_UNC).withProperties(
        PropertyFactory.lineColor(Amber.toArgb()),
        PropertyFactory.lineWidth(2f),
        PropertyFactory.lineOpacity(0.6f),
        PropertyFactory.visibility(Property.NONE),
    )
    val ghostLine = LineLayer(LYR_GHOST, SRC_GHOST).withProperties(
        PropertyFactory.lineColor(Ghost.copy(alpha = 0.40f).toArgb()),
        PropertyFactory.lineWidth(3.5f),
        PropertyFactory.lineOpacity(0.55f),
        PropertyFactory.lineCap(Property.LINE_CAP_ROUND),
        PropertyFactory.lineJoin(Property.LINE_JOIN_ROUND),
        PropertyFactory.visibility(Property.NONE),
    )
    val gnssLine = LineLayer(LYR_GNSS, SRC_GNSS).withProperties(
        PropertyFactory.lineColor(Gnss.toArgb()),
        PropertyFactory.lineWidth(3f),
        PropertyFactory.lineCap(Property.LINE_CAP_ROUND),
        PropertyFactory.lineJoin(Property.LINE_JOIN_ROUND),
    )
    val drLine = LineLayer(LYR_DR, SRC_DR).withProperties(
        PropertyFactory.lineColor(Accent.toArgb()),
        PropertyFactory.lineWidth(5f),
        PropertyFactory.lineCap(Property.LINE_CAP_ROUND),
        PropertyFactory.lineJoin(Property.LINE_JOIN_ROUND),
    )
    val ghostVehLayer = SymbolLayer(LYR_GHOST_VEHICLE, SRC_GHOST_VEHICLE).withProperties(
        PropertyFactory.iconImage(GHOST_IMG),
        PropertyFactory.iconAllowOverlap(true),
        PropertyFactory.iconIgnorePlacement(true),
        PropertyFactory.iconAnchor(Property.ICON_ANCHOR_CENTER),
        PropertyFactory.visibility(Property.NONE),
    )
    val vehLayer = SymbolLayer(LYR_VEHICLE, SRC_VEHICLE).withProperties(
        PropertyFactory.iconImage(VEHICLE_IMG),
        PropertyFactory.iconAllowOverlap(true),
        PropertyFactory.iconIgnorePlacement(true),
        PropertyFactory.iconRotationAlignment(Property.ICON_ROTATION_ALIGNMENT_MAP),
        PropertyFactory.iconAnchor(Property.ICON_ANCHOR_CENTER),
        PropertyFactory.iconRotate(0f),
    )
    style.addLayer(uncFill)
    style.addLayer(uncLine)
    style.addLayer(ghostLine)
    style.addLayer(gnssLine)
    style.addLayer(drLine)
    style.addLayer(ghostVehLayer)
    style.addLayer(vehLayer)

    refs.gnss = gnssSrc
    refs.dr = drSrc
    refs.ghost = ghostSrc
    refs.ghostVehicle = ghostVehSrc
    refs.ghostLine = ghostLine
    refs.ghostVehicleLayer = ghostVehLayer
    refs.vehicle = vehSrc
    refs.unc = uncSrc
    refs.vehicleLayer = vehLayer
    refs.uncFill = uncFill
    refs.uncLine = uncLine
    refs.iconDirectional = directional
    refs.ready = true
}

/**
 * Rebuild the GNSS and dead-reckoned polyline sources from the current track.
 * Split with the same 2 s staleness window as the mode badge (see
 * [segmentTrail]); each run becomes a LineString, grouped into two feature
 * collections so the two colours are two layers.
 */
private fun pushTrail(refs: MapRefs, track: TrackSnapshot, oLat: Double, oLon: Double) {
    val gnssSrc = refs.gnss ?: return
    val drSrc = refs.dr ?: return
    val gnssFeatures = ArrayList<Feature>()
    val drFeatures = ArrayList<Feature>()
    for (seg in segmentTrail(track.ins)) {
        if (seg.points.size < 2) continue
        val pts = seg.points.map { p ->
            val g = projectFromOrigin(oLat, oLon, p.east, p.north)
            Point.fromLngLat(g.lon, g.lat)
        }
        val f = Feature.fromGeometry(LineString.fromLngLats(pts))
        if (seg.gnss) gnssFeatures.add(f) else drFeatures.add(f)
    }
    gnssSrc.setGeoJson(FeatureCollection.fromFeatures(gnssFeatures))
    drSrc.setGeoJson(FeatureCollection.fromFeatures(drFeatures))
}

/**
 * Faint red naive-DR trail + puck from [ghostTrack]. Visibility follows [show].
 * Puck uses the last trail point (same EN frame as COAST, projected from origin).
 */
private fun pushGhost(
    refs: MapRefs,
    ghostTrack: TrackSnapshot,
    oLat: Double,
    oLon: Double,
    show: Boolean,
) {
    val trailSrc = refs.ghost ?: return
    val vehSrc = refs.ghostVehicle ?: return
    val pts = ghostTrack.ins
    val visible = show && pts.isNotEmpty()
    if (visible != refs.ghostVisible) {
        val vis = if (visible) Property.VISIBLE else Property.NONE
        refs.ghostLine?.setProperties(PropertyFactory.visibility(vis))
        refs.ghostVehicleLayer?.setProperties(PropertyFactory.visibility(vis))
        refs.ghostVisible = visible
    }
    if (!visible) {
        trailSrc.setGeoJson(FeatureCollection.fromFeatures(emptyList()))
        vehSrc.setGeoJson(FeatureCollection.fromFeatures(emptyList()))
        return
    }
    if (pts.size >= 2) {
        val line = pts.map { p ->
            val g = projectFromOrigin(oLat, oLon, p.east, p.north)
            Point.fromLngLat(g.lon, g.lat)
        }
        trailSrc.setGeoJson(Feature.fromGeometry(LineString.fromLngLats(line)))
    } else {
        trailSrc.setGeoJson(FeatureCollection.fromFeatures(emptyList()))
    }
    val tip = pts.last()
    val g = projectFromOrigin(oLat, oLon, tip.east, tip.north)
    vehSrc.setGeoJson(Point.fromLngLat(g.lon, g.lat))
}

/**
 * A closed polygon approximating a circle of [radiusM] metres around a point,
 * so the uncertainty is drawn in real metres on the ground rather than in
 * screen pixels. Uses the same local flat-Earth scaling the estimator projects
 * with, so it cannot disagree with the track.
 */
private fun circlePolygonFeature(centerLat: Double, centerLon: Double, radiusM: Double): Feature {
    val mpd = metersPerDeg(centerLat)
    val steps = 48
    val ring = ArrayList<Point>(steps + 1)
    for (i in 0..steps) {
        val a = 2.0 * Math.PI * i / steps
        val east = radiusM * cos(a)
        val north = radiusM * sin(a)
        ring.add(Point.fromLngLat(centerLon + east / mpd.mLon, centerLat + north / mpd.mLat))
    }
    return Feature.fromGeometry(Polygon.fromLngLats(listOf(ring)))
}

@Composable
private fun MapLegend(
    navMode: NavMode,
    headingReferenced: Boolean,
    showGhost: Boolean,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier
            .clip(RoundedCornerShape(8.dp))
            .background(Bg.copy(alpha = 0.82f))
            .padding(horizontal = 10.dp, vertical = 8.dp),
        verticalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        if (showGhost) {
            LegendRow(Ghost, "naive DR (no map)")
            LegendRow(Accent, "COAST")
        } else {
            LegendRow(Gnss, "GNSS TRACKED")
            LegendRow(Accent, "DEAD RECKONED")
        }
        if (!headingReferenced && navMode != NavMode.IDLE) {
            Text(
                "heading not tied to north yet",
                color = Amber,
                fontFamily = IdrMono,
                fontSize = 8.sp,
            )
        }
    }
}

@Composable
private fun LegendRow(color: androidx.compose.ui.graphics.Color, label: String) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Box(
            Modifier
                .width(16.dp)
                .height(3.dp)
                .clip(RoundedCornerShape(2.dp))
                .background(color),
        )
        Text(
            label,
            modifier = Modifier.padding(start = 6.dp),
            color = Fg,
            fontFamily = IdrMono,
            fontSize = 8.sp,
            letterSpacing = 0.8.sp,
        )
    }
}

/** What the frame loop needs to know, snapshotted once per composition. */
// Vehicle position is driven by Animatable + withFrameNanos (Phase 5.3).

// ---------------------------------------------------------------------------
// Network reachability
// ---------------------------------------------------------------------------

/**
 * Live network reachability, used only to decide whether asking for tiles is
 * worth it. Nothing here reads or reports anything about the network.
 */
@Composable
private fun rememberOnline(): State<Boolean> {
    val ctx = LocalContext.current
    val state = remember { mutableStateOf(true) }
    DisposableEffect(ctx) {
        val cm = ctx.getSystemService(ConnectivityManager::class.java)
        if (cm == null) {
            // Cannot tell; assume yes and let the map's own load result decide.
            state.value = true
            return@DisposableEffect onDispose { }
        }
        state.value = hasInternet(cm)
        val callback = object : ConnectivityManager.NetworkCallback() {
            override fun onAvailable(network: Network) {
                state.value = true
            }

            override fun onLost(network: Network) {
                state.value = hasInternet(cm)
            }

            override fun onCapabilitiesChanged(network: Network, caps: NetworkCapabilities) {
                state.value = caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
            }
        }
        val registered = runCatching { cm.registerDefaultNetworkCallback(callback) }.isSuccess
        onDispose {
            if (registered) runCatching { cm.unregisterNetworkCallback(callback) }
        }
    }
    return state
}

private fun hasInternet(cm: ConnectivityManager): Boolean = runCatching {
    val caps = cm.getNetworkCapabilities(cm.activeNetwork)
    caps != null && caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
}.getOrDefault(false)

// ---------------------------------------------------------------------------
// Vehicle icon
// ---------------------------------------------------------------------------

/**
 * The vehicle icon as a [Bitmap] for a MapLibre symbol image, drawn rather than
 * shipped as a PNG so it matches the chevron on the Canvas map exactly and
 * scales with the display density.
 *
 * [directional] false draws a dot instead: heading is not a compass bearing
 * until a GNSS bearing has referenced it, and an arrow on a north-up map is a
 * claim about the Earth that we would not be able to back up.
 */
private fun vehicleBitmap(density: Float, directional: Boolean): Bitmap {
    val size = (40f * density).roundToInt().coerceIn(56, 220)
    val s = size.toFloat()
    val c = s / 2f
    val bmp = Bitmap.createBitmap(size, size, Bitmap.Config.ARGB_8888)
    val canvas = android.graphics.Canvas(bmp)

    val halo = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Accent.copy(alpha = 0.22f).toArgb()
        style = Paint.Style.FILL
    }
    canvas.drawCircle(c, c, s * 0.46f, halo)

    val fill = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = android.graphics.Color.WHITE
        style = Paint.Style.FILL
    }
    val edge = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Accent.toArgb()
        style = Paint.Style.STROKE
        strokeWidth = s * 0.07f
        strokeJoin = Paint.Join.ROUND
    }

    if (directional) {
        val body = Path().apply {
            moveTo(c, s * 0.10f)
            lineTo(s * 0.80f, s * 0.86f)
            lineTo(c, s * 0.66f)
            lineTo(s * 0.20f, s * 0.86f)
            close()
        }
        canvas.drawPath(body, fill)
        canvas.drawPath(body, edge)
    } else {
        canvas.drawCircle(c, c, s * 0.22f, fill)
        canvas.drawCircle(c, c, s * 0.22f, edge)
    }
    return bmp
}

/** Red ghost puck (#FF5252) — plain disk so it contrasts with the COAST chevron. */
private fun ghostBitmap(density: Float): Bitmap {
    val size = (36f * density).roundToInt().coerceIn(48, 180)
    val s = size.toFloat()
    val c = s / 2f
    val bmp = Bitmap.createBitmap(size, size, Bitmap.Config.ARGB_8888)
    val canvas = android.graphics.Canvas(bmp)
    val halo = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Ghost.copy(alpha = 0.28f).toArgb()
        style = Paint.Style.FILL
    }
    canvas.drawCircle(c, c, s * 0.46f, halo)
    val fill = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Ghost.toArgb()
        style = Paint.Style.FILL
    }
    val edge = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = android.graphics.Color.WHITE
        style = Paint.Style.STROKE
        strokeWidth = s * 0.06f
    }
    canvas.drawCircle(c, c, s * 0.28f, fill)
    canvas.drawCircle(c, c, s * 0.28f, edge)
    return bmp
}
