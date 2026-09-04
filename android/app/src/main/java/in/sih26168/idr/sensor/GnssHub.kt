package `in`.sih26168.idr.sensor

import android.annotation.SuppressLint
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.location.GnssStatus
import android.location.Location
import android.location.LocationListener
import android.location.LocationManager
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.HandlerThread
import android.os.Looper
import android.os.SystemClock
import `in`.sih26168.idr.data.GnssFix
import `in`.sih26168.idr.data.LocationStatus
import java.util.concurrent.atomic.AtomicInteger

/**
 * GNSS source that tolerates location being off, denied, or switched mid-ride.
 *
 * The original version subscribed once at [start] to whichever providers
 * happened to be enabled at that instant. That is wrong for this app: the whole
 * point is journeys where location comes and goes. This version watches
 * [LocationManager.PROVIDERS_CHANGED_ACTION] and re-subscribes when providers
 * appear, so a user who turns location on halfway through a ride gets fixes
 * without restarting the session -- and one who turns it off gets a state
 * change rather than silence.
 *
 * [onStatus] fires on every change of the blocking state so the estimator and
 * the UI can react. It never throws on a missing permission; a denied
 * permission is simply reported as [LocationStatus.PERMISSION_DENIED].
 */
class GnssHub(
    private val context: Context,
    private val onFix: (GnssFix) -> Unit,
    private val onStatus: (LocationStatus) -> Unit = {},
) : LocationListener {
    private val lm = context.getSystemService(Context.LOCATION_SERVICE) as LocationManager
    private val nSats = AtomicInteger(0)
    private var thread: HandlerThread? = null
    private var statusCb: GnssStatus.Callback? = null
    private var providerRx: BroadcastReceiver? = null
    private var subscribed = false

    @Volatile
    var lastStatus: LocationStatus = LocationStatus.UNKNOWN
        private set

    fun start() {
        stop()
        val t = HandlerThread("idr-gnss").also { it.start(); thread = it }
        val handler = Handler(t.looper)

        // Re-subscribe when the user toggles location or a provider appears.
        val rx = object : BroadcastReceiver() {
            override fun onReceive(c: Context?, intent: Intent?) {
                subscribe(t.looper, handler)
                publishStatus()
            }
        }
        providerRx = rx
        try {
            val filter = IntentFilter(LocationManager.PROVIDERS_CHANGED_ACTION).apply {
                addAction(LocationManager.MODE_CHANGED_ACTION)
            }
            if (Build.VERSION.SDK_INT >= 33) {
                context.registerReceiver(rx, filter, Context.RECEIVER_NOT_EXPORTED)
            } else {
                context.registerReceiver(rx, filter)
            }
        } catch (_: Exception) {
            // A missing receiver only costs us live re-subscription; polling in
            // the service still updates the status.
            providerRx = null
        }

        subscribe(t.looper, handler)
        publishStatus()
    }

    /** Re-read the blocking state and tell the listener if it changed. */
    fun refreshStatus() = publishStatus()

    @SuppressLint("MissingPermission")
    private fun subscribe(looper: Looper, handler: Handler) {
        if (!LocationGate.hasPermission(context)) return
        if (subscribed) {
            // Providers changed: drop and re-add so a newly enabled provider
            // is picked up and a disabled one is not left registered.
            try {
                lm.removeUpdates(this)
            } catch (_: Exception) {
            }
            subscribed = false
        }

        if (statusCb == null) {
            val cb = object : GnssStatus.Callback() {
                override fun onSatelliteStatusChanged(status: GnssStatus) {
                    var used = 0
                    for (i in 0 until status.satelliteCount) {
                        if (status.usedInFix(i)) used += 1
                    }
                    nSats.set(used)
                }
            }
            try {
                if (Build.VERSION.SDK_INT >= 30) {
                    lm.registerGnssStatusCallback(context.mainExecutor, cb)
                } else {
                    @Suppress("DEPRECATION")
                    lm.registerGnssStatusCallback(cb, handler)
                }
                statusCb = cb
            } catch (_: SecurityException) {
            } catch (_: Exception) {
            }
        }

        var any = false
        try {
            if (lm.isProviderEnabled(LocationManager.GPS_PROVIDER)) {
                lm.requestLocationUpdates(LocationManager.GPS_PROVIDER, 0L, 0f, this, looper)
                any = true
            }
            if (lm.isProviderEnabled(LocationManager.NETWORK_PROVIDER)) {
                lm.requestLocationUpdates(LocationManager.NETWORK_PROVIDER, 1_000L, 0f, this, looper)
                any = true
            }
        } catch (_: SecurityException) {
        } catch (_: Exception) {
        }
        subscribed = any
    }

    private fun publishStatus() {
        val s = LocationGate.status(context)
        if (s != lastStatus) {
            lastStatus = s
            onStatus(s)
        }
    }

    fun stop() {
        try {
            lm.removeUpdates(this)
        } catch (_: Exception) {
        }
        subscribed = false
        statusCb?.let {
            try {
                lm.unregisterGnssStatusCallback(it)
            } catch (_: Exception) {
            }
        }
        statusCb = null
        providerRx?.let {
            try {
                context.unregisterReceiver(it)
            } catch (_: Exception) {
            }
        }
        providerRx = null
        thread?.quitSafely()
        thread = null
    }

    override fun onLocationChanged(location: Location) {
        val tNs = if (location.elapsedRealtimeNanos != 0L) {
            location.elapsedRealtimeNanos
        } else {
            SystemClock.elapsedRealtimeNanos()
        }
        val accV = if (Build.VERSION.SDK_INT >= 26 && location.hasVerticalAccuracy()) {
            location.verticalAccuracyMeters.toDouble()
        } else {
            Double.NaN
        }
        onFix(
            GnssFix(
                tNs = tNs,
                lat = location.latitude,
                lon = location.longitude,
                alt = if (location.hasAltitude()) location.altitude else 0.0,
                speed = if (location.hasSpeed()) location.speed.toDouble() else 0.0,
                bearing = if (location.hasBearing()) location.bearing.toDouble() else Double.NaN,
                accH = if (location.hasAccuracy()) location.accuracy.toDouble() else Double.NaN,
                accV = accV,
                nSats = nSats.get(),
            ),
        )
    }

    @Deprecated("Deprecated in Java")
    override fun onStatusChanged(provider: String?, status: Int, extras: Bundle?) = Unit

    override fun onProviderEnabled(provider: String) {
        publishStatus()
    }

    override fun onProviderDisabled(provider: String) {
        nSats.set(0)
        publishStatus()
    }
}
