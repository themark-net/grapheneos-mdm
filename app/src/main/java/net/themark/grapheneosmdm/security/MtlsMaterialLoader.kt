package net.themark.grapheneosmdm.security

import android.content.Context
import android.util.Log
import java.io.ByteArrayInputStream
import java.io.File
import java.security.KeyStore
import java.security.cert.CertificateFactory
import java.security.cert.X509Certificate
import javax.net.ssl.KeyManagerFactory
import javax.net.ssl.TrustManagerFactory
import javax.net.ssl.X509TrustManager

/**
 * Loads client certificate + private key + CA for OkHttp mutual TLS.
 *
 * Preference order (issue #3 / ADR path):
 * 1. Android Keystore PKCS#12 entry under [KEYSTORE_ALIAS] (imported at enroll).
 * 2. App-private directory [PROTECTED_DIR] with `client.p12` + `ca.pem`
 *    (MODE_PRIVATE files; never world-readable; excluded from backup via
 *    [android:allowBackup=false] on the application).
 *
 * Aligns with lab step-ca issuance: device client certs minted by the fleet CA
 * (see docs/MTLS.md and themark-net/workstation-environment lab_ca).
 */
fun interface MtlsMaterialLoader {
    fun load(): MtlsMaterial?
}

data class MtlsMaterial(
    val keyManagers: Array<javax.net.ssl.KeyManager>,
    val trustManager: X509TrustManager,
    val source: String,
)

class DefaultMtlsMaterialLoader(
    private val context: Context,
    private val keystorePassword: CharArray = CharArray(0),
) : MtlsMaterialLoader {

    override fun load(): MtlsMaterial? {
        loadFromAndroidKeystore()?.let { return it }
        loadFromProtectedFiles()?.let { return it }
        Log.w(TAG, "No mTLS material found (Keystore alias or ${PROTECTED_DIR}/)")
        return null
    }

    private fun loadFromAndroidKeystore(): MtlsMaterial? {
        return try {
            val ks = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
            if (!ks.containsAlias(KEYSTORE_ALIAS)) return null
            // AndroidKeyStore entries are typically PrivateKeyEntry with cert chain.
            val kmf = KeyManagerFactory.getInstance(KeyManagerFactory.getDefaultAlgorithm())
            kmf.init(ks, null)

            val caPem = readProtectedFile("ca.pem")
            val trust = if (caPem != null) {
                trustManagerFromPem(caPem)
            } else {
                // Fall back to system trust if CA file absent (not ideal for lab).
                systemTrustManager()
            }
            MtlsMaterial(kmf.keyManagers, trust, "android-keystore:$KEYSTORE_ALIAS")
        } catch (e: Exception) {
            Log.w(TAG, "AndroidKeyStore load failed: ${e.message}")
            null
        }
    }

    private fun loadFromProtectedFiles(): MtlsMaterial? {
        val p12 = readProtectedFile("client.p12") ?: return null
        val caPem = readProtectedFile("ca.pem") ?: return null
        return try {
            val ks = KeyStore.getInstance("PKCS12").apply {
                load(ByteArrayInputStream(p12), keystorePassword)
            }
            val kmf = KeyManagerFactory.getInstance(KeyManagerFactory.getDefaultAlgorithm())
            kmf.init(ks, keystorePassword)
            MtlsMaterial(kmf.keyManagers, trustManagerFromPem(caPem), "protected-files")
        } catch (e: Exception) {
            Log.e(TAG, "Protected PKCS12 load failed", e)
            null
        }
    }

    private fun protectedDir(): File =
        context.getDir(PROTECTED_DIR, Context.MODE_PRIVATE)

    private fun readProtectedFile(name: String): ByteArray? {
        val f = File(protectedDir(), name)
        if (!f.isFile) return null
        return f.readBytes()
    }

    companion object {
        private const val TAG = "MtlsMaterialLoader"
        const val KEYSTORE_ALIAS = "grapheneos_mdm_client"
        const val PROTECTED_DIR = "mtls"

        fun trustManagerFromPem(pemBytes: ByteArray): X509TrustManager {
            val cf = CertificateFactory.getInstance("X.509")
            val certs = mutableListOf<X509Certificate>()
            ByteArrayInputStream(pemBytes).use { stream ->
                while (stream.available() > 0) {
                    val c = cf.generateCertificate(stream) as? X509Certificate ?: break
                    certs.add(c)
                }
            }
            require(certs.isNotEmpty()) { "CA PEM contained no certificates" }
            val ts = KeyStore.getInstance(KeyStore.getDefaultType()).apply {
                load(null, null)
                certs.forEachIndexed { i, c -> setCertificateEntry("ca-$i", c) }
            }
            val tmf = TrustManagerFactory.getInstance(TrustManagerFactory.getDefaultAlgorithm())
            tmf.init(ts)
            return tmf.trustManagers.filterIsInstance<X509TrustManager>().first()
        }

        fun systemTrustManager(): X509TrustManager {
            val tmf = TrustManagerFactory.getInstance(TrustManagerFactory.getDefaultAlgorithm())
            tmf.init(null as KeyStore?)
            return tmf.trustManagers.filterIsInstance<X509TrustManager>().first()
        }
    }
}
