package net.themark.grapheneosmdm.policy

import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import android.util.Log
import net.themark.grapheneosmdm.protocol.AttestationInfo
import java.security.KeyPairGenerator
import java.security.KeyStore
import java.security.cert.X509Certificate

/**
 * Android Keystore key attestation. [previousChallengeB64] is the nonce already
 * baked into the key. A new nonce replaces the key. No nonce reports `format=none`.
 */
internal class KeyAttestor {
    fun attest(challengeB64: String?, previousChallengeB64: String?): AttestationInfo {
        if (challengeB64.isNullOrBlank()) return AttestationInfo(format = "none")
        val challenge = try {
            Base64.decode(challengeB64, Base64.DEFAULT)
        } catch (_: IllegalArgumentException) {
            return AttestationInfo(format = "none")
        }
        if (challenge.isEmpty() || challenge.size > MAX_CHALLENGE) {
            return AttestationInfo(format = "none")
        }
        return try {
            val chain = certificateChain(challenge, reuse = challengeB64 == previousChallengeB64)
            val leaf = chain.first() as X509Certificate
            val encoded = chain.fold(ByteArray(0)) { acc, cert -> acc + cert.encoded }
            val boot = leaf.getExtensionValue(KEY_ATTESTATION_OID)?.let {
                verifiedBootStateFromAttestation(it)
            }
            AttestationInfo(
                format = "keymint",
                payloadB64 = Base64.encodeToString(encoded, Base64.NO_WRAP),
                verifiedBootState = boot,
            )
        } catch (e: Exception) {
            Log.w(TAG, "key attestation failed", e)
            AttestationInfo(format = "none")
        }
    }

    private fun certificateChain(
        challenge: ByteArray,
        reuse: Boolean,
    ): Array<java.security.cert.Certificate> {
        val ks = KeyStore.getInstance(ANDROID_KEYSTORE).apply { load(null) }
        if (reuse) {
            ks.getCertificateChain(ALIAS)?.let { return it }
        } else if (ks.containsAlias(ALIAS)) {
            ks.deleteEntry(ALIAS)
        }
        val generator = KeyPairGenerator.getInstance(KeyProperties.KEY_ALGORITHM_EC, ANDROID_KEYSTORE)
        generator.initialize(
            KeyGenParameterSpec.Builder(ALIAS, KeyProperties.PURPOSE_SIGN)
                .setDigests(KeyProperties.DIGEST_SHA256)
                .setAttestationChallenge(challenge)
                .build(),
        )
        generator.generateKeyPair()
        return ks.getCertificateChain(ALIAS) ?: error("attestation chain missing")
    }

    companion object {
        private const val TAG = "KeyAttestor"
        private const val ANDROID_KEYSTORE = "AndroidKeyStore"
        private const val ALIAS = "grapheneos_mdm_attest"
        private const val MAX_CHALLENGE = 128
    }
}
