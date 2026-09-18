package net.themark.grapheneosmdm.apps

/**
 * PackageInstaller session outcomes + retry policy (issue #4).
 */
enum class InstallKind {
    /** Package not currently installed. */
    FRESH,
    /** Package already present; session is an update. */
    UPDATE,
}

enum class InstallStatusCode {
    SUCCESS,
    PENDING_USER_ACTION,
    FAILURE,
    FAILURE_ABORTED,
    FAILURE_BLOCKED,
    FAILURE_CONFLICT,
    FAILURE_INCOMPATIBLE,
    FAILURE_INVALID,
    FAILURE_STORAGE,
    FAILURE_TIMEOUT,
    UNKNOWN,
}

data class InstallStatus(
    val code: InstallStatusCode,
    val message: String? = null,
    val sessionId: Int? = null,
    val otherPackageName: String? = null,
) {
    val isSuccess: Boolean get() = code == InstallStatusCode.SUCCESS
}

data class InstallOutcome(
    val status: InstallStatus,
    val kind: InstallKind,
    val attempts: Int,
) {
    val isSuccess: Boolean get() = status.isSuccess
}

object InstallRetryPolicy {
    /** Statuses worth another PackageInstaller session attempt. */
    fun shouldRetry(code: InstallStatusCode): Boolean = when (code) {
        InstallStatusCode.FAILURE,
        InstallStatusCode.FAILURE_STORAGE,
        InstallStatusCode.FAILURE_TIMEOUT,
        InstallStatusCode.UNKNOWN,
        -> true
        else -> false
    }

    fun backoffMs(attemptIndexZeroBased: Int): Long {
        val base = 750L
        val exp = 1L shl attemptIndexZeroBased.coerceIn(0, 4)
        return base * exp
    }
}

object InstallStatusMapper {
    fun fromPackageInstallerExtra(status: Int): InstallStatusCode = when (status) {
        android.content.pm.PackageInstaller.STATUS_SUCCESS -> InstallStatusCode.SUCCESS
        android.content.pm.PackageInstaller.STATUS_PENDING_USER_ACTION ->
            InstallStatusCode.PENDING_USER_ACTION
        android.content.pm.PackageInstaller.STATUS_FAILURE -> InstallStatusCode.FAILURE
        android.content.pm.PackageInstaller.STATUS_FAILURE_ABORTED ->
            InstallStatusCode.FAILURE_ABORTED
        android.content.pm.PackageInstaller.STATUS_FAILURE_BLOCKED ->
            InstallStatusCode.FAILURE_BLOCKED
        android.content.pm.PackageInstaller.STATUS_FAILURE_CONFLICT ->
            InstallStatusCode.FAILURE_CONFLICT
        android.content.pm.PackageInstaller.STATUS_FAILURE_INCOMPATIBLE ->
            InstallStatusCode.FAILURE_INCOMPATIBLE
        android.content.pm.PackageInstaller.STATUS_FAILURE_INVALID ->
            InstallStatusCode.FAILURE_INVALID
        android.content.pm.PackageInstaller.STATUS_FAILURE_STORAGE ->
            InstallStatusCode.FAILURE_STORAGE
        else -> InstallStatusCode.UNKNOWN
    }
}
