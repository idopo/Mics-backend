# STATE: MICS Backend

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-03-15)

**Core value:** Researchers can define, modify, and deploy behavioral task logic without writing Python or restarting the Pi.
**Current focus:** Planning complete — ready to begin Phase 1

---

## Current Position

**Milestone:** M1 — ToolKit + FDA Redesign + Pi Code Editor
**Phase:** Not started (Phase 1 next)
**Progress:** ░░░░░░░░░░ 0%

---

## Decisions Made

| Decision | Made | Rationale |
|---|---|---|
| Hardware_Event logging is unconditional | 2026-03-15 | execute_trigger() always dispatches Hardware_Event; trigger_assignments only adds semantic layer |
| FDA v2 JSON with entry_actions | 2026-03-15 | Declarative state bodies; no exec() or pickle needed |
| SEMANTIC_HARDWARE in toolkit | 2026-03-15 | Decouples logic from physical wiring; same JSON on different rigs |
| Hot-reload is next-entry safe | 2026-03-15 | Method refs replaced between next() calls; no state interruption |
| Monaco + asyncssh for Pi editor | 2026-03-15 | Jupyter/code-server too heavy for Pi |
| _state_method_registry keyed by name string | 2026-03-15 | Python bound method identity is fragile after rebuild |
| Phase 5 independent of Phases 1-4 | 2026-03-15 | Pi editor viewer has no dependency on toolkit/FDA work |

---

## Blockers

None currently.

---

## Open Questions

- OR conditions between FDA transitions — deferred to v2; AND-only is sufficient
- Multi-Pi Pi editor support — deferred to v2; single Pi host for now
- Audit log for Pi exec actions — deferred to v2

---

## Next Actions

1. `/gsd:discuss-phase 1` — gather context before planning Phase 1 (Pi Foundation)
   - OR: `/gsd:plan-phase 1` — skip discussion, go straight to atomic task plans
2. Phase 5 (Pi Editor: Viewer) can be planned and executed in parallel with Phase 1

---
*Last updated: 2026-03-15 after GSD initialization*
