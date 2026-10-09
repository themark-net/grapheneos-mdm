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

Phase 5, issue #47. One line each: choice | alternatives | why

- Base `build/p5-gha-kvm` on `main` 51c6c3b | base on `build/p4-disallow-add-user` | PR #46 is merged (squash 51c6c3b has the same tree as a598034)
- GitHub-hosted `ubuntu-latest` with a `/dev/kvm` udev rule | self-hosted runner on nimo | founder gate: no runner, host or service changes on nimo; hosted runners expose KVM for free on public repos
- `reactivecircus/android-emulator-runner` v2.38.0 pinned by commit SHA | hand-rolled sdkmanager/avdmanager/emulator steps; a floating `@v2` tag | maintained action that installs `aosp_atd` and waits for boot; SHA pin keeps the supply chain fixed
- A CI wrapper `scripts/ci-emulator-policy.sh` that runs the legs and asserts exit codes | several lines in the action's `script:` input | the action runs each `script:` line in its own `sh -c`; a bash file can hold `PIPESTATUS`, groups and a summary
- CI overrides (`SERIAL=emulator-5554`, `ANDROID_ADB_SERVER_PORT=5037`, `ANDROID_USER_HOME=$HOME/.android`, `GRADLE_BIN=gradle`) live in the wrapper | change the operate script's defaults | nimo defaults stay exactly as benched
- Legs in order absent, false, true-then-false, true | only true and one negative | both negative modes are asserted; true-then-false proves clear without owner reset; true last leaves the documented post-run state that the job asserts
- `DISALLOW_ADD_USER=true-then-false` as a fourth mode of the same script | a separate script; restart the lab server with a new desired.json | one script, same enroll path; the per-device override is the real operator path (`fleet_store.py set-desired`) and `lab_checkin.py` reads it per request
- No app code change for clear | add a new clear path | `PolicyManager` already calls `clearUserRestriction` on `false`, and `PolicyRestrictionTest.falseFlagsClearRestrictions` covers the mapping
- Build the test-only APK in a step before the emulator boots | let the script build inside the emulator step | shorter emulator time; the script's own Gradle call is then up to date
- Path filter includes `app/**`, `protocol/**` and Gradle files besides the script, `server/**` and the workflow | only the four paths named in the issue | the APK under test is built from `app/` and the Gradle files; protocol changes alter desired-state parsing
- `push` filtered to `main` only | push on every branch | PR runs cover branches; avoids double runs per push
- Timeout 45 minutes, `emulator-boot-timeout` 900 s | action defaults (no job timeout, 600 s boot) | ATD boot on a hosted runner can be slow; a hung job must not burn hours
- Upload `/tmp/mdm-ci` minus `*/certs/` | upload everything | lab private keys are throwaway but are still keys; logs, dumpsys and sqlite are enough
- `UI_PORT` used for the listener check and every message; `LAB_URL` follows `PORT` | keep 8787 / 8443 literals | parked nit (1); one source of truth per port
- Manual edits instead of Grok Build headless | Build-first on nimo | nimo was offline (desktop app not connected) when the slice started
- Keep the strict fingerprint guard `Android/sdk_slim_x86_64/emu64x:15/*` with no CI override | `FINGERPRINT_ALLOW` env set to whatever the runner prints; widen the case pattern | run 37974703736 printed `Android/sdk_slim_x86_64/emu64x:15/AE3A.240806.019/12368160:userdebug/test-keys`, the same r01 image as the nimo bench, so the guard already accepted it
- Prebuild `assembleDebug` against the runner's preinstalled SDK | add `android-actions/setup-android` before that step | `ubuntu-latest` already had `ANDROID_HOME` and platform 35; the step succeeded, and the emulator action then installed `aosp_atd` into that SDK
- `git apply --3way` of the draft, dropping only the extra blank line at the end of `docs/EMULATOR.md` | keep the patch byte-for-byte, including the `git diff --check` whitespace error | `main` was still `51c6c3b`, so there was no content conflict; the extra newline was the only whitespace error
- One emulator-runner retry only when `/tmp/mdm-ci/script-started` is missing | `if: failure()` retry of every failure; unlimited retries | a boot, KVM, or image-install failure gets one more attempt; a leg that already started is the result and must not be retried away
- `avd-name: mdm36` on the hosted runner | leave the action default name `test` | the nimo bench AVD is `mdm36`; the serial stays `emulator-5554` because the action's console port is 5554
- Lab certs in `/tmp/mdm-certs/<leg>`, outside the uploaded log dir, and the upload also excludes `!/tmp/mdm-ci/**/certs/**` plus pem/p12/key/crt | exclusion glob only | the repo is public; a glob miss must not publish the CA key, `client-key.pem`, or `client.p12`
- SHA-pin checkout, setup-java, setup-python, setup-gradle, and upload-artifact | leave the floating major tags | same supply-chain pin as the emulator action; the SHAs are the current tips of those major tags
- Per-leg lines in `$GITHUB_STEP_SUMMARY` from the wrapper | a later step that parses the logs | the wrapper already has each leg's restriction file, devices JSON, and PASS/FAIL line
- Run URL in a final docs-only commit citing the code SHA | include in same commit; leave out | avoids the chicken-and-egg; path filter skips the emulator job for docs-only
