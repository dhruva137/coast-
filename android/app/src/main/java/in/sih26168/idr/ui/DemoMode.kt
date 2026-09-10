package `in`.sih26168.idr.ui

import android.content.Context
import android.util.Log
import `in`.sih26168.idr.IdrBus
import `in`.sih26168.idr.data.AppMode
import `in`.sih26168.idr.data.Prefs
import `in`.sih26168.idr.record.RecordService

/**
 * One-tap judge path: skip setup, arm replay + blackout + ghost, start NAVIGATE.
 * Safe on rotate / deny-permissions / airplane mode — never throws to the UI.
 */
object DemoMode {
    private const val TAG = "DemoMode"

    const val EXPLAINER =
        "GPS is off. Position is coming from the phone's motion sensors + the road map."

    const val REPLAY_LABEL = "REPLAY — real dataset, real estimator."

    const val HANDOVER = "GPS LOST  →  COAST"

    fun arm(prefs: Prefs, bus: IdrBus) {
        prefs.authDone = true
        prefs.onboardingDone = true
        prefs.vehicleCheckDone = true
        prefs.demoMode = true
        prefs.replayMode = true
        prefs.showGhostCar = true
        bus.setReplayEnabled(true)
        bus.setShowGhost(true)
        bus.setBlackout(true)
    }

    fun start(context: Context, prefs: Prefs, bus: IdrBus) {
        arm(prefs, bus)
        try {
            RecordService.start(context.applicationContext, AppMode.NAVIGATE)
        } catch (t: Throwable) {
            Log.w(TAG, "Demo NAVIGATE start failed (non-fatal)", t)
        }
    }

    fun clear(prefs: Prefs, bus: IdrBus) {
        prefs.demoMode = false
        bus.setBlackout(false)
        // Leave replayMode / ghost for the user — Settings toggles own those.
        // Blackout always drops so a cleared demo cannot leave the map GNSS-blind.
    }
}
