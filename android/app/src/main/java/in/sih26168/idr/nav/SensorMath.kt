package `in`.sih26168.idr.nav

import kotlin.math.atan2
import kotlin.math.cos
import kotlin.math.hypot
import kotlin.math.sin
import kotlin.math.sqrt

/**
 * Pure orientation and compass-drawing math, extracted so it can be unit
 * tested without a device. All functions here take numbers and return numbers;
 * they never touch Android SDK types.
 *
 * ## Coordinate system (standard Android device frame)
 *
 * * `+X` = right edge of phone
 * * `+Y` = top edge of phone
 * * `+Z` = out of the screen toward the user
 *
 * Gravity vector `(gx, gy, gz)` is what `TYPE_GRAVITY` / `TYPE_ACCELEROMETER`
 * reports. When the phone lies face-up flat, `g = (0, 0, +9.8)`.
 *
 * ## Screen coordinate system for [needleTip]
 *
 * Compose Canvas has `+x` right, `+y` down. "Up on screen" is therefore
 * `(0, −r)`. When the phone rotates clockwise (top of phone swings east),
 * true north sits to the left of the top of the phone, so the needle appears
 * to rotate counter-clockwise on screen. This is what most people mean by
 * "the compass points to north as I turn."
 */
object SensorMath {

    /**
     * Pitch angle in degrees from the gravity vector. Positive when the top
     * of the phone is up (e.g. held vertically in reading position).
     *
     * `pitch = atan2(−gy, sqrt(gx² + gz²))`
     */
    fun pitchFromGravity(gx: Float, gy: Float, gz: Float): Float {
        val flat = sqrt(gx * gx + gz * gz)
        return Math.toDegrees(atan2((-gy).toDouble(), flat.toDouble())).toFloat()
    }

    /**
     * Roll angle in degrees from the gravity vector. Positive when the right
     * edge of the phone is lower than the left edge.
     *
     * `roll = atan2(gx, gz)`
     */
    fun rollFromGravity(gx: Float, gy: Float, gz: Float): Float =
        Math.toDegrees(atan2(gx.toDouble(), gz.toDouble())).toFloat()

    /**
     * The tip of a compass needle that indicates true north on a screen where
     * the top of the phone is up.
     *
     * `heading` is the device's own bearing in degrees clockwise from north
     * (the standard `SensorManager.getOrientation` azimuth channel, converted
     * to degrees and wrapped into `[0, 360)`). At `heading = 0` the phone
     * points north and the needle points straight up. At `heading = 90` the
     * phone points east and the needle points to the left of the screen (true
     * north is behind the phone's left edge).
     *
     * Returned as an `(x, y)` offset from the given centre, in the same pixel
     * units as `radius`, ready to hand to `drawLine` / `drawPath`.
     */
    fun needleTip(headingDeg: Float, radius: Float): Pair<Float, Float> {
        // Screen +y is DOWN, so "up" is (0, -radius). As the phone rotates
        // clockwise (heading increases), true north on screen swings CCW —
        // the sign convention here matches SensorManager.getOrientation and
        // is unit-tested end-to-end in SensorMathTest.
        val theta = Math.toRadians(headingDeg.toDouble()).toFloat()
        val s = sin(theta.toDouble()).toFloat()
        val c = cos(theta.toDouble()).toFloat()
        val x = -radius * s
        val y = -radius * c
        return x to y
    }

    /**
     * Short-way angular delta (in degrees) from [from] to [to], wrapping the
     * 360° discontinuity so a linear smoother across the wrap does not spin
     * the needle the long way around.
     *
     * Result is in `(-180, +180]`.
     */
    fun shortWayDelta(fromDeg: Float, toDeg: Float): Float =
        ((toDeg - fromDeg + 540f) % 360f) - 180f

    /**
     * Wrap an angle into `[0, 360)`.
     */
    fun wrap360(deg: Float): Float = ((deg % 360f) + 360f) % 360f

    /**
     * Eight-point cardinal name for a bearing in degrees.
     */
    fun cardinal(headingDeg: Float): String {
        val d = wrap360(headingDeg)
        return when {
            d < 22.5f || d >= 337.5f -> "north"
            d < 67.5f -> "north-east"
            d < 112.5f -> "east"
            d < 157.5f -> "south-east"
            d < 202.5f -> "south"
            d < 247.5f -> "south-west"
            d < 292.5f -> "west"
            else -> "north-west"
        }
    }
}
