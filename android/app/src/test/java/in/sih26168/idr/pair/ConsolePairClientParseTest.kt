package `in`.sih26168.idr.pair

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class ConsolePairClientParseTest {
    @Test
    fun parsesFullPairUrl() {
        val raw =
            "http://192.168.1.10:8787/pair?s=AbCdEfGhIjKlMnOp&lan=http%3A%2F%2F192.168.1.10%3A8787&relay=https%3A%2F%2Frelay.example%2F"
        val p = ConsolePairClient.parse(raw)
        assertNotNull(p)
        assertEquals("AbCdEfGhIjKlMnOp", p!!.token)
        assertEquals("http://192.168.1.10:8787", p.lanBase)
        assertEquals("https://relay.example", p.relayBase)
    }

    @Test
    fun parsesBareTokenWithFallbackBase() {
        val p = ConsolePairClient.parseWithFallbackBase(
            "AbCdEfGhIjKlMnOpQr",
            "http://192.168.137.1:8787/",
        )
        assertNotNull(p)
        assertEquals("AbCdEfGhIjKlMnOpQr", p!!.token)
        assertEquals("http://192.168.137.1:8787", p.lanBase)
    }

    @Test
    fun parsesCoastSchemeDeepLink() {
        val raw =
            "coast://pair?s=AbCdEfGhIjKlMnOp&lan=http%3A%2F%2F192.168.137.1%3A8787"
        val p = ConsolePairClient.parse(raw)
        assertNotNull(p)
        assertEquals("AbCdEfGhIjKlMnOp", p!!.token)
        assertEquals("http://192.168.137.1:8787", p.lanBase)
        assertNull(p.relayBase)
    }

    @Test
    fun parsesQuotedMultilinePaste() {
        val raw = "\"\nhttp://10.0.0.4:8787/pair?s=AbCdEfGhIjKlMnOp&lan=http%3A%2F%2F10.0.0.4%3A8787\n\""
        val p = ConsolePairClient.parse(raw)
        assertNotNull(p)
        assertEquals("AbCdEfGhIjKlMnOp", p!!.token)
        assertEquals("http://10.0.0.4:8787", p.lanBase)
    }

    @Test
    fun rejectsBareTokenWithoutBase() {
        assertNotNull(ConsolePairClient.parse("AbCdEfGhIjKlMnOp"))
        assertNull(ConsolePairClient.parseWithFallbackBase("AbCdEfGhIjKlMnOp", null))
    }

    @Test
    fun parsesPhoneMintedRelayOnlyUrl() {
        val raw =
            "https://coast.paper2anything.com/pair?s=AbCdEfGhIj&relay=https%3A%2F%2Fcoast.paper2anything.com"
        val p = ConsolePairClient.parse(raw)
        assertNotNull(p)
        assertEquals("AbCdEfGhIj", p!!.token)
        assertEquals("https://coast.paper2anything.com", p.relayBase)
        assertNull("phone-initiated QR must not treat the relay origin as LAN", p.lanBase)
        assertTrue(p.hasEndpoint())
    }

    @Test
    fun parsesPhoneMintedUrlWithOptionalLan() {
        val raw =
            "https://coast.paper2anything.com/pair?s=Ab-Cd_EfGh&relay=https%3A%2F%2Fcoast.paper2anything.com&lan=http%3A%2F%2F192.168.137.1%3A8787"
        val p = ConsolePairClient.parse(raw)
        assertNotNull(p)
        assertEquals("Ab-Cd_EfGh", p!!.token)
        assertEquals("https://coast.paper2anything.com", p.relayBase)
        assertEquals("http://192.168.137.1:8787", p.lanBase)
    }

    @Test
    fun parsesPhoneMintedCoastScheme() {
        val raw =
            "coast://pair?s=AbCdEfGh&relay=https%3A%2F%2Fcoast.paper2anything.com"
        val p = ConsolePairClient.parse(raw)
        assertNotNull(p)
        assertEquals("AbCdEfGh", p!!.token)
        assertEquals("https://coast.paper2anything.com", p.relayBase)
        assertNull(p.lanBase)
    }

    @Test
    fun parsesEightAndTwelveCharPhoneTokens() {
        val eight = ConsolePairClient.parse(
            "https://relay.example/pair?s=AbCdEfGh&relay=https%3A%2F%2Frelay.example",
        )
        assertNotNull(eight)
        assertEquals("AbCdEfGh", eight!!.token)
        assertEquals(8, eight.token.length)
        assertNull(eight.lanBase)

        val twelve = ConsolePairClient.parse(
            "https://relay.example/pair?s=AbCdEfGhIjKl&relay=https%3A%2F%2Frelay.example",
        )
        assertNotNull(twelve)
        assertEquals("AbCdEfGhIjKl", twelve!!.token)
        assertEquals(12, twelve.token.length)
        assertNull(twelve.lanBase)
    }

    @Test
    fun consoleOriginStillInfersLanWhenRelayDiffers() {
        val raw =
            "http://192.168.1.10:8787/pair?s=AbCdEfGhIjKlMnOp&relay=https%3A%2F%2Frelay.example"
        val p = ConsolePairClient.parse(raw)
        assertNotNull(p)
        assertEquals("http://192.168.1.10:8787", p!!.lanBase)
        assertEquals("https://relay.example", p.relayBase)
    }

    @Test
    fun pairPayloadRoundTripRelayOnly() {
        val token = ConsolePairClient.mintToken()
        val url = ConsolePairClient.pairPayload(token, "https://coast.paper2anything.com/")
        val p = ConsolePairClient.parse(url)
        assertNotNull(p)
        assertEquals(token, p!!.token)
        assertEquals("https://coast.paper2anything.com", p.relayBase)
        assertNull(p.lanBase)
    }

    @Test
    fun pairPayloadRoundTripWithLan() {
        val token = ConsolePairClient.mintToken(8)
        val url = ConsolePairClient.pairPayload(
            token,
            "https://relay.example/pair",
            "http://192.168.137.1:8787/",
        )
        val p = ConsolePairClient.parse(url)
        assertNotNull(p)
        assertEquals(token, p!!.token)
        assertEquals("https://relay.example", p.relayBase)
        assertEquals("http://192.168.137.1:8787", p.lanBase)
    }

    @Test
    fun mintTokenIsUrlSafeAndShortLivedLength() {
        val seen = HashSet<String>()
        repeat(40) {
            val t = ConsolePairClient.mintToken()
            assertTrue(ConsolePairClient.isPairToken(t))
            assertTrue(t.length in 8..12)
            assertTrue(t.all { it.isLetterOrDigit() || it == '-' || it == '_' })
            seen.add(t)
        }
        assertEquals(40, seen.size)
        assertEquals(8, ConsolePairClient.mintToken(3).length)
        assertEquals(12, ConsolePairClient.mintToken(99).length)
    }

    @Test
    fun rejectsSevenCharTokenInPhoneUrl() {
        assertNull(
            ConsolePairClient.parse(
                "https://relay.example/pair?s=AbCdEfG&relay=https%3A%2F%2Frelay.example",
            ),
        )
    }
}
