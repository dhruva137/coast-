package `in`.sih26168.idr.sensor

import android.content.Context
import `in`.sih26168.idr.data.GnssFix
import `in`.sih26168.idr.data.LocationStatus
import `in`.sih26168.idr.data.SensorFrame
import `in`.sih26168.idr.data.SensorReport

/**
 * Phone sensors via the existing [SensorHub] / [GnssHub] pair.
 *
 * Numeric behaviour is identical to wiring those hubs directly into
 * [in.sih26168.idr.record.RecordService] — this is only an interface adapter.
 *
 * When [blackout] returns true, GNSS fixes are dropped (not delivered). The
 * estimator then coasts on IMU alone, same as a real outage.
 */
class LiveSensorSource(
    private val context: Context,
    private val blackout: () -> Boolean = { false },
) : SensorSource {
    private var sensors: SensorHub? = null
    private var gnss: GnssHub? = null
    private var report: SensorReport = SensorReport()

    override fun start(
        onFrame: (SensorFrame) -> Unit,
        onGnss: (GnssFix?) -> Unit,
        onStatus: (LocationStatus) -> Unit,
    ) {
        stop()
        val hub = SensorHub(context, onFrame)
        sensors = hub
        hub.start()
        report = hub.report
        gnss = GnssHub(
            context = context,
            onFix = { fix ->
                if (!blackout()) onGnss(fix)
            },
            onStatus = { status ->
                if (blackout()) onStatus(LocationStatus.LOST) else onStatus(status)
            },
        ).also { it.start() }
    }

    override fun stop() {
        gnss?.stop()
        gnss = null
        sensors?.stop()
        sensors = null
    }

    override fun refreshStatus() {
        gnss?.refreshStatus()
    }

    override fun sensorReport(): SensorReport = report

    override fun sensorNotes(): String = sensors?.sensorNotes() ?: ""
}
