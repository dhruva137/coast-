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
import `in`.sih26168.idr.data.LocationStatus
import `in`.sih26168.idr.data.OriginSource
import `in`.sih26168.idr.data.Prefs
import `in`.sih26168.idr.data.RecordStats
import `in`.sih26168.idr.demo.TrackerHooks
import `in`.sih26168.idr.nav.OnnxSpeedModel
import `in`.sih26168.idr.nav.SimpleIns
import `in`.sih26168.idr.sensor.GnssHub
import `in`.sih26168.idr.sensor.IoVnbdCsv
import `in`.sih26168.idr.sensor.LiveSensorSource
import `in`.sih26168.idr.sensor.LocationGate
import `in`.sih26168.idr.sensor.ReplaySensorSource
import `in`.sih26168.idr.sensor.SensorHub
import `in`.sih26168.idr.sensor.SensorSource
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.UUID

/**
 * Foreground service: RECORD writes frozen CSV; NAVIGATE runs [SimpleIns].
 * Survives screen-off via FGS + partial wake lock.
 *
 * NAVIGATE does not require location. It arms on the IMU alone and runs in
 * relative mode; GNSS, when and if it appears, upgrades the same session to an
 * absolute one. Nothing here blocks on a fix.
 *
 * NAVIGATE sensors come from a [SensorSource]: live phone hubs by default, or
 * a bundled IO-VNBD-style replay when [IdrBus.replayEnabled] is set.
 */
class RecordService : LifecycleService() {
    private lateinit var bus: IdrBus
    private var wakeLock: PowerManager.WakeLock? = null
    private var sensors: SensorHub? = null
    private var gnss: GnssHub? = null
    private var source: SensorSource? = null
    private var logger: CsvLogger? = null
    private val ins = SimpleIns()
    private val insLock = Any()
    private var speedModel: OnnxSpeedModel? = null
    private var lastHudNs = 0L
    private var lastTrackNs = 0L
    private var lastStatsNs = 0L
    private var lastLocationCheckNs = 0L
    private var startedAt = 0L
    /** Stable id for optional LAN tracker frames this arm (tracker flavor only). */
    private var sessionId: String = ""
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
        sessionId = UUID.randomUUID().toString().take(8)
        lastHudNs = 0L
        lastTrackNs = 0L
        lastStatsNs = 0L
        lastLocationCheckNs = 0L
        lastFixLat = Double.NaN
        lastFixLon = Double.NaN

        // Read the location gate up front so the first HUD frame already carries
        // the true state instead of a hopeful default.
        val gate = LocationGate.status(this)
        bus.publishLocation(gate)
        synchronized(insLock) { ins.setLocationStatus(gate) }

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
            gnss = GnssHub(
                context = this,
                onFix = { fix ->
                    lastFixLat = fix.lat
                    lastFixLon = fix.lon
                    drainMarks()
                    created.logGnss(fix)
                    publishRecord(fix.tNs, force = true)
                },
                onStatus = { status -> bus.publishLocation(status) },
            ).also { it.start() }
            publishRecord(startedAt, force = true)
        } else {
            // Load AVNet-tiny once per arm. A failure here is reported on the
            // HUD, never papered over -- the estimator just stays in FALLBACK.
            val model = OnnxSpeedModel(this)
            speedModel = model
            val prefs = Prefs(this)
            synchronized(insLock) {
                ins.setModelStatus(model.ready, model.error, model.droppedWindows)
                applyMountLocked(prefs)
            }
            val blackout = { bus.gnssBlackout.value }
            val wantReplay = bus.replayEnabled.value
            val navSource: SensorSource = if (wantReplay) {
                try {
                    ReplaySensorSource(
                        context = this,
                        assetPath = IoVnbdCsv.DEFAULT_ASSET,
                        blackout = blackout,
                    )
                } catch (t: Throwable) {
                    // Missing / unreadable asset → live sensors, never crash.
                    android.util.Log.w(TAG, "Replay asset failed, falling back to live", t)
                    bus.setReplayEnabled(false)
                    LiveSensorSource(this, blackout)
                }
            } else {
                LiveSensorSource(this, blackout)
            }
            bus.setReplayActive(navSource is ReplaySensorSource)
            source = navSource
            navSource.start(
                onFrame = { frame ->
                    // Inference runs on the sensor/replay thread, off main, and
                    // only fires on the ~10 Hz ticks where a window closes.
                    val est = model.onImu(frame)
                    synchronized(insLock) {
                        if (est != null) ins.onModel(est, model.hz)
                        ins.setModelStatus(model.ready, model.error, model.droppedWindows)
                        drainMarksLocked()
                        drainOriginLocked()
                        ins.onImu(frame)
                        maybeRecheckLocationLocked(frame.tNs)
                        maybePublishHudLocked(frame.tNs)
                    }
                },
                onGnss = { fix ->
                    if (fix == null || bus.gnssBlackout.value) return@start
                    lastFixLat = fix.lat
                    lastFixLon = fix.lon
                    synchronized(insLock) {
                        ins.onGnss(fix)
                        maybePublishHudLocked(fix.tNs, force = true)
                    }
                },
                onStatus = { status ->
                    val effective =
                        if (bus.gnssBlackout.value) LocationStatus.LOST else status
                    bus.publishLocation(effective)
                    synchronized(insLock) { ins.setLocationStatus(effective) }
                },
            )
            bus.publishSensors(navSource.sensorReport())
            synchronized(insLock) {
                bus.publishHud(ins.snapshot(SystemClock.elapsedRealtimeNanos(), AppMode.NAVIGATE))
                bus.publishTrack(ins.trackSnapshot())
            }
        }
        startInForeground()
    }

    /** Load the calibrated mount from prefs, or fall back to raw device axes. */
    private fun applyMountLocked(prefs: Prefs) {
        val rotation = prefs.mount
        val note = prefs.mountNote
        ins.setMount(
            rotation,
            if (rotation != null && note.isNotBlank()) {
                "mount calibrated: $note"
            } else if (rotation != null) {
                "mount calibrated"
            } else {
                "raw device axes -- not calibrated"
            },
        )
    }

    /**
     * The broadcast receiver in [GnssHub] covers the common toggles, but a
     * permission revoked from Settings while we run produces no broadcast, so
     * re-read the gate roughly once a second. Cheap: two boolean lookups.
     */
    private fun maybeRecheckLocationLocked(tNs: Long) {
        if (lastLocationCheckNs != 0L && tNs - lastLocationCheckNs < 1_000_000_000L) return
        lastLocationCheckNs = tNs
        if (bus.gnssBlackout.value) {
            ins.setLocationStatus(LocationStatus.LOST)
            if (bus.location.value != LocationStatus.LOST) {
                bus.publishLocation(LocationStatus.LOST)
            }
            return
        }
        if (bus.replayActive.value) {
            // Replay owns status via SensorSource callbacks.
            source?.refreshStatus()
            return
        }
        val blocking = LocationGate.blockingStatus(this)
        val status = blocking ?: LocationStatus.WAITING_FOR_FIX
        ins.setLocationStatus(status)
        if (bus.location.value != status) bus.publishLocation(status)
        source?.refreshStatus()
        gnss?.refreshStatus()
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
        if (bus.markRequested && ins.armed) {
            bus.markRequested = false
            bus.publishHud(ins.mark())
        }
    }

    /** Apply a start point the user set by hand, or a request to drop it. */
    private fun drainOriginLocked() {
        if (bus.clearOriginRequested) {
            bus.clearOriginRequested = false
            ins.clearUserOrigin()
        }
        val lat = bus.pendingOriginLat
        val lon = bus.pendingOriginLon
        if (lat != null && lon != null) {
            bus.pendingOriginLat = null
            bus.pendingOriginLon = null
            ins.setUserOrigin(lat, lon, bus.pendingOriginSource)
        }
        if (bus.mountDirty) {
            bus.mountDirty = false
            applyMountLocked(Prefs(this))
        }
    }

    /**
     * Push telemetry to the UI at [HUD_PERIOD_NS], and the track at the slower
     * [TRACK_PERIOD_NS].
     *
     * PERFORMANCE. This used to publish at 20 Hz, and each frame carried a full
     * copy of both trails, so the Compose tree that collected it re-ran 20 times
     * a second with two freshly allocated lists behind it. 10 Hz is past the
     * point a human reads a changing number, and the track -- the only part that
     * is expensive to draw -- moves at 4 Hz, which is still faster than the
     * camera spring settles.
     */
    private fun maybePublishHudLocked(tNs: Long, force: Boolean = false) {
        if (!force && lastHudNs != 0L && tNs - lastHudNs < HUD_PERIOD_NS) return
        lastHudNs = tNs
        val snap = ins.snapshot(tNs, AppMode.NAVIGATE)
        bus.publishHud(snap)
        // Flavor-specific: standard no-ops; tracker may POST off a bg thread.
        TrackerHooks.onHud(this, snap, sessionId)
        if (force || lastTrackNs == 0L || tNs - lastTrackNs >= TRACK_PERIOD_NS) {
            lastTrackNs = tNs
            // No-ops unless the estimator actually appended a point.
            bus.publishTrack(ins.trackSnapshot())
        }
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
        val log = logger
        try {
            log?.close()
        } catch (_: Exception) {
        }
        val dir = log?.dir
        logger = null
        tearDown()
        bus.setMode(AppMode.IDLE)
        var qualitySummary: String? = null
        if (dir != null) {
            try {
                val report = QualityGate.writeReport(dir)
                qualitySummary = report.summary
            } catch (_: Exception) {
            }
        }
        bus.publishRecord(
            RecordStats(
                running = false,
                sessionDir = dir?.absolutePath,
                qualitySummary = qualitySummary,
            ),
        )
        stopForeground(STOP_FOREGROUND_REMOVE)
        stopSelf()
    }

    private fun tearDown(keepWakelock: Boolean = false) {
        source?.stop()
        source = null
        bus.setReplayActive(false)
        gnss?.stop()
        gnss = null
        sensors?.stop()
        sensors = null
        // After the sensor thread is down, so no run() is in flight.
        try {
            speedModel?.close()
        } catch (_: Exception) {
        }
        speedModel = null
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
        val navigating = bus.mode.value == AppMode.NAVIGATE
        val usingGnss = LocationGate.hasPermission(this)
        // Say what is being collected and where it goes, in the notification
        // itself. A user who pulls the shade down mid-ride should not have to
        // open the app to find out what it is doing with the sensors.
        val title = if (navigating) {
            getString(R.string.notif_navigate_title)
        } else {
            getString(R.string.notif_record_title)
        }
        val text = when {
            navigating && usingGnss -> getString(R.string.notif_navigate_gnss)
            navigating -> getString(R.string.notif_navigate_imu)
            usingGnss -> getString(R.string.notif_record_gnss)
            else -> getString(R.string.notif_record_imu)
        }
        val notif: Notification = NotificationCompat.Builder(this, IdrApplication.CHANNEL_ID)
            .setContentTitle(title)
            .setContentText(text)
            .setStyle(NotificationCompat.BigTextStyle().bigText(text))
            .setSmallIcon(R.drawable.ic_stat_idr)
            .setContentIntent(pending)
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .setShowWhen(false)
            .setCategory(NotificationCompat.CATEGORY_SERVICE)
            .build()
        // FOREGROUND_SERVICE_TYPE_LOCATION requires the location permission to
        // actually be held; declaring it without the grant throws and kills the
        // app. Without location we are still a legitimate dataSync service --
        // the IMU stream is what we are keeping alive for.
        if (Build.VERSION.SDK_INT >= 34) {
            val type = if (usingGnss) {
                ServiceInfo.FOREGROUND_SERVICE_TYPE_LOCATION or
                    ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC
            } else {
                ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC
            }
            startForeground(IdrApplication.NOTIF_ID, notif, type)
        } else {
            startForeground(IdrApplication.NOTIF_ID, notif)
        }
    }

    companion object {
        private const val TAG = "RecordService"

        /** 10 Hz. Fast enough to read as live, slow enough to skip most frames. */
        private const val HUD_PERIOD_NS = 100_000_000L

        /** 4 Hz. The map path is rebuilt at most this often. */
        private const val TRACK_PERIOD_NS = 250_000_000L

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

        /** Convenience for the Drive screen setting a start point by hand. */
        fun originSourceForMap(): OriginSource = OriginSource.USER_MAP
    }
}

private fun String.sanitize(): String =
    lowercase(Locale.US).replace(Regex("[^a-z0-9_\\-]+"), "_").trim('_').ifBlank { "rider" }
