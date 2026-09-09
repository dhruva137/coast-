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
     * Prefer the dark map chrome. Light theme is not wired yet — the toggle
     * still persists so a later Theme pass can honour it without a migration.
     */
    var mapDarkTheme: Boolean
        get() = sp.getBoolean(KEY_MAP_DARK, true)
        set(v) = sp.edit().putBoolean(KEY_MAP_DARK, v).apply()

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
     * Draw the naive/ghost track when the demo pipeline exposes one.
     * Prefs-only until the bus gains a ghost setter (file 05).
     */
    var showGhostCar: Boolean
        get() = sp.getBoolean(KEY_GHOST, false)
        set(v) = sp.edit().putBoolean(KEY_GHOST, v).apply()

    /**
     * Opt-in LAN phone-tracker (file 07). Off by default.
     * Only the `tracker` product flavor posts; `standard` never uploads
     * even when this is true (TrackerHooks is a no-op there).
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
        const val KEY_DIAGNOSTICS = "diagnostics_open"
        const val KEY_KMH = "speed_kmh"
        const val KEY_BASEMAP = "basemap_enabled"
        const val KEY_MAP_DARK = "map_dark_theme"
        const val KEY_VEHICLE = "vehicle_kind"
        const val KEY_REPLAY = "replay_mode"
        const val KEY_GHOST = "show_ghost_car"
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
