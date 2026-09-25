# AGENTS.md — grapheneos-mdm

Custom Device Owner MDM agent for GrapheneOS fleets (Kotlin / AOSP DevicePolicyManager).

**Software-only / no device-demo by default:** prefer unit/integration against protocol schemas and lab server stubs. Do not treat device enrollment or live Pixel demos as required agent verification unless explicitly tasked.

## Mandatory reads

1. [DESIGN.md](DESIGN.md)
2. [docs/](docs/) — enrollment, mTLS, scheduling, handoff
3. [README.md](README.md)

## Testing standing rule
Prefer the Testing Trophy: mostly integration/E2E for product confidence. Unit tests only for shaky/non-obvious behavior. Forbidden: tautological tests and implementation-detail tests. Prefer sociable tests; doubles only at awkward boundaries + contract tests for externals. Every non-trivial change: How could this fail? How do we recover?

No tautological or implementation-detail unit sprawl as Done.

## Verify

```bash
./gradlew :app:assembleDebug
# prefer protocol/server tests and software-only checks over live device demos
```
