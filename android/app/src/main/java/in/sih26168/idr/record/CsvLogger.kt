package `in`.sih26168.idr.record

import android.os.Build
import `in`.sih26168.idr.data.GnssFix
import `in`.sih26168.idr.data.SensorFrame
import `in`.sih26168.idr.data.SessionConfig
import org.json.JSONObject
import java.io.BufferedWriter
import java.io.File
import java.io.FileOutputStream
import java.io.OutputStreamWriter
import java.nio.charset.StandardCharsets
import java.util.Locale
import java.util.concurrent.locks.ReentrantLock
import kotlin.concurrent.withLock

/**
 * Frozen log schema, bible §5.8:
 *
 *   imu.csv   t_ns,ax,ay,az,gx,gy,gz,mx,my,mz,pressure_hpa,lux
 *   gnss.csv  t_ns,lat,lon,alt,speed,bearing,acc_h,acc_v,n_sats
 *   meta.json phone, mount, vehicle, rider, route, loop-closure, notes
 *
 * t_ns is monotonic [SystemClock.elapsedRealtimeNanos] (sensor timestamps
 * on Android are that same clock).
 */
class CsvLogger(
    val dir: File,
    private var meta: SessionConfig,
    private var sensorNotes: String = "",
) : AutoCloseable {
    private val lock = ReentrantLock()
    private val imuOut: BufferedWriter
    private val gnssOut: BufferedWriter
    private var imuRows: Long = 0
    private var gnssRows: Long = 0
    private var imuDirty: Int = 0
    private var firstImuNs: Long = 0L
    private var lastImuNs: Long = 0L

    val imuCount: Long get() = imuRows
    val gnssCount: Long get() = gnssRows

    init {
        dir.mkdirs()
        imuOut = writer(File(dir, "imu.csv"))
        gnssOut = writer(File(dir, "gnss.csv"))
        imuOut.appendLine("t_ns,ax,ay,az,gx,gy,gz,mx,my,mz,pressure_hpa,lux")
        gnssOut.appendLine("t_ns,lat,lon,alt,speed,bearing,acc_h,acc_v,n_sats")
        writeMetaLocked()
    }

    fun logImu(f: SensorFrame) = lock.withLock {
        if (firstImuNs == 0L) firstImuNs = f.tNs
        lastImuNs = f.tNs
        imuOut.append(f.tNs.toString()).append(',')
            .append(d(f.ax)).append(',')
            .append(d(f.ay)).append(',')
            .append(d(f.az)).append(',')
            .append(d(f.gx)).append(',')
            .append(d(f.gy)).append(',')
            .append(d(f.gz)).append(',')
            .append(d(f.mx)).append(',')
            .append(d(f.my)).append(',')
            .append(d(f.mz)).append(',')
            .append(d(f.pressureHpa)).append(',')
            .append(d(f.lux))
            .append('\n')
        imuRows += 1
        imuDirty += 1
        if (imuDirty >= 200) {
            imuOut.flush()
            imuDirty = 0
        }
    }

    fun logGnss(g: GnssFix) = lock.withLock {
        gnssOut.append(g.tNs.toString()).append(',')
            .append(d(g.lat, 9)).append(',')
            .append(d(g.lon, 9)).append(',')
            .append(d(g.alt, 3)).append(',')
            .append(d(g.speed, 4)).append(',')
            .append(d(g.bearing, 3)).append(',')
            .append(d(g.accH, 3)).append(',')
            .append(d(g.accV, 3)).append(',')
            .append(g.nSats.toString())
            .append('\n')
        gnssRows += 1
        gnssOut.flush()
    }

    fun updateLoopClosure(lat: Double, lon: Double) = lock.withLock {
        meta = meta.copy(loopClosureLat = lat, loopClosureLon = lon)
        writeMetaLocked()
    }

    fun setSensorNotes(notes: String) = lock.withLock {
        sensorNotes = notes
        writeMetaLocked()
    }

    fun imuHz(): Double {
        if (firstImuNs == 0L || lastImuNs <= firstImuNs) return 0.0
        val dt = (lastImuNs - firstImuNs) / 1e9
        return if (dt > 0.0) imuRows / dt else 0.0
    }

    override fun close() = lock.withLock {
        imuOut.flush()
        gnssOut.flush()
        writeMetaLocked()
        imuOut.close()
        gnssOut.close()
    }

    private fun writeMetaLocked() {
        val lc = JSONObject()
            .put("lat", meta.loopClosureLat ?: JSONObject.NULL)
            .put("lon", meta.loopClosureLon ?: JSONObject.NULL)
        val notes = buildString {
            append(meta.notes)
            if (sensorNotes.isNotBlank()) {
                if (isNotEmpty()) append(" | ")
                append(sensorNotes)
            }
        }
        val obj = JSONObject()
            .put("phone_model", meta.phoneModel)
            .put("mount_type", meta.mountType.name)
            .put("vehicle", meta.vehicle.name)
            .put("rider", meta.rider)
            .put("route_id", meta.routeId)
            .put("loop_closure", lc)
            .put("notes", notes)
            .put("imu_hz", imuHz())
            .put("leans", meta.leans)
            .put("android_release", Build.VERSION.RELEASE)
            .put("sdk_int", Build.VERSION.SDK_INT)
        File(dir, "meta.json").writeText(obj.toString(2), StandardCharsets.UTF_8)
    }

    private fun writer(file: File): BufferedWriter {
        return BufferedWriter(
            OutputStreamWriter(FileOutputStream(file, false), StandardCharsets.UTF_8),
            64 * 1024,
        )
    }

    private fun d(x: Double, digits: Int = 6): String {
        if (x.isNaN() || x.isInfinite()) return "0"
        return String.format(Locale.US, "%.${digits}f", x)
    }
}
