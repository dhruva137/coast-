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

    fun setConfig(c: SessionConfig) {
        _config.value = c
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
