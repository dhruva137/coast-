package `in`.sih26168.idr.sensor

import `in`.sih26168.idr.data.GnssFix
import `in`.sih26168.idr.data.SensorFrame
import java.io.BufferedReader
import java.io.InputStream
import java.io.InputStreamReader
import kotlin.math.abs

/**
 * One row of an IO-VNBD smartphone (S-*.csv) stream, already remapped into the
 * vehicle-frame channels the estimator expects.
 *
 * Gyro remapping matches `lab/stress/load_iovnbd.py`:
 *   gx = Gyroscope (Roll)
 *   gy = Gyroscope (Yaw)
 *   gz = -Gyroscope (Pitch)   // vehicle yaw
 */
data class IoVnbdRow(
    val tNs: Long,
    val frame: SensorFrame,
    val fix: GnssFix?,
)

/**
 * Pure-JVM parser for IO-VNBD-style smartphone CSVs. No Android dependency so
 * unit tests can feed fixtures without Robolectric.
 */
object IoVnbdCsv {
    const val DEFAULT_ASSET = "demo/iovnbd_demo.csv"

    fun parse(input: InputStream, maxRows: Int = Int.MAX_VALUE): List<IoVnbdRow> {
        val reader = BufferedReader(InputStreamReader(input, Charsets.UTF_8))
        val headerLine = reader.readLine() ?: return emptyList()
        val headers = splitCsvLine(headerLine).map { it.trim() }
        val idx = HeaderIndex(headers)

        val rawTimes = ArrayList<Double>(4096)
        val staged = ArrayList<RawRow>(4096)
        var line: String?
        while (reader.readLine().also { line = it } != null) {
            if (staged.size >= maxRows) break
            val cols = splitCsvLine(line!!)
            if (cols.size < headers.size) continue
            val tRaw = cols.d(idx.t) ?: continue
            val ax = cols.d(idx.ax) ?: continue
            val ay = cols.d(idx.ay) ?: continue
            val az = cols.d(idx.az) ?: continue
            val gyroYaw = cols.d(idx.gyroYaw) ?: 0.0
            val gyroPitch = cols.d(idx.gyroPitch) ?: 0.0
            val gyroRoll = cols.d(idx.gyroRoll) ?: 0.0
            val mx = cols.d(idx.mx) ?: 0.0
            val my = cols.d(idx.my) ?: 0.0
            val mz = cols.d(idx.mz) ?: 0.0
            val pressure = cols.d(idx.pressure) ?: 1013.25
            val lux = cols.d(idx.lux) ?: 0.0

            val lat = cols.d(idx.lat)
            val lon = cols.d(idx.lon)
            val alt = cols.d(idx.alt) ?: 0.0
            val speedRaw = cols.d(idx.speed)
            val bearing = cols.d(idx.bearing) ?: Double.NaN
            val accH = cols.d(idx.accH) ?: Double.NaN
            val sats = cols.i(idx.sats) ?: 0
            val gnssValid = cols.i(idx.gnssValid)

            rawTimes += tRaw
            staged += RawRow(
                tRaw = tRaw,
                ax = ax, ay = ay, az = az,
                gyroYaw = gyroYaw, gyroPitch = gyroPitch, gyroRoll = gyroRoll,
                mx = mx, my = my, mz = mz,
                pressure = pressure, lux = lux,
                lat = lat, lon = lon, alt = alt,
                speedRaw = speedRaw, bearing = bearing, accH = accH,
                sats = sats, gnssValid = gnssValid,
            )
        }
        if (staged.isEmpty()) return emptyList()

        val t0 = rawTimes.first()
        val diffs = rawTimes.zipWithNext { a, b -> b - a }.filter { it.isFinite() && it > 0 }
        val medianDiff = median(diffs)
        // TIME SINCE START is milliseconds in real smartphone tables; the
        // synthetic fixture also stores ms. Seconds only if median step ≤ 5.
        val timeIsMs = medianDiff > 5.0
        val toSec = if (timeIsMs) 1e-3 else 1.0

        // GPS speed in the fixture / many S-logs is km/h. Convert when the
        // path-integrated magnitude is closer to km/h than m/s, or header says so.
        val speedIsKmh = idx.speedHeaderLooksKmh || inferSpeedIsKmh(staged, toSec)

        val out = ArrayList<IoVnbdRow>(staged.size)
        for (r in staged) {
            val tSec = (r.tRaw - t0) * toSec
            val tNs = (tSec * 1e9).toLong()
            // Same right-handed remap as load_iovnbd.py.
            val gx = r.gyroRoll
            val gy = r.gyroYaw
            val gz = -r.gyroPitch
            val frame = SensorFrame(
                tNs = tNs,
                ax = r.ax, ay = r.ay, az = r.az,
                gx = gx, gy = gy, gz = gz,
                mx = r.mx, my = r.my, mz = r.mz,
                pressureHpa = r.pressure,
                lux = r.lux,
            )
            val fix = toFix(r, tNs, speedIsKmh)
            out += IoVnbdRow(tNs = tNs, frame = frame, fix = fix)
        }
        return out
    }

    private fun toFix(r: RawRow, tNs: Long, speedIsKmh: Boolean): GnssFix? {
        val lat = r.lat
        val lon = r.lon
        if (lat == null || lon == null || !lat.isFinite() || !lon.isFinite()) return null
        // Explicit GNSS-valid column wins when present.
        if (r.gnssValid != null && r.gnssValid == 0) return null
        // AccH of 999 is the fixture's outage sentinel.
        if (r.accH.isFinite() && r.accH >= 500.0) return null
        if (r.sats == 0 && r.gnssValid == null) return null
        val speedMps = when {
            r.speedRaw == null || !r.speedRaw.isFinite() -> 0.0
            speedIsKmh -> r.speedRaw / 3.6
            else -> r.speedRaw
        }
        return GnssFix(
            tNs = tNs,
            lat = lat,
            lon = lon,
            alt = r.alt,
            speed = speedMps,
            bearing = r.bearing,
            accH = r.accH,
            accV = Double.NaN,
            nSats = r.sats,
        )
    }

    private fun inferSpeedIsKmh(rows: List<RawRow>, toSec: Double): Boolean {
        // Compare Σ speed*dt against GNSS path length; pick the unit that fits.
        if (rows.size < 4) return true
        var path = 0.0
        var asMps = 0.0
        var asKmh = 0.0
        for (i in 1 until rows.size) {
            val a = rows[i - 1]
            val b = rows[i]
            val dt = (b.tRaw - a.tRaw) * toSec
            if (dt <= 0 || dt > 2.0) continue
            val la = a.lat
            val lo = a.lon
            val lb = b.lat
            val lob = b.lon
            if (la != null && lo != null && lb != null && lob != null &&
                la.isFinite() && lo.isFinite() && lb.isFinite() && lob.isFinite()
            ) {
                val meanLat = Math.toRadians((la + lb) * 0.5)
                val north = Math.toRadians(lb - la) * 6_371_008.8
                val east = Math.toRadians(lob - lo) * 6_371_008.8 * kotlin.math.cos(meanLat)
                val step = kotlin.math.hypot(east, north)
                if (step < 500.0 && step > 1e-3) path += step
            }
            val sp = b.speedRaw
            if (sp != null && sp.isFinite() && sp >= 0) {
                asMps += sp * dt
                asKmh += (sp / 3.6) * dt
            }
        }
        if (path < 10.0) return true // fixture / short clip default
        return abs(kotlin.math.ln(maxOf(asKmh, 1e-9) / path)) <=
            abs(kotlin.math.ln(maxOf(asMps, 1e-9) / path))
    }

    private fun median(values: List<Double>): Double {
        if (values.isEmpty()) return 100.0
        val s = values.sorted()
        val m = s.size / 2
        return if (s.size % 2 == 0) 0.5 * (s[m - 1] + s[m]) else s[m]
    }

    private fun splitCsvLine(line: String): List<String> {
        // IO-VNBD rows are simple comma-separated with no embedded quotes.
        return line.split(',')
    }

    private fun List<String>.d(i: Int?): Double? {
        if (i == null || i !in indices) return null
        val s = this[i].trim()
        if (s.isEmpty()) return null
        return s.toDoubleOrNull()
    }

    private fun List<String>.i(i: Int?): Int? {
        if (i == null || i !in indices) return null
        val s = this[i].trim()
        if (s.isEmpty()) return null
        return s.toDoubleOrNull()?.toInt()
    }

    private class HeaderIndex(headers: List<String>) {
        private val norms = headers.map { norm(it) }
        val t = find("time since start", "timestamp", "time", "t")
        val lat = find("gps latitude", "latitude", "lat")
        val lon = find("gps longitude", "longitude", "lon", "lng")
        val alt = find("gps altitude", "altitude", "alt")
        val speed = find("gps speed", "speed", "velocity")
        val bearing = find("gps orientation", "gps heading", "bearing", "orientation (yaw)", "orientation yaw")
        val accH = find("gps accuracy", "accuracy", "hdop", "horizontal accuracy")
        val sats = find("gps satellites in range", "satellites", "n sats", "nsats")
        val ax = find("accelerometer x", "accel_x", "acc_x", "ax")
        val ay = find("accelerometer y", "accel_y", "acc_y", "ay")
        val az = find("accelerometer z", "accel_z", "acc_z", "az")
        val gyroYaw = find("gyroscope yaw", "gyro_z", "gz")
        val gyroPitch = find("gyroscope pitch", "gyro_y", "gy")
        val gyroRoll = find("gyroscope roll", "gyro_x", "gx")
        val mx = find("magnetic field x", "mag_x", "mx")
        val my = find("magnetic field y", "mag_y", "my")
        val mz = find("magnetic field z", "mag_z", "mz")
        val pressure = find("pressure", "baro", "pressure hpa")
        val lux = find("light", "lux")
        val gnssValid = find("gnss valid", "gps valid")
        val speedHeaderLooksKmh: Boolean =
            speed?.let { norms[it] }?.let { n -> "km" in n && "h" in n.replace(" ", "") } == true

        private fun find(vararg aliases: String): Int? {
            val compactAliases = aliases.map { it.replace(" ", "") }.toSet()
            for ((i, n) in norms.withIndex()) {
                val compact = n.replace(" ", "")
                if (n in aliases || compact in compactAliases) return i
                for (a in aliases) {
                    if (a.length > 3 && a in n) return i
                }
            }
            return null
        }

        private fun norm(name: String): String {
            var s = name.trim().lowercase()
            s = s.replace(Regex("[^\\x00-\\x7f]"), " ")
            for (ch in charArrayOf('[', ']', '(', ')', '{', '}', '^', '/')) {
                s = s.replace(ch, ' ')
            }
            s = s.replace('_', ' ').replace('-', ' ').replace(',', ' ')
            return s.split(Regex("\\s+")).filter { it.isNotEmpty() }.joinToString(" ")
        }
    }

    private data class RawRow(
        val tRaw: Double,
        val ax: Double,
        val ay: Double,
        val az: Double,
        val gyroYaw: Double,
        val gyroPitch: Double,
        val gyroRoll: Double,
        val mx: Double,
        val my: Double,
        val mz: Double,
        val pressure: Double,
        val lux: Double,
        val lat: Double?,
        val lon: Double?,
        val alt: Double,
        val speedRaw: Double?,
        val bearing: Double,
        val accH: Double,
        val sats: Int,
        val gnssValid: Int?,
    )
}
