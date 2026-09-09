package `in`.sih26168.idr.sensor

import android.content.Context
import android.os.Handler
import android.os.HandlerThread
import android.os.SystemClock
import `in`.sih26168.idr.data.GnssFix
import `in`.sih26168.idr.data.LocationStatus
import `in`.sih26168.idr.data.SensorFrame
import `in`.sih26168.idr.data.SensorReport
import java.util.concurrent.atomic.AtomicBoolean

/**
 * Streams a pre-parsed IO-VNBD drive through the same callbacks as
 * [LiveSensorSource], pacing emissions to the recorded timestamps (~10 Hz).
 *
 * The estimator downstream cannot tell this apart from live sensors. When
 * [blackout] is true, GNSS rows are suppressed (same contract as live).
 */
class ReplaySensorSource(
    private val rows: List<IoVnbdRow>,
    private val blackout: () -> Boolean = { false },
    private val onFinished: (() -> Unit)? = null,
) : SensorSource {

    constructor(
        context: Context,
        assetPath: String = IoVnbdCsv.DEFAULT_ASSET,
        blackout: () -> Boolean = { false },
        onFinished: (() -> Unit)? = null,
    ) : this(
        rows = context.assets.open(assetPath).use { IoVnbdCsv.parse(it) },
        blackout = blackout,
        onFinished = onFinished,
    )

    private var thread: HandlerThread? = null
    private var handler: Handler? = null
    private val running = AtomicBoolean(false)
    private var wallStartMs = 0L
    private var t0Ns = 0L
    private var index = 0

    override fun start(
        onFrame: (SensorFrame) -> Unit,
        onGnss: (GnssFix?) -> Unit,
        onStatus: (LocationStatus) -> Unit,
    ) {
        stop()
        if (rows.isEmpty()) {
            onStatus(LocationStatus.NO_PROVIDER)
            onFinished?.invoke()
            return
        }
        running.set(true)
        index = 0
        t0Ns = rows.first().tNs
        wallStartMs = SystemClock.elapsedRealtime()
        val t = HandlerThread("idr-replay").also { it.start(); thread = it }
        val h = Handler(t.looper).also { handler = it }
        onStatus(LocationStatus.WAITING_FOR_FIX)
        h.post { tick(onFrame, onGnss, onStatus) }
    }

    /**
     * Test / injection helper: emit every row immediately on the caller thread
     * using the recorded timestamps (no Handler, no wall clock). Production
     * demo path uses [start] for real-time pacing.
     */
    fun emitAllSync(
        onFrame: (SensorFrame) -> Unit,
        onGnss: (GnssFix?) -> Unit,
        onStatus: (LocationStatus) -> Unit = {},
        baseTns: Long = 1_000_000_000L,
    ) {
        if (rows.isEmpty()) {
            onStatus(LocationStatus.NO_PROVIDER)
            onFinished?.invoke()
            return
        }
        val t0 = rows.first().tNs
        onStatus(LocationStatus.WAITING_FOR_FIX)
        for (row in rows) {
            val tNs = baseTns + (row.tNs - t0)
            onFrame(row.frame.copy(tNs = tNs))
            if (!blackout()) {
                val fix = row.fix
                if (fix != null) {
                    onGnss(fix.copy(tNs = tNs))
                    onStatus(LocationStatus.LIVE)
                }
            } else {
                onStatus(LocationStatus.LOST)
            }
        }
        onFinished?.invoke()
    }

    private fun tick(
        onFrame: (SensorFrame) -> Unit,
        onGnss: (GnssFix?) -> Unit,
        onStatus: (LocationStatus) -> Unit,
    ) {
        if (!running.get()) return
        if (index >= rows.size) {
            running.set(false)
            onFinished?.invoke()
            return
        }
        val row = rows[index]
        index += 1

        // Stamp with the phone clock so SimpleIns dt math stays valid; wall
        // pacing below follows the recorded row cadence (~10 Hz).
        val emitTns = SystemClock.elapsedRealtimeNanos()
        onFrame(row.frame.copy(tNs = emitTns))

        val suppress = blackout()
        if (!suppress) {
            val fix = row.fix
            if (fix != null) {
                onGnss(fix.copy(tNs = emitTns))
                onStatus(LocationStatus.LIVE)
            }
        } else {
            onStatus(LocationStatus.LOST)
        }

        if (index >= rows.size) {
            running.set(false)
            onFinished?.invoke()
            return
        }
        val nextRelNs = rows[index].tNs - t0Ns
        val delayMs = delayUntilNextMs(wallStartMs, nextRelNs, SystemClock.elapsedRealtime())
        handler?.postDelayed({ tick(onFrame, onGnss, onStatus) }, delayMs)
    }

    override fun stop() {
        running.set(false)
        handler?.removeCallbacksAndMessages(null)
        handler = null
        thread?.quitSafely()
        thread = null
    }

    override fun sensorReport(): SensorReport = SensorReport(
        accelUncal = true,
        gyroUncal = true,
        mag = true,
        gnss = true,
    )

    override fun sensorNotes(): String =
        "source=replay,rows=${rows.size},hz≈10,asset=IO-VNBD-style"

    companion object {
        /** Pure pacing math — unit-tested without Android Handler. */
        fun delayUntilNextMs(wallStartMs: Long, nextRelNs: Long, nowMs: Long): Long {
            val dueAtMs = wallStartMs + nextRelNs / 1_000_000L
            return (dueAtMs - nowMs).coerceAtLeast(0L)
        }
    }
}
