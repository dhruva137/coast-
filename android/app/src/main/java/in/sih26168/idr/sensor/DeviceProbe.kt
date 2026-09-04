package `in`.sih26168.idr.sensor

import android.content.Context
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import android.os.Build
import android.os.Handler
import android.os.HandlerThread
import android.os.SystemClock
import `in`.sih26168.idr.data.DeviceCheck
import `in`.sih26168.idr.data.DeviceVerdict
import `in`.sih26168.idr.data.Finding
import `in`.sih26168.idr.data.FindingLevel
import `in`.sih26168.idr.data.SensorSpec

/**
 * Startup hardware self-check.
 *
 * Many budget Android phones either ship without a gyroscope or expose a
 * software-fused stand-in that is useless for dead reckoning. This class
 * answers that question with facts the platform actually gives us, plus one
 * measured number, and hands the UI a verdict it must show even when it is bad.
 *
 * Two passes:
 *
 *  1. [inventory] -- pure [SensorManager] query. Instant, no permissions, no
 *     side effects. Presence, name, vendor, resolution, range, and the
 *     ADVERTISED fastest rate derived from `minDelay`.
 *  2. [probe] -- registers accel + gyro at `SENSOR_DELAY_FASTEST` for
 *     [PROBE_MS] and COUNTS events. The advertised rate is a claim; this is a
 *     measurement, and on mid-range hardware the two often disagree.
 *
 * Nothing here degrades silently. If the gyro is missing the verdict is FAIL
 * and the card says dead reckoning will not work on this device.
 */
object DeviceProbe {

    /** Length of the measured-rate burst. Long enough to average out jitter. */
    const val PROBE_MS = 2500L

    /**
     * Below this the 10 Hz decimation window in `OnnxSpeedModel` has too few
     * samples per 100 ms bin for the mean to suppress mount vibration.
     */
    private const val MIN_USABLE_HZ = 50.0

    /** Comfortable rate: >= 5 samples per 100 ms bin after jitter. */
    private const val GOOD_HZ = 100.0

    /**
     * Substrings that appear in the names of software/fusion sensors on
     * Android HALs. This is a HEURISTIC, not an API -- the card always prints
     * the raw name and vendor next to it so a reader can judge for themselves.
     */
    private val SOFTWARE_HINTS = listOf(
        "virtual", "software", "fusion", "fused", "synthetic", "emulat", "composite",
    )

    fun inventory(context: Context): DeviceCheck {
        val sm = context.getSystemService(Context.SENSOR_SERVICE) as SensorManager
        val check = DeviceCheck(
            probed = false,
            accel = spec(sm, Sensor.TYPE_ACCELEROMETER),
            accelUncal = spec(sm, Sensor.TYPE_ACCELEROMETER_UNCALIBRATED),
            gyro = spec(sm, Sensor.TYPE_GYROSCOPE),
            gyroUncal = spec(sm, Sensor.TYPE_GYROSCOPE_UNCALIBRATED),
            mag = spec(sm, Sensor.TYPE_MAGNETIC_FIELD),
            magUncal = spec(sm, Sensor.TYPE_MAGNETIC_FIELD_UNCALIBRATED),
            baro = spec(sm, Sensor.TYPE_PRESSURE),
            device = listOf(Build.MANUFACTURER, Build.MODEL)
                .filter { it.isNotBlank() }
                .joinToString(" ")
                .ifBlank { "unknown device" },
            androidRelease = "Android ${Build.VERSION.RELEASE} (API ${Build.VERSION.SDK_INT})",
        )
        return check.withFindings()
    }

    /**
     * Measure the rate we actually get. Blocking for about [PROBE_MS]; call it
     * off the main thread. Returns [base] enriched with measured rates and a
     * recomputed verdict.
     */
    fun probe(context: Context, base: DeviceCheck): DeviceCheck {
        val sm = context.getSystemService(Context.SENSOR_SERVICE) as SensorManager
        val wanted = listOfNotNull(
            sm.getDefaultSensor(Sensor.TYPE_ACCELEROMETER),
            sm.getDefaultSensor(Sensor.TYPE_ACCELEROMETER_UNCALIBRATED),
            sm.getDefaultSensor(Sensor.TYPE_GYROSCOPE),
            sm.getDefaultSensor(Sensor.TYPE_GYROSCOPE_UNCALIBRATED),
            sm.getDefaultSensor(Sensor.TYPE_MAGNETIC_FIELD),
            sm.getDefaultSensor(Sensor.TYPE_PRESSURE),
        )
        if (wanted.isEmpty()) return base.copy(probed = true).withFindings()

        val counts = HashMap<Int, Int>()
        val firstNs = HashMap<Int, Long>()
        val lastNs = HashMap<Int, Long>()
        val lock = Any()

        val thread = HandlerThread("idr-probe").apply { start() }
        val listener = object : SensorEventListener {
            override fun onAccuracyChanged(sensor: Sensor?, accuracy: Int) = Unit
            override fun onSensorChanged(event: SensorEvent) {
                val type = event.sensor.type
                // Sensor event timestamps are elapsedRealtimeNanos; fall back to
                // the wall clock if the HAL reports 0 (some HALs do).
                val t = if (event.timestamp != 0L) event.timestamp else SystemClock.elapsedRealtimeNanos()
                synchronized(lock) {
                    counts[type] = (counts[type] ?: 0) + 1
                    if (firstNs[type] == null) firstNs[type] = t
                    lastNs[type] = t
                }
            }
        }
        val handler = Handler(thread.looper)
        wanted.forEach { sm.registerListener(listener, it, SensorManager.SENSOR_DELAY_FASTEST, handler) }
        try {
            Thread.sleep(PROBE_MS)
        } catch (_: InterruptedException) {
            Thread.currentThread().interrupt()
        } finally {
            sm.unregisterListener(listener)
            thread.quitSafely()
        }

        fun measured(type: Int): Double = synchronized(lock) {
            val n = counts[type] ?: return@synchronized Double.NaN
            val a = firstNs[type] ?: return@synchronized Double.NaN
            val b = lastNs[type] ?: return@synchronized Double.NaN
            val span = (b - a) / 1e9
            // n events span n-1 intervals; fewer than 2 events tells us nothing.
            if (n < 2 || span <= 0.0) Double.NaN else (n - 1) / span
        }

        return base.copy(
            probed = true,
            accel = base.accel.copy(measuredHz = measured(Sensor.TYPE_ACCELEROMETER)),
            accelUncal = base.accelUncal.copy(measuredHz = measured(Sensor.TYPE_ACCELEROMETER_UNCALIBRATED)),
            gyro = base.gyro.copy(measuredHz = measured(Sensor.TYPE_GYROSCOPE)),
            gyroUncal = base.gyroUncal.copy(measuredHz = measured(Sensor.TYPE_GYROSCOPE_UNCALIBRATED)),
            mag = base.mag.copy(measuredHz = measured(Sensor.TYPE_MAGNETIC_FIELD)),
            baro = base.baro.copy(measuredHz = measured(Sensor.TYPE_PRESSURE)),
        ).withFindings()
    }

    private fun spec(sm: SensorManager, type: Int): SensorSpec {
        val s = sm.getDefaultSensor(type) ?: return SensorSpec(present = false)
        val minDelay = s.minDelay
        return SensorSpec(
            present = true,
            name = s.name ?: "",
            vendor = s.vendor ?: "",
            minDelayUs = minDelay,
            advertisedHz = if (minDelay > 0) 1_000_000.0 / minDelay else Double.NaN,
            resolution = s.resolution.toDouble(),
            maxRange = s.maximumRange.toDouble(),
            powerMa = s.power.toDouble(),
        )
    }

    private fun looksSoftware(spec: SensorSpec): Boolean {
        if (!spec.present) return false
        val hay = (spec.name + " " + spec.vendor).lowercase()
        return SOFTWARE_HINTS.any { hay.contains(it) }
    }

    /** Best rate we know for a sensor: measured if we have it, else advertised. */
    private fun bestHz(spec: SensorSpec): Double =
        if (spec.measuredHz.isFinite() && spec.measuredHz > 0.0) spec.measuredHz else spec.advertisedHz

    private fun hzText(spec: SensorSpec): String {
        val m = spec.measuredHz
        val a = spec.advertisedHz
        val measured = if (m.isFinite() && m > 0.0) "measured %.0f Hz".format(m) else "not measured"
        val advertised = if (a.isFinite()) "advertised %.0f Hz".format(a) else "no rate advertised"
        return "$measured, $advertised"
    }

    /**
     * Turn the inventory into a verdict plus a list a non-expert can read.
     * The rules are deliberately blunt: no gyro means no dead reckoning, and
     * we say so rather than quietly running a worse estimator.
     */
    private fun DeviceCheck.withFindings(): DeviceCheck {
        val out = ArrayList<Finding>()
        var worst = DeviceVerdict.PASS

        fun demote(to: DeviceVerdict) {
            val rank = mapOf(
                DeviceVerdict.PASS to 0,
                DeviceVerdict.DEGRADED to 1,
                DeviceVerdict.FAIL to 2,
            )
            if ((rank[to] ?: 0) > (rank[worst] ?: 0)) worst = to
        }

        // ---- Gyroscope: the one that decides whether this app works at all --
        val anyGyro = gyro.present || gyroUncal.present
        if (!anyGyro) {
            demote(DeviceVerdict.FAIL)
            out += Finding(
                FindingLevel.FAIL,
                "No gyroscope",
                "This phone reports no gyroscope of any kind. Dead reckoning needs " +
                    "turn rate; without it the app cannot track heading and will not " +
                    "produce a usable track. Nothing here will fix that in software.",
            )
        } else {
            val g = if (gyroUncal.present) gyroUncal else gyro
            val soft = looksSoftware(gyro) || looksSoftware(gyroUncal)
            if (soft) {
                demote(DeviceVerdict.DEGRADED)
                out += Finding(
                    FindingLevel.WARN,
                    "Gyroscope may be software-fused",
                    "The driver name suggests a virtual sensor rather than a physical " +
                        "gyro. A fused gyro is derived from the accelerometer and " +
                        "compass and lags real turns, so heading will drift faster " +
                        "than the numbers this app quotes. Raw name: " +
                        "\"${g.name}\" by \"${g.vendor}\".",
                )
            } else {
                out += Finding(
                    FindingLevel.OK,
                    "Gyroscope present",
                    "\"${g.name}\" by \"${g.vendor}\". Turn rate is available, which " +
                        "is what heading is integrated from.",
                )
            }
            if (!gyroUncal.present) {
                demote(DeviceVerdict.DEGRADED)
                out += Finding(
                    FindingLevel.WARN,
                    "No uncalibrated gyroscope",
                    "Only the calibrated gyro is exposed, so the platform subtracts " +
                        "its own bias estimate before we see the data. This app " +
                        "prefers to model bias itself. It will still run on the " +
                        "calibrated stream, with less control over drift.",
                )
            }
            val hz = bestHz(g)
            when {
                !hz.isFinite() -> {
                    demote(DeviceVerdict.DEGRADED)
                    out += Finding(
                        FindingLevel.WARN,
                        "Gyroscope rate unknown",
                        "The platform advertises no minimum delay and the probe did " +
                            "not see enough events to measure one. Rate will be " +
                            "shown live on the Diagnostics panel once you start.",
                    )
                }
                hz < MIN_USABLE_HZ -> {
                    demote(DeviceVerdict.DEGRADED)
                    out += Finding(
                        FindingLevel.WARN,
                        "Slow gyroscope: ${hzText(g)}",
                        "Below about ${MIN_USABLE_HZ.toInt()} Hz there are too few " +
                            "samples in each 100 ms window for averaging to reject " +
                            "mount vibration. Expect noticeably worse heading.",
                    )
                }
                hz < GOOD_HZ -> out += Finding(
                    FindingLevel.OK,
                    "Gyroscope rate: ${hzText(g)}",
                    "Enough for the 10 Hz estimator window, with less headroom than " +
                        "we would like.",
                )
                else -> out += Finding(
                    FindingLevel.OK,
                    "Gyroscope rate: ${hzText(g)}",
                    "Comfortably above what the 10 Hz estimator window needs.",
                )
            }
        }

        // ---- Accelerometer ---------------------------------------------------
        val anyAccel = accel.present || accelUncal.present
        if (!anyAccel) {
            demote(DeviceVerdict.FAIL)
            out += Finding(
                FindingLevel.FAIL,
                "No accelerometer",
                "Speed and mount orientation both come from the accelerometer. " +
                    "Without it there is nothing to dead-reckon with.",
            )
        } else {
            val a = if (accelUncal.present) accelUncal else accel
            out += Finding(
                FindingLevel.OK,
                "Accelerometer present: ${hzText(a)}",
                "\"${a.name}\" by \"${a.vendor}\", range " +
                    "%.0f m/s2, resolution %.5f m/s2.".format(a.maxRange, a.resolution),
            )
            if (!accelUncal.present) {
                demote(DeviceVerdict.DEGRADED)
                out += Finding(
                    FindingLevel.WARN,
                    "No uncalibrated accelerometer",
                    "The platform applies its own bias correction before we see the " +
                        "data. The app runs, but its own bias model has less to work with.",
                )
            }
        }

        // ---- Magnetometer ----------------------------------------------------
        if (mag.present || magUncal.present) {
            out += Finding(
                FindingLevel.OK,
                "Compass present",
                "Used only as a coarse sanity check on heading. On a two-wheeler the " +
                    "engine and frame distort it badly, so this app does not fuse it " +
                    "into the estimate.",
            )
        } else {
            out += Finding(
                FindingLevel.WARN,
                "No compass",
                "Not required. Heading comes from the gyroscope, not the compass.",
            )
        }

        // ---- Barometer -------------------------------------------------------
        if (baro.present) {
            out += Finding(
                FindingLevel.OK,
                "Barometer present",
                "Gives a relative altitude signal, useful for flyovers and multi-storey " +
                    "car parks. Not required for horizontal position.",
            )
        } else {
            out += Finding(
                FindingLevel.OK,
                "No barometer",
                "Optional. Horizontal position and distance are unaffected; the app " +
                    "simply will not know which deck of a car park you are on.",
            )
        }

        return copy(verdict = worst, findings = out)
    }

    /** One-line summary for the top of the card. */
    fun headline(check: DeviceCheck): String = when (check.verdict) {
        DeviceVerdict.PASS -> "This phone can do dead reckoning."
        DeviceVerdict.DEGRADED -> "This phone will work, with limits."
        DeviceVerdict.FAIL -> "This phone cannot do dead reckoning."
        DeviceVerdict.UNKNOWN -> "Checking sensors..."
    }

    /** True when the estimator is worth arming at all. */
    fun usable(check: DeviceCheck): Boolean =
        check.verdict == DeviceVerdict.PASS || check.verdict == DeviceVerdict.DEGRADED
}
