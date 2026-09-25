package net.themark.grapheneosmdm.policy

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class AttestationExtTest {

    @Test
    fun readsVerifiedBootStateFromRootOfTrust() {
        val root = seq(
            tlv(0x04, byteArrayOf(0x11)),
            tlv(0x01, byteArrayOf(0xff.toByte())),
            tlv(0x02, byteArrayOf(0)),
        )
        val description = seq(tlv(0x02, byteArrayOf(4)), context(704, root))
        assertEquals("Verified", verifiedBootStateFromAttestation(description))
        assertEquals("Failed", verifiedBootStateFromAttestation(seq(context(704, seq(
            tlv(0x04, byteArrayOf(0x01)),
            tlv(0x01, byteArrayOf(0x00)),
            tlv(0x02, byteArrayOf(3)),
        )))))
    }

    @Test
    fun unwrapsJavaOctetStringAndIgnoresMissingRoot() {
        val inner = seq(tlv(0x02, byteArrayOf(1)))
        val wrapped = tlv(0x04, inner)
        assertNull(verifiedBootStateFromAttestation(wrapped))
        assertNull(verifiedBootStateFromAttestation(byteArrayOf()))
    }

    private fun seq(vararg parts: ByteArray) = tlv(0x30, parts.concat())

    private fun context(number: Int, content: ByteArray): ByteArray {
        val tag = byteArrayOf(0xbf.toByte(), 0x85.toByte(), 0x40)
        check(number == 704)
        return tag + length(content.size) + content
    }

    private fun tlv(tag: Int, content: ByteArray) =
        byteArrayOf(tag.toByte()) + length(content.size) + content

    private fun length(n: Int) = byteArrayOf(n.toByte())

    private fun Array<out ByteArray>.concat(): ByteArray = fold(ByteArray(0)) { a, b -> a + b }
}
