# 13 — Fleet operator: non-goals

**Status:** Design DoD 2026-09-27 PT  
**PR:** [#34](https://github.com/themark-net/grapheneos-mdm/pull/34) · tip `a065ecd` (`a065ecd171d14a0139402f652203225984b495c5`)

---

## Hard non-goals (this slice)

| Out | Why |
|-----|-----|
| Bind outside loopback | `ui_server.py` must refuse non-localhost hosts (already on tip). No LAN/public operator UI. |
| Change mTLS check-in | Phones stay on the mutual-TLS port / `lab_checkin.py`. UI reads the same sqlite; does not accept phone traffic. |
| Replace Ansible sync | `ansible_sync.py` + `group_vars` remain valid; UI is parallel operator path for lab DB. |
| Production control plane | FastAPI/Go plane, step-ca UX, multi-tenant auth — future. |
| Enrollment / QR / SetupWizard | Covered by enrollment docs + #8 park; not this chrome. |
| Attestation policy UX | Show status pill only; no challenge issuance controls in UI this slice. |
| APK catalog / signing UI | Catalog stays server-side. |
| Fake seeded devices | Empty DB = empty-state copy only. |
| Design notes / ADR / board URLs in the window | UI is the app — operator copy only. |
| pfy / Leasegrid / Jobbar work | Wrong product. |
| Wipe as “edit JSON + meta note only” | **Forbidden.** Confirm + recover required (Design decision). |
| Silent apply of wipe via Save | **Forbidden.** Gate on Save override / Save group / dedicated Wipe. |
| Claiming device is wiped without evidence | No fake green. Queued / failed / missing only. |

---

## Soft non-goals (defer unless trivial)

| Defer | Note |
|-------|------|
| Confirm modal for `reboot` / `lock` | Destructive-ish but non-erase; wipe is the required gate this slice |
| Bulk multi-select wipe | One device or one group at a time |
| Edit membership from group detail | Assign from device detail |
| Undo wipe after phone executed | Factory reset is one-way; recover = re-enroll (docs), not UI undo |
| Light theme / i18n | Dark lab chrome on tip is fine |
| AuthN on loopback UI | Loopback bind is the boundary this slice |

---

## In-scope reminder (so non-goals aren’t misread)

- Devices + Groups tabs, list/detail IA
- Group desired edit + apply
- Device group assign + override edit/clear
- Wipe confirm (device id or group name type-to-confirm) + recover status strip
- Operate-or-FAIL on every visible control
- Pack lives in `docs/design/` (this package)

---

## Merge hygiene

- PR tip may rebase while Design lands; cite `a065ecd` as Design baseline; DevBot lands pack-aligned UI on clean tip.
- Do not re-introduce ansible sync files as a second copy if already on main (PR body already notes this).
