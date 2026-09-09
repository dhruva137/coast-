package `in`.sih26168.idr.demo

import `in`.sih26168.idr.data.HudState
import `in`.sih26168.idr.data.NavMode
import `in`.sih26168.idr.data.Prefs
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicLong

/**
 * Demo-only LAN POST of the current estimate to the presenter's laptop.
 *
 * Fire-and-forget on a background executor; never blocks the estimator thread.
 * Failures are silent. Address is presenter-entered (Prefs), never a cloud host.
 */
internal class LanUploader {
    private val executor = Executors.newSingleThreadExecutor { r ->
        Thread(r, "idr-lan-uploader").apply { isDaemon = true }
    }
    private val lastPostMs = AtomicLong(0L)

    fun maybePost(prefs: Prefs, hud: HudState, session: String) {
        if (!prefs.trackerOptIn) return
        val ip = prefs.trackerLanIp.trim()
        if (ip.isEmpty() || !looksLikeLanHost(ip)) return

        val now = System.currentTimeMillis()
        val prev = lastPostMs.get()
        if (now - prev < INTERVAL_MS) return
        if (!lastPostMs.compareAndSet(prev, now)) return

        val mode = when (hud.navMode) {
            NavMode.GNSS -> "GNSS"
            else -> "IDR"
        }
        val payload = JSONObject()
            .put("t", now)
            .put("lat", jsonNum(hud.lat))
            .put("lon", jsonNum(hud.lon))
            .put("east", jsonNum(hud.east))
            .put("north", jsonNum(hud.north))
            .put("mode", mode)
            .put("speed_mps", jsonNum(hud.speedMps))
            .put("heading_deg", jsonNum(hud.headingDeg))
            .put("session", session)
            .toString()
        val url = "http://$ip:$PORT/ingest"

        executor.execute {
            try {
                val conn = (URL(url).openConnection() as HttpURLConnection).apply {
                    requestMethod = "POST"
                    connectTimeout = TIMEOUT_MS
                    readTimeout = TIMEOUT_MS
                    doOutput = true
                    setRequestProperty("Content-Type", "application/json; charset=utf-8")
                    setRequestProperty("Connection", "close")
                }
                try {
                    conn.outputStream.use { it.write(payload.toByteArray(Charsets.UTF_8)) }
                    conn.responseCode // drain status; ignore value
                } finally {
                    conn.disconnect()
                }
            } catch (_: Exception) {
                // Silent: venue wifi / wrong IP must never crash navigation.
            }
        }
    }

    private fun jsonNum(v: Double): Any =
        if (v.isFinite()) v else JSONObject.NULL

    private fun looksLikeLanHost(host: String): Boolean {
        if (host.length > 64) return false
        if (host.contains('/') || host.contains(' ') || host.contains(':')) return false
        // Presenter-entered hostname or dotted IPv4; reject obvious cloud URLs.
        if (host.contains("://")) return false
        return HOST_RE.matches(host)
    }

    companion object {
        private const val PORT = 8787
        private const val INTERVAL_MS = 500L
        private const val TIMEOUT_MS = 800
        private val HOST_RE = Regex("""^[A-Za-z0-9][A-Za-z0-9.\-]*$""")
    }
}
