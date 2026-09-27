# 10 — Fleet operator: primary journey

**Status:** Design DoD 2026-09-27 PT  
**PR:** [#34](https://github.com/themark-net/grapheneos-mdm/pull/34) · tip `a065ecd` (`a065ecd171d14a0139402f652203225984b495c5`)  
**Audience:** Operator on the lab host running `ui_server.py` (loopback only)

---

## One-liner

View the fleet → open a group → edit its desired state → Apply (with wipe gated) → see honest result on the same page.

---

## Actors & surfaces

| Actor | Surface | Notes |
|-------|---------|-------|
| Lab operator | Browser at loopback UI (`ui_server.py`) | Same sqlite as mTLS check-in `--db` |
| Phone (agent) | mTLS check-in | **Out of this chrome** — unchanged |
| Ansible sync | CLI `ansible_sync.py` | Parallel path; UI does not replace it |

---

## Primary journey (happy path)

### J1 — View fleet

1. Operator starts `python3 ui_server.py --db fleet.sqlite --desired desired-state.example.json`.
2. Opens the page. Header: product title + one-line operator context (“Lab fleet on this machine…”). No board URLs, no design notes.
3. **Devices** tab selected by default.
4. Left list shows devices that have checked in (id, group, package count, attestation pill, last check-in). Empty DB → empty-state copy pointing at check-in filling the list — **no seeded fake row**.
5. Selecting a row opens detail: identity + inventory summary + group assign + desired editor.

**Never ask:** device id, cert CN, last check-in, attestation — already on the row/detail.

### J2 — Edit group desired

1. Operator switches to **Groups**.
2. Left list: groups (name, device count, updated). Empty → “No groups yet” + create form in detail.
3. Select a group (or create one with name + JSON shell prefilled from known schema defaults: `schemaVersion: 1`, empty `requiredPackages`, empty `policyFlags`).
4. Detail shows: group name as title, member device ids (prefilled from store), desired JSON editor loaded from group desired.
5. Operator edits JSON (packages, policyFlags, non-destructive commands).

**Never ask:** group name when editing existing; member list; schemaVersion defaults on create.

### J3 — Apply

1. Operator clicks **Save group** / **Apply** (label: **Save group** for create/update — same control).
2. Client validates JSON parse; on fail → FAIL in-window under the editor (no toast-only success fiction).
3. **Destructive gate (wipe):** if parsed `commands` contains any `{ "type": "wipe", ... }`, **do not** PUT yet — open wipe confirm (see [12-FLEET-OP-WIREFRAMES.md](12-FLEET-OP-WIREFRAMES.md) W4–W5). Confirm identity is the **group name** + listed member device ids.
4. On confirm (or no wipe present): PUT `/api/groups/<name>` with body.
5. Success → stay on group detail; show brief in-window OK (“Saved”) and refreshed `updatedAt` / member list. No navigation away.
6. API 4xx/5xx → FAIL copy from `error` body in the detail error slot. No fake green.

### J4 — Verify on a device (optional continuation)

1. Switch to Devices → select a member device.
2. Detail shows `desiredSource: group` and resolved desired reflecting the save (read-only resolve view or editor showing override-or-resolved per current PR behavior).
3. Assign group from device detail if needed: select + **Save group** — contextual to that device.

---

## Secondary journeys (same chrome)

| Journey | Steps | Notes |
|---------|-------|-------|
| Device override | Devices → select → edit desired → **Save override** | Wipe in JSON → same confirm gate, identity = **device id** |
| Clear override | **Clear override** | Returns to group then default; confirm only if clearing would drop a pending wipe command the operator still sees as active (optional soft confirm — see wireframes) |
| Wipe device (dedicated) | Devices → select → **Wipe device…** | Preferred path vs JSON; opens confirm with device id prefilled |
| Delete group | Groups → select → **Delete group** | Confirm with group name type-to-confirm; unassigns membership per store behavior |
| Empty fleet | Open page with empty DB | Empty states only — create group still available on Groups tab |

---

## Pain → target (vs tip `a065ecd` chrome)

| Pain on tip | Target |
|-------------|--------|
| Wipe is a sentence in meta copy under the JSON editor | Dedicated **Wipe device…** + confirm gate; JSON wipe intercepted on Apply |
| Apply with `"type":"wipe"` succeeds silently | Confirm modal → then apply; cancel leaves editor unchanged |
| No recover / FAIL story after wipe requested | Status strip: wipe queued / wipe failed / device missing — honest, in-window |
| Group wipe via JSON would hit N devices with no list | Confirm lists every member device id from selection/store |

---

## FAIL criteria (journey-level)

| Failure | Operator sees | Recover |
|---------|---------------|---------|
| Invalid JSON on Apply | Red error under editor; no save | Fix JSON; Apply again |
| Unknown / missing group on save | FAIL from API | Re-select from list / recreate |
| Wipe confirm dismissed | No network write | Edit or leave |
| Wipe confirm: typed id mismatch | Confirm disabled / FAIL “doesn’t match” | Type exact id shown |
| Wipe applied; device never checks in | Detail: “Wipe queued — waiting for check-in” (warn), not green “wiped” | Wait / trigger check-in on device; or clear wipe command via non-wipe save |
| Device row gone / 404 on open | FAIL “unknown device” in detail | Refresh list; check mTLS DB |
| Server refuse bind / page load fail | Error in detail on first load | Restart `ui_server.py` on loopback |

---

## Out of journey

mTLS enrollment, Ansible sync CLI, attestation challenge issuance, APK catalog, production control plane — see [13-FLEET-OP-NON-GOALS.md](13-FLEET-OP-NON-GOALS.md).
