# Autonomous decisions — 2026-10-16

Phase 7.1, issue #53. One line each: choice | alternatives | why

- Phase 7.1 is the six follow-ups in one pull request | six pull requests; close #53 in this pull request | the items are hygiene on the merged Phase 7 job; #53 stays open for the Cursor Approval waiver
- After-false `device_policy` needs `UserRestrictionPolicyKey` or a non-empty indented line under `Local Policies:` or `Global Policies:` | accept the header line alone | a header with no body is not a dumpsys section and must not count as a clear
- `policy_restriction.py` exits 2 when it cannot read the input file | keep exit 1 | a read error is not "not applied" and must not count as a clear
- `CLEAR_LEG_STUB` treats `SERIAL=` and `ANDROID_SERIAL=` as set (`${VAR+x}`) | treat empty as unset | a set-but-empty serial is still a caller target
- `accept_cleared_restriction` saves and restores errexit | leave the unconditional `set -e` | a caller with errexit off must not have it turned on
- Ref #53 stays open for the Cursor Approval waiver | close #53 when this pull request merges | the waiver closes when a green Cursor Approval lands on main; this pull request does not close it

## Handoff

Phase 7 pull request #52 merged to main at `8a7164c`. emulator-policy run 38446617330 (https://github.com/themark-net/grapheneos-mdm/actions/runs/38446617330) on `8744c58` is green. This branch is Phase 7.1, issue #53. After this pull request lands, org-can-do work is exhausted. The next step is the founder-only Pixel/GrapheneOS stop. The image is an AOSP ATD emulator. Attestation is not asserted. Issue #53 stays open for the Cursor Approval waiver. Draft PR #42 stays untouched. Issue #8 stays closed.
