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
                  {
                    "packageName": "net.themark.grapheneosmdm",
                    "versionName": "0.1.0-alpha",
                    "apkUrl": "/v1/catalog/grapheneosmdm.apk",
                    "sha256": "c4b21224817aab1213dcdb25a690682422dcacf438bbab13fba7897aa3bdcc4b"
                  }
                ],
                "policyFlags": {
                  "disallowAddUser": true,
                  "minSecurityPatch": "2026-09-01",
                  "passwordComplexity": "low",
                  "maximumTimeToLockMs": 30000,
                  "suspendedPackages": ["com.example.game"],
                  "permissionGrants": [
                    {
                      "packageName": "com.example.app",
                      "permission": "android.permission.CAMERA",
                      "state": "granted"
                    }
                  ]
                },
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
        assertEquals("/v1/catalog/grapheneosmdm.apk", response.desiredState.requiredPackages[0].apkUrl)
        assertEquals(64, response.desiredState.requiredPackages[0].sha256!!.length)
        assertNotNull(response.shortLivedToken)
        assertEquals("abc", response.shortLivedToken!!.token)
        assertEquals("2026-09-01", response.desiredState.policyFlags.minSecurityPatch)
        assertEquals("low", response.desiredState.policyFlags.passwordComplexity)
        assertEquals(30_000L, response.desiredState.policyFlags.maximumTimeToLockMs)
        assertEquals(listOf("com.example.game"), response.desiredState.policyFlags.suspendedPackages)
        val grant = response.desiredState.policyFlags.permissionGrants!!.single()
        assertEquals("com.example.app", grant.packageName)
        assertEquals("android.permission.CAMERA", grant.permission)
        assertEquals("granted", grant.state)
    }

    @Test
    fun desiredStateMinimal() {
        val json = """{"schemaVersion":1,"requiredPackages":[],"policyFlags":{}}"""
        val state = ProtocolJson.desiredStateAdapter.fromJson(json)!!
        assertEquals(1, state.schemaVersion)
        assertTrue(state.requiredPackages.isEmpty())
    }
}
