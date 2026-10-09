# Autonomous decisions — 2026-10-09

Phase 4, issue #45. One line each: choice | alternatives | why

- `DISALLOW_ADD_USER=true|false|absent` on one script | three scripts, or a separate JSON flag file | the bench mode is the only switch; false and absent fail at the restriction step as the negative proof
- Parse `dumpsys user` restriction blocks and `dumpsys device_policy` engine/bundle lines | one source only | Android 14/15 can show an applied restriction in either dump
- Also accept the Android 15 per-user header `Device policy restrictions:` | only the three names Effective / global / local | this image's UserManagerService prints that header for the per-user device-policy bundle
- One lab broadcast and one check-in | two check-ins like Phase 3 | attestation is not this phase; policy flags apply on the first desired-state response
- Exact restriction token, and an explicit false is not applied | substring search for `no_add_user` | `no_add_user=false` is not applied, and `no_add_managed_profile` / `no_add_clone_profile` / `no_add_private_profile` are other restrictions
- Start `ui_server.py` only after the restriction check, and refuse port 8787 if it is already bound | start the UI first | the log order is enroll, check-in, restriction, operator list; a busy or non-localhost port fails closed
- Skip attestation assertions and do not run `same_db_attestation.py` | reuse the Phase 3 checker | this phase must not claim attestation passed
- `server/policy_restriction.py` as the parser the script shells out to | awk inside the shell script | the match rules are the shaky part and the unit tests target them
- `OUT=/tmp/mdm-phase4-policy` and guest files `mdm-phase4-*` | reuse the Phase 3 output directory | a Phase 3 sqlite and cert set must not mix with this run
- PASS line only when mode is true and `no_add_user` is applied | print PASS whenever the helper exits 0 | false and absent are negative proofs and must exit non-zero; the PASS sentence names `disallowAddUser=true`
- One logcat level per tag (`PolicyManager:D`) | keep `TAG:I TAG:D TAG:W TAG:E` from the Phase 3 template | `adb logcat -s` keeps only the last spec per tag, which hid the Info line and failed the first bench run
- Accept `UserRestrictionPolicyKey userRestriction_<name>` and judge only the `Resolved Policy` section when present | word-boundary token only; any true value in the block | that is the literal Android 15 format on mdm36, and a per-admin true with resolved null is not applied
- Bench with `GRADLE_BIN=/tmp/gradle-8.9/bin/gradle` (existing user-space download) | add a gradle wrapper jar to the repo | no repo or host change needed; wrapper is a separate decision
- Leave the emulator running after the bench | stop it | the Phase 3 script and this one both leave it up; no wipe or shutdown beyond what Phase 3 does
