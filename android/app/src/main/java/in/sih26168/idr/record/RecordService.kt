package `in`.sih26168.idr.record

import android.app.Notification
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
import android.os.PowerManager
import android.os.SystemClock
import androidx.core.app.NotificationCompat
import androidx.lifecycle.LifecycleService
import `in`.sih26168.idr.IdrApplication
import `in`.sih26168.idr.IdrBus
import `in`.sih26168.idr.MainActivity
import `in`.sih26168.idr.R
import `in`.sih26168.idr.data.AppMode
import `in`.sih26168.idr.data.RecordStats
import `in`.sih26168.idr.nav.SimpleIns
import `in`.sih26168.idr.sensor.GnssHub
import `in`.sih26168.idr.sensor.SensorHub
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * Foreground service: RECORD writes frozen CSV; NAVIGATE runs [SimpleIns].
 * Survives screen-off via FGS + partial wake lock.
 */
class RecordService : LifecycleService() {
    private lateinit var bus: IdrBus
    private var wakeLock: PowerManager.WakeLock? = null
    private var sensors: SensorHub? = null
    private var gnss: GnssHub? = null
    private var logger: CsvLogger? = null
    private val ins = SimpleIns()
    private val insLock = Any()
    private var lastHudNs = 0L
    private var lastStatsNs = 0L
    private var startedAt = 0L
    @Volatile private var lastFixLat = Double.NaN
    @Volatile private var lastFixLon = Double.NaN

    override fun onCreate() {
        super.onCreate()
        bus = (application as IdrApplication).bus
        startInForeground()
        val pm = getSystemService(POWER_SERVICE) as PowerManager
        wakeLock = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "idr:record").apply {
            setReferenceCounted(false)
            acquire()
        }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        super.onStartCommand(intent, flags, startId)
        startInForeground()
        when (intent?.action) {
            ACTION_START_RECORD -> startMode(AppMode.RECORD)
            ACTION_START_NAVIGATE -> startMode(AppMode.NAVIGATE)
            ACTION_STOP -> stopEverything()
            ACTION_MARK -> bus.markRequested = true
            ACTION_CLEAR_MARK -> bus.clearMarkRequested = true
            null -> if (bus.mode.value == AppMode.IDLE) stopEverything()
        }
        return START_STICKY
    }

    override fun onBind(intent: Intent): IBinder? {
        super.onBind(intent)
        return null
    }

    override fun onDestroy() {
        tearDown()
        super.onDestroy()
    }

    private fun startMode(mode: AppMode) {
        tearDown(keepWakelock = true)
        synchronized(insLock) { ins.reset() }
        bus.setMode(mode)
        startedAt = SystemClock.elapsedRealtimeNanos()
        lastHudNs = 0L
        lastStatsNs = 0L
        lastFixLat = Double.NaN
        lastFixLon = Double.NaN

        if (mode == AppMode.RECORD) {
            val cfg = bus.config.value
            val rider = cfg.rider.ifBlank { "rider" }.sanitize()
            val vehicle = cfg.vehicle.name
            val stamp = SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(Date())
            val dir = File(File(File(logsRoot(), rider), vehicle), stamp)
            val created = CsvLogger(dir, cfg)
            logger = created
            val hub = SensorHub(this) { frame ->
                drainMarks()
                created.logImu(frame)
                publishRecord(frame.tNs)
            }
            sensors = hub
            hub.start()
            created.setSensorNotes(hub.sensorNotes())
            bus.publishSensors(hub.report)
            gnss = GnssHub(this) { fix ->
                lastFixLat = fix.lat
                lastFixLon = fix.lon
                drainMarks()
                created.logGnss(fix)
                publishRecord(fix.tNs, force = true)
            }.also { it.start() }
            publishRecord(startedAt, force = true)
        } else {
            val hub = SensorHub(this) { frame ->
                synchronized(insLock) {
                    drainMarksLocked()
                    ins.onImu(frame)
                    maybePublishHudLocked(frame.tNs)
                }
            }
            sensors = hub
            hub.start()
            bus.publishSensors(hub.report)
            gnss = GnssHub(this) { fix ->
                lastFixLat = fix.lat
                lastFixLon = fix.lon
                synchronized(insLock) {
                    ins.onGnss(fix)
                    maybePublishHudLocked(fix.tNs, force = true)
                }
            }.also { it.start() }
            synchronized(insLock) {
                bus.publishHud(ins.snapshot(SystemClock.elapsedRealtimeNanos(), AppMode.NAVIGATE))
            }
        }
        startInForeground()
    }

    private fun drainMarks() {
        if (bus.clearMarkRequested) {
            bus.clearMarkRequested = false
        }
        if (bus.markRequested && lastFixLat.isFinite() && lastFixLon.isFinite()) {
            bus.markRequested = false
            logger?.updateLoopClosure(lastFixLat, lastFixLon)
        }
    }

    private fun drainMarksLocked() {
        if (bus.clearMarkRequested) {
            bus.clearMarkRequested = false
            ins.clearMark()
        }
        if (bus.markRequested && ins.seeded) {
            bus.markRequested = false
            bus.publishHud(ins.mark())
        }
    }

    private fun maybePublishHudLocked(tNs: Long, force: Boolean = false) {
        if (!force && lastHudNs != 0L && tNs - lastHudNs < 50_000_000L) return
        lastHudNs = tNs
        bus.publishHud(ins.snapshot(tNs, AppMode.NAVIGATE))
    }

    private fun publishRecord(tNs: Long, force: Boolean = false) {
        if (!force && lastStatsNs != 0L && tNs - lastStatsNs < 100_000_000L) return
        lastStatsNs = tNs
        val log = logger
        bus.publishRecord(
            RecordStats(
                running = true,
                sessionDir = log?.dir?.absolutePath,
                imuRows = log?.imuCount ?: 0L,
                gnssRows = log?.gnssCount ?: 0L,
                startedAtNs = startedAt,
                imuHz = log?.imuHz() ?: 0.0,
            ),
        )
    }

    private fun stopEverything() {
        val dir = logger?.dir?.absolutePath
        tearDown()
        bus.setMode(AppMode.IDLE)
        bus.publishRecord(RecordStats(running = false, sessionDir = dir))
        stopForeground(STOP_FOREGROUND_REMOVE)
        stopSelf()
    }

    private fun tearDown(keepWakelock: Boolean = false) {
        gnss?.stop()
        gnss = null
        sensors?.stop()
        sensors = null
        try {
            logger?.close()
        } catch (_: Exception) {
        }
        logger = null
        if (!keepWakelock) {
            if (wakeLock?.isHeld == true) wakeLock?.release()
        }
    }

    private fun logsRoot(): File {
        val ext = getExternalFilesDir(null) ?: filesDir
        return File(ext, "data")
    }

    private fun startInForeground() {
        val pending = PendingIntent.getActivity(
            this,
            0,
            Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val text = when (bus.mode.value) {
            AppMode.NAVIGATE -> getString(R.string.notif_navigate)
            else -> getString(R.string.notif_record)
        }
        val notif: Notification = NotificationCompat.Builder(this, IdrApplication.CHANNEL_ID)
            .setContentTitle("IDR · SIH26168")
            .setContentText(text)
            .setSmallIcon(R.drawable.ic_stat_idr)
            .setContentIntent(pending)
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .setCategory(NotificationCompat.CATEGORY_SERVICE)
            .build()
        if (Build.VERSION.SDK_INT >= 34) {
            startForeground(
                IdrApplication.NOTIF_ID,
                notif,
                ServiceInfo.FOREGROUND_SERVICE_TYPE_LOCATION or
                    ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE,
            )
        } else {
            startForeground(IdrApplication.NOTIF_ID, notif)
        }
    }

    companion object {
        const val ACTION_START_RECORD = "in.sih26168.idr.START_RECORD"
        const val ACTION_START_NAVIGATE = "in.sih26168.idr.START_NAVIGATE"
        const val ACTION_STOP = "in.sih26168.idr.STOP"
        const val ACTION_MARK = "in.sih26168.idr.MARK"
        const val ACTION_CLEAR_MARK = "in.sih26168.idr.CLEAR_MARK"

        fun start(context: Context, mode: AppMode) {
            val i = Intent(context, RecordService::class.java).setAction(
                if (mode == AppMode.RECORD) ACTION_START_RECORD else ACTION_START_NAVIGATE,
            )
            if (Build.VERSION.SDK_INT >= 26) {
                context.startForegroundService(i)
            } else {
                context.startService(i)
            }
        }

        fun stop(context: Context) {
            context.startService(Intent(context, RecordService::class.java).setAction(ACTION_STOP))
        }

        fun mark(context: Context) {
            context.startService(Intent(context, RecordService::class.java).setAction(ACTION_MARK))
        }
    }
}

private fun String.sanitize(): String =
    lowercase(Locale.US).replace(Regex("[^a-z0-9_\\-]+"), "_").trim('_').ifBlank { "rider" }
