package `in`.sih26168.idr.demo

import android.content.Context
import `in`.sih26168.idr.data.HudState
import `in`.sih26168.idr.data.Prefs

/**
 * `standard` flavor: no LAN uploader. Keeps the F8 claim that no position
 * data ever leaves the device. Prefs keys may still exist for UI, but this
 * is a hard no-op.
 */
object TrackerHooks {
    fun onHud(context: Context, hud: HudState, session: String) {
        // Intentionally empty.
    }

    fun bannerVisible(prefs: Prefs): Boolean = false
}
