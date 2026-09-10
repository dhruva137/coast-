package `in`.sih26168.idr.pair

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.io.File

/**
 * On-device ring of pairing frames. Written while the radio is dead (tunnel,
 * AP isolation, airplane mode) and flushed when [ConsolePairClient] can reach
 * the console again. Not a cloud sync — the file lives in cacheDir and is
 * wiped on Unpair.
 */
class PairingQueue(context: Context) {
    private val file = File(context.applicationContext.cacheDir, "pair_queue.jsonl")
    private val lock = Any()

    fun enqueue(obj: JSONObject) {
        synchronized(lock) {
            val lines = readLines() + obj.toString()
            writeLines(lines.takeLast(MAX))
        }
    }

    fun drain(max: Int): JSONArray {
        synchronized(lock) {
            val lines = readLines()
            val take = lines.take(max.coerceAtLeast(0))
            writeLines(lines.drop(take.size))
            val arr = JSONArray()
            take.forEach { line ->
                runCatching { arr.put(JSONObject(line)) }
            }
            return arr
        }
    }

    fun requeueFront(arr: JSONArray) {
        synchronized(lock) {
            val extra = ArrayList<String>(arr.length())
            for (i in 0 until arr.length()) {
                extra.add(arr.getJSONObject(i).toString())
            }
            writeLines(extra + readLines())
        }
    }

    fun size(): Int = synchronized(lock) { readLines().size }

    fun clear() {
        synchronized(lock) { if (file.exists()) file.delete() }
    }

    private fun readLines(): List<String> {
        if (!file.exists()) return emptyList()
        return file.readLines().filter { it.isNotBlank() }
    }

    private fun writeLines(lines: List<String>) {
        val keep = lines.takeLast(MAX)
        if (keep.isEmpty()) {
            if (file.exists()) file.delete()
            return
        }
        file.writeText(keep.joinToString("\n") + "\n")
    }

    companion object {
        const val MAX = 800
    }
}
