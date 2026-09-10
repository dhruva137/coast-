package `in`.sih26168.idr.pair

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Test

class ConsolePairClientTest {

    @Test
    fun `parses console pair_payload URL`() {
        val raw =
            "http://192.168.137.1:8787/pair?s=AbCdEfGhIjKlMnOp&lan=http%3A%2F%2F192.168.137.1%3A8787&relay=http%3A%2F%2Frelay.example%3A8787"
        val cfg = ConsolePairClient.parse(raw)
        assertNotNull(cfg)
        assertEquals("AbCdEfGhIjKlMnOp", cfg!!.token)
        assertEquals("http://192.168.137.1:8787", cfg.lanBase)
        assertEquals("http://relay.example:8787", cfg.relayBase)
    }

    @Test
    fun `bare token needs fallback base`() {
        assertNull(ConsolePairClient.parseWithFallbackBase("AbCdEfGhIjKlMnOp", null))
        val cfg = ConsolePairClient.parseWithFallbackBase(
            "AbCdEfGhIjKlMnOp",
            "http://192.168.1.10:8787",
        )
        assertNotNull(cfg)
        assertEquals("http://192.168.1.10:8787", cfg!!.lanBase)
        assertNull(cfg.relayBase)
    }

    @Test
    fun `rejects short tokens`() {
        assertNull(ConsolePairClient.parse("short"))
        assertNull(ConsolePairClient.parse("../etc/passwd"))
    }

    @Test
    fun `parses phone-minted relay plus nonce`() {
        val raw =
            "https://coast.paper2anything.com/pair?s=Ph0neMint_1&relay=https%3A%2F%2Fcoast.paper2anything.com"
        val cfg = ConsolePairClient.parse(raw)
        assertNotNull(cfg)
        assertEquals("Ph0neMint_1", cfg!!.token)
        assertEquals("https://coast.paper2anything.com", cfg.relayBase)
        assertNull(cfg.lanBase)
    }
}
