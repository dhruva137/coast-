package `in`.sih26168.idr.demo

import android.content.Context
import `in`.sih26168.idr.data.HudState
import `in`.sih26168.idr.data.Prefs

/**
 * `standard` flavor: no [LanUploader]. Console QR pairing still works via
 * [in.sih26168.idr.pair] in main — that path is not gated on this flavor.
 */
object TrackerHooks {
    fun onHud(context: Context, hud: HudState, session: String) {
        // Intentionally empty.
    }

    fun bannerVisible(prefs: Prefs): Boolean = false
}
