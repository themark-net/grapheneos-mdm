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

    private val waiters = ConcurrentHashMap<Int, Waiter>()

    fun register(sessionId: Int) {
        waiters[sessionId] = Waiter()
    }

    fun complete(sessionId: Int, status: InstallStatus) {
        val w = waiters[sessionId] ?: return
        w.result.compareAndSet(null, status)
        w.latch.countDown()
    }

    fun await(sessionId: Int, timeoutMs: Long): InstallStatus {
        val w = waiters[sessionId]
            ?: return InstallStatus(
                InstallStatusCode.UNKNOWN,
                message = "no waiter registered for session $sessionId",
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
            waiters.remove(sessionId)
        }
    }
}
