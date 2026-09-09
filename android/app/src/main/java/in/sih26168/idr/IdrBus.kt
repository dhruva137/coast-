package `in`.sih26168.idr

import android.os.Build
import `in`.sih26168.idr.data.AppMode
import `in`.sih26168.idr.data.DeviceCheck
import `in`.sih26168.idr.data.HudState
import `in`.sih26168.idr.data.LocationStatus
import `in`.sih26168.idr.data.MountType
import `in`.sih26168.idr.data.OriginSource
import `in`.sih26168.idr.data.RecordStats
import `in`.sih26168.idr.data.SensorReport
import `in`.sih26168.idr.data.SessionConfig
import `in`.sih26168.idr.data.TrackSnapshot
import `in`.sih26168.idr.data.VehicleKind
import `in`.sih26168.idr.nav.VehicleProfile
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update

/** Process-wide bus so Compose and [record.RecordService] share one clock. */
class IdrBus {
    private val _mode = MutableStateFlow(AppMode.IDLE)
    val mode: StateFlow<AppMode> = _mode.asStateFlow()

    private val _config = MutableStateFlow(
        SessionConfig(
            phoneModel = listOf(Build.MANUFACTURER, Build.MODEL)
                .filter { it.isNotBlank() }
                .joinToString(" ")
                .ifBlank { "unknown" },
            mountType = MountType.handlebar,
            vehicle = VehicleKind.scooter,
            rider = "rider",
            routeId = "campus_loop",
            notes = "",
        ),
    )
    val config: StateFlow<SessionConfig> = _config.asStateFlow()

    private val _hud = MutableStateFlow(HudState())
    val hud: StateFlow<HudState> = _hud.asStateFlow()

    /**
     * The map track, deliberately a SEPARATE flow from [hud].
     *
     * It changes far less often than the telemetry and it is the only piece of
     * state that is expensive to diff or to draw. Keeping it here means a speed
     * readout ticking at 10 Hz cannot invalidate the map, and the map's cached
     * `Path` survives every HUD frame that did not add a point.
     */
    private val _track = MutableStateFlow(TrackSnapshot())
    val track: StateFlow<TrackSnapshot> = _track.asStateFlow()

    private val _record = MutableStateFlow(RecordStats())
    val record: StateFlow<RecordStats> = _record.asStateFlow()

    private val _sensors = MutableStateFlow(SensorReport())
    val sensors: StateFlow<SensorReport> = _sensors.asStateFlow()

    /** Result of the startup hardware self-check. */
    private val _device = MutableStateFlow(DeviceCheck())
    val device: StateFlow<DeviceCheck> = _device.asStateFlow()

    /** Location availability as last read, independent of whether we are armed. */
    private val _location = MutableStateFlow(LocationStatus.UNKNOWN)
    val location: StateFlow<LocationStatus> = _location.asStateFlow()

    /**
     * Demo: suppress GNSS deliveries (live + replay). HUD reads this to flip
     * the GPS→IDR pill; the estimator just stops receiving fixes.
     */
    private val _gnssBlackout = MutableStateFlow(false)
    val gnssBlackout: StateFlow<Boolean> = _gnssBlackout.asStateFlow()

    /**
     * When true, the next NAVIGATE arm uses [in.sih26168.idr.sensor.ReplaySensorSource]
     * instead of live phone sensors.
     */
    private val _replayEnabled = MutableStateFlow(false)
    val replayEnabled: StateFlow<Boolean> = _replayEnabled.asStateFlow()

    /** True while a replay drive is actively feeding the estimator. */
    private val _replayActive = MutableStateFlow(false)
    val replayActive: StateFlow<Boolean> = _replayActive.asStateFlow()

    /**
     * Naive double-integration ghost track (P1-1). Same IMU as COAST; no ZUPT /
     * map lock. UI draws the red puck when [showGhost] is true.
     */
    private val _ghostTrack = MutableStateFlow(TrackSnapshot())
    val ghostTrack: StateFlow<TrackSnapshot> = _ghostTrack.asStateFlow()

    private val _showGhost = MutableStateFlow(false)
    val showGhost: StateFlow<Boolean> = _showGhost.asStateFlow()

    /**
     * P1-2 ZUPT tabletop: leave the phone still and compare naive vs COAST
     * speeds side-by-side. Physics produces the naive drift — do not script it.
     */
    private val _zuptTabletop = MutableStateFlow(false)
    val zuptTabletop: StateFlow<Boolean> = _zuptTabletop.asStateFlow()

    /** Horizontal speed from [nav.NaiveGhostEstimator], m/s. */
    private val _naiveGhostSpeedMps = MutableStateFlow(0.0)
    val naiveGhostSpeedMps: StateFlow<Double> = _naiveGhostSpeedMps.asStateFlow()

    /** COAST HUD speed mirrored for the tabletop readout, m/s. */
    private val _coastSpeedMps = MutableStateFlow(0.0)
    val coastSpeedMps: StateFlow<Double> = _coastSpeedMps.asStateFlow()

    fun setConfig(c: SessionConfig) {
        _config.value = c
    }

    fun setBlackout(on: Boolean) {
        _gnssBlackout.value = on
    }

    fun setReplayEnabled(on: Boolean) {
        _replayEnabled.value = on
    }

    fun setReplayActive(on: Boolean) {
        _replayActive.value = on
    }

    fun setShowGhost(on: Boolean) {
        _showGhost.value = on
    }

    fun setZuptTabletop(on: Boolean) {
        _zuptTabletop.value = on
    }

    /**
     * Change the vehicle, keeping `leans` consistent with the profile.
     *
     * Use this rather than `setConfig(cfg.copy(vehicle = ...))`. `leans` is not
     * a free choice: it is a property of the vehicle, and the caller that set it
     * by hand got it wrong once already -- `v != VehicleKind.car` was correct
     * when the enum held four values and silently marked metro, train, bus and
     * walking as leaning vehicles the moment it held ten. Deriving it from
     * [VehicleProfile] removes the chance to disagree.
     */
    fun setVehicle(v: VehicleKind) {
        _config.update { it.copy(vehicle = v, leans = VehicleProfile.of(v).leans) }
    }

    fun setMode(m: AppMode) {
        _mode.value = m
        _hud.update { it.copy(mode = m) }
    }

    fun publishHud(h: HudState) {
        _hud.value = h
    }

    /** No-ops when the estimator has not appended a point since the last call. */
    fun publishTrack(t: TrackSnapshot) {
        if (_track.value.version != t.version) _track.value = t
    }

    /** No-ops when the ghost estimator has not appended a point since the last call. */
    fun publishGhostTrack(t: TrackSnapshot) {
        if (_ghostTrack.value.version != t.version) _ghostTrack.value = t
    }

    /** Side-by-side speeds for the ZUPT tabletop (and any HUD that wants them). */
    fun publishGhostSpeeds(naiveMps: Double, coastMps: Double) {
        _naiveGhostSpeedMps.value = naiveMps
        _coastSpeedMps.value = coastMps
    }

    fun publishRecord(s: RecordStats) {
        _record.value = s
    }

    fun publishSensors(r: SensorReport) {
        _sensors.value = r
    }

    fun publishDevice(d: DeviceCheck) {
        _device.value = d
    }

    fun publishLocation(s: LocationStatus) {
        _location.value = s
    }

    @Volatile
    var markRequested: Boolean = false

    @Volatile
    var clearMarkRequested: Boolean = false

    /**
     * A start point the user asserted by long-pressing the map or typing
     * coordinates. Picked up by [record.RecordService] on the next IMU tick and
     * cleared. Null latitude means "no request pending".
     */
    @Volatile
    var pendingOriginLat: Double? = null

    @Volatile
    var pendingOriginLon: Double? = null

    @Volatile
    var pendingOriginSource: OriginSource = OriginSource.USER_MAP

    @Volatile
    var clearOriginRequested: Boolean = false

    /** True when the mount rotation in prefs changed and the service must reload it. */
    @Volatile
    var mountDirty: Boolean = false

    fun requestOrigin(lat: Double, lon: Double, source: OriginSource) {
        pendingOriginSource = source
        pendingOriginLon = lon
        // Latitude last: the service tests it to decide the request is complete.
        pendingOriginLat = lat
    }
}
