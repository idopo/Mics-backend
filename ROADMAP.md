# MICS Backend — Roadmap

Priorities in order. Each item links to a backlog task for full context.

## Now (High Priority)

### MICS-001 — ToolKit + FDA Phase 1
Pi tasks load their state machine from JSON; HANDSHAKE includes FLAGS field.
**Context:** `.claude/backlog/MICS-001-toolkit-fda-phase1.md`

### MICS-002 — ToolKit + FDA Phase 2
DB split (`task_toolkits` vs `task_definitions`) + new API endpoints.
**Context:** `.claude/backlog/MICS-002-toolkit-fda-phase2.md` *(to be created)*

## Soon (Medium Priority)

### MICS-003 — Visual FDA Editor (Phase 3)
React-flow based GUI to assemble FDA graphs; stores as JSON task definition.
**Context:** `.claude/backlog/MICS-003-toolkit-fda-phase3.md` *(to be created)*

### MICS-004 — Subject / Project / Experiment Hierarchy
Three-level data organization above the current flat subject list.
**Context:** `.claude/backlog/MICS-004-subject-project-experiment.md`

## Backlog

See `.claude/backlog/BACKLOG.md` for all items.

## Done

- React SPA initial implementation (Index, Subjects, Protocols, PilotSessions, SubjectSessions pages)
- Session overrides modal (per-step param overrides, run history)
- Subject filter with typeahead chips
- Stop run endpoint wired to correct API path
