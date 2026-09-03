package `in`.sih26168.idr.ui

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import `in`.sih26168.idr.data.HudState
import `in`.sih26168.idr.nav.metersPerDeg
import `in`.sih26168.idr.ui.theme.Accent
import `in`.sih26168.idr.ui.theme.Amber
import `in`.sih26168.idr.ui.theme.Bg
import `in`.sih26168.idr.ui.theme.IdrMono
import `in`.sih26168.idr.ui.theme.Line
import `in`.sih26168.idr.ui.theme.Telem
import kotlin.math.max
import kotlin.math.min

/**
 * Offline map placeholder (no paid SDK). Swap for MapLibre Native + MBTiles
 * later — see comments in app/build.gradle.kts.
 */
@Composable
fun TrailMap(
    hud: HudState,
    modifier: Modifier = Modifier,
) {
    val gnssDenied = !hud.gnssLock
    Box(modifier.background(Bg, RoundedCornerShape(12.dp))) {
        Canvas(Modifier.fillMaxSize()) {
            val w = size.width
            val h = size.height
            // Instrument grid
            val step = 48f
            var x = 0f
            while (x < w) {
                drawLine(Line, Offset(x, 0f), Offset(x, h), 1f)
                x += step
            }
            var y = 0f
            while (y < h) {
                drawLine(Line, Offset(0f, y), Offset(w, y), 1f)
                y += step
            }

            val pts = hud.insTrail + hud.gnssTrail
            if (pts.size >= 1) {
                val origin = pts.first()
                val mpd = metersPerDeg(origin.lat)
                fun toEnu(lat: Double, lon: Double): Pair<Float, Float> {
                    val e = ((lon - origin.lon) * mpd.mLon).toFloat()
                    val n = ((lat - origin.lat) * mpd.mLat).toFloat()
                    return e to n
                }
                val enu = pts.map { toEnu(it.lat, it.lon) }
                var minE = Float.POSITIVE_INFINITY
                var maxE = Float.NEGATIVE_INFINITY
                var minN = Float.POSITIVE_INFINITY
                var maxN = Float.NEGATIVE_INFINITY
                enu.forEach { (e, n) ->
                    minE = min(minE, e); maxE = max(maxE, e)
                    minN = min(minN, n); maxN = max(maxN, n)
                }
                val spanE = max(12f, maxE - minE)
                val spanN = max(12f, maxN - minN)
                val pad = 36f
                val sx = (w - 2 * pad) / spanE
                val sy = (h - 2 * pad) / spanN
                val s = min(sx, sy)
                fun xy(e: Float, n: Float): Offset {
                    val px = pad + (e - minE) * s
                    val py = h - pad - (n - minN) * s
                    return Offset(px, py)
                }

                fun stroke(color: Color, trail: List<Pair<Float, Float>>) {
                    if (trail.size < 2) return
                    val path = Path()
                    val first = xy(trail[0].first, trail[0].second)
                    path.moveTo(first.x, first.y)
                    for (i in 1 until trail.size) {
                        val p = xy(trail[i].first, trail[i].second)
                        path.lineTo(p.x, p.y)
                    }
                    drawPath(path, color, style = Stroke(width = 4f, cap = StrokeCap.Round))
                }

                val gnssEnu = hud.gnssTrail.map { toEnu(it.lat, it.lon) }
                val insEnu = hud.insTrail.map { toEnu(it.lat, it.lon) }
                stroke(Telem.copy(alpha = 0.85f), gnssEnu)
                stroke(Accent, insEnu)

                if (insEnu.isNotEmpty()) {
                    val last = insEnu.last()
                    val c = xy(last.first, last.second)
                    drawCircle(Accent.copy(alpha = 0.25f), 16f, c)
                    drawCircle(Accent, 6f, c)
                }
            }

            // North tick
            drawLine(Telem, Offset(w - 28f, 36f), Offset(w - 28f, 18f), 3f)
        }

        if (gnssDenied) {
            val sec = if (hud.outageSec.isFinite()) "%.1f".format(hud.outageSec) else "—"
            Text(
                text = "GNSS DENIED  ·  coasting INS  ·  ${sec}s",
                modifier = Modifier
                    .align(Alignment.TopCenter)
                    .padding(10.dp)
                    .background(Amber.copy(alpha = 0.18f), RoundedCornerShape(6.dp))
                    .padding(horizontal = 12.dp, vertical = 6.dp),
                color = Amber,
                fontFamily = IdrMono,
                fontSize = 11.sp,
                letterSpacing = 1.1.sp,
            )
        }

        Text(
            "CANVAS MAP · MapLibre optional",
            modifier = Modifier
                .align(Alignment.BottomStart)
                .padding(10.dp),
            color = Color(0xFF8B98A5),
            fontFamily = IdrMono,
            fontSize = 9.sp,
            letterSpacing = 1.sp,
        )
    }
}
