package `in`.sih26168.idr.demo

import android.content.Context
import `in`.sih26168.idr.data.HudState
import `in`.sih26168.idr.data.Prefs

/**
 * `tracker` flavor bridge: optional LAN stream when Prefs say so.
 * Wired from [in.sih26168.idr.record.RecordService] off the HUD publish path;
 * the uploader itself hops to a background thread immediately.
 */
object TrackerHooks {
    private val uploader = LanUploader()

    fun onHud(context: Context, hud: HudState, session: String) {
        uploader.maybePost(Prefs(context), hud, session)
    }

    fun bannerVisible(prefs: Prefs): Boolean =
        prefs.trackerOptIn && prefs.trackerLanIp.trim().isNotEmpty()
}
