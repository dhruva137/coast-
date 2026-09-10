package `in`.sih26168.idr.nav

import `in`.sih26168.idr.data.NavMode

/**
 * Drop-in slot for the graph particle filter (map-in-loop).
 *
 * The shipped APK always has [SimpleIns] as FREE-DR. A later native library
 * named [NATIVE_LIB] implements this same contract and can be loaded without
 * touching Compose, pairing, or the Drive shell.
 *
 * **Particle spread is not confidence.** Never copy [GraphPfEstimate.spreadM]
 * onto [in.sih26168.idr.data.HudState.uncertaintyM] — that radius is the
 * modelled GNSS/DR growth term, not a PF cloud.
 */
data class GraphPfEstimate(
    val eastM: Double,
    val northM: Double,
    val headingRad: Double,
    /** Diagnostic only. Do not treat as a confidence / accuracy radius. */
    val spreadM: Double = Double.NaN,
)

interface GraphPfEngine {
    fun seed(eastM: Double, northM: Double, headingRad: Double, tNs: Long)
    fun step(dtSec: Double, speedMps: Double, yawRateRadS: Double, tNs: Long)
    fun estimate(): GraphPfEstimate?
    fun reset()

    companion object {
        const val LABEL_MAP_PF = "MAP-PF"
        const val LABEL_FREE_DR = "FREE-DR"
        const val LABEL_RELATIVE = "RELATIVE"
        const val NATIVE_LIB = "coast_graph_pf"

        /**
         * Load the native filter if the APK ships it. JVM unit tests and the
         * current APK both get null and stay on [SimpleIns].
         */
        fun tryLoad(): GraphPfEngine? = NativeGraphPfEngine.loadOrNull()

        fun hudLabel(engine: GraphPfEngine?, navMode: NavMode): String {
            if (navMode == NavMode.RELATIVE || navMode == NavMode.IDLE) {
                return LABEL_RELATIVE
            }
            if (engine != null) return LABEL_MAP_PF
            return LABEL_FREE_DR
        }
    }
}

/**
 * JNI stub. `seed` / `step` / `estimate` stay no-ops until `libcoast_graph_pf`
 * is packaged. [loadOrNull] never throws — missing native code is the
 * expected baseline.
 */
internal class NativeGraphPfEngine private constructor() : GraphPfEngine {
    private var seeded = false

    override fun seed(eastM: Double, northM: Double, headingRad: Double, tNs: Long) {
        seeded = nativeSeed(eastM, northM, headingRad, tNs)
    }

    override fun step(dtSec: Double, speedMps: Double, yawRateRadS: Double, tNs: Long) {
        if (!seeded) return
        nativeStep(dtSec, speedMps, yawRateRadS, tNs)
    }

    override fun estimate(): GraphPfEstimate? {
        if (!seeded) return null
        return nativeEstimate()
    }

    override fun reset() {
        seeded = false
        nativeReset()
    }

    private external fun nativeSeed(eastM: Double, northM: Double, headingRad: Double, tNs: Long): Boolean
    private external fun nativeStep(dtSec: Double, speedMps: Double, yawRateRadS: Double, tNs: Long)
    private external fun nativeEstimate(): GraphPfEstimate?
    private external fun nativeReset()

    companion object {
        fun loadOrNull(): GraphPfEngine? {
            return try {
                System.loadLibrary(GraphPfEngine.NATIVE_LIB)
                NativeGraphPfEngine()
            } catch (_: UnsatisfiedLinkError) {
                null
            } catch (_: SecurityException) {
                null
            }
        }
    }
}
