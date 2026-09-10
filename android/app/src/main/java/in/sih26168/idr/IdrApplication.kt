package `in`.sih26168.idr

import android.app.Application
import android.app.NotificationChannel
import android.app.NotificationManager
import android.os.Build
import `in`.sih26168.idr.pair.PairingUploader

class IdrApplication : Application() {
    lateinit var bus: IdrBus
        private set

    override fun onCreate() {
        super.onCreate()
        bus = IdrBus()
        PairingUploader.start(this)
        if (Build.VERSION.SDK_INT >= 26) {
            val nm = getSystemService(NotificationManager::class.java)
            nm.createNotificationChannel(
                NotificationChannel(
                    CHANNEL_ID,
                    getString(R.string.channel_record),
                    NotificationManager.IMPORTANCE_LOW,
                ).apply {
                    setShowBadge(false)
                    // Shown in Android's own notification settings, so it has to
                    // be readable by somebody who is not on this project.
                    description = "The ongoing notice that appears while the app " +
                        "is tracking with the screen off. Turning it off does not " +
                        "stop tracking, it only hides it."
                },
            )
        }
    }

    companion object {
        const val CHANNEL_ID = "idr_record"
        const val NOTIF_ID = 26168
    }
}
