# Check-in protocol (issue #3)

Minimal JSON schemas shared by the Android agent and the lab check-in server.

| Schema | Role |
|--------|------|
| `inventory-report.schema.json` | Device → server inventory body |
| `desired-state.schema.json` | Server desired packages + policy flags |
| `checkin-request.schema.json` | `POST /v1/checkin` request envelope |
| `checkin-response.schema.json` | Response envelope (desired state + optional short-lived token) |

Wire format is JSON over HTTPS with **mutual TLS** (fleet/lab CA). See [docs/MTLS.md](../docs/MTLS.md).

Kotlin models live in `app/.../protocol/` and must stay field-compatible with these schemas.
