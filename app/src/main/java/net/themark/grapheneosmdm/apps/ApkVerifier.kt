package net.themark.grapheneosmdm.apps

import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import android.util.Log
import java.io.File
import java.io.FileInputStream
import java.security.MessageDigest
import java.security.cert.CertificateFactory
import java.security.cert.X509Certificate

/**
 * Verify APK integrity before PackageInstaller commit (issue #4).
 * Hash is mandatory when the catalog/check-in supplies [expectedSha256].
 */
object ApkVerifier {
    private const val TAG = "ApkVerifier"

    fun sha256Hex(file: File): String {
        val digest = MessageDigest.getInstance("SHA-256")
        FileInputStream(file).use { input ->
            val buf = ByteArray(64 * 1024)
            while (true) {
                val n = input.read(buf)
                if (n <= 0) break
                digest.update(buf, 0, n)
            }
        }
        return digest.digest().joinToString("") { b -> "%02x".format(b) }
    }

    fun verifySha256(file: File, expectedSha256: String): Boolean {
        val expected = expectedSha256.trim().lowercase()
        if (!expected.matches(Regex("^[a-f0-9]{64}$"))) {
            Log.e(TAG, "Invalid expected sha256 format")
            return false
        }
        val actual = sha256Hex(file)
        val ok = actual == expected
        if (!ok) {
            Log.e(TAG, "SHA-256 mismatch expected=$expected actual=$actual")
        }
        return ok
    }

    /**
     * Compare the APK's signing certificate SHA-256 (DER) to [expectedCertSha256].
     * Uses archive PackageInfo; fails closed on parse errors.
     */
    fun verifySigningCertSha256(
        context: Context,
        apkFile: File,
        expectedCertSha256: String,
    ): Boolean {
        val expected = expectedCertSha256.trim().lowercase()
        if (!expected.matches(Regex("^[a-f0-9]{64}$"))) {
            Log.e(TAG, "Invalid expected signingCertSha256 format")
            return false
        }
        val flags = if (Build.VERSION.SDK_INT >= 28) {
            PackageManager.GET_SIGNING_CERTIFICATES
        } else {
            @Suppress("DEPRECATION")
            PackageManager.GET_SIGNATURES
        }
        val info = context.packageManager.getPackageArchiveInfo(apkFile.absolutePath, flags)
            ?: run {
                Log.e(TAG, "Unable to parse package archive ${apkFile.name}")
                return false
            }
        val digests = signingCertDigests(info)
        if (digests.isEmpty()) {
            Log.e(TAG, "No signing certs found in ${apkFile.name}")
            return false
        }
        val ok = digests.any { it == expected }
        if (!ok) {
            Log.e(TAG, "Signing cert mismatch expected=$expected actual=$digests")
        }
        return ok
    }

    private fun signingCertDigests(info: android.content.pm.PackageInfo): List<String> {
        val digest = MessageDigest.getInstance("SHA-256")
        if (Build.VERSION.SDK_INT >= 28) {
            val signingInfo = info.signingInfo ?: return emptyList()
            val signers = if (signingInfo.hasMultipleSigners()) {
                signingInfo.apkContentsSigners
            } else {
                signingInfo.signingCertificateHistory
            }
            return signers.map { sig ->
                digest.reset()
                digest.digest(sig.toByteArray()).joinToString("") { b -> "%02x".format(b) }
            }
        }
        @Suppress("DEPRECATION")
        val sigs = info.signatures ?: return emptyList()
        return sigs.map { sig ->
            digest.reset()
            digest.digest(sig.toByteArray()).joinToString("") { b -> "%02x".format(b) }
        }
    }

    /** Optional helper for operators hashing a leaf cert PEM/DER offline. */
    fun sha256OfX509Der(der: ByteArray): String {
        val cf = CertificateFactory.getInstance("X.509")
        val cert = cf.generateCertificate(der.inputStream()) as X509Certificate
        return MessageDigest.getInstance("SHA-256")
            .digest(cert.encoded)
            .joinToString("") { b -> "%02x".format(b) }
    }
}
