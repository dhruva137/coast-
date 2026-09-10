package `in`.sih26168.idr.ui

import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.AnimationVector1D
import androidx.compose.animation.core.Spring
import androidx.compose.animation.core.spring
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.MutableState
import androidx.compose.runtime.Stable
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import `in`.sih26168.idr.IdrBus
import `in`.sih26168.idr.data.HudState
import kotlin.math.abs
import kotlin.math.sqrt
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.launch

/**
 * Snap instead of interpolating when a fix jumps farther than this (metres).
 * A GNSS re-acquisition after a long coast is a real discontinuity; sliding
 * across it would invent a path the vehicle never took.
 */
internal const val MARKER_TELEPORT_M = 30f

/**
 * Critically damped spring between ~10 Hz fixes.
 *
 * Settling time for a unit-mass spring is ~4 / sqrt(stiffness). 800 → ~140 ms,
 * in the 100–180 ms Uber-like window. 280 felt laggy; 1500+ reads as a teleport.
 */
internal val MarkerSpring = spring<Float>(
    dampingRatio = Spring.DampingRatioNoBouncy,
    stiffness = 800f,
)

/**
 * Stable handle to the HUD flow so a parent that recomposes at 10 Hz can still
 * *skip* the map tree: [IdrBus] is an unstable type, this wrapper is not, and
 * [remember] returns the same instance for the life of the bus.
 *
 * Public properties never change (the [StateFlow] identity is fixed). Values
 * arrive through the flow, not by mutating this object.
 */
@Stable
internal class VehicleMotionSource(val hud: StateFlow<HudState>) {
    constructor(bus: IdrBus) : this(bus.hud)
}

/** Draw-phase extras. Writes here must not be Compose state. */
internal class VehicleDrawExtras {
    @Volatile var uncertaintyM: Double = Double.NaN
    @Volatile var headingReferenced: Boolean = false
}

/**
 * Animatables + rare chrome. Position/bearing are read in draw / [androidx.compose.runtime.withFrameNanos];
 * [chrome] is Snapshot state that only updates when [vehicleChromeOf] actually changes.
 */
@Stable
internal class VehicleSubscription(
    val east: Animatable<Float, AnimationVector1D>,
    val north: Animatable<Float, AnimationVector1D>,
    val bearing: Animatable<Float, AnimationVector1D>,
    val extras: VehicleDrawExtras,
    val chrome: MutableState<VehicleChrome>,
)

/**
 * Collect [hud] into Animatables. Interpolated frames never become Compose UI
 * state, so 60 fps motion cannot recompose map chrome.
 *
 * This is a [LaunchedEffect] on the flow identity, not on east/north/heading.
 * Keying the effect on the target metres would cancel and restart the animation
 * at 10 Hz — the parent-HUD-recomposition bug this exists to fix.
 *
 * `snapshotFlow` is the right tool when the source already lives in Snapshot
 * state. The HUD does not: putting it there (`collectAsState`) is what makes
 * the map tree recompose. We collect the [StateFlow] directly.
 */
@Composable
internal fun subscribeVehicleMotion(hud: StateFlow<HudState>): VehicleSubscription {
    val initial = hud.value
    val east = remember { Animatable(initial.east.toFloat().finiteOrZero()) }
    val north = remember { Animatable(initial.north.toFloat().finiteOrZero()) }
    val bearing = remember { Animatable(initial.headingDeg.toFloat().finiteOrZero()) }
    val extras = remember {
        VehicleDrawExtras().also {
            it.uncertaintyM = initial.uncertaintyM
            it.headingReferenced = initial.headingReferenced
        }
    }
    val chrome = remember { mutableStateOf(vehicleChromeOf(initial)) }
    val sub = remember { VehicleSubscription(east, north, bearing, extras, chrome) }

    LaunchedEffect(hud) {
        hud.collect { h ->
            extras.uncertaintyM = h.uncertaintyM
            extras.headingReferenced = h.headingReferenced

            val te = h.east.toFloat()
            val tn = h.north.toFloat()
            if (te.isFinite() && tn.isFinite()) {
                val de = te - east.value
                val dn = tn - north.value
                if (sqrt(de * de + dn * dn) > MARKER_TELEPORT_M) {
                    east.snapTo(te)
                    north.snapTo(tn)
                } else {
                    launch { east.animateTo(te, MarkerSpring) }
                    launch { north.animateTo(tn, MarkerSpring) }
                }
            }

            val th = h.headingDeg.toFloat()
            if (th.isFinite()) {
                launch {
                    val short = shortestBearingTarget(bearing.value, th)
                    if (abs(short - bearing.value) > 45f) {
                        bearing.snapTo(wrap360Deg(th.toDouble()).toFloat())
                    } else {
                        bearing.animateTo(short, MarkerSpring)
                        val v = bearing.value
                        if (v > 720f || v < -360f) {
                            bearing.snapTo(wrap360Deg(v.toDouble()).toFloat())
                        }
                    }
                }
            }

            val next = vehicleChromeOf(h)
            if (next != chrome.value) chrome.value = next
        }
    }
    return sub
}

/**
 * Backend / legend fields only. Distinct from the 10 Hz pose so a panel that
 * must choose MapLibre vs Canvas does not recompose on every fix.
 */
@Composable
internal fun rememberVehicleChrome(hud: StateFlow<HudState>): VehicleChrome {
    val state = remember { mutableStateOf(vehicleChromeOf(hud.value)) }
    LaunchedEffect(hud) {
        hud.map(::vehicleChromeOf).distinctUntilChanged().collect { state.value = it }
    }
    return state.value
}

private fun Float.finiteOrZero(): Float = if (isFinite()) this else 0f
