package `in`.sih26168.idr.sensor

import android.content.Context
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import android.os.Handler
import android.os.HandlerThread
import android.os.SystemClock
import `in`.sih26168.idr.data.SensorFrame
import `in`.sih26168.idr.data.SensorReport

/**
 * Raw (uncalibrated) IMU at [SensorManager.SENSOR_DELAY_FASTEST].
 * We own bias — do not subtract the platform's estimated bias slots.
 *
 * Accel uncalibrated is the master clock; each tick emits a fused frame
 * with the latest gyro / mag / baro / lux.
 */
class SensorHub(
    context: Context,
    private val onFrame: (SensorFrame) -> Unit,
) : SensorEventListener {
    private val sm = context.getSystemService(Context.SENSOR_SERVICE) as SensorManager
    private var thread: HandlerThread? = null

    @Volatile private var gx = 0.0
    @Volatile private var gy = 0.0
    @Volatile private var gz = 0.0
    @Volatile private var mx = 0.0
    @Volatile private var my = 0.0
    @Volatile private var mz = 0.0
    @Volatile private var pressure = 0.0
    @Volatile private var lux = 0.0

    var report: SensorReport = SensorReport()
        private set

    fun start() {
        stop()
        val t = HandlerThread("idr-imu").also { it.start(); thread = it }
        val h = Handler(t.looper)

        val accUncal = sm.getDefaultSensor(Sensor.TYPE_ACCELEROMETER_UNCALIBRATED)
        val gyroUncal = sm.getDefaultSensor(Sensor.TYPE_GYROSCOPE_UNCALIBRATED)
        val acc = accUncal ?: sm.getDefaultSensor(Sensor.TYPE_ACCELEROMETER)
        val gyro = gyroUncal ?: sm.getDefaultSensor(Sensor.TYPE_GYROSCOPE)
        val magUncal = sm.getDefaultSensor(Sensor.TYPE_MAGNETIC_FIELD_UNCALIBRATED)
        val mag = magUncal ?: sm.getDefaultSensor(Sensor.TYPE_MAGNETIC_FIELD)
        val baro = sm.getDefaultSensor(Sensor.TYPE_PRESSURE)
        val light = sm.getDefaultSensor(Sensor.TYPE_LIGHT)

        report = SensorReport(
            accelUncal = accUncal != null,
            gyroUncal = gyroUncal != null,
            accelFallback = accUncal == null && acc != null,
            gyroFallback = gyroUncal == null && gyro != null,
            mag = mag != null,
            pressure = baro != null,
            light = light != null,
        )

        listOfNotNull(acc, gyro, mag, baro, light).forEach { s ->
            sm.registerListener(this, s, SensorManager.SENSOR_DELAY_FASTEST, h)
        }
    }

    fun stop() {
        sm.unregisterListener(this)
        thread?.quitSafely()
        thread = null
    }

    fun sensorNotes(): String = buildList {
        add(if (report.accelUncal) "accel=uncalibrated" else if (report.accelFallback) "accel=calibrated-fallback" else "accel=missing")
        add(if (report.gyroUncal) "gyro=uncalibrated" else if (report.gyroFallback) "gyro=calibrated-fallback" else "gyro=missing")
        add(if (report.mag) "mag=yes" else "mag=no")
        add(if (report.pressure) "baro=yes" else "baro=no")
        add(if (report.light) "light=yes" else "light=no")
    }.joinToString(",")

    override fun onAccuracyChanged(sensor: Sensor?, accuracy: Int) = Unit

    override fun onSensorChanged(event: SensorEvent) {
        val v = event.values
        when (event.sensor.type) {
            Sensor.TYPE_GYROSCOPE_UNCALIBRATED, Sensor.TYPE_GYROSCOPE -> {
                gx = v[0].toDouble()
                gy = v[1].toDouble()
                gz = v[2].toDouble()
            }
            Sensor.TYPE_MAGNETIC_FIELD_UNCALIBRATED, Sensor.TYPE_MAGNETIC_FIELD -> {
                mx = v[0].toDouble()
                my = v[1].toDouble()
                mz = v[2].toDouble()
            }
            Sensor.TYPE_PRESSURE -> pressure = v[0].toDouble()
            Sensor.TYPE_LIGHT -> lux = v[0].toDouble()
            Sensor.TYPE_ACCELEROMETER_UNCALIBRATED, Sensor.TYPE_ACCELEROMETER -> {
                val tNs = if (event.timestamp != 0L) event.timestamp else SystemClock.elapsedRealtimeNanos()
                onFrame(
                    SensorFrame(
                        tNs = tNs,
                        ax = v[0].toDouble(),
                        ay = v[1].toDouble(),
                        az = v[2].toDouble(),
                        gx = gx, gy = gy, gz = gz,
                        mx = mx, my = my, mz = mz,
                        pressureHpa = pressure,
                        lux = lux,
                    ),
                )
            }
        }
    }
}
