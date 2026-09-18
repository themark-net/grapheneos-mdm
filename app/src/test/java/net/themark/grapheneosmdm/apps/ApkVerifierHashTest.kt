package net.themark.grapheneosmdm.apps

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File
import java.nio.file.Files

class ApkVerifierHashTest {

    @Test
    fun sha256MatchesKnownVector() {
        val dir = Files.createTempDirectory("apk-verify").toFile()
        val f = File(dir, "x.apk")
        f.writeBytes("lab-placeholder-apk\n".toByteArray())
        val hex = ApkVerifier.sha256Hex(f)
        assertEquals("c4b21224817aab1213dcdb25a690682422dcacf438bbab13fba7897aa3bdcc4b", hex)
        assertTrue(ApkVerifier.verifySha256(f, hex))
        assertFalse(ApkVerifier.verifySha256(f, "0".repeat(64)))
        dir.deleteRecursively()
    }
}
