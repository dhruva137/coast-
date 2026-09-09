package `in`.sih26168.idr.record

import android.content.Context
import android.content.Intent
import androidx.core.content.FileProvider
import `in`.sih26168.idr.nav.haversineM
import org.json.JSONObject
import java.io.BufferedInputStream
import java.io.BufferedOutputStream
import java.io.File
import java.io.FileInputStream
import java.io.FileOutputStream
import java.util.Locale
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream
import kotlin.math.cos

data class SessionSummary(
    val dir: File,
    val name: String,
    val rider: String,
    val vehicle: String,
    val routeId: String,
    val mount: String,
    val imuRows: Long,
    val gnssRows: Long,
    val imuHz: Double,
    val quality: QualityReport?,
    val modifiedMs: Long,
    /** Session length in seconds; null when it cannot be derived. */
    val durationSec: Double?,
    /** Path length in metres from GNSS (or quality.json); null if unknown. */
    val distanceM: Double?,
    /**
     * Peak dead-reckon drift since last fix, metres. Field logs do not store
     * this today — callers must show an honest "—" when null.
     */
    val maxDriftSinceFixM: Double?,
)

/** One point on a session's recorded track (lat/lon absolute when available). */
data class SessionTrackPoint(
    val lat: Double,
    val lon: Double,
    val tNs: Long,
    /** True = GNSS fix; false = dead-reckoned (IDR) sample if ever logged. */
    val fromGnss: Boolean,
)

/** Last known absolute fix from the most recent session (or null). */
data class SessionLastFix(
    val sessionName: String,
    val lat: Double,
    val lon: Double,
    val tNs: Long,
    val modifiedMs: Long,
    val vehicle: String,
)

/**
 * Browse / rename / delete / zip sessions under app external files `data/`.
 */
object SessionStore {
    fun logsRoot(context: Context): File {
        val ext = context.getExternalFilesDir(null) ?: context.filesDir
        return File(ext, "data").also { it.mkdirs() }
    }

    fun listSessions(context: Context): List<SessionSummary> {
        val root = logsRoot(context)
        if (!root.isDirectory) return emptyList()
        val dirs = ArrayList<File>()
        root.walkTopDown().maxDepth(4).forEach { f ->
            if (f.isDirectory && File(f, "imu.csv").isFile) dirs += f
        }
        return dirs
            .map { summarize(it) }
            .sortedByDescending { it.modifiedMs }
    }

    fun summarize(dir: File): SessionSummary {
        val meta = readMeta(dir)
        val qualityFile = File(dir, "quality.json")
        val quality = when {
            qualityFile.isFile -> readQuality(qualityFile)
            else -> null
        }
        val imuFile = File(dir, "imu.csv")
        val gnssFile = File(dir, "gnss.csv")
        val imuRows = countDataRows(imuFile)
        val gnssRows = countDataRows(gnssFile)

        val durationSec = quality?.durationSec?.takeIf { it > 0.0 }
            ?: durationFromImu(imuFile)
        val distanceM = quality?.distanceM?.takeIf { it >= 0.0 && gnssRows > 0 }
            ?: distanceFromGnss(gnssFile)

        return SessionSummary(
            dir = dir,
            name = dir.name,
            rider = meta.optString("rider", "—"),
            vehicle = meta.optString("vehicle", "—"),
            routeId = meta.optString("route_id", "—"),
            mount = meta.optString("mount_type", "—"),
            imuRows = imuRows,
            gnssRows = gnssRows,
            imuHz = meta.optDouble("imu_hz", Double.NaN),
            quality = quality,
            modifiedMs = dir.lastModified(),
            durationSec = durationSec,
            distanceM = distanceM,
            // Not persisted in field logs / quality.json — keep null so UI shows "—".
            maxDriftSinceFixM = null,
        )
    }

    /**
     * Load a session track for the static history map.
     *
     * Field sessions only persist `gnss.csv` (absolute fixes). There is no IDR
     * trail file today, so returned points are GNSS-flagged. If a future
     * `trail.csv` (`t_ns,lat,lon,from_gnss`) appears, it is preferred so the
     * map can paint GNSS blue / IDR teal segments.
     */
    fun loadSessionTrack(dir: File): List<SessionTrackPoint> {
        val trail = File(dir, "trail.csv")
        if (trail.isFile) {
            val fromTrail = parseTrailCsv(trail)
            if (fromTrail.isNotEmpty()) return fromTrail
        }
        return parseGnssAsTrack(File(dir, "gnss.csv"))
    }

    /** Most recent session's last absolute GNSS fix, or null. */
    fun lastKnownFix(context: Context): SessionLastFix? {
        val sessions = listSessions(context)
        for (s in sessions) {
            val pts = loadSessionTrack(s.dir)
            val last = pts.lastOrNull { it.lat.isFinite() && it.lon.isFinite() } ?: continue
            return SessionLastFix(
                sessionName = s.name,
                lat = last.lat,
                lon = last.lon,
                tNs = last.tNs,
                modifiedMs = s.modifiedMs,
                vehicle = s.vehicle,
            )
        }
        return null
    }

    fun evaluateAndPersist(dir: File): QualityReport = QualityGate.writeReport(dir)

    fun renameSession(dir: File, newName: String): File {
        val safe = sanitizeName(newName)
        require(safe.isNotBlank()) { "empty name" }
        val dest = File(dir.parentFile, safe)
        require(!dest.exists()) { "name already exists" }
        check(dir.renameTo(dest)) { "rename failed" }
        return dest
    }

    fun deleteSession(dir: File): Boolean {
        if (!dir.exists()) return true
        return dir.deleteRecursively()
    }

    fun zipSession(dir: File): File {
        val out = File(dir.parentFile, "${dir.name}.zip")
        ZipOutputStream(BufferedOutputStream(FileOutputStream(out))).use { zos ->
            dir.walkTopDown().forEach { file ->
                if (!file.isFile) return@forEach
                val rel = file.relativeTo(dir).path.replace('\\', '/')
                zos.putNextEntry(ZipEntry("${dir.name}/$rel"))
                BufferedInputStream(FileInputStream(file)).use { input ->
                    input.copyTo(zos)
                }
                zos.closeEntry()
            }
        }
        return out
    }

    fun shareIntent(context: Context, zip: File): Intent {
        val uri = FileProvider.getUriForFile(
            context,
            "${context.packageName}.files",
            zip,
        )
        return Intent(Intent.ACTION_SEND).apply {
            type = "application/zip"
            putExtra(Intent.EXTRA_STREAM, uri)
            putExtra(Intent.EXTRA_SUBJECT, "COAST session ${zip.nameWithoutExtension}")
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        }
    }

    fun sanitizeName(raw: String): String =
        raw.trim()
            .lowercase(Locale.US)
            .replace(Regex("[^a-z0-9_\\-]+"), "_")
            .trim('_')

    private fun readMeta(dir: File): JSONObject {
        val f = File(dir, "meta.json")
        return try {
            if (f.isFile) JSONObject(f.readText()) else JSONObject()
        } catch (_: Exception) {
            JSONObject()
        }
    }

    private fun readQuality(file: File): QualityReport? {
        return try {
            val o = JSONObject(file.readText())
            val issues = ArrayList<QualityIssue>()
            val arr = o.optJSONArray("issues")
            if (arr != null) {
                for (i in 0 until arr.length()) {
                    val it = arr.getJSONObject(i)
                    issues += QualityIssue(
                        code = it.optString("code"),
                        message = it.optString("message"),
                        fatal = it.optBoolean("fatal", true),
                    )
                }
            }
            val verdict = try {
                QualityVerdict.valueOf(o.optString("verdict", "FAIL"))
            } catch (_: Exception) {
                QualityVerdict.FAIL
            }
            QualityReport(
                verdict = verdict,
                issues = issues,
                durationSec = o.optDouble("duration_sec", 0.0),
                imuHz = o.optDouble("imu_hz", 0.0),
                imuRows = o.optLong("imu_rows", 0L),
                gnssRows = o.optLong("gnss_rows", 0L),
                distanceM = o.optDouble("distance_m", 0.0),
                meanAccH = o.optDouble("mean_acc_h_m", Double.NaN),
                maxGapSec = o.optDouble("max_imu_gap_sec", 0.0),
                loopClosureMarked = o.optBoolean("loop_closure_marked", false),
                loopSpanM = if (o.isNull("loop_span_m")) null else o.optDouble("loop_span_m"),
            )
        } catch (_: Exception) {
            null
        }
    }

    private fun countDataRows(file: File): Long {
        if (!file.isFile) return 0L
        var n = 0L
        file.bufferedReader().useLines { lines ->
            lines.drop(1).forEach { if (it.isNotBlank()) n++ }
        }
        return n
    }

    /** First/last IMU timestamp → duration; avoids a full quality pass. */
    private fun durationFromImu(file: File): Double? {
        if (!file.isFile) return null
        var first = 0L
        var last = 0L
        file.bufferedReader().useLines { lines ->
            lines.drop(1).forEach { line ->
                if (line.isBlank()) return@forEach
                val t = line.substringBefore(',').toLongOrNull() ?: return@forEach
                if (first == 0L) first = t
                last = t
            }
        }
        if (first == 0L || last <= first) return null
        return (last - first) / 1e9
    }

    private fun distanceFromGnss(file: File): Double? {
        val pts = parseGnssAsTrack(file)
        if (pts.size < 2) return if (pts.isEmpty()) null else 0.0
        var d = 0.0
        for (i in 1 until pts.size) {
            val step = haversineM(pts[i - 1].lat, pts[i - 1].lon, pts[i].lat, pts[i].lon)
            if (step.isFinite() && step < 200.0) d += step
        }
        return d
    }

    private fun parseGnssAsTrack(file: File): List<SessionTrackPoint> {
        if (!file.isFile) return emptyList()
        val out = ArrayList<SessionTrackPoint>(512)
        file.bufferedReader().useLines { lines ->
            lines.drop(1).forEach { line ->
                if (line.isBlank()) return@forEach
                val p = line.split(',')
                if (p.size < 3) return@forEach
                val t = p[0].toLongOrNull() ?: return@forEach
                val lat = p[1].toDoubleOrNull() ?: return@forEach
                val lon = p[2].toDoubleOrNull() ?: return@forEach
                if (!lat.isFinite() || !lon.isFinite()) return@forEach
                out += SessionTrackPoint(lat, lon, t, fromGnss = true)
            }
        }
        return out
    }

    /** Optional future schema: t_ns,lat,lon,from_gnss */
    private fun parseTrailCsv(file: File): List<SessionTrackPoint> {
        val out = ArrayList<SessionTrackPoint>(1024)
        file.bufferedReader().useLines { lines ->
            lines.drop(1).forEach { line ->
                if (line.isBlank()) return@forEach
                val p = line.split(',')
                if (p.size < 3) return@forEach
                val t = p[0].toLongOrNull() ?: return@forEach
                val lat = p[1].toDoubleOrNull() ?: return@forEach
                val lon = p[2].toDoubleOrNull() ?: return@forEach
                if (!lat.isFinite() || !lon.isFinite()) return@forEach
                val fromGnss = when {
                    p.size < 4 -> true
                    p[3].equals("1", true) || p[3].equals("true", true) -> true
                    else -> false
                }
                out += SessionTrackPoint(lat, lon, t, fromGnss = fromGnss)
            }
        }
        return out
    }

    /**
     * Project lat/lon points into local east/north metres from the first point.
     * Used by the static session map (no MapLibre dependency).
     */
    fun toLocalEn(points: List<SessionTrackPoint>): List<Pair<Float, Float>> {
        if (points.isEmpty()) return emptyList()
        val oLat = points.first().lat
        val oLon = points.first().lon
        val cosLat = cos(Math.toRadians(oLat))
        return points.map { p ->
            val east = ((p.lon - oLon) * 111_320.0 * cosLat).toFloat()
            val north = ((p.lat - oLat) * 110_540.0).toFloat()
            east to north
        }
    }
}
