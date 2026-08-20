package net.themark.grapheneosmdm.apps

import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageInstaller
import android.util.Log
import java.io.File
import java.io.FileInputStream

/**
 * Handles silent install / update / uninstall of APKs.
 * Requires Device Owner privileges.
 */
class AppManager(private val context: Context) {

    private val packageInstaller = context.packageManager.packageInstaller

    /**
     * Silently install or update an APK file.
     * The calling process must be Device Owner.
     */
    fun installApk(apkFile: File, packageName: String? = null): Boolean {
        return try {
            val params = PackageInstaller.SessionParams(PackageInstaller.SessionParams.MODE_FULL_INSTALL)
            if (packageName != null) {
                params.setAppPackageName(packageName)
            }
            // For Android 12+ you may want:
            // params.setRequireUserAction(PackageInstaller.SessionParams.USER_ACTION_NOT_REQUIRED)

            val sessionId = packageInstaller.createSession(params)
            val session = packageInstaller.openSession(sessionId)

            FileInputStream(apkFile).use { input ->
                session.openWrite("package", 0, apkFile.length()).use { output ->
                    input.copyTo(output)
                    session.fsync(output)
                }
            }

            val callbackIntent = Intent(context, InstallResultReceiver::class.java)
            val pending = PendingIntent.getBroadcast(
                context,
                sessionId,
                callbackIntent,
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_MUTABLE
            )
            session.commit(pending.intentSender)
            session.close()
            Log.i(TAG, "Install session $sessionId committed for ${apkFile.name}")
            true
        } catch (e: Exception) {
            Log.e(TAG, "Failed to install ${apkFile.absolutePath}", e)
            false
        }
    }

    fun uninstall(packageName: String): Boolean {
        return try {
            val callbackIntent = Intent(context, InstallResultReceiver::class.java)
            val pending = PendingIntent.getBroadcast(
                context,
                packageName.hashCode(),
                callbackIntent,
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_MUTABLE
            )
            packageInstaller.uninstall(packageName, pending.intentSender)
            true
        } catch (e: Exception) {
            Log.e(TAG, "Failed to uninstall $packageName", e)
            false
        }
    }

    companion object {
        private const val TAG = "AppManager"
    }
}

/** BroadcastReceiver that receives PackageInstaller status callbacks. */
class InstallResultReceiver : android.content.BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val status = intent.getIntExtra(PackageInstaller.EXTRA_STATUS, PackageInstaller.STATUS_FAILURE)
        val message = intent.getStringExtra(PackageInstaller.EXTRA_STATUS_MESSAGE)
        Log.i("InstallResult", "status=$status message=$message")
        // TODO: report success/failure back to server / update local desired-state tracking
    }
}
