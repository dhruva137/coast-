package `in`.sih26168.idr.nav

/**
 * Multi-level car-park floor changes from barometric pressure ([SensorFrame.pressureHpa]).
 *
 * Near sea level ≈ 1 hPa per 8.3 m; one storey ≈ 3–3.5 m ≈ 0.36–0.42 hPa. Weather
 * drifts slowly; this detector looks for a **sustained step** relative to the
 * pressure locked at the last accepted floor — not an absolute altitude.
 *
 * Samples with non-finite or non-positive pressure are ignored (no baro / cold start).
 */
class BaroFloorDetector(
    /** Minimum |ΔP| to treat as one floor. */
    private val stepHpa: Double = 0.40,
    /** EMA coefficient on raw pressure (0–1). Lower = more weather rejection. */
    private val smoothAlpha: Double = 0.08,
    /** How long |ΔP| must stay past [stepHpa] before accepting a floor. */
    private val holdNs: Long = 1_500_000_000L,
    /** UI "recent change" window. */
    private val recentNs: Long = 15_000_000_000L,
) {
    private var smoothed = Double.NaN
    private var floorPressure = Double.NaN
    private var candidateSign = 0
    private var candidateSinceNs = 0L

    /** Relative floor index; 0 at first valid lock. Up = lower pressure. */
    var floorIndex: Int = 0
        private set

    /** True once any floor step has been accepted this session. */
    var changedThisSession: Boolean = false
        private set

    private var lastChangeNs: Long = 0L

    val pressureHpa: Double
        get() = smoothed

    val deltaFromFloorHpa: Double
        get() = if (smoothed.isFinite() && floorPressure.isFinite()) {
            smoothed - floorPressure
        } else {
            Double.NaN
        }

    fun reset() {
        smoothed = Double.NaN
        floorPressure = Double.NaN
        candidateSign = 0
        candidateSinceNs = 0L
        floorIndex = 0
        changedThisSession = false
        lastChangeNs = 0L
    }

    /** True if a floor step was accepted within [recentNs] of [nowNs]. */
    fun recentlyChanged(nowNs: Long): Boolean {
        if (lastChangeNs == 0L) return false
        val age = nowNs - lastChangeNs
        return age in 0L until recentNs
    }

    /**
     * Feed one pressure sample. Returns true when a floor step is accepted.
     */
    fun onPressure(tNs: Long, pressureHpa: Double): Boolean {
        if (!pressureHpa.isFinite() || pressureHpa <= 0.0) return false

        smoothed = if (!smoothed.isFinite()) {
            pressureHpa
        } else {
            smoothAlpha * pressureHpa + (1.0 - smoothAlpha) * smoothed
        }

        if (!floorPressure.isFinite()) {
            floorPressure = smoothed
            return false
        }

        val delta = smoothed - floorPressure
        val sign = when {
            delta >= stepHpa -> 1   // higher P → descended a floor
            delta <= -stepHpa -> -1 // lower P → ascended a floor
            else -> 0
        }

        if (sign == 0) {
            candidateSign = 0
            candidateSinceNs = 0L
            return false
        }

        if (sign != candidateSign) {
            candidateSign = sign
            candidateSinceNs = tNs
            return false
        }

        if (candidateSinceNs == 0L) {
            candidateSinceNs = tNs
            return false
        }

        if (tNs - candidateSinceNs < holdNs) return false

        // Accept: re-lock baseline at the smoothed pressure so the next storey
        // needs another full stepHpa (and we avoid ±step float edge cases).
        floorPressure = smoothed
        floorIndex -= sign // lower pressure → higher floor index
        changedThisSession = true
        lastChangeNs = tNs
        candidateSign = 0
        candidateSinceNs = 0L
        return true
    }

    fun note(nowNs: Long): String {
        if (!smoothed.isFinite()) return "no barometer pressure yet"
        val d = deltaFromFloorHpa
        val dStr = if (d.isFinite()) "%+.2f hPa vs floor lock".format(d) else "--"
        return when {
            recentlyChanged(nowNs) -> "FLOOR CHANGED → relative floor $floorIndex ($dStr)"
            changedThisSession -> "relative floor $floorIndex ($dStr)"
            else -> "floor lock @ %.2f hPa · $dStr".format(floorPressure)
        }
    }
}
