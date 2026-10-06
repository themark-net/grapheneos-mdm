# AGENTS.md — grapheneos-mdm

Custom Device Owner MDM agent for GrapheneOS fleets (Kotlin / AOSP DevicePolicyManager).

**Posture:** [docs/ROADMAP.md](docs/ROADMAP.md) (Feature GO). Host-only and AOSP-emulator work is org-can-do. A physical Pixel stays founder-only. Prefer protocol and lab-server tests unless the task is the emulator bench named in the roadmap.

## Mandatory reads

1. [DESIGN.md](DESIGN.md)
2. [docs/ROADMAP.md](docs/ROADMAP.md) — phases and the next slice
3. [docs/](docs/) — enrollment, mTLS, scheduling, handoff
4. [README.md](README.md)

## Testing standing rule
Prefer the Testing Trophy: mostly integration/E2E for product confidence. Unit tests only for shaky/non-obvious behavior. Forbidden: tautological tests and implementation-detail tests. Prefer sociable tests; doubles only at awkward boundaries + contract tests for externals. Every non-trivial change: How could this fail? How do we recover?

No tautological or implementation-detail unit sprawl as Done.

## Verify

```bash
./gradlew :app:assembleDebug
# prefer protocol/server tests and software-only checks over live device demos
# Emulator bench shipped #36/#38 (AOSP ATD, not GrapheneOS): scripts/emulator-device-owner.sh
# Next slice is docs/ROADMAP.md Phase 3 (same-database attestation round-trip)
```
