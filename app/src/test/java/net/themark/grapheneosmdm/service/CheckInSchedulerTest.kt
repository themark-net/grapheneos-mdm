package net.themark.grapheneosmdm.service

import androidx.work.NetworkType
import net.themark.grapheneosmdm.security.SecureConfigStore
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.util.concurrent.ConcurrentHashMap
import android.content.SharedPreferences

class CheckInSchedulerTest {

    @Test
    fun clampInterval_enforcesWorkManagerMinimum() {
        assertEquals(15L, CheckInScheduler.clampIntervalMinutes(1L))
        assertEquals(15L, CheckInScheduler.clampIntervalMinutes(15L))
        assertEquals(60L, CheckInScheduler.clampIntervalMinutes(60L))
    }

    @Test
    fun clampInterval_enforcesDailyMaximum() {
        assertEquals(24L * 60L, CheckInScheduler.clampIntervalMinutes(99_999L))
    }

    @Test
    fun buildConstraints_defaultsRequireNetworkAndBattery() {
        val store = SecureConfigStore.wrap(MemoryPrefs())
        val c = CheckInScheduler.buildConstraints(store)
        assertEquals(NetworkType.CONNECTED, c.requiredNetworkType)
        assertTrue(c.requiresBatteryNotLow())
        assertFalse(c.requiresCharging())
        assertFalse(c.requiresDeviceIdle())
        assertTrue(c.requiresStorageNotLow())
    }

    @Test
    fun buildConstraints_honorsDisabledFlags() {
        val store = SecureConfigStore.wrap(MemoryPrefs())
        store.requireNetworkConnected = false
        store.requireBatteryNotLow = false
        val c = CheckInScheduler.buildConstraints(store)
        assertEquals(NetworkType.NOT_REQUIRED, c.requiredNetworkType)
        assertFalse(c.requiresBatteryNotLow())
    }

    @Test
    fun secureConfig_intervalDefaultsAndPersists() {
        val store = SecureConfigStore.wrap(MemoryPrefs())
        assertEquals(SecureConfigStore.DEFAULT_CHECKIN_INTERVAL_MIN, store.checkInIntervalMinutes)
        store.checkInIntervalMinutes = 45L
        assertEquals(45L, store.checkInIntervalMinutes)
        assertTrue(store.requireNetworkConnected)
        assertTrue(store.requireBatteryNotLow)
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
