package `in`.sih26168.idr.ui

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class SignalHistoryTest {
    @Test
    fun eventRoundTripJsonPreservesCoords() {
        val e = SignalHistory.Event(
            kind = SignalHistory.KIND_GNSS_LOST,
            atMs = 1_700_000_000_000L,
            lat = 52.4068,
            lon = -1.5197,
            nSats = 8,
            note = "GNSS handover",
        )
        val back = SignalHistory.Event.fromJson(e.toJson())
        assertEquals(e.kind, back.kind)
        assertEquals(e.atMs, back.atMs)
        assertEquals(e.lat!!, back.lat!!, 1e-9)
        assertEquals(e.lon!!, back.lon!!, 1e-9)
        assertEquals(e.nSats, back.nSats)
        assertEquals(e.note, back.note)
    }

    @Test
    fun missingOptionalFieldsStayNull() {
        val o = JSONObject()
            .put("kind", SignalHistory.KIND_SESSION_START)
            .put("atMs", 42L)
        val e = SignalHistory.Event.fromJson(o)
        assertNull(e.lat)
        assertNull(e.lon)
        assertNull(e.nSats)
        assertNull(e.note)
    }
}
