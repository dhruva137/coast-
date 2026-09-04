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

    var useKmh: Boolean
        get() = sp.getBoolean(KEY_KMH, true)
        set(v) = sp.edit().putBoolean(KEY_KMH, v).apply()

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
        const val KEY_MOUNT_SET = "mount_set"
        const val KEY_MOUNT_NOTE = "mount_note"
        const val KEY_MOUNT_PREFIX = "mount_"
    }
}
