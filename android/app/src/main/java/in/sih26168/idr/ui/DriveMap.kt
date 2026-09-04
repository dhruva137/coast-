package `in`.sih26168.idr.ui

import androidx.compose.animation.core.Spring
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.spring
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
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
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import `in`.sih26168.idr.data.HudState
import `in`.sih26168.idr.data.NavMode
import `in`.sih26168.idr.ui.theme.Accent
import `in`.sih26168.idr.ui.theme.Amber
import `in`.sih26168.idr.ui.theme.Bg
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
 */
@Composable
fun DriveMap(
    hud: HudState,
    modifier: Modifier = Modifier,
    onLongPress: () -> Unit = {},
) {
    val pts = hud.insTrail

    // ---- Camera: fit the track, then follow it with a critically damped spring.
    var minE = -30f
    var maxE = 30f
    var minN = -30f
    var maxN = 30f
    if (pts.isNotEmpty()) {
        minE = Float.POSITIVE_INFINITY; maxE = Float.NEGATIVE_INFINITY
        minN = Float.POSITIVE_INFINITY; maxN = Float.NEGATIVE_INFINITY
        pts.forEach { p ->
            val e = p.east.toFloat()
            val n = p.north.toFloat()
            minE = min(minE, e); maxE = max(maxE, e)
            minN = min(minN, n); maxN = max(maxN, n)
        }
        // Always keep the origin marker in frame; it is the anchor of the story.
        minE = min(minE, 0f); maxE = max(maxE, 0f)
        minN = min(minN, 0f); maxN = max(maxN, 0f)
    }
    val targetCx = (minE + maxE) / 2f
    val targetCy = (minN + maxN) / 2f
    // 60 m floor stops a stationary phone from rendering at absurd zoom.
    val targetSpan = max(60f, max(maxE - minE, maxN - minN) * 1.25f)

    val camSpring = spring<Float>(dampingRatio = Spring.DampingRatioNoBouncy, stiffness = 120f)
    val cx by animateFloatAsState(targetCx, camSpring, label = "camX")
    val cy by animateFloatAsState(targetCy, camSpring, label = "camY")
    val span by animateFloatAsState(targetSpan, camSpring, label = "camSpan")

    // Heading is animated through its cosine and sine so the icon does not spin
    // the long way round when the bearing wraps through 360.
    val hdgRad = (hud.headingDeg * Math.PI / 180.0).toFloat()
    val iconSpring = spring<Float>(dampingRatio = Spring.DampingRatioNoBouncy, stiffness = 300f)
    val hc by animateFloatAsState(cos(hdgRad), iconSpring, label = "hc")
    val hs by animateFloatAsState(sin(hdgRad), iconSpring, label = "hs")
    val drawHeadingDeg = (atan2(hs, hc) * 180.0 / Math.PI).toFloat()

    BoxWithConstraints(
        modifier
            .background(Bg, RoundedCornerShape(16.dp))
            .pointerInput(Unit) {
                detectTapGestures(onLongPress = { onLongPress() })
            },
    ) {
        // Recompute the scale outside the DrawScope so the scale bar can be
        // labelled with a real number rather than drawn as an unlabelled stick.
        val density = LocalDensity.current
        val wPx = with(density) { maxWidth.toPx() }
        val hPx = with(density) { maxHeight.toPx() }
        val pad = 24f
        val scale = if (span > 0f) (min(wPx, hPx) - 2 * pad) / span else 1f
        val barMetres = niceStep(90f / scale)
        val barPx = barMetres * scale

        Canvas(Modifier.fillMaxSize()) {
            val w = size.width
            val h = size.height
            if (w <= 0f || h <= 0f) return@Canvas

            fun px(e: Float, n: Float) = Offset(
                w / 2f + (e - cx) * scale,
                h / 2f - (n - cy) * scale,
            )

            drawMetreGrid(w, h, scale, cx, cy)

            // ---- Track ---------------------------------------------------
            if (pts.size >= 2) {
                val path = Path()
                var started = false
                pts.forEach { p ->
                    val o = px(p.east.toFloat(), p.north.toFloat())
                    if (!started) {
                        path.moveTo(o.x, o.y)
                        started = true
                    } else {
                        path.lineTo(o.x, o.y)
                    }
                }
                drawPath(path, Accent, style = Stroke(width = 7f, cap = StrokeCap.Round))
            }
            // GNSS track over the top, so a judge can see the two diverge.
            val g = hud.gnssTrail
            if (g.size >= 2) {
                val path = Path()
                var started = false
                g.forEach { p ->
                    val o = px(p.east.toFloat(), p.north.toFloat())
                    if (!started) {
                        path.moveTo(o.x, o.y)
                        started = true
                    } else {
                        path.lineTo(o.x, o.y)
                    }
                }
                drawPath(
                    path,
                    Telem.copy(alpha = 0.7f),
                    style = Stroke(
                        width = 4f,
                        cap = StrokeCap.Round,
                        pathEffect = PathEffect.dashPathEffect(floatArrayOf(12f, 10f)),
                    ),
                )
            }

            // ---- Origin marker -------------------------------------------
            if (pts.isNotEmpty()) {
                val o = px(0f, 0f)
                drawCircle(Mute, 9f, o, style = Stroke(width = 3f))
                drawLine(Mute, Offset(o.x - 14f, o.y), Offset(o.x + 14f, o.y), 2f)
                drawLine(Mute, Offset(o.x, o.y - 14f), Offset(o.x, o.y + 14f), 2f)
            }

            // ---- Vehicle + uncertainty -----------------------------------
            if (pts.isNotEmpty() || hud.navMode != NavMode.IDLE) {
                val here = px(hud.east.toFloat(), hud.north.toFloat())
                val r = hud.uncertaintyM
                if (r.isFinite() && r > 0.0) {
                    val rp = (r * scale).toFloat()
                    // Do not paint the whole viewport when the circle grows huge;
                    // the number beside the map still tells the truth.
                    if (rp in 2f..(max(w, h) * 1.5f)) {
                        val modelled = hud.navMode != NavMode.GNSS
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

            drawScaleBar(h, barPx)
            if (hud.headingReferenced) drawNorthArrow(w)
        }

        // ---- Overlays ----------------------------------------------------
        if (barPx.isFinite() && barPx >= 12f) {
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

        if (!hud.headingReferenced && hud.navMode != NavMode.IDLE) {
            Text(
                "UP = THE WAY YOU WERE FACING AT START (no north reference yet)",
                modifier = Modifier
                    .align(Alignment.TopStart)
                    .padding(10.dp)
                    .background(Amber.copy(alpha = 0.16f), RoundedCornerShape(6.dp))
                    .padding(horizontal = 10.dp, vertical = 6.dp),
                color = Amber,
                fontFamily = IdrMono,
                fontSize = 9.sp,
                letterSpacing = 0.8.sp,
            )
        }

        if (pts.isEmpty()) {
            Text(
                if (hud.navMode == NavMode.IDLE) {
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
            if (hud.navMode == NavMode.RELATIVE) {
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
