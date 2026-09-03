package `in`.sih26168.idr.sensor

import android.annotation.SuppressLint
import android.content.Context
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
import java.util.concurrent.atomic.AtomicInteger

class GnssHub(
    context: Context,
    private val onFix: (GnssFix) -> Unit,
) : LocationListener {
    private val lm = context.getSystemService(Context.LOCATION_SERVICE) as LocationManager
    private val nSats = AtomicInteger(0)
    private var thread: HandlerThread? = null
    private var statusCb: GnssStatus.Callback? = null

    @SuppressLint("MissingPermission")
    fun start() {
        stop()
        val t = HandlerThread("idr-gnss").also { it.start(); thread = it }
        val looper: Looper = t.looper
        val handler = Handler(looper)

        val cb = object : GnssStatus.Callback() {
            override fun onSatelliteStatusChanged(status: GnssStatus) {
                var used = 0
                for (i in 0 until status.satelliteCount) {
                    if (status.usedInFix(i)) used += 1
                }
                nSats.set(used)
            }
        }
        statusCb = cb
        try {
            if (Build.VERSION.SDK_INT >= 30) {
                lm.registerGnssStatusCallback(context.mainExecutor, cb)
            } else {
                @Suppress("DEPRECATION")
                lm.registerGnssStatusCallback(cb, handler)
            }
        } catch (_: SecurityException) {
            // Permission gate in UI; service no-ops GNSS if denied.
        }

        try {
            if (lm.isProviderEnabled(LocationManager.GPS_PROVIDER)) {
                lm.requestLocationUpdates(LocationManager.GPS_PROVIDER, 0L, 0f, this, looper)
            }
            if (lm.isProviderEnabled(LocationManager.NETWORK_PROVIDER)) {
                lm.requestLocationUpdates(LocationManager.NETWORK_PROVIDER, 1_000L, 0f, this, looper)
            }
        } catch (_: SecurityException) {
        }
    }

    fun stop() {
        try {
            lm.removeUpdates(this)
        } catch (_: Exception) {
        }
        statusCb?.let {
            try {
                lm.unregisterGnssStatusCallback(it)
            } catch (_: Exception) {
            }
        }
        statusCb = null
        thread?.quitSafely()
        thread = null
    }

    override fun onLocationChanged(location: Location) {
        val tNs = if (Build.VERSION.SDK_INT >= 17 && location.elapsedRealtimeNanos != 0L) {
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
    override fun onProviderEnabled(provider: String) = Unit
    override fun onProviderDisabled(provider: String) = Unit
}
