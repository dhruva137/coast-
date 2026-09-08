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
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.FloatState
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.State
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.runtime.snapshotFlow
import androidx.compose.runtime.withFrameNanos
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.google.android.gms.common.ConnectionResult
import com.google.android.gms.common.GoogleApiAvailability
import com.google.android.gms.maps.CameraUpdateFactory
import com.google.android.gms.maps.model.BitmapDescriptor
import com.google.android.gms.maps.model.BitmapDescriptorFactory
import com.google.android.gms.maps.model.CameraPosition
import com.google.android.gms.maps.model.Dash
import com.google.android.gms.maps.model.Gap
import com.google.android.gms.maps.model.JointType
import com.google.android.gms.maps.model.LatLng
import com.google.android.gms.maps.model.MapStyleOptions
import com.google.android.gms.maps.model.PatternItem
import com.google.android.gms.maps.model.RoundCap
import com.google.maps.android.compose.CameraMoveStartedReason
import com.google.maps.android.compose.Circle
import com.google.maps.android.compose.GoogleMap
import com.google.maps.android.compose.GoogleMapComposable
import com.google.maps.android.compose.MapProperties
import com.google.maps.android.compose.MapType
import com.google.maps.android.compose.MapUiSettings
import com.google.maps.android.compose.Marker
import com.google.maps.android.compose.MarkerState
import com.google.maps.android.compose.rememberMarkerState
import com.google.maps.android.compose.Polyline
import com.google.maps.android.compose.rememberCameraPositionState
import `in`.sih26168.idr.BuildConfig
import `in`.sih26168.idr.R
import `in`.sih26168.idr.data.HudState
import `in`.sih26168.idr.data.NavMode
import `in`.sih26168.idr.data.Prefs
import `in`.sih26168.idr.data.TrackSnapshot
import `in`.sih26168.idr.nav.haversineM
import `in`.sih26168.idr.ui.theme.Accent
import `in`.sih26168.idr.ui.theme.Amber
import `in`.sih26168.idr.ui.theme.Bg
import `in`.sih26168.idr.ui.theme.Gnss
import `in`.sih26168.idr.ui.theme.IdrMono
import `in`.sih26168.idr.ui.theme.Line
import `in`.sih26168.idr.ui.theme.Mute
import `in`.sih26168.idr.ui.theme.Text as Fg
import kotlinx.coroutines.launch
import kotlin.math.min
import kotlin.math.roundToInt

/**
 * The map panel: a real Google basemap when one is possible, and the metre-grid
 * Canvas ([DriveMap]) when it is not.
 *
 * ## Why both exist
 *
 * The problem statement asks for a UI "displaying a smooth, uninterrupted
 * vehicle icon showing seamless navigation", and a stranger reads that as a maps
 * app. Maps SDK for Android is unmetered -- map loads are free, and no billed
 * API (Places, Directions, Roads) is used anywhere in this app.
 *
 * But the basemap is the one part of this screen that can fail for reasons
 * outside the app: no key in a fresh clone, no Play services, no network at the
 * venue. Every one of those falls back to the Canvas with a line saying which,
 * because a blank grey Google tile in front of a judge is worse than an honest
 * metre grid. [chooseMapBackend] holds that decision and is unit tested.
 */
@Composable
fun DriveMapPanel(
    hud: HudState,
    track: TrackSnapshot,
    navMode: NavMode,
    modifier: Modifier = Modifier,
    mapModifier: Modifier = Modifier,
    onLongPress: () -> Unit = {},
) {
    val ctx = LocalContext.current
    val prefs = remember { Prefs(ctx) }
    var basemapWanted by remember { mutableStateOf(prefs.basemapEnabled) }
    // Play services is a device property; it cannot change under a running
    // process in any way that matters here, so this is checked once.
    val playServicesOk = remember { playServicesAvailable(ctx) }
    val online by rememberOnline()
    // Survives rotation deliberately: once tiles have arrived, the SDK serves
    // them from its own cache, so dropping the network must NOT tear the map
    // down. That case -- moving map, no signal -- is the entire demo.
    var tilesEverLoaded by rememberSaveable { mutableStateOf(false) }

    val origin = originFrom(hud.lat, hud.lon, hud.east, hud.north)
    val choice = chooseMapBackend(
        hasApiKey = BuildConfig.MAPS_KEY_PRESENT,
        playServicesOk = playServicesOk,
        basemapWanted = basemapWanted,
        online = online,
        tilesEverLoaded = tilesEverLoaded,
        navMode = navMode,
        hasAbsolutePosition = hud.hasAbsolutePosition && origin != null,
    )

    Column(modifier, verticalArrangement = Arrangement.spacedBy(4.dp)) {
        if (choice.backend == MapBackend.GOOGLE && origin != null) {
            GoogleDriveMap(
                hud = hud,
                track = track,
                navMode = navMode,
                origin = origin,
                modifier = mapModifier,
                onLongPress = onLongPress,
                onMapLoaded = { tilesEverLoaded = true },
            )
        } else {
            DriveMap(
                hud = hud,
                track = track,
                navMode = navMode,
                modifier = mapModifier,
                onLongPress = onLongPress,
                // Nothing to explain before the user has pressed START: the
                // Canvas already says "Press START to begin tracking".
                caption = if (navMode == NavMode.IDLE && track.ins.isEmpty()) null else choice.reason,
            )
        }

        // Offered only when a basemap is actually available, so it is never a
        // switch that does nothing. It is also the privacy control: with the
        // basemap off this app makes no network request at all.
        if (BuildConfig.MAPS_KEY_PRESENT && playServicesOk) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
                Text(
                    if (basemapWanted) "SHOW GRID INSTEAD" else "SHOW MAP",
                    modifier = Modifier
                        .clip(RoundedCornerShape(8.dp))
                        .clickable {
                            basemapWanted = !basemapWanted
                            prefs.basemapEnabled = basemapWanted
                        }
                        .padding(horizontal = 10.dp, vertical = 6.dp),
                    color = Mute,
                    fontFamily = IdrMono,
                    fontSize = 10.sp,
                    letterSpacing = 1.2.sp,
                )
            }
        }
    }
}

/** Follow zoom. 17 is "you can see which street you are on" without hunting. */
private const val FOLLOW_ZOOM = 17f

/**
 * The COAST layer on a real basemap.
 *
 * ## What is drawn, and what each thing means
 *
 *  * **Green polyline** -- the track while a live GNSS fix was anchoring it.
 *  * **Orange polyline, thicker** -- the track while it was dead reckoned from
 *    the IMU alone. Colour AND width differ, so the distinction survives a
 *    colour-blind reader and a projector. These are the same two colours the
 *    mode badge at the top of the screen uses, and the split is computed with
 *    the same 2 s staleness window the estimator uses to choose the mode, so the
 *    line and the badge cannot contradict each other. See [segmentTrail].
 *  * **Circle** -- the uncertainty from `HudState.uncertaintyM`, which is the
 *    OS-reported accuracy under GNSS (solid) and the distance-and-drift model
 *    otherwise (dashed). It is NOT a particle-filter spread: `docs/
 *    ARCHITECTURE_V2.md` measured that spread against true error at **-0.23**,
 *    i.e. slightly anti-correlated, and drawing it as a confidence radius would
 *    tell the user "trust me" exactly when the filter is most wrong.
 *  * **Vehicle icon** -- a chevron when heading has been tied to true north by a
 *    GNSS bearing, and a plain dot when it has not. Before that reference exists
 *    `headingDeg` is the angle turned since arming from an arbitrary zero;
 *    pointing a chevron with it on a north-up map would be a fabrication.
 *
 * ## Performance
 *
 * The rules the Canvas map earned the hard way apply here too:
 *
 *  * The projected polylines are built once per appended point
 *    (`remember(track.version, origin)`), never per frame. The origin is
 *    quantised (see [quantiseDeg]) because it is recovered from the HUD by
 *    arithmetic whose last digits wobble as the vehicle moves, and that wobble
 *    would otherwise invalidate the cache ten times a second.
 *  * The 60 Hz vehicle animation writes the marker position straight into
 *    `MarkerState` from a `withFrameNanos` loop, which is OUTSIDE composition
 *    entirely. Only [VehicleLayer], one leaf, recomposes per frame -- the
 *    polylines and the surrounding screen do not.
 */
@Composable
fun GoogleDriveMap(
    hud: HudState,
    track: TrackSnapshot,
    navMode: NavMode,
    origin: GeoPoint,
    modifier: Modifier = Modifier,
    onLongPress: () -> Unit = {},
    onMapLoaded: () -> Unit = {},
) {
    val ctx = LocalContext.current
    val density = LocalDensity.current
    val scope = rememberCoroutineScope()

    val oLat = quantiseDeg(origin.lat)
    val oLon = quantiseDeg(origin.lon)

    val lines = remember(track.version, oLat, oLon) {
        segmentTrail(track.ins).map { seg ->
            MapPolyline(
                gnss = seg.gnss,
                points = seg.points.map { p ->
                    val g = projectFromOrigin(oLat, oLon, p.east, p.north)
                    LatLng(g.lat, g.lon)
                },
            )
        }
    }

    val markerState = remember { MarkerState(LatLng(oLat, oLon)) }
    val centre = remember { mutableStateOf(LatLng(oLat, oLon)) }
    val bearing = remember { mutableFloatStateOf(0f) }
    val smoother = remember { VehicleSmoother() }
    // Plain array, not state: the gesture watcher needs the last drawn position
    // and must not be woken up by it.
    val rendered = remember { doubleArrayOf(oLat, oLon) }

    var following by remember { mutableStateOf(true) }
    var gesturing by remember { mutableStateOf(false) }
    var viewportMinPx by remember { mutableIntStateOf(0) }

    val camera = rememberCameraPositionState {
        position = CameraPosition.fromLatLngZoom(LatLng(oLat, oLon), FOLLOW_ZOOM)
    }

    // Read in composition, consumed in the frame loop. rememberUpdatedState is
    // exactly the tool for "the effect must see the newest value without being
    // restarted by it".
    val target by rememberUpdatedState(
        VehicleTarget(oLat, oLon, hud.east, hud.north, hud.headingDeg),
    )

    LaunchedEffect(Unit) {
        var lastNs = 0L
        while (true) {
            withFrameNanos { now ->
                val dt = if (lastNs == 0L) 0.0 else (now - lastNs) / 1e9
                lastNs = now
                val t = target
                smoother.step(dt, t.east, t.north, t.headingDeg)
                val g = projectFromOrigin(t.originLat, t.originLon, smoother.east, smoother.north)
                rendered[0] = g.lat
                rendered[1] = g.lon
                val here = LatLng(g.lat, g.lon)
                // Straight into the marker node's own state: no composition of
                // ours is involved in moving the vehicle.
                markerState.position = here
                centre.value = here
                bearing.floatValue = smoother.bearingDeg.toFloat()
                if (following && !gesturing) {
                    val cur = camera.position
                    camera.position = CameraPosition.Builder()
                        .target(here)
                        // Keep whatever the user zoomed, rotated or tilted to.
                        .zoom(cur.zoom)
                        .bearing(cur.bearing)
                        .tilt(cur.tilt)
                        .build()
                }
            }
        }
    }

    // Following stops the moment a drag starts -- overriding the camera under a
    // finger is the definition of fighting the user -- and is re-evaluated when
    // the gesture ends. A pinch that leaves the vehicle near the centre resumes
    // following; a pan that carries it away does not. See [shouldBreakFollow].
    LaunchedEffect(camera) {
        snapshotFlow { camera.isMoving }.collect { moving ->
            if (moving) {
                if (camera.cameraMoveStartedReason == CameraMoveStartedReason.GESTURE) {
                    gesturing = true
                }
            } else if (gesturing) {
                gesturing = false
                val pos = camera.position
                val offsetM = haversineM(
                    pos.target.latitude, pos.target.longitude, rendered[0], rendered[1],
                )
                following = !shouldBreakFollow(
                    offsetM = offsetM,
                    metresPerPixel = metresPerPixel(pos.zoom.toDouble(), pos.target.latitude),
                    viewportMinPx = viewportMinPx,
                )
            }
        }
    }

    val mapStyle = remember(ctx) {
        runCatching { MapStyleOptions.loadRawResourceStyle(ctx, R.raw.map_style_night) }.getOrNull()
    }
    val properties = remember(mapStyle) {
        MapProperties(
            mapType = MapType.NORMAL,
            mapStyleOptions = mapStyle,
            // Our own estimate is the position on this screen. The blue dot is
            // the OS fused location, which would quietly contradict it during an
            // outage -- and it needs a permission the app deliberately survives
            // without.
            isMyLocationEnabled = false,
            isTrafficEnabled = false,
            isBuildingEnabled = false,
        )
    }
    val uiSettings = remember {
        MapUiSettings(
            compassEnabled = true,
            mapToolbarEnabled = false,
            myLocationButtonEnabled = false,
            zoomControlsEnabled = false,
            tiltGesturesEnabled = false,
            indoorLevelPickerEnabled = false,
        )
    }

    val gnssWidth = with(density) { 4.dp.toPx() }
    val drWidth = with(density) { 6.dp.toPx() }
    val directional = hud.headingReferenced
    val icon = remember(directional, density.density) {
        runCatching { vehicleIcon(density.density, directional) }.getOrNull()
    }
    val modelled = navMode != NavMode.GNSS
    val dashed = remember { listOf<PatternItem>(Dash(26f), Gap(18f)) }

    Box(
        modifier
            .background(Bg)
            .onSizeChanged { viewportMinPx = min(it.width, it.height) },
    ) {
        GoogleMap(
            modifier = Modifier.fillMaxSize(),
            cameraPositionState = camera,
            properties = properties,
            uiSettings = uiSettings,
            onMapLoaded = onMapLoaded,
            onMapLongClick = { onLongPress() },
        ) {
            for (line in lines) {
                if (line.points.size < 2) continue
                Polyline(
                    points = line.points,
                    color = if (line.gnss) Gnss else Accent,
                    width = if (line.gnss) gnssWidth else drWidth,
                    jointType = JointType.ROUND,
                    startCap = RoundCap(),
                    endCap = RoundCap(),
                    zIndex = if (line.gnss) 1f else 2f,
                )
            }

            VehicleLayer(
                markerState = markerState,
                centre = centre,
                bearing = bearing,
                icon = icon,
                directional = directional,
                uncertaintyM = hud.uncertaintyM,
                modelled = modelled,
                dashed = dashed,
            )
        }

        MapLegend(
            navMode = navMode,
            headingReferenced = hud.headingReferenced,
            modifier = Modifier
                .align(Alignment.TopStart)
                .padding(10.dp),
        )

        if (!following) {
            Text(
                "RE-CENTRE",
                modifier = Modifier
                    .align(Alignment.BottomEnd)
                    .padding(12.dp)
                    .clip(RoundedCornerShape(99.dp))
                    .background(Bg.copy(alpha = 0.85f))
                    .clickable {
                        scope.launch {
                            runCatching {
                                camera.animate(
                                    CameraUpdateFactory.newLatLngZoom(
                                        LatLng(rendered[0], rendered[1]),
                                        maxOf(camera.position.zoom, FOLLOW_ZOOM),
                                    ),
                                    500,
                                )
                            }
                            following = true
                        }
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
 * The vehicle and its uncertainty, alone in their own composable ON PURPOSE.
 *
 * These are the only two things that move at the display refresh rate. Compose
 * restarts the smallest enclosing composable that read the state that changed,
 * so keeping them in a leaf means a 60 Hz animation costs two map nodes rather
 * than the whole map subtree -- which is precisely the bug that made the old
 * Canvas map feel laggy.
 */
@Composable
@GoogleMapComposable
private fun VehicleLayer(
    markerState: MarkerState,
    centre: State<LatLng>,
    bearing: FloatState,
    icon: BitmapDescriptor?,
    directional: Boolean,
    uncertaintyM: Double,
    modelled: Boolean,
    dashed: List<PatternItem>,
) {
    val here = centre.value

    if (uncertaintyDrawable(uncertaintyM)) {
        val tint = if (modelled) Amber else Gnss
        Circle(
            center = here,
            radius = uncertaintyM,
            fillColor = tint.copy(alpha = 0.10f),
            strokeColor = tint.copy(alpha = 0.60f),
            strokeWidth = 4f,
            // Dashed = modelled, solid = measured. Same convention as the
            // Canvas map and as the MEASURED / MODELLED label on the accuracy
            // card, so the three can never say different things.
            strokePattern = if (modelled) dashed else null,
            zIndex = 0.5f,
        )
    }

    Marker(
        state = markerState,
        icon = icon,
        anchor = Offset(0.5f, 0.5f),
        // Flat: the icon lies on the map and turns with it, which is what makes
        // the rotation mean a compass bearing rather than a screen angle.
        flat = true,
        rotation = if (directional) bearing.floatValue else 0f,
        zIndex = 10f,
    )
}

@Composable
private fun MapLegend(navMode: NavMode, headingReferenced: Boolean, modifier: Modifier = Modifier) {
    Column(
        modifier
            .clip(RoundedCornerShape(8.dp))
            .background(Bg.copy(alpha = 0.82f))
            .padding(horizontal = 10.dp, vertical = 8.dp),
        verticalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        LegendRow(Gnss, "GNSS TRACKED")
        LegendRow(Accent, "DEAD RECKONED")
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

/** One projected run of the track, cached against the track version. */
private data class MapPolyline(val gnss: Boolean, val points: List<LatLng>)

/** What the frame loop needs to know, snapshotted once per composition. */
private data class VehicleTarget(
    val originLat: Double,
    val originLon: Double,
    val east: Double,
    val north: Double,
    val headingDeg: Double,
)

// ---------------------------------------------------------------------------
// Device capability
// ---------------------------------------------------------------------------

/**
 * Whether Maps SDK can run at all. It is a Google Play services client, so on a
 * device without Play services -- an AOSP build, a de-Googled phone, some
 * emulator images -- the MapView draws nothing and reports no error.
 */
fun playServicesAvailable(context: Context): Boolean = runCatching {
    GoogleApiAvailability.getInstance()
        .isGooglePlayServicesAvailable(context) == ConnectionResult.SUCCESS
}.getOrDefault(false)

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
 * The vehicle icon, drawn rather than shipped as a PNG so it matches the chevron
 * on the Canvas map exactly and scales with the display density.
 *
 * [directional] false draws a dot instead: heading is not a compass bearing
 * until a GNSS bearing has referenced it, and an arrow on a north-up map is a
 * claim about the Earth that we would not be able to back up.
 */
private fun vehicleIcon(density: Float, directional: Boolean): BitmapDescriptor {
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
    return BitmapDescriptorFactory.fromBitmap(bmp)
}

/** Unused import guard: keeps [Line] referenced if the legend loses its border. */
@Suppress("unused")
private val legendHairline = Line
