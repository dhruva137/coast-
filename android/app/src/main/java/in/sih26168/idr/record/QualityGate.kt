package `in`.sih26168.idr.record

import `in`.sih26168.idr.nav.haversineM
import org.json.JSONObject
import java.io.File
import kotlin.math.abs

enum class QualityVerdict { KEEP, RETRY, FAIL }

data class QualityIssue(
    val code: String,
    val message: String,
    val fatal: Boolean = true,
)

data class QualityReport(
    val verdict: QualityVerdict,
    val issues: List<QualityIssue>,
    val durationSec: Double,
    val imuHz: Double,
    val imuRows: Long,
    val gnssRows: Long,
    val distanceM: Double,
    val meanAccH: Double,
    val maxGapSec: Double,
    val loopClosureMarked: Boolean,
    val loopSpanM: Double?,
) {
    val summary: String
        get() = when (verdict) {
            QualityVerdict.KEEP -> "KEEP · usable field log"
            QualityVerdict.RETRY -> "RETRY · ${issues.firstOrNull()?.message ?: "fixable issues"}"
            QualityVerdict.FAIL -> "FAIL · ${issues.firstOrNull()?.message ?: "unusable"}"
        }

    fun toJson(): JSONObject {
        val arr = org.json.JSONArray()
        for (i in issues) {
            arr.put(
                JSONObject()
                    .put("code", i.code)
                    .put("message", i.message)
                    .put("fatal", i.fatal),
            )
        }
        return JSONObject()
            .put("verdict", verdict.name)
            .put("summary", summary)
            .put("duration_sec", durationSec)
            .put("imu_hz", imuHz)
            .put("imu_rows", imuRows)
            .put("gnss_rows", gnssRows)
            .put("distance_m", distanceM)
            .put("mean_acc_h_m", meanAccH)
            .put("max_imu_gap_sec", maxGapSec)
            .put("loop_closure_marked", loopClosureMarked)
            .put("loop_span_m", loopSpanM ?: JSONObject.NULL)
            .put("issues", arr)
    }
}

/**
 * Offline quality gate for field sessions. Pure JVM — unit-testable without a device.
 *
 * Thresholds match the SIH field protocol: short loops are OK if IMU is dense and
 * GNSS is present for truth; silent IMU gaps and missing meta fail hard.
 */
object QualityGate {
    const val MIN_DURATION_SEC = 90.0
    const val MIN_DISTANCE_M = 150.0
    const val MIN_IMU_HZ = 40.0
    const val MIN_IMU_ROWS = 2_000L
    const val MIN_GNSS_ROWS = 8L
    const val MAX_MEAN_ACC_H_M = 40.0
    const val MAX_IMU_GAP_SEC = 1.5
    const val LOOP_WARN_SPAN_M = 80.0

    fun evaluateSession(dir: File): QualityReport {
        val imuFile = File(dir, "imu.csv")
        val gnssFile = File(dir, "gnss.csv")
        val metaFile = File(dir, "meta.json")
        val issues = mutableListOf<QualityIssue>()

        if (!metaFile.isFile) {
            issues += QualityIssue("NO_META", "meta.json missing — session is worthless")
        }
        if (!imuFile.isFile) {
            issues += QualityIssue("NO_IMU", "imu.csv missing")
            return QualityReport(
                verdict = QualityVerdict.FAIL,
                issues = issues,
                durationSec = 0.0,
                imuHz = 0.0,
                imuRows = 0,
                gnssRows = 0,
                distanceM = 0.0,
                meanAccH = Double.NaN,
                maxGapSec = 0.0,
                loopClosureMarked = false,
                loopSpanM = null,
            )
        }

        val imu = parseImu(imuFile)
        val gnss = if (gnssFile.isFile) parseGnss(gnssFile) else emptyList()
        val meta = if (metaFile.isFile) readMeta(metaFile) else MetaBits()

        val durationSec = if (imu.size >= 2) (imu.last().tNs - imu.first().tNs) / 1e9 else 0.0
        val imuHz = if (durationSec > 0.0) imu.size / durationSec else 0.0
        val maxGap = maxImuGapSec(imu)
        val distance = pathLengthM(gnss)
        val meanAcc = meanAccH(gnss)
        val loopSpan = loopSpanM(gnss, meta)

        if (imu.size < MIN_IMU_ROWS) {
            issues += QualityIssue("SHORT_IMU", "IMU rows ${imu.size} < $MIN_IMU_ROWS")
        }
        if (durationSec < MIN_DURATION_SEC) {
            issues += QualityIssue("SHORT_DURATION", "Duration ${fmt(durationSec)}s < ${MIN_DURATION_SEC.toInt()}s")
        }
        if (imuHz < MIN_IMU_HZ) {
            issues += QualityIssue("LOW_IMU_HZ", "IMU rate ${fmt(imuHz)} Hz < ${MIN_IMU_HZ.toInt()} Hz")
        }
        if (maxGap > MAX_IMU_GAP_SEC) {
            issues += QualityIssue("IMU_GAP", "Max IMU gap ${fmt(maxGap)}s > ${MAX_IMU_GAP_SEC}s (screen-off kill?)")
        }
        if (gnss.size < MIN_GNSS_ROWS) {
            issues += QualityIssue("FEW_GNSS", "GNSS fixes ${gnss.size} < $MIN_GNSS_ROWS (need outdoor truth)")
        }
        if (distance < MIN_DISTANCE_M && gnss.size >= MIN_GNSS_ROWS) {
            issues += QualityIssue("SHORT_PATH", "Path ${fmt(distance)} m < ${MIN_DISTANCE_M.toInt()} m")
        }
        if (meanAcc.isFinite() && meanAcc > MAX_MEAN_ACC_H_M && gnss.size >= MIN_GNSS_ROWS) {
            issues += QualityIssue(
                "POOR_GNSS",
                "Mean horizontal accuracy ${fmt(meanAcc)} m > ${MAX_MEAN_ACC_H_M.toInt()} m",
                fatal = false,
            )
        }
        if (meta.mountBlank) {
            issues += QualityIssue("NO_MOUNT", "mount_type missing in meta", fatal = false)
        }
        if (meta.riderBlank) {
            issues += QualityIssue("NO_RIDER", "rider blank in meta", fatal = false)
        }
        if (meta.loopMarked && loopSpan != null && loopSpan > LOOP_WARN_SPAN_M) {
            issues += QualityIssue(
                "LOOP_FAR",
                "Loop mark vs path ends ${fmt(loopSpan)} m apart — check chalk mark",
                fatal = false,
            )
        }

        val fatal = issues.any { it.fatal }
        val soft = issues.any { !it.fatal }
        val verdict = when {
            fatal -> QualityVerdict.FAIL
            soft -> QualityVerdict.RETRY
            else -> QualityVerdict.KEEP
        }

        return QualityReport(
            verdict = verdict,
            issues = issues,
            durationSec = durationSec,
            imuHz = imuHz,
            imuRows = imu.size.toLong(),
            gnssRows = gnss.size.toLong(),
            distanceM = distance,
            meanAccH = meanAcc,
            maxGapSec = maxGap,
            loopClosureMarked = meta.loopMarked,
            loopSpanM = loopSpan,
        )
    }

    fun writeReport(dir: File, report: QualityReport = evaluateSession(dir)): QualityReport {
        File(dir, "quality.json").writeText(report.toJson().toString(2))
        return report
    }

    private data class ImuRow(val tNs: Long)
    private data class GnssRow(
        val tNs: Long,
        val lat: Double,
        val lon: Double,
        val accH: Double,
    )
    private data class MetaBits(
        val loopMarked: Boolean = false,
        val loopLat: Double? = null,
        val loopLon: Double? = null,
        val mountBlank: Boolean = false,
        val riderBlank: Boolean = false,
    )

    private fun parseImu(file: File): List<ImuRow> {
        val out = ArrayList<ImuRow>(4096)
        file.bufferedReader().useLines { lines ->
            lines.drop(1).forEach { line ->
                if (line.isBlank()) return@forEach
                val t = line.substringBefore(',').toLongOrNull() ?: return@forEach
                out += ImuRow(t)
            }
        }
        return out
    }

    private fun parseGnss(file: File): List<GnssRow> {
        val out = ArrayList<GnssRow>(512)
        file.bufferedReader().useLines { lines ->
            lines.drop(1).forEach { line ->
                if (line.isBlank()) return@forEach
                val p = line.split(',')
                if (p.size < 8) return@forEach
                val t = p[0].toLongOrNull() ?: return@forEach
                val lat = p[1].toDoubleOrNull() ?: return@forEach
                val lon = p[2].toDoubleOrNull() ?: return@forEach
                val acc = p[7].toDoubleOrNull() ?: Double.NaN
                if (!lat.isFinite() || !lon.isFinite()) return@forEach
                out += GnssRow(t, lat, lon, acc)
            }
        }
        return out
    }

    private fun readMeta(file: File): MetaBits {
        return try {
            val o = JSONObject(file.readText())
            val lc = o.optJSONObject("loop_closure")
            val lat = lc?.optDouble("lat")?.takeIf { it.isFinite() && !lc.isNull("lat") }
            val lon = lc?.optDouble("lon")?.takeIf { it.isFinite() && !lc.isNull("lon") }
            MetaBits(
                loopMarked = lat != null && lon != null,
                loopLat = lat,
                loopLon = lon,
                mountBlank = o.optString("mount_type").isBlank(),
                riderBlank = o.optString("rider").isBlank(),
            )
        } catch (_: Exception) {
            MetaBits(mountBlank = true, riderBlank = true)
        }
    }

    private fun maxImuGapSec(rows: List<ImuRow>): Double {
        if (rows.size < 2) return 0.0
        var max = 0.0
        for (i in 1 until rows.size) {
            val gap = (rows[i].tNs - rows[i - 1].tNs) / 1e9
            if (gap > max) max = gap
        }
        return max
    }

    private fun pathLengthM(rows: List<GnssRow>): Double {
        if (rows.size < 2) return 0.0
        var d = 0.0
        for (i in 1 until rows.size) {
            val step = haversineM(rows[i - 1].lat, rows[i - 1].lon, rows[i].lat, rows[i].lon)
            if (step.isFinite() && step < 200.0) d += step
        }
        return d
    }

    private fun meanAccH(rows: List<GnssRow>): Double {
        val vals = rows.map { it.accH }.filter { it.isFinite() && it > 0.0 }
        if (vals.isEmpty()) return Double.NaN
        return vals.sum() / vals.size
    }

    private fun loopSpanM(rows: List<GnssRow>, meta: MetaBits): Double? {
        if (rows.isEmpty()) return null
        val a = rows.first()
        val b = rows.last()
        val endSpan = haversineM(a.lat, a.lon, b.lat, b.lon)
        if (meta.loopLat != null && meta.loopLon != null) {
            val toMark = haversineM(b.lat, b.lon, meta.loopLat, meta.loopLon)
            return maxOf(endSpan, toMark)
        }
        return endSpan.takeIf { abs(endSpan) >= 0.0 }
    }

    private fun fmt(x: Double): String = String.format(java.util.Locale.US, "%.1f", x)
}
