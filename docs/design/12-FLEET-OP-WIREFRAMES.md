# 12 — Fleet operator: wireframes & contextual levers

**Status:** Design DoD 2026-09-27 PT  
**PR:** [#34](https://github.com/themark-net/grapheneos-mdm/pull/34) · tip `a065ecd` (`a065ecd171d14a0139402f652203225984b495c5`)

Iron: never ask known facts; every lever tied to the selection on screen.

---

## W1 — Devices: list + detail (baseline)

```
┌ GrapheneOS MDM ──────────────── Lab fleet on this machine. Phones check in over mTLS. ┐
│ [Devices●] [Groups]                                                                    │
├─────────────────────┬──────────────────────────────────────────────────────────────────┤
│ pixel-7             │ pixel-7                                                          │
│ pixels · 12 pkgs ·  │ Certificate … · source: group                                    │
│   [ok]              │ Last check-in …   Attestation [ok] …                             │
│ 16 · patch … · …    │ Group [ pixels ▼ ] [ Save group ]                                │
│                     │                                                                  │
│ pixel-8             │ Desired state                                                    │
│ …                   │ ┌ JSON …………………………………………………………… ┐                                 │
│                     │ └…………………………………………………………………┘                                 │
│                     │ [ Save override ] [ Clear override ]                             │
│                     │ (status / FAIL)                                                  │
│                     │ Installed packages (table)                                       │
│                     │ ── Danger ─────────────────────────────────                      │
│                     │ Factory-reset this device on next check-in.                      │
│                     │ [ Wipe device… ]                                                 │
└─────────────────────┴──────────────────────────────────────────────────────────────────┘
```

**Levers (device selected):**

| Control | Prefill / context | Action |
|---------|-------------------|--------|
| Group `<select>` | Options = known groups; current selected | — |
| Save group | deviceId from selection | POST group assign / clear |
| Desired textarea | override if present else resolvedDesired | — |
| Save override | deviceId + parsed JSON | POST desired **via wipe gate** |
| Clear override | deviceId | DELETE desired |
| Wipe device… | deviceId shown in confirm | Opens W4 (no JSON edit required) |

**Remove from chrome (tip cleanup):** long meta lecture “A wipe command in this JSON runs…” as the *only* wipe UX. Replace with Danger lever + gate. Short hint OK: “Wipe is under Danger — or confirm if JSON includes wipe.”

---

## W2 — Groups: edit desired → apply

```
│ [Devices] [Groups●]                                                                    │
├─────────────────────┬──────────────────────────────────────────────────────────────────┤
│ pixels              │ pixels                                                           │
│ 2 devices · …       │ pixel-7, pixel-8                                                 │
│                     │ ┌ group desired JSON ………………………… ┐                             │
│ lab                 │ └……………………………………………………………┘                             │
│ 1 device · …        │ [ Save group ]  [ Delete group ]                                 │
│                     │ (status / FAIL)                                                  │
└─────────────────────┴──────────────────────────────────────────────────────────────────┘
```

**Levers:**

| Control | Prefill | Action |
|---------|---------|--------|
| Create (no selection) | Name empty; JSON shell schemaVersion 1 | PUT new |
| Save group | name + members from store; JSON from editor | PUT **via wipe gate** |
| Delete group | name | Type-to-confirm group name → DELETE |

Member list is read-only here; assignment stays on device detail.

---

## W3 — Empty states

**Devices empty list:**  
“No phone has checked in yet. The list fills after a mutual-TLS check-in against this database.”

**Devices empty detail (no selection):**  
“Create a group on the Groups tab if you want a shared desired state waiting for the first device.”

**Groups empty list:**  
“No groups yet.” + detail = New group form.

No sample/seeded rows.

---

## W4 — Wipe confirm (device)

Triggered by **Wipe device…** OR Save override/Save group when parsed JSON contains `commands` entry with `type: "wipe"`.

```
┌ Confirm wipe ──────────────────────────────────────────┐
│ This factory-resets the device on its next check-in.   │
│ It cannot be undone from this page.                    │
│                                                        │
│ Device   pixel-7          ← prefilled, not an ask      │
│ Group    pixels           ← if any                     │
│ Source   device override / group / …                   │
│                                                        │
│ Type the device id to confirm:                         │
│ [ pixel-7____________ ]                                │
│                                                        │
│ [ Cancel ]              [ Wipe on next check-in ]      │
│ (primary disabled until input === deviceId)            │
└────────────────────────────────────────────────────────┘
```

**Rules:**

1. Identity fields are display-only from selection — never “which device?” prompts.
2. Confirm button disabled until type-to-confirm matches `deviceId` exactly.
3. Cancel closes modal; editor/network unchanged.
4. On confirm from dedicated Wipe: write desired that includes a wipe command (merge into current override or set override with minimal wipe payload). Prefer: take current resolved/override JSON, ensure a wipe command with a new `id`, Save override path.
5. On confirm from JSON Save: proceed with the pending PUT/POST that was intercepted.
6. After success: close modal; status strip → **Wipe queued** (warn), not green “Wiped”.

---

## W5 — Wipe confirm (group)

When Save group JSON contains wipe:

```
┌ Confirm wipe for group ────────────────────────────────┐
│ Saving this group queues a factory reset for every     │
│ member on their next check-in.                         │
│                                                        │
│ Group    pixels                                        │
│ Members  pixel-7, pixel-8     ← full list from store   │
│ Count    2                                             │
│                                                        │
│ Type the group name to confirm:                        │
│ [ pixels_____________ ]                                │
│                                                        │
│ [ Cancel ]         [ Wipe all members on check-in ]    │
└────────────────────────────────────────────────────────┘
```

If member list is empty: still allow save of wipe-in-JSON (policy waiting for future members) but copy must say “No devices assigned now — wipe runs when a device in this group checks in.” Type-to-confirm remains group name.

---

## W6 — Recover / status strip (honest)

After wipe request or on device detail when resolved desired contains wipe:

| State | How detected | Copy (warn/bad) | Operator next step |
|-------|--------------|-----------------|--------------------|
| **Queued** | Desired (override or resolved) has wipe command; device still in list; recent check-in predates save or inventory still present | “Wipe queued — runs on next check-in.” | Wait / trigger check-in on phone |
| **Failed to queue** | API error on save/wipe | FAIL from server `error` | Fix / retry; no claim of wipe |
| **Device missing** | GET device 404 / not in list after refresh | “Unknown device — not in this database.” | Refresh; verify check-in DB |
| **Still present after expected wipe** | Device checks in again with inventory; wipe command still in desired or cleared by agent semantics | “Device checked in again. Wipe may not have applied — inspect desired commands.” | Re-open confirm or clear wipe command |
| **Command cleared** | Operator saved desired without wipe | Clear warn strip | — |

**Never:** green “Device wiped” solely because Save returned 200. Loopback UI cannot observe DPM wipe completion directly this slice; honesty = queued / failed / missing / still-present.

---

## W7 — Delete group confirm

```
│ Delete group pixels?                                   │
│ Members become ungrouped (per store). Desired removed. │
│ Type group name: [ ________ ]                          │
│ [ Cancel ]  [ Delete group ]                           │
```

Tip today deletes with no confirm — add type-to-confirm (group name).

---

## Contextual levers map (summary)

| On screen | Lever | Must not ask |
|-----------|-------|--------------|
| Device detail | Save group, Save/Clear override, Wipe device… | device id, cert, inventory fields |
| Group detail | Save/Create, Delete | group name (edit), member list |
| Wipe modal | type-to-confirm, Cancel, confirm | which device/group — already shown |
| Any Apply | parse JSON → wipe gate | “did you mean wipe?” after silent save |

---

## Operate-or-FAIL (every control)

| Control | Success | FAIL |
|---------|---------|------|
| Save group (device) | Detail refresh; source/group updated | `.error` text |
| Save override | Refresh; source=device | parse / API error in `.error` |
| Clear override | Refresh; source group/default | API error |
| Save group (groups) | Refresh updatedAt | parse / API / wipe cancel |
| Wipe confirm | Queued status | mismatch / API error |
| Delete group | Selection cleared; list refresh | mismatch / API |
| Tab / row select | Opens detail | load error in detail |

No control may appear to succeed while only logging to console.
