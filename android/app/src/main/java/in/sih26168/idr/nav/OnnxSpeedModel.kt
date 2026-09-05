package `in`.sih26168.idr.nav

import ai.onnxruntime.OnnxTensor
import ai.onnxruntime.OrtEnvironment
import ai.onnxruntime.OrtSession
import android.content.Context
import `in`.sih26168.idr.data.SensorFrame
import java.nio.FloatBuffer
import java.util.concurrent.Executors
import java.util.concurrent.ThreadFactory
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicReference
import kotlin.math.exp
import kotlin.math.max
import kotlin.math.min

/**
 * One inference of `lab/models/weights/avnet_tiny.onnx` (FrequencyDecoupledNet).
 *
 * Heads mirror `backbone.FrequencyDecoupledNet.split_heads` and the variance
 * post-processing in `lab/models/infer.py`: `exp(clamp(logvar, -8, 4))`.
 */
data class SpeedEstimate(
    val tNs: Long,
    val speed: Double,
    val psiDot: Double,
    val rollRes: Double,
    val pitchRes: Double,
    val speedVar: Double,
    val yawVar: Double,
    val latencyMs: Double,
)

/**
 * On-device AVNet-tiny runner. ONNX Runtime Mobile, CPU, single intra-op thread.
 *
 * Contract copied from the training pipeline — a mismatch here is silent garbage:
 *
 *  * input  `imu`     float32 (1, 6, 20), channel-major
 *  * channels        ax, ay, az, gx, gy, gz  (`log_schema.IMU6_COLUMNS`)
 *  * units           raw specific force in m/s² **including gravity**, gyro rad/s.
 *                    No mean/std normalisation was applied at train time
 *                    (`train_avnet.py` feeds `batch.imu` straight through), and
 *                    `kinematic_speed_prior` subtracts g internally, so the app
 *                    must *not* remove gravity either.
 *  * window          20 samples @ 10 Hz = 2.0 s (`log_schema.WINDOW_SAMPLES`)
 *  * output `outputs` float32 (1, 6) =
 *                    speed, psi_dot, roll_res, pitch_res, logvar_speed, logvar_psi
 *
 * [SensorHub] runs at `SENSOR_DELAY_FASTEST` (100–500 Hz). Picking the newest
 * sample every 100 ms would alias mount vibration straight into the 0–5 Hz band
 * the FIR split treats as signal, so each 100 ms bin is **mean-decimated** —
 * that is the anti-aliasing IO-VNBD's native 10 Hz logger already applied to
 * the training data.
 *
 * Failure is loud: if the asset is missing or the session will not build,
 * [ready] stays false, [error] carries the reason and [onImu] returns null
 * forever. There is no constant stand-in pretending to be a model.
 *
 * ## Threading and backpressure
 *
 * [onImu] is called from the IMU handler thread at the full sensor rate. It only
 * does bin arithmetic there. When a 100 ms bin closes and the window is full it
 * hands a COPY of the window to a single background thread and returns
 * immediately; the completed estimate is picked up by a later [onImu] call.
 *
 * `OrtSession.run` used to be called inline on that handler thread. It never
 * touched the main thread, so it was not the source of UI jank directly -- but a
 * slow window stalled the sensor looper, so IMU samples backed up and arrived in
 * bursts, which shows up as a stuttering speed readout and a jittery track. If
 * an inference is still running when the next window closes, that window is
 * DROPPED ([droppedWindows] counts them). Queueing would be worse: stale speed
 * is wrong speed, and this is a live navigation display.
 */
class OnnxSpeedModel(context: Context) : AutoCloseable {

    private var env: OrtEnvironment? = null
    private var session: OrtSession? = null
    private var inputName: String = INPUT_NAME

    @Volatile
    var error: String? = null
        private set

    val ready: Boolean
        get() = session != null

    /** Sustained successful-inference rate, Hz. Target is 10.0. */
    @Volatile
    var hz: Double = 0.0
        private set

    /** Latency of the most recent successful [OrtSession.run], ms. */
    @Volatile
    var lastLatencyMs: Double = 0.0
        private set

    @Volatile
    var last: SpeedEstimate? = null
        private set

    // 10 Hz ring, sample-major: ring[i * CHANNELS + c].
    private val ring = FloatArray(WINDOW * CHANNELS)
    private var ringCount = 0
    private var ringHead = 0

    // Current 100 ms decimation bin.
    private val binSum = DoubleArray(CHANNELS)
    private var binN = 0
    private var binStartNs = 0L

    private val input = FloatArray(CHANNELS * WINDOW)
    private var runs = 0
    private var hzWindowNs = 0L

    // ---- Backpressure ------------------------------------------------------
    /** One thread, below the IMU thread in priority. Never touches the main thread. */
    private val worker = Executors.newSingleThreadExecutor(
        ThreadFactory { r ->
            Thread(r, "idr-onnx").apply {
                isDaemon = true
                priority = Thread.NORM_PRIORITY - 1
            }
        },
    )
    private val inFlight = AtomicBoolean(false)
    private val completed = AtomicReference<SpeedEstimate?>(null)
    private val closed = AtomicBoolean(false)

    /** Windows skipped because the previous inference had not finished. */
    @Volatile
    var droppedWindows: Long = 0L
        private set

    init {
        try {
            val bytes = context.assets.open(ASSET).use { it.readBytes() }
            val e = OrtEnvironment.getEnvironment()
            val opts = OrtSession.SessionOptions().apply {
                setIntraOpNumThreads(1)
                setOptimizationLevel(OrtSession.SessionOptions.OptLevel.ALL_OPT)
            }
            val s = e.createSession(bytes, opts)
            inputName = s.inputNames.firstOrNull() ?: INPUT_NAME
            env = e
            session = s
        } catch (t: Throwable) {
            error = "$ASSET load failed: ${t.javaClass.simpleName}: ${t.message ?: "no message"}"
        }
    }

    fun reset() {
        ringCount = 0
        ringHead = 0
        binN = 0
        binStartNs = 0L
        binSum.fill(0.0)
        runs = 0
        hzWindowNs = 0L
        hz = 0.0
        lastLatencyMs = 0.0
        last = null
        completed.set(null)
        droppedWindows = 0L
    }

    /**
     * Feed one raw IMU frame, cheaply, on the caller's thread.
     *
     * Returns the newest COMPLETED estimate the moment one is available, and
     * null otherwise — including on the tick that dispatched the window that
     * will produce it. In practice that is a delay of one inference, ~1 frame at
     * 10 Hz, which the estimator's own staleness window already tolerates.
     */
    fun onImu(frame: SensorFrame): SpeedEstimate? {
        if (session == null) return null
        // Drain first, so a result that landed while we were away is picked up
        // even on a tick where no bin closes.
        val ready = completed.getAndSet(null)

        if (binStartNs == 0L) binStartNs = frame.tNs
        // A backwards or absurd jump (clock change, resumed logger) restarts the bin.
        val span = frame.tNs - binStartNs
        if (span < 0L || span > 4L * BIN_NS) {
            binN = 0
            binSum.fill(0.0)
            binStartNs = frame.tNs
        }

        binSum[0] += frame.ax
        binSum[1] += frame.ay
        binSum[2] += frame.az
        binSum[3] += frame.gx
        binSum[4] += frame.gy
        binSum[5] += frame.gz
        binN += 1

        if (frame.tNs - binStartNs < BIN_NS) return ready

        val n = binN.toDouble()
        val base = ringHead * CHANNELS
        for (c in 0 until CHANNELS) ring[base + c] = (binSum[c] / n).toFloat()
        ringHead = (ringHead + 1) % WINDOW
        if (ringCount < WINDOW) ringCount += 1
        binN = 0
        binSum.fill(0.0)
        binStartNs = frame.tNs

        if (ringCount < WINDOW) return ready
        dispatchWindow(frame.tNs)
        return ready
    }

    /**
     * Transpose the ring into the model layout and hand a COPY to the worker.
     *
     * The copy matters: [ring] keeps being written by the IMU thread while the
     * worker runs, and feeding a tensor a buffer that is mutating underneath it
     * is exactly the kind of silent-garbage bug the contract note above warns
     * about. 120 floats per window at 10 Hz is nothing.
     */
    private fun dispatchWindow(tNs: Long) {
        if (closed.get()) return
        // Oldest → newest, transposed into the (1, 6, 20) channel-major layout
        // torch.onnx.export baked in from `train_avnet.py`'s (N, 6, T) tensors.
        val oldest = ringHead // ring is full, so head points at the oldest sample
        for (t in 0 until WINDOW) {
            val base = ((oldest + t) % WINDOW) * CHANNELS
            for (c in 0 until CHANNELS) input[c * WINDOW + t] = ring[base + c]
        }
        if (!inFlight.compareAndSet(false, true)) {
            // Previous inference still running. Drop this window rather than
            // queue it: a queued window would be delivered as current speed.
            droppedWindows += 1
            return
        }
        val window = input.copyOf()
        try {
            worker.execute {
                try {
                    runWindow(tNs, window)?.let { completed.set(it) }
                } finally {
                    inFlight.set(false)
                }
            }
        } catch (_: Throwable) {
            // Executor shut down between the closed check and here.
            inFlight.set(false)
        }
    }

    private fun runWindow(tNs: Long, window: FloatArray): SpeedEstimate? {
        val s = session ?: return null
        val e = env ?: return null

        val out: FloatArray
        val t0 = System.nanoTime()
        try {
            OnnxTensor.createTensor(e, FloatBuffer.wrap(window), SHAPE).use { tensor ->
                s.run(mapOf(inputName to tensor)).use { result ->
                    @Suppress("UNCHECKED_CAST")
                    out = (result[0].value as Array<FloatArray>)[0]
                }
            }
        } catch (t: Throwable) {
            error = "inference failed: ${t.javaClass.simpleName}: ${t.message ?: "no message"}"
            return null
        }
        val latencyMs = (System.nanoTime() - t0) / 1e6

        if (out.size < 6 || out.any { !it.isFinite() }) {
            error = "model returned ${out.size} non-finite/short outputs"
            return null
        }

        noteHz(tNs)
        lastLatencyMs = latencyMs
        error = null
        val est = SpeedEstimate(
            tNs = tNs,
            speed = max(0.0, out[0].toDouble()),
            psiDot = out[1].toDouble(),
            rollRes = out[2].toDouble(),
            pitchRes = out[3].toDouble(),
            speedVar = expLogVar(out[4]),
            yawVar = expLogVar(out[5]),
            latencyMs = latencyMs,
        )
        last = est
        return est
    }

    private fun noteHz(tNs: Long) {
        if (hzWindowNs == 0L) {
            hzWindowNs = tNs
            return
        }
        runs += 1
        val dt = (tNs - hzWindowNs) / 1e9
        if (dt >= 1.0) {
            hz = runs / dt
            runs = 0
            hzWindowNs = tNs
        }
    }

    override fun close() {
        closed.set(true)
        // Stop accepting work, then wait briefly for an in-flight run so the
        // session is never closed out from under OrtSession.run.
        try {
            worker.shutdown()
            worker.awaitTermination(2, java.util.concurrent.TimeUnit.SECONDS)
        } catch (_: InterruptedException) {
            Thread.currentThread().interrupt()
        } catch (_: Throwable) {
        }
        try {
            session?.close()
        } catch (_: Throwable) {
        }
        session = null
        // OrtEnvironment is a process-wide singleton — do not close it here.
        env = null
    }

    private companion object {
        const val ASSET = "avnet_tiny.onnx"
        const val INPUT_NAME = "imu"
        const val WINDOW = 20
        const val CHANNELS = 6
        const val BIN_NS = 100_000_000L // 10 Hz
        val SHAPE = longArrayOf(1, CHANNELS.toLong(), WINDOW.toLong())

        /** `infer.py`: `exp(clip(logvar, -8, 4))`. */
        fun expLogVar(v: Float): Double = exp(min(4.0, max(-8.0, v.toDouble())))
    }
}
