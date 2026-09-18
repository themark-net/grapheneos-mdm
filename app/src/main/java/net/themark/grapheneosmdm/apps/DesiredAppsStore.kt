package net.themark.grapheneosmdm.apps

import android.content.Context
import net.themark.grapheneosmdm.protocol.DesiredState
import net.themark.grapheneosmdm.protocol.ProtocolJson
import net.themark.grapheneosmdm.protocol.RequiredPackage

/**
 * Local persistence of the last desired-apps list from check-in.
 * Survives process death so a later boot can re-enforce without a round-trip.
 */
class DesiredAppsStore(context: Context) {
    private val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    fun save(packages: List<RequiredPackage>) {
        val wrapped = DesiredState(requiredPackages = packages)
        prefs.edit()
            .putString(KEY_JSON, ProtocolJson.desiredStateAdapter.toJson(wrapped))
            .apply()
    }

    fun load(): List<RequiredPackage> {
        val raw = prefs.getString(KEY_JSON, null) ?: return emptyList()
        return try {
            ProtocolJson.desiredStateAdapter.fromJson(raw)?.requiredPackages.orEmpty()
        } catch (_: Exception) {
            emptyList()
        }
    }

    companion object {
        private const val PREFS = "desired_apps"
        private const val KEY_JSON = "desired_state_json"
    }
}
