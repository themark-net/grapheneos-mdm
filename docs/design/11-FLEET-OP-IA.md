# 11 — Fleet operator: information architecture

**Status:** Design DoD 2026-09-27 PT  
**PR:** [#34](https://github.com/themark-net/grapheneos-mdm/pull/34) · tip `a065ecd` (`a065ecd171d14a0139402f652203225984b495c5`)

---

## Places (one page, two modes)

```
┌─────────────────────────────────────────────────────────────┐
│ Header: product title + one operator context line           │
│ Nav: [Devices] [Groups]                                     │
├──────────────────┬──────────────────────────────────────────┤
│ LIST (left)      │ DETAIL (right)                            │
│ · rows / empty   │ · identity                               │
│ · selection      │ · facts from store/inventory             │
│                  │ · contextual levers                      │
│                  │ · desired JSON (power)                   │
│                  │ · danger zone (wipe / delete)            │
│                  │ · FAIL / status slot                     │
└──────────────────┴──────────────────────────────────────────┘
```

No separate Settings, Tags, Admin, or Docs surfaces in this chrome.

---

## Modes

| Mode | List content | Detail when selected | Detail when none selected |
|------|--------------|----------------------|---------------------------|
| **Devices** | Checked-in devices | Device identity + inventory + group assign + desired override + Wipe | Empty-state: point to check-in / Groups for waiting policy |
| **Groups** | Named groups | Group identity + members + desired editor + Delete | New-group form (name + default JSON shell) |

Tab press resets selection (current tip behavior) — keep: avoids stale cross-mode selection. Prefer auto-select first row when list non-empty (current tip).

---

## Objects & fields (operator-facing)

### Device (list row)

| Show | Source | Notes |
|------|--------|-------|
| deviceId | store | Primary label (mono) |
| group or “no group” | store | |
| packageCount | inventory | |
| attestationStatus pill | store | ok / none / missing / bad classes |
| osVersion · securityPatch · lastCheckinAt | inventory / store | |

### Device (detail)

| Region | Contents | Levers |
|--------|----------|--------|
| Identity | deviceId (h2), clientCn, desiredSource | — |
| Facts | last check-in, attestation + boot, OS/patch, location, users | — (read-only) |
| Group | select of known groups + “No group” | **Save group** |
| Desired | textarea of override-or-resolved JSON | **Save override**, **Clear override** |
| Packages | table packageName / version | — |
| Danger | Wipe consequence one-liner | **Wipe device…** |
| Status | `.error` / status strip | operate-or-FAIL |

### Group (list row)

| Show | Source |
|------|--------|
| name | store |
| deviceCount · updatedAt | store |

### Group (detail)

| Region | Contents | Levers |
|--------|----------|--------|
| Identity | name (h2) or “New group” | name input only when creating |
| Members | device id list (or “No devices assigned”) | — (assign from Devices) |
| Desired | textarea | **Save group** / **Create group** |
| Danger | Delete consequence | **Delete group** (existing only) |
| Status | FAIL / OK slot | |

---

## Resolution model (copy must match store)

Desired for a device = **device override** → else **group desired** → else **server default file**.

Operator copy in chrome:

- “Source: device / group / default” (short) — already on tip.
- Save override = write device row.
- Clear override = fall back to group then default.
- Save group = write group desired; members pick it up on resolve unless overridden.

Do **not** lecture adapters or sqlite paths in the window.

---

## Destructive keys (IA rule)

| Key / action | Where it lives | Gate |
|--------------|----------------|------|
| `commands[].type == "wipe"` | Desired JSON (device or group) | **Confirm before any write** — see wireframes |
| Dedicated wipe | Device danger zone | Confirm (preferred entry) |
| Delete group | Group danger zone | Type group name to confirm |
| `lock` / `reboot` | Desired JSON | No modal in this slice (non-erase); may add later |
| `disallowFactoryReset` | policyFlags | Not a wipe; no wipe modal |

**Rule:** Desired JSON remains for power users. Any Apply/Save path that would persist a wipe command **must** pass the confirm gate. Silent apply of wipe is FAIL for Reviewer.

---

## Navigation rules

1. Everything actionable is on the current detail for the selected object.
2. No global “command palette” or tag soup for wipe/group/desired.
3. Switching Devices ↔ Groups is the only top-level nav.
4. Member assignment: edit on **device** detail (device has one group). Group detail lists members read-only this slice.

---

## Copy tone (operator chrome)

- Short, imperative, factual.
- Empty states tell the next real step (check-in / create group).
- Status: queued / failed / missing — never “wiped ✓” without evidence from inventory/absence rules (see recover in journey + wireframes).
