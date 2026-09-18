package net.themark.grapheneosmdm.security

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey

/**
 * Secure storage for server base URL and short-lived tokens (issue #3).
 *
 * Uses EncryptedSharedPreferences (AES256-GCM) backed by Android Keystore.
 * Falls back to MODE_PRIVATE prefs only when crypto library init fails
 * (instrumented/unit test environments without Keystore); production devices
 * should always hit the encrypted path.
 */
class SecureConfigStore(
    private val prefs: SharedPreferences,
) {
    var serverBaseUrl: String?
        get() = prefs.getString(KEY_BASE_URL, null)?.takeIf { it.isNotBlank() }
        set(value) {
            prefs.edit().putString(KEY_BASE_URL, value).apply()
        }

    var shortLivedToken: String?
        get() = prefs.getString(KEY_TOKEN, null)?.takeIf { it.isNotBlank() }
        set(value) {
            prefs.edit().putString(KEY_TOKEN, value).apply()
        }

    var tokenExpiresAtEpochMs: Long
        get() = prefs.getLong(KEY_TOKEN_EXPIRES, 0L)
        set(value) {
            prefs.edit().putLong(KEY_TOKEN_EXPIRES, value).apply()
        }

    fun clearToken() {
        prefs.edit()
            .remove(KEY_TOKEN)
            .remove(KEY_TOKEN_EXPIRES)
            .apply()
    }

    fun hasUsableToken(nowEpochMs: Long = System.currentTimeMillis()): Boolean {
        val token = shortLivedToken ?: return false
        if (token.isBlank()) return false
        val exp = tokenExpiresAtEpochMs
        return exp <= 0L || nowEpochMs < exp
    }

    companion object {
        private const val PREFS_NAME = "mdm_secure_config"
        private const val KEY_BASE_URL = "server_base_url"
        private const val KEY_TOKEN = "short_lived_token"
        private const val KEY_TOKEN_EXPIRES = "short_lived_token_expires_ms"

        fun create(context: Context): SecureConfigStore {
            val prefs = try {
                val masterKey = MasterKey.Builder(context)
                    .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
                    .build()
                EncryptedSharedPreferences.create(
                    context,
                    PREFS_NAME,
                    masterKey,
                    EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
                    EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
                )
            } catch (e: Exception) {
                // Unit tests / broken Keystore: still avoid world-readable storage.
                context.getSharedPreferences(PREFS_NAME + "_fallback", Context.MODE_PRIVATE)
            }
            return SecureConfigStore(prefs)
        }

        /** Test / DI helper. */
        fun wrap(prefs: SharedPreferences): SecureConfigStore = SecureConfigStore(prefs)
    }
}
