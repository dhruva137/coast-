package `in`.sih26168.idr

import android.app.Application
import android.app.NotificationChannel
import android.app.NotificationManager
import android.os.Build

class IdrApplication : Application() {
    lateinit var bus: IdrBus
        private set

    override fun onCreate() {
        super.onCreate()
        bus = IdrBus()
        if (Build.VERSION.SDK_INT >= 26) {
            val nm = getSystemService(NotificationManager::class.java)
            nm.createNotificationChannel(
                NotificationChannel(
                    CHANNEL_ID,
                    getString(R.string.channel_record),
                    NotificationManager.IMPORTANCE_LOW,
                ).apply {
                    setShowBadge(false)
                    description = "Foreground IMU/GNSS logging for SIH26168"
                },
            )
        }
    }

    companion object {
        const val CHANNEL_ID = "idr_record"
        const val NOTIF_ID = 26168
    }
}
