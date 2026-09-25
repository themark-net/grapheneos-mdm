package net.themark.grapheneosmdm.apps

import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicReference

/**
 * Bridges [InstallResultReceiver] callbacks to waiting [AppManager] callers.
 */
object InstallSessionBus {
    private data class Waiter(
        val latch: CountDownLatch = CountDownLatch(1),
        val result: AtomicReference<InstallStatus> = AtomicReference(),
    )

    private val waiters = ConcurrentHashMap<Any, Waiter>()

    fun register(sessionId: Int) {
        waiters[sessionId] = Waiter()
    }

    fun complete(sessionId: Int, status: InstallStatus) {
        completeKey(sessionId, status)
    }

    fun await(sessionId: Int, timeoutMs: Long): InstallStatus {
        return awaitKey(sessionId, timeoutMs, sessionId)
    }

    fun registerPackage(packageName: String) {
        waiters[packageKey(packageName)] = Waiter()
    }

    fun completePackage(packageName: String, status: InstallStatus) {
        completeKey(packageKey(packageName), status)
    }

    fun awaitPackage(packageName: String, timeoutMs: Long): InstallStatus {
        return awaitKey(packageKey(packageName), timeoutMs, sessionId = null)
    }

    fun cancelPackage(packageName: String) {
        waiters.remove(packageKey(packageName))
    }

    private fun packageKey(packageName: String): String = "uninstall:$packageName"

    private fun completeKey(key: Any, status: InstallStatus) {
        val w = waiters[key] ?: return
        w.result.compareAndSet(null, status)
        w.latch.countDown()
    }

    private fun awaitKey(key: Any, timeoutMs: Long, sessionId: Int?): InstallStatus {
        val w = waiters[key]
            ?: return InstallStatus(
                InstallStatusCode.UNKNOWN,
                message = "no waiter registered for $key",
                sessionId = sessionId,
            )
        return try {
            val ok = w.latch.await(timeoutMs, TimeUnit.MILLISECONDS)
            if (!ok) {
                InstallStatus(
                    InstallStatusCode.FAILURE_TIMEOUT,
                    message = "timed out waiting for PackageInstaller callback",
                    sessionId = sessionId,
                )
            } else {
                w.result.get() ?: InstallStatus(
                    InstallStatusCode.UNKNOWN,
                    message = "empty install callback",
                    sessionId = sessionId,
                )
            }
        } finally {
            waiters.remove(key)
        }
    }
}
