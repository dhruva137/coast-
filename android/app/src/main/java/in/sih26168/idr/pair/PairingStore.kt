package `in`.sih26168.idr.pair

import android.content.Context
import android.content.SharedPreferences
import `in`.sih26168.idr.BuildConfig
import `in`.sih26168.idr.R

/**
 * Active console-pairing session. Survives process death so Drive can keep
 * streaming and show the paired indicator after a rotate / cold start.
 *
 * Cleared only by explicit Unpair — never by navigation stop.
 *
 * Also holds a phone-minted short-lived nonce so either side can initiate:
 * the phone shows a QR (`relay` + `s`, optional `lan`) and the laptop scans it.
 */
class PairingStore(context: Context) {
    private val appCtx = context.applicationContext
    private val sp: SharedPreferences =
        appCtx.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    var paired: Boolean
        get() = sp.getBoolean(KEY_PAIRED, false) && token.isNotBlank() &&
            (baseUrl.isNotBlank() || lanBase.isNotBlank() || relayBase.isNotBlank())
        set(v) = sp.edit().putBoolean(KEY_PAIRED, v).apply()

    var token: String
        get() = sp.getString(KEY_TOKEN, "") ?: ""
        set(v) = sp.edit().putString(KEY_TOKEN, v).apply()

    /** Pinned ingest base that last answered the race (no trailing slash). */
    var baseUrl: String
        get() = sp.getString(KEY_BASE, "") ?: ""
        set(v) = sp.edit().putString(KEY_BASE, v.trimEnd('/')).apply()

    var lanBase: String
        get() = sp.getString(KEY_LAN, "") ?: ""
        set(v) = sp.edit().putString(KEY_LAN, v.trimEnd('/')).apply()

    var relayBase: String
        get() = sp.getString(KEY_RELAY, "") ?: ""
        set(v) = sp.edit().putString(KEY_RELAY, v.trimEnd('/')).apply()

    /** Console-assigned label (Judge-1, …) from the first successful ingest. */
    var label: String
        get() = sp.getString(KEY_LABEL, "") ?: ""
        set(v) = sp.edit().putString(KEY_LABEL, v).apply()

    fun saveActivated(
        token: String,
        baseUrl: String,
        lanBase: String?,
        relayBase: String?,
        label: String,
    ) {
        sp.edit()
            .putBoolean(KEY_PAIRED, true)
            .putString(KEY_TOKEN, token)
            .putString(KEY_BASE, baseUrl.trimEnd('/'))
            .putString(KEY_LAN, (lanBase ?: "").trimEnd('/'))
            .putString(KEY_RELAY, (relayBase ?: "").trimEnd('/'))
            .putString(KEY_LABEL, label)
            .apply()
    }

    fun updatePin(baseUrl: String) {
        sp.edit().putString(KEY_BASE, baseUrl.trimEnd('/')).apply()
    }

    fun updateLabel(label: String) {
        if (label.isBlank()) return
        sp.edit().putString(KEY_LABEL, label).apply()
    }

    /**
     * Relay origin for phone-minted codes. String resource first, then
     * [BuildConfig.DEFAULT_PAIR_RELAY] — never a hardcoded secret in call sites.
     */
    fun defaultRelayBase(): String {
        val fromRes = runCatching { appCtx.getString(R.string.default_pair_relay) }
            .getOrDefault("")
            .trim()
        if (fromRes.isNotEmpty()) return ConsolePairClient.normalizeBase(fromRes)
        return ConsolePairClient.normalizeBase(BuildConfig.DEFAULT_PAIR_RELAY)
    }

    /**
     * Mint (or reuse an unexpired) short-lived pairing nonce and persist it
     * with the relay URL. Does **not** mark the session paired — call
     * [PairingUploader.activate] with [LocalPairCode.toParsedPair] so ingest starts.
     *
     * If a live paired session already exists, returns that token so the QR
     * cannot rotate out from under an in-flight stream.
     */
    fun mintLocalToken(
        relayUrl: String? = null,
        lanBase: String? = null,
        nowMs: Long = System.currentTimeMillis(),
    ): LocalPairCode {
        val relay = ConsolePairClient.normalizeBase(
            relayUrl?.takeIf { it.isNotBlank() } ?: defaultRelayBase(),
        )
        val lan = lanBase?.let { ConsolePairClient.normalizeBase(it) }?.takeIf { it.isNotEmpty() }
        // Same-Wi-Fi demo: console address alone is enough (no public relay / VLAN).
        val endpoint = when {
            relay.isNotEmpty() -> relay
            lan != null -> lan
            else -> throw IllegalArgumentException(
                "No pairing relay or console Wi-Fi address configured",
            )
        }

        if (paired && ConsolePairClient.isPairToken(token)) {
            val liveRelay = relayBase.ifBlank { endpoint }
            val liveLan = this.lanBase.takeIf { it.isNotBlank() } ?: lan
            return LocalPairCode(
                token = token,
                relayBase = liveRelay,
                lanBase = liveLan,
                expiresAtMs = Long.MAX_VALUE,
                qrPayload = ConsolePairClient.pairPayload(token, liveRelay, liveLan),
            )
        }

        currentLocalMint(nowMs)?.let { existing ->
            if (existing.relayBase.equals(endpoint, ignoreCase = true)) {
                if (lan != null && lan != existing.lanBase) {
                    val updated = existing.copy(
                        lanBase = lan,
                        qrPayload = ConsolePairClient.pairPayload(existing.token, endpoint, lan),
                    )
                    persistMint(updated)
                    return updated
                }
                return existing
            }
        }

        val nonce = ConsolePairClient.mintToken()
        val code = LocalPairCode(
            token = nonce,
            relayBase = endpoint,
            lanBase = lan,
            expiresAtMs = nowMs + ConsolePairClient.LOCAL_TOKEN_TTL_MS,
            qrPayload = ConsolePairClient.pairPayload(nonce, endpoint, lan),
        )
        persistMint(code)
        return code
    }

    /** Unexpired phone-minted code, or null if none / expired. */
    fun currentLocalMint(nowMs: Long = System.currentTimeMillis()): LocalPairCode? {
        val tok = sp.getString(KEY_MINT_TOKEN, "")?.trim().orEmpty()
        val relay = ConsolePairClient.normalizeBase(sp.getString(KEY_MINT_RELAY, "") ?: "")
        val lan = ConsolePairClient.normalizeBase(sp.getString(KEY_MINT_LAN, "") ?: "")
            .takeIf { it.isNotEmpty() }
        val expires = sp.getLong(KEY_MINT_EXPIRES, 0L)
        if (!ConsolePairClient.isPairToken(tok) || relay.isEmpty()) return null
        if (expires > 0L && nowMs >= expires) return null
        return LocalPairCode(
            token = tok,
            relayBase = relay,
            lanBase = lan,
            expiresAtMs = expires,
            qrPayload = ConsolePairClient.pairPayload(tok, relay, lan),
        )
    }

    fun clear() {
        sp.edit().clear().apply()
    }

    /** Drop a cached phone-minted code so NEW CODE rotates. */
    fun clearMint() {
        sp.edit()
            .remove(KEY_MINT_TOKEN)
            .remove(KEY_MINT_RELAY)
            .remove(KEY_MINT_LAN)
            .remove(KEY_MINT_EXPIRES)
            .apply()
    }

    private fun persistMint(code: LocalPairCode) {
        sp.edit()
            .putString(KEY_MINT_TOKEN, code.token)
            .putString(KEY_MINT_RELAY, code.relayBase)
            .putString(KEY_MINT_LAN, code.lanBase ?: "")
            .putLong(KEY_MINT_EXPIRES, code.expiresAtMs)
            .apply()
    }

    data class LocalPairCode(
        val token: String,
        val relayBase: String,
        val lanBase: String?,
        val expiresAtMs: Long,
        val qrPayload: String,
    ) {
        fun toParsedPair(): ConsolePairClient.ParsedPair =
            ConsolePairClient.ParsedPair(
                token = token,
                lanBase = lanBase,
                relayBase = relayBase,
            )

        fun isExpired(nowMs: Long = System.currentTimeMillis()): Boolean =
            expiresAtMs != Long.MAX_VALUE && nowMs >= expiresAtMs
    }

    private companion object {
        const val PREFS = "idr_console_pair"
        const val KEY_PAIRED = "paired"
        const val KEY_TOKEN = "token"
        const val KEY_BASE = "base_url"
        const val KEY_LAN = "lan_base"
        const val KEY_RELAY = "relay_base"
        const val KEY_LABEL = "label"
        const val KEY_MINT_TOKEN = "mint_token"
        const val KEY_MINT_RELAY = "mint_relay"
        const val KEY_MINT_LAN = "mint_lan"
        const val KEY_MINT_EXPIRES = "mint_expires_ms"
    }
}
