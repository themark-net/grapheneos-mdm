package net.themark.grapheneosmdm.security

import android.content.SharedPreferences
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.util.concurrent.ConcurrentHashMap

/**
 * JVM unit test with an in-memory SharedPreferences fake (no Android Keystore).
 */
class SecureConfigStoreTest {

    @Test
    fun storesBaseUrlAndToken() {
        val store = SecureConfigStore.wrap(MemoryPrefs())
        store.serverBaseUrl = "https://mdm.lab:8443"
        store.shortLivedToken = "tok-1"
        store.tokenExpiresAtEpochMs = System.currentTimeMillis() + 60_000
        assertEquals("https://mdm.lab:8443", store.serverBaseUrl)
        assertTrue(store.hasUsableToken())
        store.clearToken()
        assertFalse(store.hasUsableToken())
    }

    @Test
    fun expiredTokenNotUsable() {
        val store = SecureConfigStore.wrap(MemoryPrefs())
        store.shortLivedToken = "tok"
        store.tokenExpiresAtEpochMs = 1L
        assertFalse(store.hasUsableToken(nowEpochMs = 100L))
    }

    private class MemoryPrefs : SharedPreferences {
        private val map = ConcurrentHashMap<String, Any?>()
        override fun getAll(): MutableMap<String, *> = map
        override fun getString(key: String?, defValue: String?): String? =
            map[key] as String? ?: defValue
        override fun getStringSet(key: String?, defValues: MutableSet<String>?): MutableSet<String>? =
            @Suppress("UNCHECKED_CAST") (map[key] as MutableSet<String>? ?: defValues)
        override fun getInt(key: String?, defValue: Int): Int = map[key] as Int? ?: defValue
        override fun getLong(key: String?, defValue: Long): Long = map[key] as Long? ?: defValue
        override fun getFloat(key: String?, defValue: Float): Float = map[key] as Float? ?: defValue
        override fun getBoolean(key: String?, defValue: Boolean): Boolean =
            map[key] as Boolean? ?: defValue
        override fun contains(key: String?): Boolean = map.containsKey(key)
        override fun edit(): SharedPreferences.Editor = object : SharedPreferences.Editor {
            private val pending = HashMap<String, Any?>()
            private var clearAll = false
            override fun putString(key: String?, value: String?): SharedPreferences.Editor {
                pending[key!!] = value; return this
            }
            override fun putStringSet(key: String?, values: MutableSet<String>?): SharedPreferences.Editor {
                pending[key!!] = values; return this
            }
            override fun putInt(key: String?, value: Int): SharedPreferences.Editor {
                pending[key!!] = value; return this
            }
            override fun putLong(key: String?, value: Long): SharedPreferences.Editor {
                pending[key!!] = value; return this
            }
            override fun putFloat(key: String?, value: Float): SharedPreferences.Editor {
                pending[key!!] = value; return this
            }
            override fun putBoolean(key: String?, value: Boolean): SharedPreferences.Editor {
                pending[key!!] = value; return this
            }
            override fun remove(key: String?): SharedPreferences.Editor {
                pending[key!!] = this; return this
            }
            override fun clear(): SharedPreferences.Editor { clearAll = true; return this }
            override fun commit(): Boolean {
                apply(); return true
            }
            override fun apply() {
                if (clearAll) map.clear()
                pending.forEach { (k, v) ->
                    if (v === this) map.remove(k) else map[k] = v
                }
                pending.clear(); clearAll = false
            }
        }
        override fun registerOnSharedPreferenceChangeListener(
            listener: SharedPreferences.OnSharedPreferenceChangeListener?,
        ) = Unit
        override fun unregisterOnSharedPreferenceChangeListener(
            listener: SharedPreferences.OnSharedPreferenceChangeListener?,
        ) = Unit
    }
}
