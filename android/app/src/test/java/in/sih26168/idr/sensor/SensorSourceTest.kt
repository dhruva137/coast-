package `in`.sih26168.idr.sensor

import `in`.sih26168.idr.data.SensorFrame
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.ByteArrayInputStream
import java.nio.charset.StandardCharsets
import java.util.concurrent.atomic.AtomicInteger
import java.util.concurrent.atomic.AtomicReference
import kotlin.math.abs

/**
 * Parser + replay contracts for the demo SensorSource path.
 *
 * Live phone behaviour is unchanged behind [LiveSensorSource]; that path is
 * covered by the existing SimpleIns suite staying green after the RecordService
 * refactor. Pacing uses [ReplaySensorSource.delayUntilNextMs] so we do not need
 * Android SystemClock stubs in JVM unit tests.
 */
class SensorSourceTest {

    private val miniCsv = """
        GPS latitude,GPS longitude,GPS altitude,GPS speed,GPS accuracy,GPS orientation,GPS satellites In range,Time since start,Date,Accelerometer X,Accelerometer Y,Accelerometer Z,Gravity X,Gravity Y,Gravity Z,Gyroscope (Yaw),Gyroscope (Pitch),Gyroscope (Roll),Magnetic field X,Magnetic field Y,Magnetic field Z,Orientation (Yaw),Orientation (Pitch),Orientation (Roll),GNSS valid,Indicated vehicle speed,Yaw rate,Indicated longitudinal acceleration,Indicated lateral acceleration
        52.40680000,-1.51970000,82.000,10.0000,2.40,0.000,11,0.0,2019-03-15 09-00-00_000,1.000000,0.000000,9.806650,0.000000,0.000000,9.806650,0.0100000,-0.2000000,0.0000000,20.000,5.000,-41.200,0.000,0.000,0.000,1,10.0000,11.45916,0.101937,0.000000
        52.40681000,-1.51970000,82.000,10.8000,2.40,0.000,11,100.0,2019-03-15 09-00-00_100,1.100000,0.000000,9.806650,0.000000,0.000000,9.806650,0.0100000,-0.2000000,0.0000000,20.000,5.000,-41.200,0.000,0.000,0.000,1,10.8000,11.45916,0.112131,0.000000
        52.40682000,-1.51970000,82.000,11.6000,2.40,0.000,11,200.0,2019-03-15 09-00-00_200,1.200000,0.000000,9.806650,0.000000,0.000000,9.806650,0.0100000,-0.2000000,0.0000000,20.000,5.000,-41.200,0.000,0.000,0.000,1,11.6000,11.45916,0.122325,0.000000
        52.40683000,-1.51970000,82.000,999.00,999.0,,0,300.0,2019-03-15 09-00-00_300,1.000000,0.000000,9.806650,0.000000,0.000000,9.806650,0.0100000,-0.2000000,0.0000000,20.000,5.000,-41.200,0.000,0.000,0.000,0,12.0000,11.45916,0.101937,0.000000
    """.trimIndent()

    @Test
    fun `IoVnbdCsv parses timestamps as ms and remaps yaw from -Pitch`() {
        val rows = IoVnbdCsv.parse(ByteArrayInputStream(miniCsv.toByteArray(StandardCharsets.UTF_8)))
        assertEquals(4, rows.size)
        assertEquals(0L, rows[0].tNs)
        assertEquals(100_000_000L, rows[1].tNs)
        assertEquals(200_000_000L, rows[2].tNs)
        // Pitch column = -0.2 → vehicle gz = -(-0.2) = 0.2
        assertEquals(0.2, rows[0].frame.gz, 1e-9)
        assertEquals(0.0, rows[0].frame.gx, 1e-9)
        assertEquals(0.01, rows[0].frame.gy, 1e-9)
        assertNotNull(rows[0].fix)
        assertNull("outage row must drop GNSS", rows[3].fix)
        assertEquals(10.0 / 3.6, rows[0].fix!!.speed, 1e-6)
    }

    @Test
    fun `delayUntilNextMs follows recorded 10 Hz cadence`() {
        assertEquals(100L, ReplaySensorSource.delayUntilNextMs(1_000L, 100_000_000L, 1_000L))
        assertEquals(0L, ReplaySensorSource.delayUntilNextMs(1_000L, 100_000_000L, 1_150L))
        assertEquals(50L, ReplaySensorSource.delayUntilNextMs(0L, 200_000_000L, 150L))
    }

    @Test
    fun `emitAllSync delivers IMU and respects blackout`() {
        val rows = IoVnbdCsv.parse(ByteArrayInputStream(miniCsv.toByteArray(StandardCharsets.UTF_8)))
        val frames = AtomicInteger(0)
        val gnss = AtomicInteger(0)
        val blackout = AtomicReference(false)
        val source = ReplaySensorSource(rows = rows, blackout = { blackout.get() })
        source.emitAllSync(
            onFrame = {
                if (frames.incrementAndGet() == 2) blackout.set(true)
            },
            onGnss = { fix -> if (fix != null) gnss.incrementAndGet() },
        )
        assertEquals(4, frames.get())
        assertTrue("gnss count was ${gnss.get()}", gnss.get() in 1..2)
    }

    @Test
    fun `blackout suppresses every GNSS fix`() {
        val rows = IoVnbdCsv.parse(ByteArrayInputStream(miniCsv.toByteArray(StandardCharsets.UTF_8)))
        val gnss = AtomicInteger(0)
        ReplaySensorSource(rows = rows, blackout = { true }).emitAllSync(
            onFrame = {},
            onGnss = { fix -> if (fix != null) gnss.incrementAndGet() },
        )
        assertEquals(0, gnss.get())
    }

    @Test
    fun `inter-row dt is ~100 ms for fixture pacing contract`() {
        val rows = IoVnbdCsv.parse(ByteArrayInputStream(miniCsv.toByteArray(StandardCharsets.UTF_8)))
        for (i in 1 until rows.size) {
            val dtMs = (rows[i].tNs - rows[i - 1].tNs) / 1_000_000.0
            assertTrue("dt=$dtMs", abs(dtMs - 100.0) < 1.0)
        }
        assertFalse(rows[0].frame.ax.isNaN())
    }

    @Test
    fun `empty input yields empty parse`() {
        assertTrue(IoVnbdCsv.parse(ByteArrayInputStream(ByteArray(0))).isEmpty())
    }
}
