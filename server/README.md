# Lab check-in server (issue #3)

Thin HTTPS stub that **requires mutual TLS** and serves desired-state on
`POST /v1/checkin` (alias: `/checkin`). Closed loop for a spare/lab Pixel in one sprint.

## Quick start

```bash
cd server
./gen-lab-certs.sh lab-certs
python3 lab_checkin.py --certs lab-certs --port 8443 --desired desired-state.example.json
```

Smoke with client cert:

```bash
curl --cacert lab-certs/ca.pem \
  --cert lab-certs/client.pem --key lab-certs/client-key.pem \
  -H 'Content-Type: application/json' \
  -d '{"schemaVersion":1,"inventory":{"schemaVersion":1,"deviceId":"lab","osVersion":"16","securityPatch":"2026-09-01","installedPackages":[]}}' \
  https://127.0.0.1:8443/v1/checkin
```

## Alignment with fleet CA / step-ca

Production devices should present client certs issued by the existing lab/fleet
CA (see `themark-net/workstation-environment` `lab_ca` / step-ca + cert-mint).
This script's openssl CA is **lab-only** so CI and a spare device can close the
loop without standing up step-ca. Swap `--certs` for real PEMs/PKCS#12 from
step-ca when moving beyond the bench.

On the agent: copy `ca.pem` + `client.p12` into the app-private `mtls/` dir
(or import into Android Keystore alias `grapheneos_mdm_client`), and set the
server base URL via `SecureConfigStore` (e.g. `https://10.42.0.x:8443`).

## Out of scope

- QR enrollment wizard (#8)
- Full AppManager catalog (#4)
- WorkManager check-in (#5)
- Commercial MDM packaging
