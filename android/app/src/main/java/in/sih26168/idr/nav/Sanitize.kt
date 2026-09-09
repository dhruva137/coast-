package `in`.sih26168.idr.nav

/**
 * Hold-last-good sanitizer for estimator outputs.
 *
 * Pattern matches [in.sih26168.idr.ui.uncertaintyDrawable]: NaN / Inf are not
 * drawable values. When a sample is non-finite we keep the previous good value
 * so the HUD never flashes garbage mid-ride.
 */
class SanitizeGate(initial: Double = 0.0) {
    var lastGood: Double = initial
        private set

    fun accept(value: Double): Double {
        if (value.isFinite()) {
            lastGood = value
            return value
        }
        return lastGood
    }

    fun reset(value: Double = 0.0) {
        lastGood = value
    }
}

/** Drop a whole IMU sample when any primary channel is non-finite. */
fun sensorFrameChannelsFinite(
    ax: Double, ay: Double, az: Double,
    gx: Double, gy: Double, gz: Double,
): Boolean =
    ax.isFinite() && ay.isFinite() && az.isFinite() &&
        gx.isFinite() && gy.isFinite() && gz.isFinite()
