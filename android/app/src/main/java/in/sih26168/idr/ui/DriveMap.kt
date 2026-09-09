package `in`.sih26168.idr.ui

import androidx.compose.animation.core.Spring
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.spring
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.State
import androidx.compose.runtime.derivedStateOf
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.rotate
import androidx.compose.ui.graphics.drawscope.withTransform
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import `in`.sih26168.idr.data.HudState
import `in`.sih26168.idr.data.NavMode
import `in`.sih26168.idr.data.TrackSnapshot
import `in`.sih26168.idr.data.TrailPoint
import `in`.sih26168.idr.ui.theme.Accent
import `in`.sih26168.idr.ui.theme.Amber
import `in`.sih26168.idr.ui.theme.Bg
import `in`.sih26168.idr.ui.theme.Ghost
import `in`.sih26168.idr.ui.theme.IdrMono
import `in`.sih26168.idr.ui.theme.Line
import `in`.sih26168.idr.ui.theme.Mute
import `in`.sih26168.idr.ui.theme.Telem
import kotlin.math.atan2
import kotlin.math.cos
import kotlin.math.max
import kotlin.math.min
import kotlin.math.sin

/**
 * The map. Draws the track the estimator actually produced, in metres, with the
 * vehicle icon and its uncertainty circle.
 *
 * ## Why there is no basemap
 *
 * MapLibre needs tiles, and the venue has no reliable wifi. Rather than ship a
 * map that goes blank when the network does, this draws the track on a metre
 * grid with a labelled scale bar. Every distance on screen is a real measured
 * distance.
 *
 * ## What is honest here
 *
 *  * Coordinates are metres of displacement from the session origin. They are
 *    valid in every mode, including with location switched off entirely.
 *  * The north arrow appears ONLY when [HudState.headingReferenced] is true, in
 *    other words once a GNSS bearing has tied heading to true north. Before
 *    that the up axis is labelled as the direction the user was facing when
 *    they started, because that is all it is.
 *  * The uncertainty circle is drawn solid when it comes from the OS-reported
 *    GNSS accuracy and dashed when it comes from the drift model. When
 *    uncertainty is unknown, nothing is drawn -- a circle of radius zero would
 *    read as perfect accuracy.
 *  * The camera is smoothed, and only the camera. Positions are drawn where the
 *    estimator put them.
 *
 * ## Why this file is written the way it is
 *
 * This composable was the largest single source of the app feeling laggy, for
 * three compounding reasons, all now fixed and each marked in place:
 *
 *  1. **The camera springs were read in composition.** `val cx by
 *     animateFloatAsState(...)` makes the READING composable recompose on every
 *     animation frame. Five springs run here, and while the vehicle is moving
 *     they never settle, so the whole map subtree -- `BoxWithConstraints`, its
 *     content lambda, and all four `Text` overlays -- was recomposed at the
 *     display refresh rate for the whole ride. They are now held as [State] and
 *     read inside the draw lambda, so they invalidate the DRAW phase only.
 *  2. **The track `Path` was rebuilt from scratch on every draw**, in screen
 *     coordinates, from a list that grew at the full IMU rate. It is now built
 *     once per new point, in metres, and the camera is applied as a canvas
 *     transform -- which is a matrix multiply, not a rebuild.
 *  3. **The camera bounds were recomputed by scanning every point, in
 *     composition.** [TrackSnapshot] now carries a bounding box the estimator
 *     maintains incrementally.
 */
@Composable
fun DriveMap(
    hud: HudState,
    track: TrackSnapshot,
    navMode: NavMode,
    modifier: Modifier = Modifier,
    onLongPress: () -> Unit = {},
    /**
     * One honest line explaining why there is no basemap underneath,
     * e.g. "No absolute position -- showing track only". Null when there is
     * nothing to explain. Supplied by [DriveMapPanel]; a blank grey tile would
     * be worse than a grid that admits what it is.
     */
    caption: String? = null,
    /** Off by default — uncertainty correlates −0.23 with true error. */
    showUncertaintyRadius: Boolean = false,
    /** P1-1 naive double-integration track (same IMU, no ZUPT / map). */
    ghostTrack: TrackSnapshot = TrackSnapshot(),
    showGhost: Boolean = false,
) {
    val empty = track.ins.isEmpty()
    val ghostPts = ghostTrack.ins
    val ghostEmpty = ghostPts.isEmpty()
    val drawGhost = showGhost && !ghostEmpty

    // ---- Camera target: O(1), from the bounds the estimator already keeps ----
    val minE: Float
    val maxE: Float
    val minN: Float
    val maxN: Float
    if (empty && !drawGhost) {
        minE = -30f; maxE = 30f; minN = -30f; maxN = 30f
    } else {
        // The origin marker is the anchor of the story and stays in frame.
        var loE = if (empty) 0.0 else min(0.0, track.minEast)
        var hiE = if (empty) 0.0 else max(0.0, track.maxEast)
        var loN = if (empty) 0.0 else min(0.0, track.minNorth)
        var hiN = if (empty) 0.0 else max(0.0, track.maxNorth)
        if (drawGhost) {
            loE = min(loE, min(0.0, ghostTrack.minEast))
            hiE = max(hiE, max(0.0, ghostTrack.maxEast))
            loN = min(loN, min(0.0, ghostTrack.minNorth))
            hiN = max(hiN, max(0.0, ghostTrack.maxNorth))
        }
        minE = loE.toFloat()
        maxE = hiE.toFloat()
        minN = loN.toFloat()
        maxN = hiN.toFloat()
    }
    val targetCx = (minE + maxE) / 2f
    val targetCy = (minN + maxN) / 2f
    // 60 m floor stops a stationary phone from rendering at absurd zoom.
    val targetSpan = max(60f, max(maxE - minE, maxN - minN) * 1.25f)

    val camSpring = spring<Float>(dampingRatio = Spring.DampingRatioNoBouncy, stiffness = 120f)
    // Deliberately NOT `by`. See point 1 in the class note: delegating here
    // would subscribe this composable to every animation frame.
    val cxState = animateFloatAsState(targetCx, camSpring, label = "camX")
    val cyState = animateFloatAsState(targetCy, camSpring, label = "camY")
    val spanState = animateFloatAsState(targetSpan, camSpring, label = "camSpan")

    // Heading is animated through its cosine and sine so the icon does not spin
    // the long way round when the bearing wraps through 360.
    val hdgRad = (hud.headingDeg * Math.PI / 180.0).toFloat()
    val iconSpring = spring<Float>(dampingRatio = Spring.DampingRatioNoBouncy, stiffness = 300f)
    val hcState = animateFloatAsState(cos(hdgRad), iconSpring, label = "hc")
    val hsState = animateFloatAsState(sin(hdgRad), iconSpring, label = "hs")

    // ---- Cached geometry, in METRES. Rebuilt once per appended point. -------
    val insPath = remember(track.version) { worldPath(track.ins) }
    val gnssPath = remember(track.version) { worldPath(track.gnss) }
    val ghostPath = remember(ghostTrack.version) { worldPath(ghostPts) }

    BoxWithConstraints(
        modifier
            .background(Bg, RoundedCornerShape(16.dp))
            .pointerInput(Unit) {
                detectTapGestures(onLongPress = { onLongPress() })
            },
    ) {
        val density = LocalDensity.current
        val wPx = with(density) { maxWidth.toPx() }
        val hPx = with(density) { maxHeight.toPx() }
        val viewPx = min(wPx, hPx)

        // The scale bar label is the one thing outside the Canvas that depends
        // on the zoom spring. derivedStateOf keeps it from recomposing on every
        // frame: niceStep is quantised to 1/2/5 x 10^n, so the value it reads
        // changes a handful of times over a whole ride.
        val barMetres by remember(viewPx) {
            derivedStateOf { niceStep(90f / scaleFor(spanState.value, viewPx)) }
        }
        val barVisible by remember(viewPx) {
            derivedStateOf {
                val px = barMetres * scaleFor(spanState.value, viewPx)
                px.isFinite() && px >= 12f
            }
        }

        Canvas(Modifier.fillMaxSize()) {
            val w = size.width
            val h = size.height
            if (w <= 0f || h <= 0f) return@Canvas

            // Reading the springs HERE keeps them in the draw phase.
            val cx = cxState.value
            val cy = cyState.value
            val scale = scaleFor(spanState.value, min(w, h))
            val drawHeadingDeg =
                (atan2(hsState.value, hcState.value) * 180.0 / Math.PI).toFloat()

            fun px(e: Float, n: Float) = Offset(
                w / 2f + (e - cx) * scale,
                h / 2f - (n - cy) * scale,
            )

            drawMetreGrid(w, h, scale, cx, cy)

            // ---- Track ---------------------------------------------------
            // The paths are in metres; the camera is a transform, so panning and
            // zooming costs a matrix, not a rebuild of thousands of segments.
            // Stroke widths are divided by the scale so they stay constant on
            // screen rather than growing with zoom.
            if (track.ins.size >= 2 || track.gnss.size >= 2 || (drawGhost && ghostPts.size >= 2)) {
                withTransform({
                    translate(w / 2f - cx * scale, h / 2f + cy * scale)
                    scale(scale, -scale, pivot = Offset.Zero)
                }) {
                    // Ghost trail under COAST so the teal line stays readable.
                    if (drawGhost && ghostPts.size >= 2) {
                        drawPath(
                            ghostPath,
                            Ghost.copy(alpha = 0.35f),
                            style = Stroke(width = 5f / scale, cap = StrokeCap.Round),
                        )
                    }
                    if (track.ins.size >= 2) {
                        drawPath(
                            insPath,
                            Accent,
                            style = Stroke(width = 7f / scale, cap = StrokeCap.Round),
                        )
                    }
                    // GNSS track over the top, so a judge can see the two diverge.
                    if (track.gnss.size >= 2) {
                        drawPath(
                            gnssPath,
                            Telem.copy(alpha = 0.7f),
                            style = Stroke(
                                width = 4f / scale,
                                cap = StrokeCap.Round,
                                pathEffect = PathEffect.dashPathEffect(
                                    floatArrayOf(12f / scale, 10f / scale),
                                ),
                            ),
                        )
                    }
                }
            }

            // ---- Origin marker -------------------------------------------
            if (!empty || drawGhost) {
                val o = px(0f, 0f)
                drawCircle(Mute, 9f, o, style = Stroke(width = 3f))
                drawLine(Mute, Offset(o.x - 14f, o.y), Offset(o.x + 14f, o.y), 2f)
                drawLine(Mute, Offset(o.x, o.y - 14f), Offset(o.x, o.y + 14f), 2f)
            }

            // ---- Ghost puck (P1-1) ----------------------------------------
            if (drawGhost) {
                val tip = ghostPts.last()
                val ghostHere = px(tip.east.toFloat(), tip.north.toFloat())
                drawCircle(Ghost.copy(alpha = 0.22f), 22f, ghostHere)
                drawCircle(Ghost, 9f, ghostHere)
                drawCircle(Color.White.copy(alpha = 0.85f), 9f, ghostHere, style = Stroke(width = 2f))
            }

            // ---- Vehicle + uncertainty -----------------------------------
            if (!empty || navMode != NavMode.IDLE) {
                val here = px(hud.east.toFloat(), hud.north.toFloat())
                val r = hud.uncertaintyM
                // Debug-only: the modelled radius is anti-correlated with error.
                if (showUncertaintyRadius && r.isFinite() && r > 0.0) {
                    val rp = (r * scale).toFloat()
                    // Do not paint the whole viewport when the circle grows huge;
                    // the number beside the map still tells the truth.
                    if (rp in 2f..(max(w, h) * 1.5f)) {
                        val modelled = navMode != NavMode.GNSS
                        val tint = if (modelled) Amber else Telem
                        drawCircle(tint.copy(alpha = 0.10f), rp, here)
                        drawCircle(
                            tint.copy(alpha = 0.55f),
                            rp,
                            here,
                            style = if (modelled) {
                                Stroke(
                                    width = 3f,
                                    pathEffect = PathEffect.dashPathEffect(floatArrayOf(14f, 10f)),
                                )
                            } else {
                                Stroke(width = 3f)
                            },
                        )
                    }
                }
                drawVehicle(here, drawHeadingDeg)
            }

            drawScaleBar(h, barMetres * scale)
            if (hud.headingReferenced) drawNorthArrow(w)
        }

        // ---- Overlays ----------------------------------------------------
        if (drawGhost) {
            Column(
                Modifier
                    .align(Alignment.TopStart)
                    .padding(10.dp)
                    .background(Bg.copy(alpha = 0.82f), RoundedCornerShape(8.dp))
                    .padding(horizontal = 10.dp, vertical = 8.dp),
            ) {
                Text(
                    "naive DR (no map)",
                    color = Ghost,
                    fontFamily = IdrMono,
                    fontSize = 9.sp,
                    letterSpacing = 0.6.sp,
                )
                Text(
                    "COAST",
                    color = Accent,
                    fontFamily = IdrMono,
                    fontSize = 9.sp,
                    letterSpacing = 0.6.sp,
                )
            }
        }

        if (barVisible) {
            Text(
                if (barMetres >= 1000f) "%.0f km".format(barMetres / 1000f) else "%.0f m".format(barMetres),
                modifier = Modifier
                    .align(Alignment.BottomStart)
                    .padding(start = 8.dp, bottom = 22.dp),
                color = Mute,
                fontFamily = IdrMono,
                fontSize = 10.sp,
            )
        }

        if (!hud.headingReferenced && navMode != NavMode.IDLE) {
            Text(
                "UP = THE WAY YOU WERE FACING AT START (no north reference yet)",
                modifier = Modifier
                    .align(Alignment.TopStart)
                    .padding(
                        start = 10.dp,
                        top = if (drawGhost) 56.dp else 10.dp,
                        end = 10.dp,
                    )
                    .background(Amber.copy(alpha = 0.16f), RoundedCornerShape(6.dp))
                    .padding(horizontal = 10.dp, vertical = 6.dp),
                color = Amber,
                fontFamily = IdrMono,
                fontSize = 9.sp,
                letterSpacing = 0.8.sp,
            )
        }

        if (empty && !drawGhost) {
            Text(
                if (navMode == NavMode.IDLE) {
                    "Press START to begin tracking"
                } else {
                    "Waiting for motion"
                },
                modifier = Modifier.align(Alignment.Center),
                color = Mute,
                fontFamily = IdrMono,
                fontSize = 13.sp,
            )
        }

        Text(
            if (navMode == NavMode.RELATIVE) {
                "displacement from your start · offline"
            } else {
                "metre grid · no basemap · offline"
            },
            modifier = Modifier
                .align(Alignment.BottomEnd)
                .padding(10.dp),
            color = Color(0xFF6C7885),
            fontFamily = IdrMono,
            fontSize = 9.sp,
        )
    }
}

/** Pixels per metre for a given span across the shorter viewport edge. */
private const val MAP_PAD_PX = 24f

private fun scaleFor(span: Float, viewPx: Float): Float =
    if (span > 0f) (viewPx - 2 * MAP_PAD_PX) / span else 1f

/**
 * A polyline in METRES (east = +x, north = +y). Built once per track version
 * and reused across every animation frame; the camera is applied as a transform.
 */
private fun worldPath(points: List<TrailPoint>): Path {
    val path = Path()
    if (points.size < 2) return path
    var started = false
    points.forEach { p ->
        val x = p.east.toFloat()
        val y = p.north.toFloat()
        if (!started) {
            path.moveTo(x, y)
            started = true
        } else {
            path.lineTo(x, y)
        }
    }
    return path
}

/** Grid whose spacing is a round number of metres for the current zoom. */
private fun DrawScope.drawMetreGrid(w: Float, h: Float, scale: Float, cx: Float, cy: Float) {
    val stepM = niceStep(60f / scale)
    val stepPx = stepM * scale
    if (stepPx < 8f || !stepPx.isFinite()) return
    // Offset so the grid is anchored to whole metres, not to the viewport.
    val originX = w / 2f - cx * scale
    val originY = h / 2f + cy * scale
    var x = originX % stepPx
    while (x < w) {
        drawLine(Line, Offset(x, 0f), Offset(x, h), 1f)
        x += stepPx
    }
    var y = originY % stepPx
    while (y < h) {
        drawLine(Line, Offset(0f, y), Offset(w, y), 1f)
        y += stepPx
    }
}

/** 1 / 2 / 5 x 10^n, so the grid and scale bar are always round numbers. */
private fun niceStep(raw: Float): Float {
    if (!raw.isFinite() || raw <= 0f) return 10f
    var mag = 1f
    var v = raw
    while (v >= 10f) { v /= 10f; mag *= 10f }
    while (v < 1f) { v *= 10f; mag /= 10f }
    val unit = when {
        v < 1.5f -> 1f
        v < 3.5f -> 2f
        v < 7.5f -> 5f
        else -> 10f
    }
    return unit * mag
}

private fun DrawScope.drawScaleBar(h: Float, lenPx: Float) {
    if (!lenPx.isFinite() || lenPx < 12f || lenPx > size.width * 0.6f) return
    val y = h - 26f
    val x0 = 24f
    drawLine(Mute, Offset(x0, y), Offset(x0 + lenPx, y), 3f)
    drawLine(Mute, Offset(x0, y - 6f), Offset(x0, y + 6f), 3f)
    drawLine(Mute, Offset(x0 + lenPx, y - 6f), Offset(x0 + lenPx, y + 6f), 3f)
}

private fun DrawScope.drawNorthArrow(w: Float) {
    val x = w - 30f
    drawLine(Telem, Offset(x, 44f), Offset(x, 18f), 3f)
    val head = Path().apply {
        moveTo(x, 12f)
        lineTo(x - 6f, 24f)
        lineTo(x + 6f, 24f)
        close()
    }
    drawPath(head, Telem)
}

/**
 * The vehicle. A chevron rather than a dot so heading is readable at a glance,
 * with a soft halo so it stays visible over the track and the grid.
 */
private fun DrawScope.drawVehicle(at: Offset, headingDeg: Float) {
    drawCircle(Accent.copy(alpha = 0.18f), 26f, at)
    rotate(degrees = headingDeg, pivot = at) {
        val body = Path().apply {
            moveTo(at.x, at.y - 20f)
            lineTo(at.x + 13f, at.y + 16f)
            lineTo(at.x, at.y + 8f)
            lineTo(at.x - 13f, at.y + 16f)
            close()
        }
        drawPath(body, Color.White)
        drawPath(body, Accent, style = Stroke(width = 3f))
    }
}
