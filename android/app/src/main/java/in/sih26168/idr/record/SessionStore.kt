package `in`.sih26168.idr.record

import android.content.Context
import android.content.Intent
import androidx.core.content.FileProvider
import org.json.JSONObject
import java.io.BufferedInputStream
import java.io.BufferedOutputStream
import java.io.File
import java.io.FileInputStream
import java.io.FileOutputStream
import java.util.Locale
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream

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
        val imuRows = countDataRows(File(dir, "imu.csv"))
        val gnssRows = countDataRows(File(dir, "gnss.csv"))
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
        )
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
            putExtra(Intent.EXTRA_SUBJECT, "IDR session ${zip.nameWithoutExtension}")
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
}
