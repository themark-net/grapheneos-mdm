package net.themark.grapheneosmdm.apps

import android.content.Context
import android.util.Log
import net.themark.grapheneosmdm.network.ApiClient
import net.themark.grapheneosmdm.protocol.RequiredPackage
import java.io.File

/**
 * Enforce local desired-apps list: download from private catalog / check-in URL,
 * verify hash (+ optional signing cert), then install via [AppManager].
 */
class DesiredAppsEnforcer(
    private val context: Context,
    private val appManager: AppManager = AppManager(context),
    private val apiClient: ApiClient = ApiClient(context),
    private val store: DesiredAppsStore = DesiredAppsStore(context),
) {
    data class EnforceReport(
        val planned: List<DesiredAppAction>,
        val installedOk: List<String> = emptyList(),
        val failed: List<String> = emptyList(),
        val skipped: List<String> = emptyList(),
    )

    fun persistAndEnforce(desired: List<RequiredPackage>): EnforceReport {
        store.save(desired)
        return enforce(desired)
    }

    fun enforceStored(): EnforceReport = enforce(store.load())

    fun enforce(desired: List<RequiredPackage>): EnforceReport {
        val tracked = store.installedByAgent()
        if (desired.isEmpty() && tracked.isEmpty()) {
            return EnforceReport(planned = emptyList())
        }
        if (!appManager.canSilentInstall()) {
            Log.w(TAG, "Skipping desired-apps enforce (not DO / not system user)")
            val names = (desired.map { it.packageName } + tracked).distinct()
            return EnforceReport(
                planned = names.map {
                    DesiredAppAction.MissingArtifact(it, "silent install unavailable")
                },
                skipped = names,
            )
        }

        val installed = desired.associate { req ->
            req.packageName to (appManager.installedVersionCode(req.packageName) ?: -1L)
        }.filterValues { it >= 0 }

        val planned = DesiredAppsPlanner.plan(
            desired,
            installed,
            tracked,
            context.packageName,
        )
        val ok = mutableListOf<String>()
        val failed = mutableListOf<String>()
        val skipped = mutableListOf<String>()

        for (action in planned) {
            when (action) {
                is DesiredAppAction.AlreadySatisfied -> {
                    skipped += action.packageName
                    Log.d(TAG, "Satisfied ${action.packageName}")
                }
                is DesiredAppAction.MissingArtifact -> {
                    failed += action.packageName
                    Log.w(TAG, "Cannot install ${action.packageName}: ${action.reason}")
                }
                is DesiredAppAction.NeedsInstall -> {
                    val result = downloadVerifyInstall(action.required, action.kind)
                    if (result) {
                        ok += action.required.packageName
                        if (action.required.packageName != context.packageName) {
                            store.trackInstalled(action.required.packageName)
                        }
                    } else {
                        failed += action.required.packageName
                    }
                }
                is DesiredAppAction.NeedsUninstall -> {
                    if (appManager.uninstall(action.packageName)) {
                        store.untrackInstalled(action.packageName)
                        ok += action.packageName
                    } else {
                        failed += action.packageName
                    }
                }
            }
        }
        Log.i(TAG, "Enforce done ok=$ok failed=$failed skipped=$skipped")
        return EnforceReport(planned, ok, failed, skipped)
    }

    private fun downloadVerifyInstall(req: RequiredPackage, kind: InstallKind): Boolean {
        val url = req.apkUrl ?: return false
        val sha = req.sha256 ?: return false
        val dest = File(context.cacheDir, "catalog-${req.packageName}.apk")
        return try {
            Log.i(TAG, "Downloading ${req.packageName} kind=$kind from $url")
            apiClient.downloadApk(url, dest)
            if (!ApkVerifier.verifySha256(dest, sha)) {
                dest.delete()
                return false
            }
            val cert = req.signingCertSha256
            if (!cert.isNullOrBlank()) {
                if (!ApkVerifier.verifySigningCertSha256(context, dest, cert)) {
                    dest.delete()
                    return false
                }
            }
            val outcome = appManager.installApk(dest, req.packageName)
            dest.delete()
            outcome.isSuccess
        } catch (e: Exception) {
            Log.e(TAG, "download/install failed for ${req.packageName}", e)
            dest.delete()
            false
        }
    }

    companion object {
        private const val TAG = "DesiredAppsEnforcer"
    }
}
