package `in`.sih26168.idr.pair

import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URI
import java.net.URL
import java.net.URLEncoder
import java.security.SecureRandom
import java.util.concurrent.Callable
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicInteger
import java.util.concurrent.atomic.AtomicReference

/**
 * Parse console QR/URL/token payloads and POST live position to `/ingest`.
 *
 * Console-initiated ([web.pairing.pair_payload]):
 * `{lan}/pair?s={token}&lan={lan_base}&relay=...`
 *
 * Phone-initiated ([pairPayload]): `{relay}/pair?s={token}&relay={relay}`
 * with optional `&lan=`. `s` + `relay` required; `lan` optional.
 *
 * Payload fields only: token, lat, lon, mode, speed_mps, acc_m.
 * Never IMEI, advertising ID, or any device fingerprint.
 */
class ConsolePairClient {

    private val consecutiveFailures = AtomicInteger(0)

    @Volatile
    var pinnedBase: String? = null
        private set

    fun resetFailures() {
        consecutiveFailures.set(0)
    }

    fun pin(base: String) {
        pinnedBase = normalizeBase(base).takeIf { it.isNotEmpty() }
        consecutiveFailures.set(0)
    }

    fun clearPin() {
        pinnedBase = null
        consecutiveFailures.set(0)
    }

    /**
     * Race [lanBase] and [relayBase] (~3.5 s each). First reachable wins.
     * Returns the pinned base or null if none answered.
     */
    fun raceAndPin(lanBase: String?, relayBase: String?): String? {
        val candidates = listOfNotNull(lanBase, relayBase)
            .map { normalizeBase(it) }
            .filter { it.isNotEmpty() }
            .distinct()
        if (candidates.isEmpty()) return null
        val winner = raceBases(candidates) ?: return null
        pin(winner)
        return winner
    }

    /**
     * POST one frame. On success resets the failure counter; after three
     * consecutive failures, re-races LAN+relay and retries once on the new pin.
     */
    fun postPosition(
        token: String,
        lat: Double,
        lon: Double,
        mode: String,
        speedMps: Double,
        accM: Double?,
        lanBase: String?,
        relayBase: String?,
        preferredBase: String?,
    ): IngestResult {
        var base = pinnedBase ?: preferredBase?.let { normalizeBase(it) }
        if (base.isNullOrBlank()) {
            base = raceAndPin(lanBase, relayBase)
        }
        if (base.isNullOrBlank()) {
            noteFailure(lanBase, relayBase)
            return IngestResult(ok = false, error = "no reachable console endpoint")
        }

        var usedBase = base
        var result = postOnce(base, token, lat, lon, mode, speedMps, accM)
        if (!result.ok) {
            if (noteFailure(lanBase, relayBase)) {
                val retried = pinnedBase
                if (retried != null && retried != base) {
                    result = postOnce(retried, token, lat, lon, mode, speedMps, accM)
                    usedBase = retried
                }
            }
        }
        if (result.ok) {
            consecutiveFailures.set(0)
            pinnedBase = usedBase
        }
        return result
    }

    fun postBatch(
        token: String,
        points: org.json.JSONArray,
        lanBase: String?,
        relayBase: String?,
        preferredBase: String?,
    ): IngestResult {
        if (points.length() == 0) return IngestResult(ok = true)
        var base = pinnedBase ?: preferredBase?.let { normalizeBase(it) }
        if (base.isNullOrBlank()) {
            base = raceAndPin(lanBase, relayBase)
        }
        if (base.isNullOrBlank()) {
            noteFailure(lanBase, relayBase)
            return IngestResult(ok = false, error = "no reachable console endpoint")
        }
        val body = JSONObject()
            .put("token", token)
            .put("points", points)
        val url = "${normalizeBase(base)}/ingest"
        return try {
            val conn = (URL(url).openConnection() as HttpURLConnection).apply {
                requestMethod = "POST"
                connectTimeout = POST_TIMEOUT_MS
                readTimeout = POST_TIMEOUT_MS
                doOutput = true
                setRequestProperty("Content-Type", "application/json; charset=utf-8")
                setRequestProperty("Connection", "close")
            }
            try {
                conn.outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }
                val code = conn.responseCode
                val text = (if (code in 200..299) conn.inputStream else conn.errorStream)
                    ?.bufferedReader()
                    ?.use { it.readText() }
                    .orEmpty()
                val json = runCatching { JSONObject(text) }.getOrNull()
                val ok = json?.optBoolean("ok", false) == true
                if (ok) {
                    consecutiveFailures.set(0)
                    pinnedBase = base
                } else {
                    noteFailure(lanBase, relayBase)
                }
                IngestResult(
                    ok = ok,
                    httpCode = code,
                    label = json?.optString("label")?.takeIf { it.isNotBlank() },
                    error = json?.optString("error")?.takeIf { it.isNotBlank() }
                        ?: if (!ok) "HTTP $code" else null,
                )
            } finally {
                conn.disconnect()
            }
        } catch (e: Exception) {
            noteFailure(lanBase, relayBase)
            IngestResult(ok = false, error = e.message ?: "network error")
        }
    }

    private fun noteFailure(lanBase: String?, relayBase: String?): Boolean {
        val n = consecutiveFailures.incrementAndGet()
        if (n < FAIL_BEFORE_RERACE) return false
        consecutiveFailures.set(0)
        raceAndPin(lanBase, relayBase)
        return true
    }

    private fun postOnce(
        base: String,
        token: String,
        lat: Double,
        lon: Double,
        mode: String,
        speedMps: Double,
        accM: Double?,
    ): IngestResult {
        val body = JSONObject()
            .put("token", token)
            .put("lat", lat)
            .put("lon", lon)
            .put("mode", mode)
            .put("speed_mps", if (speedMps.isFinite() && speedMps >= 0.0) speedMps else 0.0)
        if (accM != null && accM.isFinite() && accM >= 0.0) {
            body.put("acc_m", accM)
        } else {
            body.put("acc_m", JSONObject.NULL)
        }
        // Deliberately omit any device / advertising identifiers.
        val url = "${normalizeBase(base)}/ingest"
        return try {
            val conn = (URL(url).openConnection() as HttpURLConnection).apply {
                requestMethod = "POST"
                connectTimeout = POST_TIMEOUT_MS
                readTimeout = POST_TIMEOUT_MS
                doOutput = true
                setRequestProperty("Content-Type", "application/json; charset=utf-8")
                setRequestProperty("Connection", "close")
            }
            try {
                conn.outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }
                val code = conn.responseCode
                val text = (if (code in 200..299) conn.inputStream else conn.errorStream)
                    ?.bufferedReader()
                    ?.use { it.readText() }
                    .orEmpty()
                val json = runCatching { JSONObject(text) }.getOrNull()
                val ok = json?.optBoolean("ok", false) == true
                IngestResult(
                    ok = ok,
                    httpCode = code,
                    label = json?.optString("label")?.takeIf { it.isNotBlank() },
                    error = json?.optString("error")?.takeIf { it.isNotBlank() }
                        ?: if (!ok) "HTTP $code" else null,
                )
            } finally {
                conn.disconnect()
            }
        } catch (e: Exception) {
            IngestResult(ok = false, error = e.message ?: "network error")
        }
    }

    data class IngestResult(
        val ok: Boolean,
        val httpCode: Int = 0,
        val label: String? = null,
        val error: String? = null,
    )

    data class ParsedPair(
        val token: String,
        val lanBase: String?,
        val relayBase: String?,
    ) {
        /** Phone-minted codes carry relay + nonce; LAN is optional. */
        fun hasEndpoint(): Boolean = !lanBase.isNullOrBlank() || !relayBase.isNullOrBlank()
    }

    companion object {
        const val RACE_TIMEOUT_MS = 3_500
        const val POST_TIMEOUT_MS = 3_500
        const val FAIL_BEFORE_RERACE = 3
        const val MINT_TOKEN_LEN_MIN = 8
        const val MINT_TOKEN_LEN_MAX = 12
        const val MINT_TOKEN_LEN_DEFAULT = 10
        const val LOCAL_TOKEN_TTL_MS = 15 * 60 * 1000L
        private val TOKEN_RE = Regex("""^[A-Za-z0-9_-]{8,64}$""")
        private const val URL_SAFE = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
        private val rng = SecureRandom()

        fun normalizeBase(raw: String): String =
            raw.trim().trimEnd('/').removeSuffix("/pair").trimEnd('/')

        fun isPairToken(raw: String): Boolean = TOKEN_RE.matches(raw.trim())

        /**
         * Short-lived URL-safe nonce for phone-initiated pairing (8–12 chars).
         * Not a device id — a one-time session value, same shape as the console mint.
         */
        fun mintToken(length: Int = MINT_TOKEN_LEN_DEFAULT): String {
            val n = length.coerceIn(MINT_TOKEN_LEN_MIN, MINT_TOKEN_LEN_MAX)
            val chars = CharArray(n)
            for (i in 0 until n) {
                chars[i] = URL_SAFE[rng.nextInt(URL_SAFE.length)]
            }
            return String(chars)
        }

        /**
         * QR / paste payload when the **phone** mints the nonce.
         * Requires [relayBase] + [token]; [lanBase] is optional (venue LAN).
         */
        fun pairPayload(token: String, relayBase: String, lanBase: String? = null): String {
            val tok = token.trim()
            require(TOKEN_RE.matches(tok)) { "pairing token must be 8–64 URL-safe characters" }
            val relay = normalizeBase(relayBase)
            require(relay.isNotEmpty()) { "relay URL is required for a phone-minted pair code" }
            val q = ArrayList<String>(3)
            q.add("s=${enc(tok)}")
            q.add("relay=${enc(relay)}")
            val lan = lanBase?.let { normalizeBase(it) }?.takeIf { it.isNotEmpty() }
            if (lan != null) q.add("lan=${enc(lan)}")
            return "$relay/pair?${q.joinToString("&")}"
        }

        private fun enc(value: String): String =
            URLEncoder.encode(value, Charsets.UTF_8.name())

        private fun sameBase(a: String, b: String): Boolean =
            normalizeBase(a).equals(normalizeBase(b), ignoreCase = true)

        /**
         * Accepts a full pair URL, `coast://pair?…`, a bare console origin + `?s=`,
         * or a raw token. Raw token alone leaves bases null — the UI must supply
         * a console URL.
         *
         * Phone-minted URLs omit `lan`. If the URL origin equals `relay` and `lan`
         * is absent, [ParsedPair.lanBase] stays null (the origin is the relay).
         * Console URLs whose origin is a LAN host still infer `lan` from the host
         * even when `relay` is present.
         */
        fun parse(raw: String): ParsedPair? {
            var trimmed = raw.trim().trim('\uFEFF')
            if (trimmed.isEmpty()) return null
            if ((trimmed.startsWith('"') && trimmed.endsWith('"')) ||
                (trimmed.startsWith('\'') && trimmed.endsWith('\''))
            ) {
                trimmed = trimmed.substring(1, trimmed.length - 1).trim()
            }
            if ('\n' in trimmed || '\r' in trimmed) {
                trimmed = trimmed.lineSequence().map { it.trim() }.firstOrNull { line ->
                    line.contains("/pair", ignoreCase = true) ||
                        line.startsWith("http", ignoreCase = true) ||
                        line.startsWith("coast:", ignoreCase = true) ||
                        TOKEN_RE.matches(line)
                } ?: trimmed.lineSequence().first().trim()
            }

            if (TOKEN_RE.matches(trimmed)) {
                return ParsedPair(token = trimmed, lanBase = null, relayBase = null)
            }

            if (trimmed.startsWith("coast:", ignoreCase = true)) {
                trimmed = trimmed
                    .replace(Regex("^coast://pair", RegexOption.IGNORE_CASE), "http://pair.invalid/pair")
                    .replace(Regex("^coast:pair", RegexOption.IGNORE_CASE), "http://pair.invalid/pair")
            }

            val uri = runCatching { URI(trimmed) }.getOrNull() ?: return null
            val query = uri.rawQuery ?: ""
            val params = query.split('&')
                .mapNotNull { part ->
                    val i = part.indexOf('=')
                    if (i <= 0) null
                    else {
                        val k = part.substring(0, i)
                        val v = java.net.URLDecoder.decode(part.substring(i + 1), Charsets.UTF_8.name())
                        k to v
                    }
                }
                .toMap()

            val token = params["s"]?.trim().orEmpty()
            if (!TOKEN_RE.matches(token)) return null

            val lanParam = params["lan"]?.takeIf { it.isNotBlank() }?.let { normalizeBase(it) }
            val relay = params["relay"]?.takeIf { it.isNotBlank() }?.let { normalizeBase(it) }

            val inferred = buildString {
                if (!uri.scheme.isNullOrBlank() &&
                    !uri.host.isNullOrBlank() &&
                    uri.host != "pair.invalid"
                ) {
                    append(uri.scheme).append("://").append(uri.host)
                    if (uri.port > 0) append(':').append(uri.port)
                }
            }.takeIf { it.isNotBlank() }?.let { normalizeBase(it) }

            // Phone-minted: origin == relay and no `lan=` → lan stays optional/null.
            // Console-minted: origin is the laptop LAN, which differs from relay.
            val lan = when {
                !lanParam.isNullOrBlank() -> lanParam
                inferred != null && (relay == null || !sameBase(inferred, relay)) -> inferred
                else -> null
            }

            return ParsedPair(
                token = token,
                lanBase = lan,
                relayBase = relay,
            )
        }

        fun parseWithFallbackBase(raw: String, fallbackBase: String?): ParsedPair? {
            val parsed = parse(raw) ?: return null
            if (parsed.lanBase != null || parsed.relayBase != null) return parsed
            val base = fallbackBase?.let { normalizeBase(it) }?.takeIf { it.isNotEmpty() }
                ?: return null
            return parsed.copy(lanBase = base)
        }

        /** First candidate that accepts a TCP+HTTP handshake within [RACE_TIMEOUT_MS]. */
        fun raceBases(candidates: List<String>): String? {
            val bases = candidates.map { normalizeBase(it) }.filter { it.isNotEmpty() }.distinct()
            if (bases.isEmpty()) return null
            if (bases.size == 1) return if (probe(bases[0])) bases[0] else null

            val executor = Executors.newFixedThreadPool(bases.size.coerceAtMost(4))
            val winner = AtomicReference<String?>(null)
            try {
                val futures = bases.map { base ->
                    executor.submit(
                        Callable {
                            if (probe(base) && winner.compareAndSet(null, base)) base else null
                        },
                    )
                }
                val deadline = System.nanoTime() + TimeUnit.MILLISECONDS.toNanos(RACE_TIMEOUT_MS.toLong())
                while (System.nanoTime() < deadline && winner.get() == null) {
                    if (futures.all { it.isDone }) break
                    Thread.sleep(25)
                }
                futures.forEach { it.cancel(true) }
                winner.get()?.let { return it }
                // Late finishers that completed inside the window.
                for (f in futures) {
                    if (!f.isDone) continue
                    val v = runCatching { f.get() }.getOrNull()
                    if (v != null) return v
                }
                return null
            } finally {
                executor.shutdownNow()
            }
        }

        private fun probe(base: String): Boolean {
            val paths = listOf("/api/health", "/pair")
            for (path in paths) {
                try {
                    val conn = (URL("$base$path").openConnection() as HttpURLConnection).apply {
                        requestMethod = "GET"
                        connectTimeout = RACE_TIMEOUT_MS
                        readTimeout = RACE_TIMEOUT_MS
                        instanceFollowRedirects = false
                        setRequestProperty("Connection", "close")
                    }
                    try {
                        conn.connect()
                        val code = conn.responseCode
                        if (code in 200..499) return true
                    } finally {
                        conn.disconnect()
                    }
                } catch (_: Exception) {
                    // try next path
                }
            }
            return false
        }
    }
}
