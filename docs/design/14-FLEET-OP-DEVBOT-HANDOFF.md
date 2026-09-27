# 14 — Fleet operator → DevBot handoff (MERGE-CLEAR)

**Status:** Design DoD 2026-09-27 PT  
**PR:** [#34 — Localhost fleet operator page](https://github.com/themark-net/grapheneos-mdm/pull/34)  
**Cite tip (Design baseline):** `a065ecd` (`a065ecd171d14a0139402f652203225984b495c5`) on `feat/fleet-ui`  
**Implement tip:** current `feat/fleet-ui` HEAD after the wipe gate, parent `d447326` (device page split into reported and configured). Design baseline behavior was `a065ecd`. The earlier rebase parent was `53758b3050e3ef3cba8e1b2c8b0a3959140a0153`.  
**Design package:** `docs/design/` files 10–13 (this handoff = 14) + `README.md`  
**Owner:** Design Bot (Pleake Ink) — report back to Design Bot / parent only; do **not** ping PM/CEO/Mark from this pack.

DevBot is rebasing in parallel. MERGE-CLEAR waits on: **this pack landed** + **clean tip** + Reviewer PASS on wipe gate.

---

## Do not

- Implement outside PR #34 scope (enrollment, mTLS changes, production plane, pfy/Leasegrid/Jobbar).
- Bind `ui_server` off loopback.
- Leave wipe as “JSON note only.”
- Seed fake devices into empty DB.
- Put design notes / ADR theology / board URLs in the operator window.
- Contact Mark / drip PM from DevBot for this slice unless PM already owns MERGE-CLEAR.

---

## Spec citations (normative)

| Doc | Implement |
|-----|-----------|
| [10-FLEET-OP-JOURNEY.md](10-FLEET-OP-JOURNEY.md) | View fleet → edit group desired → apply; FAIL table |
| [11-FLEET-OP-IA.md](11-FLEET-OP-IA.md) | Places, objects, destructive-key rule |
| [12-FLEET-OP-WIREFRAMES.md](12-FLEET-OP-WIREFRAMES.md) | Levers W1–W7; wipe confirm; recover strip |
| [13-FLEET-OP-NON-GOALS.md](13-FLEET-OP-NON-GOALS.md) | Loopback-only; mTLS untouched |
| `protocol/desired-state.schema.json` | `commands[].type` includes `wipe` |
| Tip `server/ui/index.html` + `server/ui_server.py` | Baseline chrome/API to extend |

---

## Tight DoD (must prove)

1. **Pack present** under `docs/design/` (10–14 + README) on the PR tip.
2. **Primary journey works:** Devices list → Groups → edit desired → Save group → device detail shows `desiredSource: group` and resolved flags.
3. **Contextual levers only** — no new settings surface; group assign / desired / wipe live on current detail.
4. **Wipe gate (device):**  
   - Dedicated **Wipe device…** on device detail Danger zone.  
   - Confirm modal prefills device id (and group if any); type-to-confirm device id; confirm disabled until match.  
   - Cancel = no write.
5. **Wipe gate (JSON):** Save override / Save group that would persist `commands` containing `type: "wipe"` **intercepts** and opens the same confirm (device id or group name + member list). No silent apply.
6. **Recover strip:** After successful wipe queue → warn “Wipe queued — runs on next check-in.” API failure → FAIL in-window. Unknown device → FAIL missing. **No fake green “wiped.”**
7. **Delete group** type-to-confirm group name (tip currently unconfirmed).
8. **Loopback refuse** preserved (`host` not localhost → exit).
9. **Empty DB** empty-state copy only — no sample row.
10. **Operate-or-FAIL** on every visible control (errors in detail `.error` / status).
11. **Tests** below green; no tautological sprawl.
12. **mTLS check-in codepath unchanged** (no behavioral edit required for MERGE-CLEAR beyond shared sqlite read).

---

## Wipe design (locked decisions)

| Decision | Spec |
|----------|------|
| Not JSON-note-only | Danger lever + confirm required |
| Prefill | Selection identity (device id / group name + members) |
| Confirm gesture | Type-to-confirm exact id/name; then explicit confirm button |
| Power-user JSON | Allowed; destructive wipe key still hits gate on Apply |
| Group wipe | Confirm lists all member device ids from store |
| Success meaning | “Queued for next check-in” only |
| Recover | Queued / failed / missing / still-present copy per W6 |

Minimal wipe payload when using dedicated button (suggested, non-binding shape):

```json
{
  "schemaVersion": 1,
  "requiredPackages": [],
  "policyFlags": {},
  "commands": [{ "type": "wipe", "id": "<opaque-id>" }]
}
```

Prefer merging wipe into the current override/resolved document so packages/flags are not accidentally wiped from desired when operator only wanted a wipe command — **merge commands array; keep other keys** unless operator’s JSON Save is the path.

---

## Test checklist (minimum)

Trophy: prefer integration/E2E against `ui_server.serve` + temp sqlite (extend `server/tests/test_ui_server.py`).

| # | Risk | How it fails | Test / recover |
|---|------|--------------|----------------|
| T1 | Page + list/edit regression | Group assign / desired resolve breaks | Existing test_page_lists_and_edits_a_device still green; recover: fix API |
| T2 | Wipe JSON silent apply | Save override with wipe skips confirm | E2E/UI logic: detect wipe in body; without confirm path, handler must not persist — or integration test of gate helper `contains_wipe(desired) -> bool` + apply rejected until `confirm=true` token if API-level; **UI must not POST until confirm**. Recover: show modal |
| T3 | Type mismatch | Confirm enabled on wrong id | Assert confirm disabled / no network when input ≠ deviceId |
| T4 | Group wipe members | Confirm omits a member | Confirm payload/list includes all `deviceIds` from `get_group` |
| T5 | Queued honesty | UI shows success=wiped on 200 | Assert status copy contains queued/waiting — not “wiped” as done |
| T6 | Unknown device | Open missing id | 404 → FAIL in detail |
| T7 | Invalid JSON | Save garbage | FAIL in `.error`; store unchanged |
| T8 | Loopback | `--host 0.0.0.0` | Process exits refuse |
| T9 | Empty DB | list devices | Empty-state string present; no fabricated device id |

Unit tests only for shaky pure helpers (e.g. `contains_wipe`, merge wipe command) — must fail if helper lies. Sociable where possible.

---

## UI DoD (paste into Reviewer / MERGE-CLEAR)

UI: Design-in-loop. Pack in docs/design/ before product UI. Never ask what we know. Levers stay contextual to the current view. Lab bolts OK; product/dogfood UI needs Design pass. UI is the app.

## Tests DoD (paste)

Tests: prefer E2E/integration/operate-or-FAIL (Trophy). No tautological or implementation-detail unit sprawl. Unit tests only for shaky behavior; must be able to fail with the bug present (sociable where possible). For each risk: how could this fail + how do we recover.

---

## PASS / FAIL for Reviewer

**PASS when:**

- `docs/design/10`–`14` + README on tip  
- Wipe cannot be applied without confirm (dedicated + JSON paths)  
- Recover strip honest (queued / FAIL / missing)  
- Primary journey group edit → apply works  
- Loopback-only + empty-state preserved  
- Tests T1–T9 (or equivalent) green  
- Tip clean for merge (rebase done)

**FAIL when:**

- Wipe still “edit JSON with a note” only  
- Silent Save of wipe  
- Fake green wiped  
- Asking operator to re-enter known device/group identity outside type-to-confirm  
- mTLS check-in rewritten  
- Design pack missing or chat-only  

---

## Implementation sketch (non-binding)

1. Land design files (already staged by Design) on branch.  
2. `index.html`: Danger zone + modal markup; `containsWipe(obj)`; intercept Save handlers; status strip helper.  
3. Dedicated Wipe: merge wipe command into override via existing POST desired.  
4. Delete group: confirm modal.  
5. Extend `test_ui_server.py` (+ small JS-free tests for wipe detection if logic moved server-side optional). Server-side optional `X-Confirm-Wipe: <id>` is **not required** if UI gate is solid and loopback-only; prefer UI gate this slice.  
6. Rebase onto main; keep PR body accurate (UI + get_group only if ansible already merged).

---

## Tip / rebase note

Design baseline was **`a065ecd`**. Implement tip is current `feat/fleet-ui` HEAD (wipe confirm on the reported/configured device page + this pack), parent `d447326`, rebased through `53758b3`. MERGE-CLEAR needs a clean mergeable tip + this DoD.
