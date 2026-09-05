package `in`.sih26168.idr.nav

import androidx.compose.runtime.Immutable
import `in`.sih26168.idr.data.VehicleKind

/**
 * What kind of thing the phone is riding in, expressed as numbers the
 * estimator can actually use.
 *
 * The old app had one motion model and a boolean called `leans`. That was
 * enough while the only targets were a scooter and a car. The problem
 * statement names "tunnels/underground metro OR similar simulated
 * environments", so a metro is a first-class target, and a metro is not a
 * scooter with the lean turned off -- it has a different top speed, a
 * different acceleration envelope, a hard non-holonomic constraint a road
 * vehicle does not have, curve radii measured in hundreds of metres, and a
 * stop at every station that lasts long enough to re-estimate gyro bias.
 *
 * ## What each dimension is for
 *
 *  * [leans] gates the coordinated-turn solver in [solveLean]. Applying a lean
 *    correction to a vehicle that cannot lean is not a harmless no-op: the
 *    solver reads any body-y gyro rate as evidence of roll and folds it into
 *    the yaw rate through `psi_dot = wy sin(phi) + wz cos(phi)`. On a car or a
 *    train that y-rate is pitch over a bump or a bogie yawing on its pivot, and
 *    turning it into heading is a fabricated turn. So the solver is switched
 *    OFF, not fed zero and left running.
 *
 *  * [lateralToleranceMps2] is the largest sustained lateral specific force the
 *    vehicle can physically produce, measured in the vehicle body frame. It is
 *    the numeric form of the non-holonomic constraint. A car can change lane;
 *    a train cannot leave the rails, so its lateral freedom is whatever the
 *    track geometry allows and nothing more. This is used as an HONESTY CHECK,
 *    never as a correction -- exceeding it means the selected profile is
 *    probably wrong, and the app says so rather than quietly mis-estimating.
 *
 *  * [maxSpeedMps] and [maxAccelMps2] reject nonsense. A dropped phone, a
 *    saturating accelerometer or a bad model window can inject a step the
 *    integrator would otherwise turn into hundreds of metres.
 *
 *  * [maxYawRateRadS] caps plausible turn rate. It is derived from
 *    `omega = v / R` with [minTurnRadiusM] at the speed the vehicle actually
 *    takes that radius. A metro cannot make a 90-degree turn in 10 m, so a
 *    45 deg/s yaw spike from a phone shifting in its cradle must not become a
 *    45 degree heading error.
 *
 *  * [zupt] tunes the stationary detector. A metro standing at a platform with
 *    traction off is far stiller than a scooter at a red light with the engine
 *    idling, and one threshold cannot serve both.
 *
 * ## Provenance of the numbers
 *
 * Every value below is a published or textbook envelope for the vehicle class,
 * cited in [rationale] and in the comment at the site. **None of them was
 * measured by this project on hardware.** They are bounds chosen to be loose
 * enough never to reject real motion and tight enough to catch nonsense; where
 * a source gives a range, the permissive end is taken.
 */
@Immutable
data class VehicleProfile(
    val kind: VehicleKind,
    /** Name a passenger would use. */
    val label: String,
    /** One line, shown next to the picker: what choosing this actually changes. */
    val oneLine: String,
    /** True only for single-track vehicles that roll into a turn. */
    val leans: Boolean,
    /** Plausible maximum roll, degrees. 0 when [leans] is false. */
    val maxLeanDeg: Double,
    /** Largest sustained lateral specific force in the body frame, m/s^2. */
    val lateralToleranceMps2: Double,
    /** m/s. Anything above this is rejected, not integrated. */
    val maxSpeedMps: Double,
    /** m/s^2, longitudinal. Bounded by the braking side, which is the larger. */
    val maxAccelMps2: Double,
    /** rad/s. See [minTurnRadiusM]. */
    val maxYawRateRadS: Double,
    /** Tightest curve the vehicle can be on, metres. Drives [maxYawRateRadS]. */
    val minTurnRadiusM: Double,
    val gnss: GnssOutlook,
    val zupt: ZuptProfile,
    /** Long-form justification, shown verbatim in Diagnostics. */
    val rationale: String,
) {
    /** Degrees, for the UI. */
    val maxYawRateDegS: Double get() = rad2deg(maxYawRateRadS)

    val maxSpeedKmh: Double get() = maxSpeedMps * 3.6

    companion object {
        /**
         * The profile used when nobody has chosen one, and the default for a
         * bare [SimpleIns].
         *
         * [VehicleKind.other] deliberately keeps the lean solver ON and every
         * limit wide, because that is the behaviour the existing estimator
         * tests pin. An unknown vehicle gets the historical path, not a new
         * untested one.
         */
        fun default(): VehicleProfile = of(VehicleKind.other)

        fun of(kind: VehicleKind): VehicleProfile = when (kind) {
            VehicleKind.metro_rail -> METRO_RAIL
            VehicleKind.train -> TRAIN
            VehicleKind.bus -> BUS
            VehicleKind.car -> CAR
            VehicleKind.auto_rickshaw -> AUTO_RICKSHAW
            VehicleKind.scooter -> SCOOTER
            VehicleKind.motorcycle -> MOTORCYCLE
            VehicleKind.bicycle -> BICYCLE
            VehicleKind.walking -> WALKING
            VehicleKind.other -> OTHER
        }

        /** Every profile, in the order the picker shows them. */
        fun all(): List<VehicleProfile> = VehicleKind.entries.map { of(it) }

        // -------------------------------------------------------------------
        // Rail
        // -------------------------------------------------------------------

        /**
         * Underground / elevated metro. The environment the problem statement
         * names, and the hardest constraint set in the list.
         *
         *  * SPEED 25 m/s (90 km/h). Indian metro rolling stock is designed for
         *    80-90 km/h and scheduled below that; 25 m/s is the design ceiling
         *    with a little headroom.
         *  * ACCEL 1.4 m/s^2. Metro service acceleration is about 1.0-1.3 m/s^2
         *    and full-service braking about the same -- both are limited by
         *    standing-passenger comfort long before they are limited by
         *    adhesion. 1.4 is the rejection threshold, not the expected value.
         *  * LATERAL 0.65 m/s^2. This is cant deficiency, the piece of lateral
         *    acceleration the track's superelevation does NOT cancel. Metro
         *    alignment is designed to about 85-100 mm of cant deficiency on
         *    1435 mm standard gauge: a_lat = g * d / G = 9.81 * 0.09 / 1.435 =
         *    0.62 m/s^2. A train physically cannot generate more sideways than
         *    the track hands it. This is the strong non-holonomic constraint --
         *    two orders tighter than a car's tyre limit.
         *  * YAW 0.17 rad/s (10 deg/s). Mainline metro minimum curve radius is
         *    200-300 m; depot and turnout curves go to about 100 m but are
         *    taken at crawl. The binding case is roughly 15 m/s on R = 150 m,
         *    omega = v/R = 0.10 rad/s. 0.17 leaves room for the yaw impulse
         *    across a turnout.
         *  * ZUPT: the whole reason this profile exists. A metro dwells 20-45 s
         *    at every platform with traction off, sitting on air springs. That
         *    is the stillest a moving vehicle ever gets, so the variance gate
         *    can be very tight and the confirmation window short.
         */
        val METRO_RAIL = VehicleProfile(
            kind = VehicleKind.metro_rail,
            label = "Metro / underground rail",
            oneLine = "No lean. Almost no sideways freedom, gentle turns, and a " +
                "zero-velocity reset at every station stop.",
            leans = false,
            maxLeanDeg = 0.0,
            lateralToleranceMps2 = 0.65,
            maxSpeedMps = 25.0,
            maxAccelMps2 = 1.4,
            maxYawRateRadS = 0.17,
            minTurnRadiusM = 150.0,
            gnss = GnssOutlook.UNAVAILABLE,
            zupt = ZuptProfile(
                enabled = true,
                windowSec = 1.0,
                minStillSec = 2.0,
                // A stopped metro car on secondary air suspension with traction
                // off: the residual is HVAC and people boarding, not machinery.
                accelVarMax = 0.02,
                accelBiasMax = 0.20,
                // Bounds the UNCORRECTED gyro bias we are trying to measure.
                // 0.06 rad/s is 3.4 deg/s, the high end for a warm phone MEMS
                // gyro; anything above that is real rotation, not bias.
                gyroMagMax = 0.06,
                gyroVarMax = 0.0015,
                rearmSec = 5.0,
            ),
            rationale = "Cant deficiency 85-100 mm on 1435 mm gauge gives 0.62 m/s2 of " +
                "unbalanced lateral acceleration; minimum mainline curve radius 200-300 m " +
                "gives 0.10 rad/s of yaw at line speed; service acceleration and braking " +
                "are both about 1.2 m/s2, limited by standing passengers.",
        )

        /**
         * Suburban / mainline train. Same physics as a metro, faster and
         * gentler: longer consists accelerate and brake more slowly, curve
         * radii are larger, and broad gauge (1676 mm) makes the same cant
         * deficiency produce slightly less lateral acceleration.
         *
         * GNSS is INTERMITTENT rather than UNAVAILABLE: a mainline train spends
         * most of its journey under open sky and loses the fix in cuttings,
         * tunnels and roofed platforms.
         *
         * ZUPT thresholds are looser than the metro's because a station stop
         * with a diesel locomotive idling at the head is not still.
         */
        val TRAIN = VehicleProfile(
            kind = VehicleKind.train,
            label = "Train (suburban / mainline)",
            oneLine = "No lean, very large turn radius, high top speed, and a " +
                "zero-velocity reset at every station.",
            leans = false,
            maxLeanDeg = 0.0,
            // 9.81 * 0.10 / 1.676 = 0.59 m/s2 on Indian broad gauge.
            lateralToleranceMps2 = 0.60,
            maxSpeedMps = 45.0,
            maxAccelMps2 = 1.0,
            maxYawRateRadS = 0.15,
            minTurnRadiusM = 300.0,
            gnss = GnssOutlook.INTERMITTENT,
            zupt = ZuptProfile(
                enabled = true,
                windowSec = 1.0,
                minStillSec = 3.0,
                accelVarMax = 0.08,
                accelBiasMax = 0.25,
                gyroMagMax = 0.06,
                gyroVarMax = 0.0025,
                rearmSec = 5.0,
            ),
            rationale = "Broad gauge 1676 mm with 100 mm cant deficiency gives 0.59 m/s2 " +
                "lateral; mainline curve radii from 300 m give 0.15 rad/s; a long consist " +
                "accelerates at well under 1 m/s2.",
        )

        // -------------------------------------------------------------------
        // Road, non-leaning
        // -------------------------------------------------------------------

        /**
         * City bus. Rigid body: it rolls on its suspension by a few degrees but
         * does not lean into a turn, so the coordinated-turn solver is off.
         *
         *  * LATERAL 4.0 m/s^2 (0.41 g). A high-floor bus has a low rollover
         *    threshold -- UNECE R107 requires it to survive a 28 degree tilt
         *    table, which is 0.53 g static, and drivers stay well under that
         *    with standing passengers aboard.
         *  * YAW 0.6 rad/s. A 12 m bus turns in a kerb-to-kerb circle of about
         *    22 m, so R ~ 11 m; at 5 m/s that is 0.45 rad/s.
         *  * ACCEL 4.0 m/s^2, set by the braking side, not the traction side --
         *    a bus accelerates at barely 1.2 m/s^2 but can brake at 4-5.
         */
        val BUS = VehicleProfile(
            kind = VehicleKind.bus,
            label = "Bus",
            oneLine = "No lean, wide turns, and a zero-velocity reset at every " +
                "bus stop and traffic light.",
            leans = false,
            maxLeanDeg = 0.0,
            lateralToleranceMps2 = 4.0,
            maxSpeedMps = 28.0,
            maxAccelMps2 = 4.0,
            maxYawRateRadS = 0.6,
            minTurnRadiusM = 11.0,
            gnss = GnssOutlook.INTERMITTENT,
            zupt = ZuptProfile(
                enabled = true,
                windowSec = 1.0,
                minStillSec = 2.0,
                // A diesel bus idling at a stop shakes noticeably.
                accelVarMax = 0.35,
                accelBiasMax = 0.30,
                gyroMagMax = 0.09,
                gyroVarMax = 0.006,
                rearmSec = 4.0,
            ),
            rationale = "UNECE R107 tilt-table 28 deg = 0.53 g static rollover; service " +
                "lateral stays near 0.4 g. 12 m wheelbase gives an 11 m turning radius, " +
                "0.45 rad/s at 5 m/s. Braking, not traction, sets the longitudinal limit.",
        )

        /**
         * Passenger car. The permissive road profile: four wheels, a real tyre
         * limit, and no lean.
         *
         *  * LATERAL 8.0 m/s^2 (0.8 g) is the dry-tarmac tyre limit for a road
         *    car. This is more than TWELVE TIMES the metro figure, which is the
         *    whole point of making lateral tolerance a per-profile number.
         *  * ACCEL 9.0 m/s^2 -- again the braking side; a car stops at ~0.9 g.
         *  * YAW 1.2 rad/s (69 deg/s): a car-park manoeuvre at R = 5 m and
         *    5 m/s is 1.0 rad/s.
         */
        val CAR = VehicleProfile(
            kind = VehicleKind.car,
            label = "Car",
            oneLine = "No lean, free to change lane, and a zero-velocity reset " +
                "whenever the car is stopped in traffic.",
            leans = false,
            maxLeanDeg = 0.0,
            lateralToleranceMps2 = 8.0,
            maxSpeedMps = 55.0,
            maxAccelMps2 = 9.0,
            maxYawRateRadS = 1.2,
            minTurnRadiusM = 5.0,
            gnss = GnssOutlook.INTERMITTENT,
            zupt = ZuptProfile(
                enabled = true,
                windowSec = 1.0,
                minStillSec = 1.5,
                accelVarMax = 0.30,
                accelBiasMax = 0.30,
                gyroMagMax = 0.09,
                gyroVarMax = 0.005,
                rearmSec = 4.0,
            ),
            rationale = "Dry-tarmac tyre limit ~0.8 g both laterally and in braking; a 5 m " +
                "turning radius at car-park speed gives ~1.0 rad/s of yaw.",
        )

        /**
         * Three-wheeler. Does NOT lean -- it is rigid and tips rather than
         * rolls, so the lean solver stays off.
         *
         * LATERAL 3.5 m/s^2 (0.36 g). Track width is about 1.15 m and the CG
         * sits around 0.65 m, but a three-wheeler rolls about a TRIANGLE and
         * the lateral offset at the single front wheel is zero, so the real
         * threshold is roughly half the two-axle static stability factor.
         * Tilt-table results for three-wheelers land near 0.4 g.
         *
         * YAW 1.8 rad/s: the turning radius is about 2.5 m, and 4 m/s round it
         * is 1.6 rad/s. Auto-rickshaws really do turn that hard.
         */
        val AUTO_RICKSHAW = VehicleProfile(
            kind = VehicleKind.auto_rickshaw,
            label = "Auto-rickshaw",
            oneLine = "Three wheels, so no lean, but very tight turns and a low " +
                "sideways limit before it would tip.",
            leans = false,
            maxLeanDeg = 0.0,
            lateralToleranceMps2 = 3.5,
            maxSpeedMps = 18.0,
            maxAccelMps2 = 4.0,
            maxYawRateRadS = 1.8,
            minTurnRadiusM = 2.5,
            gnss = GnssOutlook.INTERMITTENT,
            zupt = ZuptProfile(
                enabled = true,
                windowSec = 1.0,
                minStillSec = 2.0,
                // A single-cylinder CNG engine idling in a light vehicle is the
                // roughest idle in this list apart from a motorcycle.
                accelVarMax = 0.60,
                accelBiasMax = 0.35,
                gyroMagMax = 0.10,
                gyroVarMax = 0.010,
                rearmSec = 4.0,
            ),
            rationale = "Three-wheel tilt-table thresholds cluster near 0.4 g; 2.5 m " +
                "turning radius at 4 m/s is 1.6 rad/s.",
        )

        // -------------------------------------------------------------------
        // Road, leaning
        // -------------------------------------------------------------------

        /**
         * Scooter. The vehicle the project was originally built around, and one
         * of the three profiles where the coordinated-turn solver runs.
         *
         * LATERAL 1.5 m/s^2, and the reasoning is the opposite of the car's. In
         * a COORDINATED turn a single-track vehicle rolls until the resultant
         * of gravity and centripetal acceleration lies along its own vertical,
         * so the body-lateral specific force is near zero however hard it
         * turns. A correctly mounted phone on a leaning vehicle should read
         * almost nothing sideways. Sustained lateral means the turn is not
         * coordinated -- a slide, a kerb, or a mount frame that is wrong.
         * 1.5 m/s^2 allows for suspension and steering transients.
         */
        val SCOOTER = VehicleProfile(
            kind = VehicleKind.scooter,
            label = "Scooter",
            oneLine = "Leans into turns, so the coordinated-turn solver runs and " +
                "heading is corrected for roll.",
            leans = true,
            maxLeanDeg = 45.0,
            lateralToleranceMps2 = 1.5,
            maxSpeedMps = 25.0,
            maxAccelMps2 = 6.0,
            maxYawRateRadS = 1.5,
            minTurnRadiusM = 3.5,
            gnss = GnssOutlook.INTERMITTENT,
            zupt = ZuptProfile(
                enabled = true,
                windowSec = 1.0,
                // A scooter at a light is the WORST case for a stationary
                // detector: the engine idles, and the rider rocks the whole
                // machine on its suspension with a foot down. Both thresholds
                // and the confirmation time are the loosest of any road profile.
                minStillSec = 2.5,
                accelVarMax = 0.90,
                accelBiasMax = 0.40,
                gyroMagMax = 0.12,
                gyroVarMax = 0.020,
                rearmSec = 4.0,
            ),
            rationale = "Coordinated turn puts the resultant along the machine's own " +
                "vertical, so measured body-lateral force stays near zero; 3.5 m U-turn " +
                "radius at 5 m/s is 1.4 rad/s of yaw.",
        )

        /** Motorcycle: a scooter with more speed, more braking and more lean. */
        val MOTORCYCLE = VehicleProfile(
            kind = VehicleKind.motorcycle,
            label = "Motorcycle",
            oneLine = "Leans into turns like a scooter, with a higher top speed " +
                "and a harder braking limit.",
            leans = true,
            maxLeanDeg = 50.0,
            lateralToleranceMps2 = 1.5,
            maxSpeedMps = 45.0,
            // Braking is limited by pitch-over near 0.9-1.0 g, not by grip.
            maxAccelMps2 = 9.0,
            maxYawRateRadS = 1.5,
            minTurnRadiusM = 3.5,
            gnss = GnssOutlook.INTERMITTENT,
            zupt = ZuptProfile(
                enabled = true,
                windowSec = 1.0,
                minStillSec = 2.5,
                accelVarMax = 0.90,
                accelBiasMax = 0.40,
                gyroMagMax = 0.12,
                gyroVarMax = 0.020,
                rearmSec = 4.0,
            ),
            rationale = "Same coordinated-turn geometry as a scooter; braking bounded by " +
                "pitch-over at about 1 g rather than by tyre grip.",
        )

        /**
         * Bicycle. Leans, but slow and light.
         *
         * ZUPT thresholds are the tightest of the road profiles because there
         * is no engine: a stopped bicycle is genuinely quiet. The confirmation
         * time is still 2 s because a rider balancing at a light wobbles.
         */
        val BICYCLE = VehicleProfile(
            kind = VehicleKind.bicycle,
            label = "Bicycle",
            oneLine = "Leans into turns, low speed, and a very quiet stop that is " +
                "easy to detect.",
            leans = true,
            maxLeanDeg = 35.0,
            lateralToleranceMps2 = 1.5,
            maxSpeedMps = 16.0,
            // A bicycle pitches over its front wheel near 0.5 g.
            maxAccelMps2 = 4.0,
            maxYawRateRadS = 1.8,
            minTurnRadiusM = 2.0,
            gnss = GnssOutlook.INTERMITTENT,
            zupt = ZuptProfile(
                enabled = true,
                windowSec = 1.0,
                minStillSec = 2.0,
                accelVarMax = 0.20,
                accelBiasMax = 0.30,
                gyroMagMax = 0.10,
                gyroVarMax = 0.008,
                rearmSec = 4.0,
            ),
            rationale = "Pitch-over near 0.5 g bounds braking; 2 m turning radius at 3 m/s " +
                "is 1.5 rad/s; no engine, so the stationary signature is clean.",
        )

        // -------------------------------------------------------------------
        // Neither
        // -------------------------------------------------------------------

        /**
         * On foot.
         *
         * The interesting entry is LATERAL 6.0 m/s^2, which is deliberately so
         * high that the check never fires. A pedestrian has NO non-holonomic
         * constraint -- they can sidestep, walk backwards, and turn on the
         * spot -- so there is no assumption to violate, and pretending there is
         * one would produce a warning that means nothing.
         *
         * Yaw is 3.5 rad/s (200 deg/s) for the same reason: a person really can
         * spin that fast, and clamping it would corrupt an honest heading.
         */
        val WALKING = VehicleProfile(
            kind = VehicleKind.walking,
            label = "Walking",
            oneLine = "No lean and no sideways constraint at all -- a person can " +
                "sidestep and turn on the spot.",
            leans = false,
            maxLeanDeg = 0.0,
            lateralToleranceMps2 = 6.0,
            // 4 m/s is 14.4 km/h, which covers a jog as well as a walk.
            maxSpeedMps = 4.0,
            maxAccelMps2 = 4.0,
            maxYawRateRadS = 3.5,
            minTurnRadiusM = 0.5,
            gnss = GnssOutlook.INTERMITTENT,
            zupt = ZuptProfile(
                enabled = true,
                windowSec = 1.0,
                // Pedestrian stops are short -- a kerb, a door -- so the
                // confirmation window has to be short too or it never fires.
                minStillSec = 1.0,
                accelVarMax = 0.25,
                accelBiasMax = 0.30,
                gyroMagMax = 0.12,
                gyroVarMax = 0.010,
                rearmSec = 3.0,
            ),
            rationale = "A pedestrian is holonomic, so the lateral check is deliberately " +
                "disabled by setting the tolerance above anything a person produces. " +
                "Heading from a hand-held phone is unreliable regardless of profile.",
        )

        /**
         * Unknown vehicle.
         *
         * Every limit is set wide enough that it never binds, and the lean
         * solver stays ON, so this reproduces EXACTLY the estimator behaviour
         * that shipped in v0.4.0 and that the existing tests pin. Choosing a
         * real profile is what enables the new constraints; not choosing one
         * cannot make the app worse than it was.
         *
         * ZUPT is still enabled, but with the longest confirmation window in
         * the list. With an unknown vibration signature there is no way to size
         * the variance gate, so the only defensible discriminator left is time:
         * demand a long, unambiguous still period before trusting it.
         */
        val OTHER = VehicleProfile(
            kind = VehicleKind.other,
            label = "Something else",
            oneLine = "No assumptions. Every limit is left wide and the lean " +
                "solver stays on, as in earlier versions of this app.",
            leans = true,
            maxLeanDeg = 50.0,
            lateralToleranceMps2 = 12.0,
            maxSpeedMps = 90.0,
            maxAccelMps2 = 12.0,
            maxYawRateRadS = 4.0,
            minTurnRadiusM = 0.5,
            gnss = GnssOutlook.INTERMITTENT,
            zupt = ZuptProfile(
                enabled = true,
                windowSec = 1.0,
                minStillSec = 8.0,
                accelVarMax = 0.15,
                accelBiasMax = 0.20,
                gyroMagMax = 0.08,
                gyroVarMax = 0.004,
                rearmSec = 8.0,
            ),
            rationale = "Deliberately unconstrained: this is the pre-profile behaviour, " +
                "kept so that not choosing a vehicle can never be worse than the previous " +
                "release.",
        )
    }
}

/** What the profile expects satellite positioning to do on this journey. */
enum class GnssOutlook {
    /** Open sky for most of the route. */
    USUALLY_AVAILABLE,

    /** Fixes come and go: underpasses, urban canyon, roofed platforms. */
    INTERMITTENT,

    /**
     * There will be no fix for the whole journey. Underground metro. The app
     * runs in RELATIVE mode from the start unless the user sets a start point,
     * and the UI must say so BEFORE the journey rather than showing a
     * "waiting for fix" banner for forty minutes.
     */
    UNAVAILABLE,
}

/**
 * Thresholds for the stationary detector, per vehicle.
 *
 * The detector is the classic acceleration-variance / gyro-energy test (Skog
 * et al., "Zero-Velocity Detection -- An Algorithm Evaluation", IEEE TBME
 * 2010). We claim the APPLICATION to a phone in a metro carriage, not the
 * method.
 *
 * All four gates must pass at once:
 *
 *  1. `|mean|a| - g| <= accelBiasMax` -- the specific force averages to
 *     gravity. A vehicle accelerating is not stopped.
 *  2. `var(|a|) <= accelVarMax` -- no vibration. THIS is the gate that
 *     actually separates a stopped vehicle from one cruising smoothly, because
 *     an accelerometer cannot tell constant velocity from rest. It works
 *     because a moving vehicle vibrates: road noise, rail joints, the engine
 *     under load.
 *  3. `mean|w| <= gyroMagMax` -- no rotation. Sized ABOVE the gyro bias we are
 *     trying to measure, or the detector would refuse to fire on the very
 *     phones that need it most.
 *  4. `var(|w|) <= gyroVarMax` -- and no shake.
 *
 * They must hold continuously for [minStillSec] before a stop is confirmed.
 */
@Immutable
data class ZuptProfile(
    val enabled: Boolean,
    /** Statistics window, seconds. */
    val windowSec: Double,
    /** Continuous stillness required before the first update fires, seconds. */
    val minStillSec: Double,
    /** Max variance of |a| over the window, (m/s^2)^2. */
    val accelVarMax: Double,
    /** Max deviation of mean |a| from g, m/s^2. */
    val accelBiasMax: Double,
    /** Max mean |w| over the window, rad/s. */
    val gyroMagMax: Double,
    /** Max variance of |w| over the window, (rad/s)^2. */
    val gyroVarMax: Double,
    /** Minimum gap between bias refreshes while still stopped, seconds. */
    val rearmSec: Double,
)
