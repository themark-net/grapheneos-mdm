package net.themark.grapheneosmdm.apps

import android.app.PendingIntent
import android.app.admin.DevicePolicyManager
import android.content.Context
import android.content.Intent
import android.content.pm.PackageInstaller
import android.content.pm.PackageManager
import android.os.Build
import android.os.UserManager
import android.util.Log
import java.io.File
import java.io.FileInputStream

/**
 * Silent install / update / uninstall via PackageInstaller (Device Owner).
 *
 * Issue #4: status handling, retry, update vs fresh, GrapheneOS unknown-sources /
 * profile behaviour.
 */
class AppManager(private val context: Context) {

    private val packageInstaller = context.packageManager.packageInstaller
    private val dpm =
        context.getSystemService(Context.DEVICE_POLICY_SERVICE) as DevicePolicyManager

    fun isDeviceOwner(): Boolean = dpm.isDeviceOwnerApp(context.packageName)

    /**
     * GrapheneOS / AOSP: Device Owner PackageInstaller sessions are privileged and
     * do not require the user "unknown sources" toggle. Secondary profiles are not
     * silently provisioned here - enforce only on the system user.
     */
    fun canSilentInstall(): Boolean {
        if (!isDeviceOwner()) {
            Log.w(TAG, "Silent install refused: not Device Owner")
            return false
        }
        if (!isSystemUser()) {
            Log.w(TAG, "Silent install refused: not system user / primary profile")
            return false
        }
        return true
    }

    fun isSystemUser(): Boolean {
        val um = context.getSystemService(Context.USER_SERVICE) as UserManager
        return if (Build.VERSION.SDK_INT >= 23) {
            um.isSystemUser
        } else {
            true
        }
    }

    fun detectInstallKind(packageName: String): InstallKind {
        return if (isPackageInstalled(packageName)) InstallKind.UPDATE else InstallKind.FRESH
    }

    fun isPackageInstalled(packageName: String): Boolean {
        return try {
            context.packageManager.getPackageInfo(packageName, 0)
            true
        } catch (_: PackageManager.NameNotFoundException) {
            false
        }
    }

    fun installedVersionCode(packageName: String): Long? {
        return try {
            val pi = context.packageManager.getPackageInfo(packageName, 0)
            if (Build.VERSION.SDK_INT >= 28) pi.longVersionCode else {
                @Suppress("DEPRECATION")
                pi.versionCode.toLong()
            }
        } catch (_: PackageManager.NameNotFoundException) {
            null
        }
    }

    /**
     * Install or update [apkFile] with status await + retry.
     * Caller must verify hash/signature first ([ApkVerifier]).
     */
    fun installApk(
        apkFile: File,
        packageName: String? = null,
        maxAttempts: Int = DEFAULT_MAX_ATTEMPTS,
        awaitTimeoutMs: Long = DEFAULT_AWAIT_TIMEOUT_MS,
    ): InstallOutcome {
        if (!canSilentInstall()) {
            return InstallOutcome(
                status = InstallStatus(
                    InstallStatusCode.FAILURE_BLOCKED,
                    message = "not device owner or not system user",
                ),
                kind = packageName?.let { detectInstallKind(it) } ?: InstallKind.FRESH,
                attempts = 0,
            )
        }
        // Unknown-sources restriction applies to end users; DO installs still proceed.
        // Log when the restriction is active so operators understand GrapheneOS posture.
        logUnknownSourcesPosture()

        val kind = when {
            packageName != null -> detectInstallKind(packageName)
            else -> InstallKind.FRESH
        }

        var last = InstallStatus(InstallStatusCode.UNKNOWN, message = "not attempted")
        var attempts = 0
        while (attempts < maxAttempts) {
            attempts++
            last = commitSessionOnce(apkFile, packageName, awaitTimeoutMs)
            if (last.isSuccess) {
                Log.i(TAG, "Install success kind=$kind attempts=$attempts pkg=$packageName")
                return InstallOutcome(last, kind, attempts)
            }
            if (!InstallRetryPolicy.shouldRetry(last.code) || attempts >= maxAttempts) {
                break
            }
            val sleep = InstallRetryPolicy.backoffMs(attempts - 1)
            Log.w(TAG, "Install retryable failure ${last.code}; sleeping ${sleep}ms")
            try {
                Thread.sleep(sleep)
            } catch (_: InterruptedException) {
                Thread.currentThread().interrupt()
                break
            }
        }
        Log.e(TAG, "Install failed kind=$kind attempts=$attempts status=$last")
        return InstallOutcome(last, kind, attempts)
    }

    private fun commitSessionOnce(
        apkFile: File,
        packageName: String?,
        awaitTimeoutMs: Long,
    ): InstallStatus {
        return try {
            val params =
                PackageInstaller.SessionParams(PackageInstaller.SessionParams.MODE_FULL_INSTALL)
            if (packageName != null) {
                params.setAppPackageName(packageName)
            }
            if (Build.VERSION.SDK_INT >= 31) {
                params.setRequireUserAction(
                    PackageInstaller.SessionParams.USER_ACTION_NOT_REQUIRED,
                )
            }

            val sessionId = packageInstaller.createSession(params)
            InstallSessionBus.register(sessionId)
            val session = packageInstaller.openSession(sessionId)
            try {
                FileInputStream(apkFile).use { input ->
                    session.openWrite("package", 0, apkFile.length()).use { output ->
                        input.copyTo(output)
                        session.fsync(output)
                    }
                }
                val callbackIntent = Intent(context, InstallResultReceiver::class.java).apply {
                    action = ACTION_INSTALL_RESULT
                    putExtra(EXTRA_SESSION_ID, sessionId)
                }
                val pending = PendingIntent.getBroadcast(
                    context,
                    sessionId,
                    callbackIntent,
                    PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_MUTABLE,
                )
                session.commit(pending.intentSender)
            } finally {
                session.close()
            }
            Log.i(TAG, "Install session $sessionId committed for ${apkFile.name}")
            InstallSessionBus.await(sessionId, awaitTimeoutMs)
        } catch (e: Exception) {
            Log.e(TAG, "Failed to install ${apkFile.absolutePath}", e)
            InstallStatus(
                InstallStatusCode.FAILURE,
                message = e.message ?: e.javaClass.simpleName,
            )
        }
    }

    private fun logUnknownSourcesPosture() {
        val um = context.getSystemService(Context.USER_SERVICE) as UserManager
        val blocked = um.hasUserRestriction(UserManager.DISALLOW_INSTALL_UNKNOWN_SOURCES)
        if (blocked) {
            Log.i(
                TAG,
                "DISALLOW_INSTALL_UNKNOWN_SOURCES is set; Device Owner PackageInstaller " +
                    "sessions still proceed (GrapheneOS/AOSP DO behaviour)",
            )
        }
    }

    fun uninstall(
        packageName: String,
        awaitTimeoutMs: Long = DEFAULT_AWAIT_TIMEOUT_MS,
    ): Boolean {
        if (!canSilentInstall()) return false
        if (packageName.isBlank() || packageName == context.packageName) {
            Log.w(TAG, "Refusing to uninstall $packageName")
            return false
        }
        InstallSessionBus.registerPackage(packageName)
        return try {
            val callbackIntent = Intent(context, InstallResultReceiver::class.java).apply {
                action = ACTION_INSTALL_RESULT
                putExtra(EXTRA_UNINSTALL_PACKAGE, packageName)
            }
            val pending = PendingIntent.getBroadcast(
                context,
                packageName.hashCode(),
                callbackIntent,
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_MUTABLE,
            )
            packageInstaller.uninstall(packageName, pending.intentSender)
            InstallSessionBus.awaitPackage(packageName, awaitTimeoutMs).isSuccess
        } catch (e: Exception) {
            InstallSessionBus.cancelPackage(packageName)
            Log.e(TAG, "Failed to uninstall $packageName", e)
            false
        }
    }

    companion object {
        private const val TAG = "AppManager"
        const val ACTION_INSTALL_RESULT = "net.themark.grapheneosmdm.INSTALL_RESULT"
        const val EXTRA_SESSION_ID = "session_id"
        const val EXTRA_UNINSTALL_PACKAGE = "uninstall_package"
        const val DEFAULT_MAX_ATTEMPTS = 3
        const val DEFAULT_AWAIT_TIMEOUT_MS = 120_000L
    }
}

/** BroadcastReceiver that receives PackageInstaller status callbacks. */
class InstallResultReceiver : android.content.BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val statusInt =
            intent.getIntExtra(PackageInstaller.EXTRA_STATUS, PackageInstaller.STATUS_FAILURE)
        val message = intent.getStringExtra(PackageInstaller.EXTRA_STATUS_MESSAGE)
        val sessionId = intent.getIntExtra(
            AppManager.EXTRA_SESSION_ID,
            intent.getIntExtra(PackageInstaller.EXTRA_SESSION_ID, -1),
        )
        val other = intent.getStringExtra(PackageInstaller.EXTRA_OTHER_PACKAGE_NAME)
        val mapped = InstallStatus(
            code = InstallStatusMapper.fromPackageInstallerExtra(statusInt),
            message = message,
            sessionId = sessionId.takeIf { it >= 0 },
            otherPackageName = other,
        )
        Log.i("InstallResult", "status=$mapped")
        if (sessionId >= 0) {
            InstallSessionBus.complete(sessionId, mapped)
        }
        intent.getStringExtra(AppManager.EXTRA_UNINSTALL_PACKAGE)
            ?.takeIf { it.isNotBlank() }
            ?.let { InstallSessionBus.completePackage(it, mapped) }
        if (mapped.code == InstallStatusCode.PENDING_USER_ACTION) {
            // Should be rare for Device Owner + USER_ACTION_NOT_REQUIRED; surface intent if present.
            val confirm = intent.getParcelableExtra<Intent>(Intent.EXTRA_INTENT)
            if (confirm != null) {
                confirm.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                try {
                    context.startActivity(confirm)
                } catch (e: Exception) {
                    Log.e("InstallResult", "Could not start user-action intent", e)
                }
            }
        }
    }
}
