package `in`.sih26168.idr.nav

/**
 * Fixed-point coordinated-turn lean solver [F5].
 *
 * Port of `core/ts/src/leansolver/index.ts`. Do not fork the maths.
 *
 * Textbook kinematics (Titterton & Weston) — we claim the APPLICATION
 * to smartphone two-wheeler dead reckoning, not the discovery:
 *
 *   ω_body = [ φ̇ , ψ̇ sin φ , ψ̇ cos φ ]
 *   ψ̇     = ω_y sin φ + ω_z cos φ          [exact, F2]
 *   φ      = arctan( v · ψ̇ / g )            [coordinated turn]
 *
 * Substitute F2 into the coordinated-turn relation and iterate.
 * Converges in 3–5 iterations. Lean RMSE 0.5–1.0° in simulation.
 *
 * Insensitivity [F6]: ψ̇_est = ψ̇ · cos(φ − φ̂)
 * Scale error depends on LEAN ERROR, not lean angle. 10° lean error → 1.5%
 * heading-rate error even at 40° lean (car-style is 23%).
 */
data class LeanObservation(
    /** Body gyro, rad/s */
    val gy: Double,
    val gz: Double,
    val gx: Double = 0.0,
    /** Forward speed, m/s (from learned odometry or GNSS) */
    val speed: Double,
    /** Optional previous lean for warm start */
    val phi0: Double? = null,
)

data class LeanSolution(
    val phi: Double,
    val psiDot: Double,
    val phiDot: Double,
    val iterations: Int,
    val residual: Double,
    val coordinated: Boolean,
)

private const val MAX_ITERS = 8
private const val TOL = 1e-9

fun yawRateFromLean(gy: Double, gz: Double, phi: Double): Double {
    return gy * kotlin.math.sin(phi) + gz * kotlin.math.cos(phi)
}

/** Car-style (WRONG on two-wheelers): ψ̇ ≈ ω_z */
fun carStyleYawRate(gz: Double): Double = gz

/**
 * Solve φ = arctan( v (ω_y sin φ + ω_z cos φ) / g ) by fixed-point iteration.
 * Returns 0 lean when nearly stopped (no observability).
 */
fun solveLean(obs: LeanObservation): LeanSolution {
    val v = maxOf(0.0, obs.speed)
    val gy = obs.gy
    val gz = obs.gz
    val gx = obs.gx

    if (v < 0.4) {
        return LeanSolution(
            phi = 0.0,
            psiDot = gz,
            phiDot = gx,
            iterations = 0,
            residual = 0.0,
            coordinated = false,
        )
    }

    var phi = obs.phi0 ?: kotlin.math.atan2(v * gz, G)
    phi = clamp(phi, -1.2, 1.2)
    var residual = 1.0
    var i = 0
    while (i < MAX_ITERS) {
        val psiDot = yawRateFromLean(gy, gz, phi)
        val next = kotlin.math.atan2(v * psiDot, G)
        residual = kotlin.math.abs(wrapPi(next - phi))
        phi = next
        if (residual < TOL) {
            i += 1
            break
        }
        i += 1
    }
    val psiDot = yawRateFromLean(gy, gz, phi)
    return LeanSolution(
        phi = phi,
        psiDot = psiDot,
        phiDot = gx,
        iterations = i,
        residual = residual,
        coordinated = kotlin.math.abs(v * psiDot) > 0.15,
    )
}

/** Closed-form check: ψ̇_est / ψ̇_true = cos(Δφ)  [F6] */
fun headingRateScaleError(dPhi: Double): Double = kotlin.math.cos(dPhi)

/**
 * Integrate heading with the lean-aware yaw rate.
 * Car-style uses gz only — diverges by cos(lean) on every turn.
 */
fun stepHeading(
    yaw: Double,
    dt: Double,
    gy: Double,
    gz: Double,
    phi: Double,
    leanAware: Boolean,
): Double {
    val psiDot = if (leanAware) yawRateFromLean(gy, gz, phi) else gz
    return wrapPi(yaw + psiDot * dt)
}
