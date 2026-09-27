# Design pack — Localhost fleet operator page

**Status:** Design DoD ready — 2026-09-27 PT  
**Owner:** Design Bot (Pleake Ink)  
**PR:** [#34 — Localhost fleet operator page](https://github.com/themark-net/grapheneos-mdm/pull/34)  
**Branch tip cited:** `a065ecd` (`a065ecd171d14a0139402f652203225984b495c5`) on `feat/fleet-ui`  
**Scope:** Loopback-only operator chrome for devices/groups + desired JSON; wipe confirm + recover. mTLS check-in untouched.  
**Not under:** pfy / Leasegrid / Jobbar HOLD.

Reviewer (`ui-is-the-app`) blocked MERGE-CLEAR for dogfood chrome without a `docs/design/` pack. This package is that pack. DevBot rebases in parallel; MERGE-CLEAR waits on pack + clean tip.

## Artifact index

| File | Contents |
|------|----------|
| [10-FLEET-OP-JOURNEY.md](10-FLEET-OP-JOURNEY.md) | Primary journey: view fleet → edit group desired → apply |
| [11-FLEET-OP-IA.md](11-FLEET-OP-IA.md) | Information architecture of the operator page |
| [12-FLEET-OP-WIREFRAMES.md](12-FLEET-OP-WIREFRAMES.md) | Contextual levers + wipe confirm / recover wireframes |
| [13-FLEET-OP-NON-GOALS.md](13-FLEET-OP-NON-GOALS.md) | Loopback-only; mTLS untouched; out of slice |
| [14-FLEET-OP-DEVBOT-HANDOFF.md](14-FLEET-OP-DEVBOT-HANDOFF.md) | Must-fix for MERGE-CLEAR; tip SHA; Tests + UI DoD; FAIL |

## Doctrine (locked)

- **Never ask what we already know** — prefill/infer from selection and store.
- **Contextual levers** — every control tied to what’s on screen; no settings dig / tag soup.
- **UI is the app** — product chrome = operator copy only (no design notes, ADR theology, adapter lectures, honest-state dumps, localhost board URLs in the window).
- **Operate-or-FAIL** — every visible control runs its action or shows FAIL in-window.

## UI DoD (paste)

UI: Design-in-loop. Pack in docs/design/ before product UI. Never ask what we know. Levers stay contextual to the current view. Lab bolts OK; product/dogfood UI needs Design pass. UI is the app.

## Tests DoD (paste)

Tests: prefer E2E/integration/operate-or-FAIL (Trophy). No tautological or implementation-detail unit sprawl. Unit tests only for shaky behavior; must be able to fail with the bug present (sociable where possible). For each risk: how could this fail + how do we recover.
