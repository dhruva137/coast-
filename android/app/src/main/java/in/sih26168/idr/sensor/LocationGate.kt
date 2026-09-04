package `in`.sih26168.idr.sensor

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.location.LocationManager
import android.os.Build
import android.provider.Settings
import androidx.core.content.ContextCompat
import `in`.sih26168.idr.data.LocationStatus

/**
 * Answers, at any instant, whether the location subsystem can give us anything
 * -- and if not, exactly which of the several different "no" cases we are in.
 *
 * The problem statement is about navigating when GNSS is unavailable, so these
 * states are first-class product behaviour, not error handling. Each one gets a
 * different banner and a different offer of help:
 *
 *  * [LocationStatus.PERMISSION_DENIED] -- ask for the permission.
 *  * [LocationStatus.SERVICES_OFF] -- the master switch is off; offer Settings.
 *  * [LocationStatus.NO_PROVIDER] -- on and permitted but nothing is enabled.
 *  * [LocationStatus.WAITING_FOR_FIX] -- everything is fine, no fix yet.
 *
 * In every one of them the app still runs, in relative mode.
 */
object LocationGate {

    fun hasPermission(context: Context): Boolean {
        val fine = ContextCompat.checkSelfPermission(
            context, Manifest.permission.ACCESS_FINE_LOCATION,
        ) == PackageManager.PERMISSION_GRANTED
        val coarse = ContextCompat.checkSelfPermission(
            context, Manifest.permission.ACCESS_COARSE_LOCATION,
        ) == PackageManager.PERMISSION_GRANTED
        return fine || coarse
    }

    /** True when only the coarse grant was given -- fixes will be low quality. */
    fun coarseOnly(context: Context): Boolean {
        val fine = ContextCompat.checkSelfPermission(
            context, Manifest.permission.ACCESS_FINE_LOCATION,
        ) == PackageManager.PERMISSION_GRANTED
        return !fine && hasPermission(context)
    }

    /** The device-wide location master switch. */
    fun servicesEnabled(context: Context): Boolean {
        val lm = context.getSystemService(Context.LOCATION_SERVICE) as? LocationManager
            ?: return false
        return try {
            if (Build.VERSION.SDK_INT >= 28) {
                lm.isLocationEnabled
            } else {
                @Suppress("DEPRECATION")
                Settings.Secure.getInt(
                    context.contentResolver,
                    Settings.Secure.LOCATION_MODE,
                    Settings.Secure.LOCATION_MODE_OFF,
                ) != Settings.Secure.LOCATION_MODE_OFF
            }
        } catch (_: Exception) {
            false
        }
    }

    fun gpsProviderEnabled(context: Context): Boolean = providerEnabled(context, LocationManager.GPS_PROVIDER)

    fun networkProviderEnabled(context: Context): Boolean =
        providerEnabled(context, LocationManager.NETWORK_PROVIDER)

    private fun providerEnabled(context: Context, provider: String): Boolean {
        val lm = context.getSystemService(Context.LOCATION_SERVICE) as? LocationManager
            ?: return false
        return try {
            lm.isProviderEnabled(provider)
        } catch (_: Exception) {
            false
        }
    }

    /**
     * The blocking status, ignoring whether a fix has actually arrived. Returns
     * null when nothing is blocking -- the caller then decides between
     * WAITING_FOR_FIX / LIVE / LOST from the age of the last fix.
     */
    fun blockingStatus(context: Context): LocationStatus? = when {
        !hasPermission(context) -> LocationStatus.PERMISSION_DENIED
        !servicesEnabled(context) -> LocationStatus.SERVICES_OFF
        !gpsProviderEnabled(context) && !networkProviderEnabled(context) -> LocationStatus.NO_PROVIDER
        else -> null
    }

    fun status(context: Context): LocationStatus =
        blockingStatus(context) ?: LocationStatus.WAITING_FOR_FIX

    /** Short line for the banner. */
    fun headline(status: LocationStatus): String = when (status) {
        LocationStatus.PERMISSION_DENIED -> "Location permission not granted"
        LocationStatus.SERVICES_OFF -> "Location is switched off on this phone"
        LocationStatus.NO_PROVIDER -> "No location provider is enabled"
        LocationStatus.WAITING_FOR_FIX -> "Waiting for a first GPS fix"
        LocationStatus.LIVE -> "GPS fix live"
        LocationStatus.LOST -> "GPS fix lost"
        LocationStatus.UNKNOWN -> "Checking location"
    }

    /**
     * What it means for the user. Every one of these ends with what the app
     * will still do, because in all of them it still does something.
     */
    fun explain(status: LocationStatus): String = when (status) {
        LocationStatus.PERMISSION_DENIED ->
            "Without it the app can never know where on the Earth you are. It will " +
                "still track how far you travel and the shape of your route, from " +
                "the motion sensors alone, starting from wherever you are now."
        LocationStatus.SERVICES_OFF ->
            "Every app on this phone is cut off from GPS, not just this one. The app " +
                "will track distance and route shape from the motion sensors, but it " +
                "cannot place them on the map until you give it a starting point."
        LocationStatus.NO_PROVIDER ->
            "Location is on but no provider is currently available. Tracking " +
                "continues from the motion sensors in relative mode."
        LocationStatus.WAITING_FOR_FIX ->
            "A cold start can take a minute or two outdoors, and indoors it may never " +
                "arrive. Tracking has already started from the motion sensors; the " +
                "route will snap onto the map the moment a fix lands."
        LocationStatus.LIVE ->
            "Position is absolute and its accuracy is the figure the operating system " +
                "reports."
        LocationStatus.LOST ->
            "This is the case the app is built for. Position is now carried forward " +
                "from the motion sensors alone, and the uncertainty circle grows with " +
                "every metre until a fix comes back."
        LocationStatus.UNKNOWN -> "Reading the location settings."
    }

    /** True when the user can fix this from the phone Settings app. */
    fun settingsWouldHelp(status: LocationStatus): Boolean =
        status == LocationStatus.SERVICES_OFF || status == LocationStatus.NO_PROVIDER

    /** True when an in-app permission request is the right offer. */
    fun permissionWouldHelp(status: LocationStatus): Boolean =
        status == LocationStatus.PERMISSION_DENIED
}
