package net.themark.grapheneosmdm.policy

/** Key attestation extension OID (KeyDescription). */
internal const val KEY_ATTESTATION_OID = "1.3.6.1.4.1.11129.2.1.17"

private const val UNIVERSAL = 0
private const val CONTEXT = 2
private const val ROOT_OF_TRUST_TAG = 704

internal fun bootStateName(code: Int): String? = when (code) {
    0 -> "Verified"
    1 -> "SelfSigned"
    2 -> "Unverified"
    3 -> "Failed"
    else -> null
}

/**
 * Read verifiedBootState from a KeyDescription DER value, or from the OCTET
 * STRING wrapper Java returns from [java.security.cert.X509Extension.getExtensionValue].
 * Returns null when the root-of-trust field is absent.
 */
internal fun verifiedBootStateFromAttestation(der: ByteArray): String? {
    val body = unwrapOctetString(der) ?: der
    return findBootState(body, 0, body.size)
}

private fun unwrapOctetString(der: ByteArray): ByteArray? {
    val tag = readTag(der, 0) ?: return null
    if (tag.klass != UNIVERSAL || tag.number != 4 || tag.constructed) return null
    val (len, lenLen) = readLen(der, tag.header) ?: return null
    val start = tag.header + lenLen
    val end = start + len
    if (end != der.size) return null
    return der.copyOfRange(start, end)
}

private fun findBootState(bytes: ByteArray, start: Int, end: Int): String? {
    var i = start
    while (i < end) {
        val tag = readTag(bytes, i) ?: return null
        val (len, lenLen) = readLen(bytes, i + tag.header) ?: return null
        val content = i + tag.header + lenLen
        val next = content + len
        if (next > end) return null
        if (tag.klass == CONTEXT && tag.number == ROOT_OF_TRUST_TAG) {
            bootFromRoot(bytes, content, next)?.let { return it }
        } else if (tag.constructed) {
            findBootState(bytes, content, next)?.let { return it }
        }
        i = next
    }
    return null
}

private fun bootFromRoot(bytes: ByteArray, start: Int, end: Int): String? {
    val tag = readTag(bytes, start) ?: return null
    val (len, lenLen) = readLen(bytes, start + tag.header) ?: return null
    val content = start + tag.header + lenLen
    val next = content + len
    if (next > end) return null
    if (tag.klass == UNIVERSAL && tag.number == 16) {
        return readBootInteger(bytes, content, next)
    }
    return readBootInteger(bytes, start, end)
}

/** RootOfTrust is verifiedBootKey, deviceLocked, then verifiedBootState. */
private fun readBootInteger(bytes: ByteArray, start: Int, end: Int): String? {
    var i = start
    repeat(2) {
        i = skipTlv(bytes, i, end) ?: return null
    }
    val value = readSmallInteger(bytes, i, end) ?: return null
    return bootStateName(value)
}

private fun readSmallInteger(bytes: ByteArray, start: Int, end: Int): Int? {
    val tag = readTag(bytes, start) ?: return null
    if (tag.klass != UNIVERSAL || tag.number != 2) return null
    val (len, lenLen) = readLen(bytes, start + tag.header) ?: return null
    val content = start + tag.header + lenLen
    if (len <= 0 || content + len > end || len > 4) return null
    var value = 0
    for (k in 0 until len) {
        value = (value shl 8) or (bytes[content + k].toInt() and 0xff)
    }
    return value
}

private fun skipTlv(bytes: ByteArray, start: Int, end: Int): Int? {
    val tag = readTag(bytes, start) ?: return null
    val (len, lenLen) = readLen(bytes, start + tag.header) ?: return null
    val next = start + tag.header + lenLen + len
    if (next > end) return null
    return next
}

private data class DerTag(val klass: Int, val constructed: Boolean, val number: Int, val header: Int)

private fun readTag(bytes: ByteArray, i: Int): DerTag? {
    if (i >= bytes.size) return null
    val first = bytes[i].toInt() and 0xff
    val klass = first shr 6
    val constructed = first and 0x20 != 0
    var number = first and 0x1f
    var header = 1
    if (number == 0x1f) {
        number = 0
        while (true) {
            if (i + header >= bytes.size || header > 4) return null
            val next = bytes[i + header].toInt() and 0xff
            header++
            number = (number shl 7) or (next and 0x7f)
            if (next and 0x80 == 0) break
        }
    }
    return DerTag(klass, constructed, number, header)
}

private fun readLen(bytes: ByteArray, i: Int): Pair<Int, Int>? {
    if (i >= bytes.size) return null
    val first = bytes[i].toInt() and 0xff
    if (first and 0x80 == 0) return first to 1
    val count = first and 0x7f
    if (count == 0 || count > 3 || i + count >= bytes.size) return null
    var len = 0
    for (k in 1..count) {
        len = (len shl 8) or (bytes[i + k].toInt() and 0xff)
    }
    return len to (1 + count)
}
