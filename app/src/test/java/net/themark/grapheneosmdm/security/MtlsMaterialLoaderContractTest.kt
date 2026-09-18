package net.themark.grapheneosmdm.security

import org.junit.Assert.assertNull
import org.junit.Assert.assertSame
import org.junit.Test
import javax.net.ssl.KeyManager
import javax.net.ssl.X509TrustManager

/**
 * Interface + fake coverage when instrumented Keystore tests are unavailable.
 */
class MtlsMaterialLoaderContractTest {

    @Test
    fun fakeLoaderReturnsNull() {
        val loader = MtlsMaterialLoader { null }
        assertNull(loader.load())
    }

    @Test
    fun fakeLoaderReturnsMaterial() {
        val trust = object : X509TrustManager {
            override fun checkClientTrusted(chain: Array<java.security.cert.X509Certificate>?, authType: String?) = Unit
            override fun checkServerTrusted(chain: Array<java.security.cert.X509Certificate>?, authType: String?) = Unit
            override fun getAcceptedIssuers(): Array<java.security.cert.X509Certificate> = emptyArray()
        }
        val material = MtlsMaterial(emptyArray<KeyManager>(), trust, "fake")
        val loader = MtlsMaterialLoader { material }
        assertSame(material, loader.load())
    }
}
