package `in`.sih26168.idr.sensor

import `in`.sih26168.idr.data.GnssFix
import `in`.sih26168.idr.data.LocationStatus
import `in`.sih26168.idr.data.SensorFrame
import `in`.sih26168.idr.data.SensorReport

/**
 * Unified sensor feed for navigation. Live phone sensors and CSV replay both
 * implement this so [in.sih26168.idr.nav.SimpleIns] cannot tell them apart.
 *
 * Uses [SensorFrame] (the project's existing IMU type); the pitch spec's
 * `ImuFrame` name maps 1:1 onto it.
 */
interface SensorSource {
    fun start(
        onFrame: (SensorFrame) -> Unit,
        onGnss: (GnssFix?) -> Unit,
        onStatus: (LocationStatus) -> Unit = {},
    )

    fun stop()

    /** Re-read location gate (live only). No-op for replay. */
    fun refreshStatus() = Unit

    /** Hardware report for the HUD; replay reports a fixed "csv" profile. */
    fun sensorReport(): SensorReport = SensorReport()

    fun sensorNotes(): String = ""
}
