# Mutual TLS check-in (issue #3)

## Goal

The agent only accepts commands over **HTTPS with client certificates** issued by
the fleet / lab CA. Inventory goes up; desired state (required packages + policy
flags) comes down. Short-lived bearer tokens from the server are optional and
stored encrypted on device.

## Agent configuration path

1. **CA + client identity**
   - Preferred: Android Keystore entry alias `grapheneos_mdm_client`
     (private key non-exportable when the platform allows).
   - Lab fallback: app-private directory `mtls/` (`Context.getDir("mtls", MODE_PRIVATE)`)
     containing `client.p12` and `ca.pem`. Application has `allowBackup=false`.
2. **Server base URL** — `SecureConfigStore` (EncryptedSharedPreferences).
   Example: `https://10.42.0.57:8443` (no path suffix; client appends `/v1/checkin`).
3. **Short-lived token** — if the check-in response includes `shortLivedToken`,
   it is stored encrypted and sent as `Authorization: Bearer …` on later calls
   until `expiresAt`.

Implementation: `DefaultMtlsMaterialLoader`, `ApiClient`, `SecureConfigStore`.

## Wire protocol

See [`protocol/`](../protocol/). `POST {baseUrl}/v1/checkin` with
`CheckInRequest` JSON; response is `CheckInResponse` including `desiredState`.

## Lab closed loop

[`server/`](../server/) is a thin Python stub that demands `ssl.CERT_REQUIRED`
and returns `desired-state.example.json`. Pass `--db` to record inventory and
apply a per-device desired-state override. Generate throwaway certs with
`server/gen-lab-certs.sh`, or point both sides at PEMs from step-ca.

## Fleet CA / step-ca / Ansible alignment

This repo does **not** embed step-ca. Fleet practice lives in
`themark-net/workstation-environment`:

| Concern | Lab pattern (workstation-environment) | This agent |
|---------|----------------------------------------|------------|
| Device client cert | step-ca + `lab_ca` cert-mint after attest | Present cert via Keystore / `client.p12` |
| CA trust | Lab root/intermediate on relying parties | `ca.pem` in trust store for OkHttp |
| Inventory / desired state | Ansible-shaped group vars (future) | JSON schemas under `protocol/` |
| Check-in transport | mTLS HTTPS | `ApiClient` → `/v1/checkin` |

When minting for phones, prefer the same device CA that RADIUS / lab relying
parties already trust. Do not commit real CA keys or provisioner passwords here.

## Explicitly parked

- QR enrollment wizard / commercial MDM packaging (#8)

Scheduling: [SCHEDULING.md](SCHEDULING.md). Desired-apps / catalog: issue #4 (landed).
