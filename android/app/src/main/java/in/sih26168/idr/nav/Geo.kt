package `in`.sih26168.idr.nav

import kotlin.math.PI
import kotlin.math.asin
import kotlin.math.atan2
import kotlin.math.cos
import kotlin.math.min
import kotlin.math.sin
import kotlin.math.sqrt

const val G = 9.80665
const val DEG = PI / 180.0
const val RAD = 180.0 / PI

fun clamp(x: Double, a: Double, b: Double): Double = maxOf(a, minOf(b, x))

fun wrapPi(a: Double): Double {
    var x = ((a + PI) % (2.0 * PI) + 2.0 * PI) % (2.0 * PI) - PI
    return x
}

fun wrap360(deg: Double): Double = ((deg % 360.0) + 360.0) % 360.0

fun deg2rad(d: Double): Double = d * DEG

fun rad2deg(r: Double): Double = r * RAD

data class MetersPerDeg(val mLat: Double, val mLon: Double)

fun metersPerDeg(latDeg: Double): MetersPerDeg {
    val lat = deg2rad(latDeg)
    val mLat = 111132.92 - 559.82 * cos(2.0 * lat) + 1.175 * cos(4.0 * lat)
    val mLon = 111412.84 * cos(lat) - 93.5 * cos(3.0 * lat)
    return MetersPerDeg(mLat, mLon)
}

fun haversineM(lat1: Double, lon1: Double, lat2: Double, lon2: Double): Double {
    val r = 6_371_000.0
    val p1 = deg2rad(lat1)
    val p2 = deg2rad(lat2)
    val dp = deg2rad(lat2 - lat1)
    val dl = deg2rad(lon2 - lon1)
    val a = sin(dp / 2.0) * sin(dp / 2.0) +
        cos(p1) * cos(p2) * sin(dl / 2.0) * sin(dl / 2.0)
    return 2.0 * r * asin(min(1.0, sqrt(a)))
}

fun hypot3(x: Double, y: Double, z: Double): Double = sqrt(x * x + y * y + z * z)

/** Compass heading 0 = north, positive east (clockwise). */
fun compassDeg(yawRad: Double): Double = wrap360(rad2deg(yawRad))
