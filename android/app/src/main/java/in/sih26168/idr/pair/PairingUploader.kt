package `in`.sih26168.idr.pair

import android.content.Context
import `in`.sih26168.idr.data.HudState
import `in`.sih26168.idr.data.NavMode
import org.json.JSONObject
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicLong

/**
 * Console ingest with a local queue. While GNSS or radio is gone the phone
 * keeps appending; the first successful POST after signal returns flushes
 * the backlog (the theft / tunnel story).
 *
 * Available on **standard** and tracker — this is the judge laptop demo path
 * (`POST /ingest` to coast_console). [in.sih26168.idr.demo.LanUploader] stays
 * tracker-flavour only.
 */
object PairingUploader {
    private val executor = Executors.newSingleThreadScheduledExecutor { r ->
        Thread(r, "idr-console-pair").apply { isDaemon = true }
    }
    private val client = ConsolePairClient()
    private val lastEnqueueMs = AtomicLong(0L)
    private val flushing = AtomicBoolean(false)
    private val started = AtomicBoolean(false)
    @Volatile private var appCtx: Context? = null

    fun start(context: Context) {
        appCtx = context.applicationContext
        if (!started.compareAndSet(false, true)) return
        executor.scheduleWithFixedDelay({ flush(appCtx ?: return@scheduleWithFixedDelay) }, 2, 2, TimeUnit.SECONDS)
    }

    fun maybePost(context: Context, hud: HudState) {
        start(context)
        val store = PairingStore(context)
        if (!store.paired) return
        if (!hud.lat.isFinite() || !hud.lon.isFinite()) return
        if (!hud.hasAbsolutePosition && hud.navMode == NavMode.RELATIVE) return

        val now = System.currentTimeMillis()
        val prev = lastEnqueueMs.get()
        if (now - prev < INTERVAL_MS) return
        if (!lastEnqueueMs.compareAndSet(prev, now)) return

        val mode = when (hud.navMode) {
            NavMode.GNSS -> "GNSS"
            NavMode.IDLE -> if (hud.gnssLock) "GNSS" else "IDR"
            else -> "IDR"
        }
        val speed = if (hud.speedMps.isFinite() && hud.speedMps >= 0.0) hud.speedMps else 0.0
        val acc = hud.accH.takeIf { it.isFinite() && it >= 0.0 }
            ?: hud.uncertaintyM.takeIf { it.isFinite() && it >= 0.0 }

        val obj = JSONObject()
            .put("lat", hud.lat)
            .put("lon", hud.lon)
            .put("mode", mode)
            .put("speed_mps", speed)
            .put("t", System.currentTimeMillis() / 1000.0)
            .put("queued", false)
        if (acc != null) obj.put("acc_m", acc) else obj.put("acc_m", JSONObject.NULL)
        PairingQueue(context).enqueue(obj)
        executor.execute { flush(context.applicationContext) }
    }

    /**
     * Blocking activate used by PairingScreen after scan / manual entry.
     *
     * Saves the session even if the console is unreachable right now — that is
     * the store-and-forward contract. A reachable console is claimed immediately
     * when lat/lon are finite.
     */
    fun activate(
        context: Context,
        parsed: ConsolePairClient.ParsedPair,
        lat: Double = Double.NaN,
        lon: Double = Double.NaN,
        mode: String = "GNSS",
        speedMps: Double = 0.0,
        accM: Double? = null,
    ): ConsolePairClient.IngestResult {
        start(context)
        val store = PairingStore(context)
        val reached = client.raceAndPin(parsed.lanBase, parsed.relayBase)
        val fallback = ConsolePairClient.normalizeBase(parsed.lanBase ?: parsed.relayBase ?: "")
        val base = reached ?: fallback
        if (base.isBlank()) {
            return ConsolePairClient.IngestResult(
                ok = false,
                error = "No console or relay address in this QR. Paste a pair URL, or mint a code on this phone.",
            )
        }
        store.saveActivated(
            token = parsed.token,
            baseUrl = client.pinnedBase ?: base,
            lanBase = parsed.lanBase,
            relayBase = parsed.relayBase,
            label = "Paired",
        )
        if (lat.isFinite() && lon.isFinite()) {
            val obj = JSONObject()
                .put("lat", lat)
                .put("lon", lon)
                .put("mode", mode)
                .put("speed_mps", if (speedMps.isFinite() && speedMps >= 0.0) speedMps else 0.0)
                .put("t", System.currentTimeMillis() / 1000.0)
                .put("queued", false)
            if (accM != null && accM.isFinite()) obj.put("acc_m", accM) else obj.put("acc_m", JSONObject.NULL)
            PairingQueue(context).enqueue(obj)
            flush(context)
            val storeNow = PairingStore(context)
            return if (storeNow.label.isNotBlank() && storeNow.label != "Paired") {
                ConsolePairClient.IngestResult(ok = true, label = storeNow.label)
            } else if (reached != null) {
                ConsolePairClient.IngestResult(ok = true, label = "Paired")
            } else {
                ConsolePairClient.IngestResult(
                    ok = true,
                    label = "Saved — will send when the console is reachable",
                )
            }
        }
        return if (reached != null) {
            ConsolePairClient.IngestResult(ok = true, label = "Paired — start Drive to stream")
        } else {
            ConsolePairClient.IngestResult(
                ok = true,
                label = "Saved — will send when the console is reachable",
            )
        }
    }

    /**
     * Phone-initiated pair: mint a short-lived nonce, persist relay + token,
     * save the session, and start the same LAN+relay race / queue flush as a
     * scanned console QR. Wi-Fi is not required — mobile data can reach the relay.
     */
    fun activateLocalMint(
        context: Context,
        relayUrl: String? = null,
        lanBase: String? = null,
        lat: Double = Double.NaN,
        lon: Double = Double.NaN,
        mode: String = "GNSS",
        speedMps: Double = 0.0,
        accM: Double? = null,
    ): Pair<PairingStore.LocalPairCode, ConsolePairClient.IngestResult> {
        val code = PairingStore(context).mintLocalToken(relayUrl = relayUrl, lanBase = lanBase)
        val result = activate(
            context = context,
            parsed = code.toParsedPair(),
            lat = lat,
            lon = lon,
            mode = mode,
            speedMps = speedMps,
            accM = accM,
        )
        return code to result
    }

    fun unpair(context: Context) {
        PairingStore(context).clear()
        PairingQueue(context).clear()
        client.clearPin()
        lastEnqueueMs.set(0L)
    }

    /** Drain the on-device queue over whatever radio is up (Wi-Fi or mobile data). */
    private fun flush(context: Context) {
        if (!flushing.compareAndSet(false, true)) return
        try {
            var batches = 0
            while (batches < 20) {
                batches++
                val store = PairingStore(context)
                if (!store.paired) return
                val q = PairingQueue(context)
                val batch = q.drain(80)
                if (batch.length() == 0) return
                // Anything sitting in the file was delayed — mark catch-up except the last live tick.
                if (batch.length() > 1) {
                    for (i in 0 until batch.length() - 1) {
                        batch.getJSONObject(i).put("queued", true)
                    }
                }
                val result = client.postBatch(
                    token = store.token,
                    points = batch,
                    lanBase = store.lanBase.takeIf { it.isNotBlank() },
                    relayBase = store.relayBase.takeIf { it.isNotBlank() },
                    preferredBase = store.baseUrl.takeIf { it.isNotBlank() },
                )
                if (!result.ok) {
                    q.requeueFront(batch)
                    return
                }
                client.pinnedBase?.let { store.updatePin(it) }
                result.label?.let { store.updateLabel(it) }
                if (q.size() == 0) return
            }
        } finally {
            flushing.set(false)
        }
    }

    private const val INTERVAL_MS = 1_000L
}
