package net.themark.grapheneosmdm.protocol

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test

class ProtocolJsonTest {

    @Test
    fun encodeDecodeRoundTrip() {
        val inventory = InventoryReport(
            deviceId = "dev-1",
            osVersion = "16",
            securityPatch = "2026-09-01",
            installedPackages = listOf(
                PackageVersion("net.themark.grapheneosmdm", "0.1.0-alpha", 1L),
            ),
            isDeviceOwner = true,
            attestation = AttestationInfo(format = "none"),
            reportedAt = "2026-09-18T06:00:00Z",
        )
        val request = CheckInRequest(inventory = inventory, agentVersion = "0.1.0-alpha")
        val json = ProtocolJson.encodeRequest(request)
        assertTrue(json.contains("\"deviceId\":\"dev-1\""))
        assertTrue(json.contains("installedPackages"))

        val responseJson = """
            {
              "schemaVersion": 1,
              "status": "ok",
              "desiredState": {
                "schemaVersion": 1,
                "requiredPackages": [
                  {"packageName": "net.themark.grapheneosmdm", "versionName": "0.1.0-alpha"}
                ],
                "policyFlags": {"disallowAddUser": true},
                "commands": [{"type": "noop", "id": "t1"}]
              },
              "shortLivedToken": {
                "token": "abc",
                "expiresAt": "2026-09-18T07:00:00Z"
              }
            }
        """.trimIndent()
        val response = ProtocolJson.decodeResponse(responseJson)
        assertEquals("ok", response.status)
        assertEquals(1, response.desiredState.requiredPackages.size)
        assertEquals("net.themark.grapheneosmdm", response.desiredState.requiredPackages[0].packageName)
        assertNotNull(response.shortLivedToken)
        assertEquals("abc", response.shortLivedToken!!.token)
    }

    @Test
    fun desiredStateMinimal() {
        val json = """{"schemaVersion":1,"requiredPackages":[],"policyFlags":{}}"""
        val state = ProtocolJson.desiredStateAdapter.fromJson(json)!!
        assertEquals(1, state.schemaVersion)
        assertTrue(state.requiredPackages.isEmpty())
    }
}
