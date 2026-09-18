package net.themark.grapheneosmdm.service

import android.content.Context
import android.util.Log
import net.themark.grapheneosmdm.network.ApiClient
import net.themark.grapheneosmdm.network.ApiException
import net.themark.grapheneosmdm.policy.PolicyManager
import net.themark.grapheneosmdm.protocol.DesiredState

/**
 * Shared mTLS check-in path used by [CheckInWorker] (and optional one-shot
 * [MdmService]). Reuses PolicyManager / ApiClient from issues #3 and #4.
 */
class CheckInRunner(
    private val context: Context,
    private val apiClient: ApiClient = ApiClient(context),
    private val policyManager: PolicyManager = PolicyManager(context),
    private val onHighPriorityCheckIn: (() -> Unit)? = null,
) {

    enum class Outcome {
        SUCCESS,
        SKIPPED_NOT_CONFIGURED,
        TRANSIENT_FAILURE,
        FAILURE,
    }

    /**
     * @param allowFollowUpCheckIn when false, ignore `checkin_now` to avoid loops
     *   (e.g. the follow-up work itself already ran immediately).
     */
    fun run(allowFollowUpCheckIn: Boolean = true): Outcome {
        Log.d(TAG, "Performing check-in…")
        val inventory = policyManager.collectInventory()
        return try {
            val response = apiClient.checkIn(inventory)
            if (response.status == "ok") {
                applyDesiredState(response.desiredState, allowFollowUpCheckIn)
            } else {
                Log.w(TAG, "Server status=${response.status} msg=${response.message}")
            }
            Log.d(TAG, "Check-in complete status=${response.status}")
            Outcome.SUCCESS
        } catch (e: IllegalStateException) {
            // Base URL / mTLS material not configured yet — expected before lab enroll.
            Log.i(TAG, "Check-in skipped: ${e.message}")
            Outcome.SKIPPED_NOT_CONFIGURED
        } catch (e: ApiException) {
            Log.e(TAG, "Check-in API error: ${e.message}")
            // Network / HTTP failures are usually transient on mobile.
            Outcome.TRANSIENT_FAILURE
        } catch (e: Exception) {
            Log.e(TAG, "Check-in failed", e)
            Outcome.TRANSIENT_FAILURE
        }
    }

    private fun applyDesiredState(state: DesiredState, allowFollowUpCheckIn: Boolean) {
        val wantsImmediate = state.commands.orEmpty().any { it.type == "checkin_now" }
        policyManager.applyDesiredState(state)
        if (wantsImmediate && allowFollowUpCheckIn) {
            Log.i(TAG, "High-priority checkin_now — requesting immediate follow-up")
            onHighPriorityCheckIn?.invoke()
                ?: CheckInScheduler.enqueueImmediate(
                    context,
                    reason = "command_checkin_now",
                    fromCheckInNow = true,
                )
        }
    }

    companion object {
        private const val TAG = "CheckInRunner"
    }
}
