# Lab check-in + private catalog server (issues #3 / #4)

Thin HTTPS stub that **requires mutual TLS** and serves desired-state on
`POST /v1/checkin` (alias: `/checkin`). Issue #4 adds a private signed-catalog
path: `GET /v1/catalog/<file>` from `--catalog-dir`.

## Quick start

```bash
cd server
./gen-lab-certs.sh lab-certs
python3 lab_checkin.py --certs lab-certs --port 8443 \
  --desired desired-state.example.json --catalog-dir ./catalog
```

Smoke with client cert:

```bash
curl --cacert lab-certs/ca.pem \
  --cert lab-certs/client.pem --key lab-certs/client-key.pem \
  -H 'Content-Type: application/json' \
  -d '{"schemaVersion":1,"inventory":{"schemaVersion":1,"deviceId":"lab","osVersion":"16","securityPatch":"2026-09-01","installedPackages":[]}}' \
  https://127.0.0.1:8443/v1/checkin

curl --cacert lab-certs/ca.pem \
  --cert lab-certs/client.pem --key lab-certs/client-key.pem \
  -O https://127.0.0.1:8443/v1/catalog/grapheneosmdm.apk
```

Desired-state package entries should include `apkUrl` (absolute HTTPS or
`/v1/catalog/...`) and `sha256` so the agent verifies bytes before
`PackageInstaller` commit. Optional `signingCertSha256` checks the APK signer.

The example `catalog/grapheneosmdm.apk` is a **placeholder** byte file for CI;
replace it with a real signed APK before lab installs.

## Alignment with fleet CA / step-ca

Production devices should present client certs issued by the existing lab/fleet
CA (see `themark-net/workstation-environment` `lab_ca` / step-ca + cert-mint).
This script's openssl CA is **lab-only** so CI and a spare device can close the
loop without standing up step-ca. Swap `--certs` for real PEMs/PKCS#12 from
step-ca when moving beyond the bench.

On the agent: copy `ca.pem` + `client.p12` into the app-private `mtls/` dir
(or import into Android Keystore alias `grapheneos_mdm_client`), and set the
server base URL via `SecureConfigStore` (e.g. `https://10.42.0.x:8443`).

## Out of scope (parked)

- QR enrollment wizard (#8)
- WorkManager check-in (#5)
- Commercial MDM packaging
