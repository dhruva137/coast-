package `in`.sih26168.idr.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import `in`.sih26168.idr.IdrBus
import `in`.sih26168.idr.data.AppMode
import `in`.sih26168.idr.data.MountType
import `in`.sih26168.idr.data.VehicleKind
import `in`.sih26168.idr.record.RecordService
import `in`.sih26168.idr.ui.theme.Accent
import `in`.sih26168.idr.ui.theme.Bg2
import `in`.sih26168.idr.ui.theme.Danger
import `in`.sih26168.idr.ui.theme.IdrMono
import `in`.sih26168.idr.ui.theme.IdrSans
import `in`.sih26168.idr.ui.theme.Line
import `in`.sih26168.idr.ui.theme.Mute
import `in`.sih26168.idr.ui.theme.Telem
import `in`.sih26168.idr.ui.theme.Text as Fg

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun RecordScreen(bus: IdrBus, permsOk: Boolean, requestPerms: () -> Unit) {
    val ctx = LocalContext.current
    val cfg by bus.config.collectAsStateWithLifecycle()
    val stats by bus.record.collectAsStateWithLifecycle()
    val sensors by bus.sensors.collectAsStateWithLifecycle()
    val mode by bus.mode.collectAsStateWithLifecycle()
    val recording = mode == AppMode.RECORD
    val fieldColors = OutlinedTextFieldDefaults.colors(
        focusedBorderColor = Accent,
        unfocusedBorderColor = Line,
        focusedLabelColor = Accent,
        unfocusedLabelColor = Mute,
        cursorColor = Accent,
        focusedTextColor = Fg,
        unfocusedTextColor = Fg,
    )

    Column(
        Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text("RECORD", fontFamily = IdrMono, color = Accent, letterSpacing = 3.sp, fontSize = 12.sp)
        Text(
            "Raw uncalibrated IMU + GNSS → frozen CSV. Any session without meta.json is worthless.",
            color = Mute,
            fontFamily = IdrSans,
            fontSize = 13.sp,
        )

        OutlinedTextField(
            value = cfg.rider,
            onValueChange = { bus.setConfig(cfg.copy(rider = it)) },
            label = { Text("rider") },
            singleLine = true,
            enabled = !recording,
            modifier = Modifier.fillMaxWidth(),
            colors = fieldColors,
        )
        OutlinedTextField(
            value = cfg.routeId,
            onValueChange = { bus.setConfig(cfg.copy(routeId = it)) },
            label = { Text("route id") },
            singleLine = true,
            enabled = !recording,
            modifier = Modifier.fillMaxWidth(),
            colors = fieldColors,
        )
        OutlinedTextField(
            value = cfg.phoneModel,
            onValueChange = { bus.setConfig(cfg.copy(phoneModel = it)) },
            label = { Text("phone model") },
            singleLine = true,
            enabled = !recording,
            modifier = Modifier.fillMaxWidth(),
            colors = fieldColors,
        )
        OutlinedTextField(
            value = cfg.notes,
            onValueChange = { bus.setConfig(cfg.copy(notes = it)) },
            label = { Text("notes") },
            enabled = !recording,
            modifier = Modifier.fillMaxWidth(),
            colors = fieldColors,
        )

        Text("VEHICLE", fontFamily = IdrMono, color = Mute, fontSize = 10.sp, letterSpacing = 1.5.sp)
        FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            VehicleKind.entries.forEach { v ->
                Chip(v.name, cfg.vehicle == v, enabled = !recording) { bus.setConfig(cfg.copy(vehicle = v, leans = v != VehicleKind.car)) }
            }
        }
        Text("MOUNT", fontFamily = IdrMono, color = Mute, fontSize = 10.sp, letterSpacing = 1.5.sp)
        FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            MountType.entries.forEach { m ->
                Chip(m.name, cfg.mountType == m, enabled = !recording) { bus.setConfig(cfg.copy(mountType = m)) }
            }
        }

        Text("SENSORS", fontFamily = IdrMono, color = Mute, fontSize = 10.sp, letterSpacing = 1.5.sp)
        FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            StatusChip("ACC_UNCAL", sensors.accelUncal)
            StatusChip("GYRO_UNCAL", sensors.gyroUncal)
            StatusChip("ACC_FB", sensors.accelFallback)
            StatusChip("GYRO_FB", sensors.gyroFallback)
            StatusChip("MAG", sensors.mag)
            StatusChip("BARO", sensors.pressure)
            StatusChip("LIGHT", sensors.light)
        }

        Spacer(Modifier.height(4.dp))
        Button(
            onClick = {
                if (!permsOk) {
                    requestPerms()
                    return@Button
                }
                if (recording) RecordService.stop(ctx) else RecordService.start(ctx, AppMode.RECORD)
            },
            modifier = Modifier
                .fillMaxWidth()
                .height(52.dp),
            colors = ButtonDefaults.buttonColors(
                containerColor = if (recording) Danger else Accent,
                contentColor = `in`.sih26168.idr.ui.theme.Bg,
            ),
            shape = RoundedCornerShape(8.dp),
        ) {
            Text(
                if (recording) "STOP RECORDING" else "START RECORDING",
                fontFamily = IdrMono,
                letterSpacing = 1.4.sp,
            )
        }

        if (!permsOk) {
            Text("Location, body sensors and notifications are required.", color = Danger, fontSize = 12.sp)
        }

        val hz = if (stats.imuHz.isFinite()) "%.0f".format(stats.imuHz) else "—"
        Text(
            "IMU ${stats.imuRows} rows  ·  GNSS ${stats.gnssRows}  ·  ~${hz} Hz",
            fontFamily = IdrMono,
            color = Telem,
            fontSize = 12.sp,
        )
        Text(
            stats.sessionDir ?: "data/<rider>/<vehicle>/<YYYYMMDD_HHMMSS>/",
            fontFamily = IdrMono,
            color = Mute,
            fontSize = 10.sp,
        )
        stats.qualitySummary?.let { q ->
            Text(
                q,
                fontFamily = IdrMono,
                color = if (q.startsWith("KEEP")) Telem else if (q.startsWith("RETRY")) Accent else Danger,
                fontSize = 12.sp,
            )
            Text(
                "Open SESSIONS tab to rename / zip / delete this log.",
                fontFamily = IdrMono,
                color = Mute,
                fontSize = 10.sp,
            )
        }
        Text(
            "Columns frozen: t_ns,ax,ay,az,gx,gy,gz,mx,my,mz,pressure_hpa,lux",
            fontFamily = IdrMono,
            color = Mute,
            fontSize = 10.sp,
        )
        Button(
            onClick = { bus.markRequested = true },
            enabled = recording,
            modifier = Modifier.fillMaxWidth(),
            colors = ButtonDefaults.buttonColors(containerColor = Telem, contentColor = `in`.sih26168.idr.ui.theme.Bg),
            shape = RoundedCornerShape(8.dp),
        ) {
            Text("MARK LOOP CLOSURE", fontFamily = IdrMono, letterSpacing = 1.2.sp)
        }
        Text(
            "Writes loop_closure lat/lon into meta.json from the latest GNSS fix.",
            fontFamily = IdrMono,
            color = Mute,
            fontSize = 10.sp,
        )
    }
}

@Composable
private fun Chip(label: String, selected: Boolean, enabled: Boolean = true, onClick: () -> Unit) {
    val bg = if (selected) Accent.copy(alpha = 0.18f) else Bg2
    val fg = if (selected) Accent else Mute
    Text(
        text = label.uppercase(),
        modifier = Modifier
            .clip(RoundedCornerShape(99.dp))
            .background(bg)
            .border(1.dp, if (selected) Accent.copy(alpha = 0.5f) else Line, RoundedCornerShape(99.dp))
            .clickable(enabled = enabled, onClick = onClick)
            .padding(horizontal = 12.dp, vertical = 6.dp),
        color = fg,
        fontFamily = IdrMono,
        fontSize = 11.sp,
    )
}

@Composable
private fun StatusChip(label: String, on: Boolean) {
    val fg = if (on) Telem else Mute
    Text(
        text = label,
        modifier = Modifier
            .clip(RoundedCornerShape(99.dp))
            .border(1.dp, fg.copy(alpha = 0.35f), RoundedCornerShape(99.dp))
            .padding(horizontal = 10.dp, vertical = 4.dp),
        color = fg,
        fontFamily = IdrMono,
        fontSize = 10.sp,
    )
}
