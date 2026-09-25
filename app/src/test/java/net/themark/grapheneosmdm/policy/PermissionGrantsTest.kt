package net.themark.grapheneosmdm.policy

import android.app.admin.DevicePolicyManager
import net.themark.grapheneosmdm.protocol.PermissionGrant
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class PermissionGrantsTest {

    private val self = "net.themark.grapheneosmdm"

    @Test
    fun mapsGrantStates() {
        assertEquals(
            DevicePolicyManager.PERMISSION_GRANT_STATE_GRANTED,
            permissionGrantConstant(" GRANTED "),
        )
        assertEquals(
            DevicePolicyManager.PERMISSION_GRANT_STATE_DENIED,
            permissionGrantConstant("denied"),
        )
        assertEquals(
            DevicePolicyManager.PERMISSION_GRANT_STATE_DEFAULT,
            permissionGrantConstant("default"),
        )
        assertNull(permissionGrantConstant(null))
        assertNull(permissionGrantConstant("allow"))
    }

    @Test
    fun nullListLeavesDeviceAlone() {
        val previous = setOf(permissionKey("com.example.app", "android.permission.CAMERA"))
        assertNull(permissionGrantChange(previous, null, self))
    }

    @Test
    fun appliesDesiredAndResetsDropped() {
        val previous = setOf(
            permissionKey("com.example.app", "android.permission.CAMERA"),
            permissionKey("com.example.app", "android.permission.RECORD_AUDIO"),
        )
        val change = permissionGrantChange(
            previous,
            listOf(
                PermissionGrant("com.example.app", "android.permission.CAMERA", "granted"),
                PermissionGrant("com.example.other", "android.permission.ACCESS_FINE_LOCATION", "denied"),
                PermissionGrant("com.example.other", "android.permission.ACCESS_FINE_LOCATION", "granted"),
                PermissionGrant(self, "android.permission.CAMERA", "granted"),
                PermissionGrant("com.example.app", "android.permission.READ_CONTACTS", "nope"),
            ),
            self,
        )!!
        assertEquals(
            listOf(
                "com.example.app" to "android.permission.CAMERA",
                "com.example.other" to "android.permission.ACCESS_FINE_LOCATION",
            ),
            change.assertOn.map { it.packageName to it.permission },
        )
        assertEquals(
            DevicePolicyManager.PERMISSION_GRANT_STATE_GRANTED,
            change.assertOn[0].grantState,
        )
        assertEquals(
            listOf("com.example.app" to "android.permission.RECORD_AUDIO"),
            change.turnOff.map { it.packageName to it.permission },
        )
        assertEquals(
            DevicePolicyManager.PERMISSION_GRANT_STATE_DEFAULT,
            change.turnOff[0].grantState,
        )
        assertEquals(
            setOf(
                permissionKey("com.example.app", "android.permission.CAMERA"),
                permissionKey("com.example.other", "android.permission.ACCESS_FINE_LOCATION"),
            ),
            change.next,
        )
    }

    @Test
    fun emptyListResetsEverythingPreviouslyManaged() {
        val previous = setOf(permissionKey("com.example.app", "android.permission.CAMERA"))
        val change = permissionGrantChange(previous, emptyList(), self)!!
        assertEquals(emptyList<PermissionApply>(), change.assertOn)
        assertEquals(1, change.turnOff.size)
        assertEquals(emptySet<String>(), change.next)
    }
}
