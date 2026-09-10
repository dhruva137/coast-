package `in`.sih26168.idr.data

import android.content.Context
import android.content.SharedPreferences

/**
 * The handful of things that must survive a restart: whether onboarding has
 * been seen, whether the developer panel is open, and the mount rotation the
 * user calibrated.
 *
 * Deliberately [SharedPreferences] and nothing more -- no database, no
 * migration surface, works with the app installed cold on a judge phone.
 */
class Prefs(context: Context) {
    private val sp: SharedPreferences =
        context.applicationContext.getSharedPreferences("idr_prefs", Context.MODE_PRIVATE)

    var onboardingDone: Boolean
        get() = sp.getBoolean(KEY_ONBOARDED, false)
        set(v) = sp.edit().putBoolean(KEY_ONBOARDED, v).apply()

    /**
     * True after the user has completed (or dismissed) the first-launch
     * Vehicle Check pre-flight. Settings can re-open the check anytime.
     */
    var vehicleCheckDone: Boolean
        get() = sp.getBoolean(KEY_VEHICLE_CHECK, false)
        set(v) = sp.edit().putBoolean(KEY_VEHICLE_CHECK, v).apply()

    var diagnosticsOpen: Boolean
        get() = sp.getBoolean(KEY_DIAGNOSTICS, false)
        set(v) = sp.edit().putBoolean(KEY_DIAGNOSTICS, v).apply()

    /**
     * Show the OpenStreetMap basemap (MapLibre) under the track. Defaults true;
     * the user can turn it off to get the metre grid back, which is also the
     * surface that works with the radio off and makes no network request.
     */
    var basemapEnabled: Boolean
        get() = sp.getBoolean(KEY_BASEMAP, true)
        set(v) = sp.edit().putBoolean(KEY_BASEMAP, v).apply()

    var useKmh: Boolean
        get() = sp.getBoolean(KEY_KMH, true)
        set(v) = sp.edit().putBoolean(KEY_KMH, v).apply()

    /**
     * Prefer the dark map chrome. Kept for migration: writes also update
     * [themePreference] (Dark/Light). Prefer [themePreference] for new code.
     */
    var mapDarkTheme: Boolean
        get() = themePreference != ThemePreference.Light
        set(v) {
            themePreference = if (v) ThemePreference.Dark else ThemePreference.Light
        }

    /**
     * Tri-state appearance: system / light / dark. Default dark (demo primary).
     * Migrates from the older [mapDarkTheme] boolean when unset.
     */
    var themePreference: ThemePreference
        get() {
            val raw = sp.getString(KEY_THEME_MODE, null)
            if (raw != null) {
                return ThemePreference.fromStorage(raw)
            }
            // Legacy boolean → dark/light (no system).
            return if (sp.getBoolean(KEY_MAP_DARK, true)) {
                ThemePreference.Dark
            } else {
                ThemePreference.Light
            }
        }
        set(v) = sp.edit().putString(KEY_THEME_MODE, v.storageKey).apply()

    /** Last vehicle profile chosen in Settings; restored onto [IdrBus] at start. */
    var vehicleKind: VehicleKind
        get() {
            val raw = sp.getString(KEY_VEHICLE, null) ?: return VehicleKind.scooter
            return runCatching { VehicleKind.valueOf(raw) }.getOrDefault(VehicleKind.scooter)
        }
        set(v) = sp.edit().putString(KEY_VEHICLE, v.name).apply()

    /** Next NAVIGATE arm uses the bundled replay source instead of live sensors. */
    var replayMode: Boolean
        get() = sp.getBoolean(KEY_REPLAY, false)
        set(v) = sp.edit().putBoolean(KEY_REPLAY, v).apply()

    /**
     * Judge-facing Demo Mode: one-tap blackout replay. Survives rotate; cleared
     * when the user stops the session or turns Replay off in Settings.
     */
    var demoMode: Boolean
        get() = sp.getBoolean(KEY_DEMO_MODE, false)
        set(v) = sp.edit().putBoolean(KEY_DEMO_MODE, v).apply()

    /**
     * Draw the naive/ghost track (red puck) when the estimator publishes one.
     * Restored onto [IdrBus.setShowGhost] at launch.
     */
    var showGhostCar: Boolean
        get() = sp.getBoolean(KEY_GHOST, false)
        set(v) = sp.edit().putBoolean(KEY_GHOST, v).apply()

    /**
     * P1-2 ZUPT tabletop: side-by-side naive vs COAST speed readouts.
     * Restored onto [IdrBus.setZuptTabletop] at launch.
     */
    var zuptTabletop: Boolean
        get() = sp.getBoolean(KEY_ZUPT_TABLETOP, false)
        set(v) = sp.edit().putBoolean(KEY_ZUPT_TABLETOP, v).apply()

    /**
     * User-forced stationary hold. Zeros coast until the rider turns it off.
     * Restored onto [IdrBus.setForceStationary] at launch. ZUPT still auto-detects
     * stops; this is the tabletop / "I am not moving" override.
     */
    var forceStationary: Boolean
        get() = sp.getBoolean(KEY_FORCE_STATIONARY, false)
        set(v) = sp.edit().putBoolean(KEY_FORCE_STATIONARY, v).apply()

    /**
     * Fuse an onset-calibrated compass during GNSS outage. Default on.
     * Persist-only here; the estimator reads this pref if the bus has no
     * fuse-compass setter yet.
     */
    var fuseCompass: Boolean
        get() = sp.getBoolean(KEY_FUSE_COMPASS, true)
        set(v) = sp.edit().putBoolean(KEY_FUSE_COMPASS, v).apply()

    /**
     * Opt-in LAN phone-tracker for the demo laptop bridge
     * (`python -m web.tracker_server`). Off by default.
     * Only the `tracker` product flavor posts; `standard` never uploads
     * even when this is true (TrackerHooks is a no-op there).
     *
     * Console QR pairing uses [in.sih26168.idr.pair.PairingStore], not these keys.
     */
    var trackerOptIn: Boolean
        get() = sp.getBoolean(KEY_TRACKER_OPT_IN, false)
        set(v) = sp.edit().putBoolean(KEY_TRACKER_OPT_IN, v).apply()

    /** Laptop LAN IPv4 for `python -m web.tracker_server` (port 8787). */
    var trackerLanIp: String
        get() = sp.getString(KEY_TRACKER_LAN_IP, "") ?: ""
        set(v) = sp.edit().putString(KEY_TRACKER_LAN_IP, v.trim()).apply()

    /**
     * Auth stub: true after "Continue as guest" or a local Sign in.
     * Never implies a network account — display name is device-local only.
     */
    var authDone: Boolean
        get() = sp.getBoolean(KEY_AUTH_DONE, false)
        set(v) = sp.edit().putBoolean(KEY_AUTH_DONE, v).apply()

    /** Local display name from the auth stub; empty means guest. */
    var displayName: String
        get() = sp.getString(KEY_DISPLAY_NAME, "") ?: ""
        set(v) = sp.edit().putString(KEY_DISPLAY_NAME, v).apply()

    /**
     * Debug-only: draw the modelled uncertainty radius on the map.
     * Off by default — that signal correlates negatively with true error (−0.23).
     */
    var showUncertaintyRadius: Boolean
        get() = sp.getBoolean(KEY_UNCERTAINTY, false)
        set(v) = sp.edit().putBoolean(KEY_UNCERTAINTY, v).apply()

    /** Free text describing the calibrated mount, shown on the Drive screen. */
    var mountNote: String
        get() = sp.getString(KEY_MOUNT_NOTE, "") ?: ""
        set(v) = sp.edit().putString(KEY_MOUNT_NOTE, v).apply()

    /**
     * The stored phone-to-vehicle rotation, or null when the user has never
     * completed a calibration that passed. Nine doubles; a partial or corrupt
     * record reads back as null rather than as a silently wrong frame.
     */
    var mount: MountRotation?
        get() {
            if (!sp.getBoolean(KEY_MOUNT_SET, false)) return null
            val v = DoubleArray(9)
            for (i in 0 until 9) {
                val bits = sp.getLong(KEY_MOUNT_PREFIX + i, Long.MIN_VALUE)
                if (bits == Long.MIN_VALUE) return null
                v[i] = Double.fromBits(bits)
                if (!v[i].isFinite()) return null
            }
            return MountRotation(
                fx = v[0], fy = v[1], fz = v[2],
                rx = v[3], ry = v[4], rz = v[5],
                dx = v[6], dy = v[7], dz = v[8],
            )
        }
        set(value) {
            val e = sp.edit()
            if (value == null) {
                e.putBoolean(KEY_MOUNT_SET, false)
                for (i in 0 until 9) e.remove(KEY_MOUNT_PREFIX + i)
                e.putString(KEY_MOUNT_NOTE, "")
            } else {
                val v = doubleArrayOf(
                    value.fx, value.fy, value.fz,
                    value.rx, value.ry, value.rz,
                    value.dx, value.dy, value.dz,
                )
                for (i in 0 until 9) e.putLong(KEY_MOUNT_PREFIX + i, v[i].toRawBits())
                e.putBoolean(KEY_MOUNT_SET, true)
            }
            e.apply()
        }

    private companion object {
        const val KEY_ONBOARDED = "onboarding_done_v1"
        const val KEY_VEHICLE_CHECK = "vehicle_check_done_v1"
        const val KEY_DIAGNOSTICS = "diagnostics_open"
        const val KEY_KMH = "speed_kmh"
        const val KEY_BASEMAP = "basemap_enabled"
        const val KEY_MAP_DARK = "map_dark_theme"
        const val KEY_THEME_MODE = "theme_mode_v1"
        const val KEY_VEHICLE = "vehicle_kind"
        const val KEY_REPLAY = "replay_mode"
        const val KEY_DEMO_MODE = "demo_mode"
        const val KEY_GHOST = "show_ghost_car"
        const val KEY_ZUPT_TABLETOP = "zupt_tabletop"
        const val KEY_FORCE_STATIONARY = "force_stationary"
        const val KEY_FUSE_COMPASS = "fuse_compass"
        const val KEY_TRACKER_OPT_IN = "tracker_opt_in"
        const val KEY_TRACKER_LAN_IP = "tracker_lan_ip"
        const val KEY_AUTH_DONE = "auth_done"
        const val KEY_DISPLAY_NAME = "display_name"
        const val KEY_UNCERTAINTY = "show_uncertainty_radius"
        const val KEY_MOUNT_SET = "mount_set"
        const val KEY_MOUNT_NOTE = "mount_note"
        const val KEY_MOUNT_PREFIX = "mount_"
    }
}
