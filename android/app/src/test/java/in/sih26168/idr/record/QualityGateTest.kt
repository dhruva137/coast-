package `in`.sih26168.idr.record

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.Rule
import org.junit.rules.TemporaryFolder
import java.io.File

class QualityGateTest {
    @get:Rule
    val tmp = TemporaryFolder()

    @Test
    fun keepOnHealthyLoop() {
        val dir = tmp.newFolder("good")
        writeMeta(dir)
        writeImu(dir, rows = 12_000, hz = 100.0) // 120 s
        writeGnssPath(dir, points = 40, stepM = 10.0)
        val r = QualityGate.evaluateSession(dir)
        assertEquals(r.issues.joinToString { it.code }, QualityVerdict.KEEP, r.verdict)
        assertTrue(r.distanceM >= 150.0)
        assertTrue(r.imuHz >= 40.0)
    }

    @Test
    fun failWithoutMetaAndShortImu() {
        val dir = tmp.newFolder("bad")
        writeImu(dir, rows = 100, hz = 100.0)
        val r = QualityGate.evaluateSession(dir)
        assertEquals(QualityVerdict.FAIL, r.verdict)
        assertTrue(r.issues.any { it.code == "NO_META" })
        assertTrue(r.issues.any { it.code == "SHORT_IMU" })
    }

    @Test
    fun failOnImuGap() {
        val dir = tmp.newFolder("gap")
        writeMeta(dir)
        val imu = File(dir, "imu.csv")
        imu.writeText(buildString {
            appendLine("t_ns,ax,ay,az,gx,gy,gz,mx,my,mz,pressure_hpa,lux")
            var t = 0L
            repeat(2500) {
                appendLine("$t,0,0,9.8,0,0,0,0,0,0,1013,100")
                t += 10_000_000L // 100 Hz
            }
            // 3 second hole
            t += 3_000_000_000L
            repeat(2500) {
                appendLine("$t,0,0,9.8,0,0,0,0,0,0,1013,100")
                t += 10_000_000L
            }
        })
        writeGnssPath(dir, points = 40, stepM = 10.0)
        val r = QualityGate.evaluateSession(dir)
        assertEquals(QualityVerdict.FAIL, r.verdict)
        assertTrue(r.issues.any { it.code == "IMU_GAP" })
    }

    @Test
    fun writeReportPersistsJson() {
        val dir = tmp.newFolder("persist")
        writeMeta(dir)
        writeImu(dir, rows = 12_000, hz = 100.0)
        writeGnssPath(dir, points = 40, stepM = 10.0)
        val r = QualityGate.writeReport(dir)
        assertTrue(File(dir, "quality.json").isFile)
        assertEquals(r.issues.joinToString { it.code }, QualityVerdict.KEEP, r.verdict)
    }

    @Test
    fun renameSanitize() {
        assertEquals("campus_loop_1", SessionStore.sanitizeName("Campus Loop #1"))
        assertEquals("a_b", SessionStore.sanitizeName("  A  B  "))
    }

    private fun writeMeta(dir: File, loopLat: Double = 12.9716, loopLon: Double = 77.0) {
        File(dir, "meta.json").writeText(
            """
            {
              "phone_model": "Test Phone",
              "mount_type": "handlebar",
              "vehicle": "scooter",
              "rider": "tester",
              "route_id": "campus_loop",
              "loop_closure": {"lat": $loopLat, "lon": $loopLon},
              "notes": "unit",
              "imu_hz": 100.0,
              "leans": true
            }
            """.trimIndent(),
        )
    }

    private fun writeImu(dir: File, rows: Int, hz: Double) {
        val dtNs = (1e9 / hz).toLong()
        File(dir, "imu.csv").writeText(buildString {
            appendLine("t_ns,ax,ay,az,gx,gy,gz,mx,my,mz,pressure_hpa,lux")
            var t = 0L
            repeat(rows) {
                appendLine("$t,0,0,9.8,0,0,0.01,0,0,0,1013.25,120")
                t += dtNs
            }
        })
    }

    /** Out-and-back path so start≈end (loop-friendly). */
    private fun writeGnssPath(dir: File, points: Int, stepM: Double) {
        val dLon = stepM / 111_320.0
        val half = points / 2
        File(dir, "gnss.csv").writeText(buildString {
            appendLine("t_ns,lat,lon,alt,speed,bearing,acc_h,acc_v,n_sats")
            var t = 0L
            var lon = 77.0
            val lat = 12.9716
            repeat(half) {
                appendLine("$t,${"%.9f".format(lat)},${"%.9f".format(lon)},900,5,90,5.0,8.0,12")
                lon += dLon
                t += 1_000_000_000L
            }
            repeat(points - half) {
                appendLine("$t,${"%.9f".format(lat)},${"%.9f".format(lon)},900,5,270,5.0,8.0,12")
                lon -= dLon
                t += 1_000_000_000L
            }
        })
    }
}
