# Autonomous decisions — 2026-10-12

Phase 6, issue #49. One line each: choice | alternatives | why

- Phase 6 = disallowFactoryReset on the hosted KVM job | Phase 3 same-database script on the runner | CEO choice: extend the green Phase 5 policy job; do not treat `chain_invalid` as attestation progress
- Generalize `scripts/emulator-policy-disallow-add-user.sh` with `RESTRICTION=disallowAddUser|disallowFactoryReset` (default `disallowAddUser`) | a second copy of the operate script; a second workflow | one enroll path, one no-wipe rule, and one clear-leg message check; the default keeps the Phase 4 command and the add-user PASS/FAIL lines
- No app or schema change | a new flag or a new `UserManager` string | `userRestrictionUpdates` already maps `disallowFactoryReset` true to `DISALLOW_FACTORY_RESET` (`no_factory_reset`) and false to `clearUserRestriction`; `PolicyRestrictionTest` lists both; `desired-state.schema.json` already has the boolean
- Factory-reset legs after the add-user legs, and the `no_add_user` post-run check before those legs | a second KVM job; interleave the modes; assert `no_add_user` only at the end | one boot; removing the test-only owner drops `no_add_user`, so that assertion has to run while it is still set
- Clear leg requires the stderr line `restriction <token> is not applied` | treat any non-zero `policy_restriction.py` exit as cleared | a dumpsys read error is also non-zero and must not count as a clear (#48 hygiene)
- Exclude `fleet.sqlite*` from the upload and delete it before the wrapper exits | leave the sqlite in the artifact; move the db outside the log dir | the WAL can hold the emulator's attestation chain; the operator page still needs the db during the leg
- Widen the upload exclusions and the cert check to `.der` `.cer` `.pfx` `.jks` `.keystore` `.csr` beside `.pem` `.key` `.p12` `.crt` | keep the Phase 5 suffix list | those suffixes are also certificates or keys (#48 hygiene)
- Do not factory-reset or wipe to prove the flag | call `wipeData` or wipe the AVD | the proof is the dumpsys token `no_factory_reset`; a wipe would destroy the bench
- Cursor cloud agent on `build/p6-factory-reset` | wait for nimo; a `cursor/` branch name | nimo was offline; the issue named this branch
- Same path filters, one boot retry, timeout 45 minutes | a cron; a second retry; a self-hosted runner | Phase 5's filters and retry already bound the job; hosted KVM stays the runner
