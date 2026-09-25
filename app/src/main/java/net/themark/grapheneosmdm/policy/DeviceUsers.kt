package net.themark.grapheneosmdm.policy

import net.themark.grapheneosmdm.protocol.DeviceUser

/** Calling user first, then other serials. Negative or duplicate serials are dropped. */
internal fun deviceUsers(callingSerial: Long, secondarySerials: List<Long>): List<DeviceUser> {
    val users = mutableListOf<DeviceUser>()
    if (callingSerial >= 0) {
        users += DeviceUser(serial = callingSerial, secondary = false)
    }
    for (serial in secondarySerials.distinct().sorted()) {
        if (serial >= 0 && serial != callingSerial) {
            users += DeviceUser(serial = serial, secondary = true)
        }
    }
    return users
}
