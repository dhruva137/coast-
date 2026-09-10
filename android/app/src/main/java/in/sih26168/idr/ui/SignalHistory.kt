package `in`.sih26168.idr.ui

import android.content.Context
import android.content.SharedPreferences
import androidx.core.content.edit
import org.json.JSONArray
import org.json.JSONObject

/**
 * Persisted event log of GNSS loss / regain transitions.
 *
 * A judge asks "what happened when you lost signal?" — this is the answer.
 * Events carry the timestamp, the transition kind, and, if the estimator had
 * an absolute fix, the coordinates it held at that moment. Persisted in
 * SharedPreferences so the log survives an app restart.
 *
 * Intentionally simple: bounded ring buffer, JSONObject serialisation, no
 * Room DB. Any dependency-free Android target can read this.
 */
object SignalHistory {

    private const val PREF_FILE = "coast_signal_history"
    private const val KEY_EVENTS = "events_json"
    private const val MAX_EVENTS = 200

    /** Kind values are lowercase constants so they survive obfuscation. */
    const val KIND_GNSS_LOST = "gnss_lost"
    const val KIND_GNSS_REACQUIRED = "gnss_reacquired"
    const val KIND_SESSION_START = "session_start"
    const val KIND_SESSION_END = "session_end"

    data class Event(
        val kind: String,
        val atMs: Long,
        val lat: Double? = null,
        val lon: Double? = null,
        val nSats: Int? = null,
        val note: String? = null,
    ) {
        fun toJson(): JSONObject {
            val o = JSONObject()
            o.put("kind", kind)
            o.put("atMs", atMs)
            if (lat != null && lat.isFinite()) o.put("lat", lat)
            if (lon != null && lon.isFinite()) o.put("lon", lon)
            if (nSats != null) o.put("nSats", nSats)
            if (note != null) o.put("note", note)
            return o
        }

        companion object {
            fun fromJson(o: JSONObject): Event = Event(
                kind = o.optString("kind", "unknown"),
                atMs = o.optLong("atMs", 0L),
                lat = if (o.has("lat")) o.optDouble("lat") else null,
                lon = if (o.has("lon")) o.optDouble("lon") else null,
                nSats = if (o.has("nSats")) o.optInt("nSats") else null,
                note = if (o.has("note")) o.optString("note") else null,
            )
        }
    }

    private fun prefs(ctx: Context): SharedPreferences =
        ctx.getSharedPreferences(PREF_FILE, Context.MODE_PRIVATE)

    fun read(ctx: Context): List<Event> {
        val raw = prefs(ctx).getString(KEY_EVENTS, null) ?: return emptyList()
        return try {
            val arr = JSONArray(raw)
            val out = ArrayList<Event>(arr.length())
            for (i in 0 until arr.length()) {
                val obj = arr.optJSONObject(i) ?: continue
                out.add(Event.fromJson(obj))
            }
            out
        } catch (_: Throwable) {
            emptyList()
        }
    }

    fun append(ctx: Context, event: Event) {
        val current = read(ctx).toMutableList()
        current.add(0, event) // newest first
        while (current.size > MAX_EVENTS) current.removeAt(current.size - 1)
        val arr = JSONArray()
        current.forEach { arr.put(it.toJson()) }
        prefs(ctx).edit { putString(KEY_EVENTS, arr.toString()) }
    }

    fun clear(ctx: Context) {
        prefs(ctx).edit { remove(KEY_EVENTS) }
    }
}
