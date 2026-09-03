package `in`.sih26168.idr

import android.os.Build
import `in`.sih26168.idr.data.AppMode
import `in`.sih26168.idr.data.HudState
import `in`.sih26168.idr.data.MountType
import `in`.sih26168.idr.data.RecordStats
import `in`.sih26168.idr.data.SensorReport
import `in`.sih26168.idr.data.SessionConfig
import `in`.sih26168.idr.data.VehicleKind
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

    private val _record = MutableStateFlow(RecordStats())
    val record: StateFlow<RecordStats> = _record.asStateFlow()

    private val _sensors = MutableStateFlow(SensorReport())
    val sensors: StateFlow<SensorReport> = _sensors.asStateFlow()

    fun setConfig(c: SessionConfig) {
        _config.value = c
    }

    fun setMode(m: AppMode) {
        _mode.value = m
        _hud.update { it.copy(mode = m) }
    }

    fun publishHud(h: HudState) {
        _hud.value = h
    }

    fun publishRecord(s: RecordStats) {
        _record.value = s
    }

    fun publishSensors(r: SensorReport) {
        _sensors.value = r
    }

    @Volatile
    var markRequested: Boolean = false

    @Volatile
    var clearMarkRequested: Boolean = false
}
