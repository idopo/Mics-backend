---
name: gsd-toolkit-fda
description: "Use GSD to plan any ToolKit or FDA feature. Adds requirements to REQUIREMENTS.md, updates ROADMAP.md, then invokes /gsd:plan-phase."
disable-model-invocation: false
context: fork
allowed-tools: [Read, Write, Edit, Glob, Grep, Bash, Agent]
---

# GSD ToolKit / FDA Planning Skill

Use this skill whenever a new ToolKit or FDA feature needs to be planned.
This keeps all planning inside the GSD framework (`.planning/`) rather than
directly editing `.claude/docs/toolkit_fda_plan.md`.

## Workflow

1. **Understand the feature** — read `.planning/REQUIREMENTS.md` and `.planning/ROADMAP.md`
   to understand existing requirements and which phase the new feature belongs in.

2. **Add requirements** — append new requirement IDs (e.g., `VAR-XX`, `HW-XX`, `HOT-XX`)
   to `.planning/REQUIREMENTS.md` with phase assignment.

3. **Update ROADMAP.md** — add the new requirement IDs to the appropriate phase row(s).

4. **Plan the phase** — invoke `/gsd:plan-phase` for the target phase. GSD will research,
   plan, and review the implementation using the updated requirements.

## Key files

- `.planning/REQUIREMENTS.md` — canonical requirement list (add here first)
- `.planning/ROADMAP.md` — phase → requirements mapping (update after adding requirements)
- `.planning/phases/` — phase plan files created by `/gsd:plan-phase`
- `.claude/docs/toolkit_fda_plan.md` — READ ONLY reference doc; do not write plans here

## Requirement naming conventions

| Prefix | Domain |
|---|---|
| FDA | FDA JSON structure & loading |
| TRIG | Trigger assignment |
| HOT | Hot-reload |
| DB | Database schema |
| UI | Visual editor |
| PROTO | Protocol integration |
| VAR | Toolkit variant tracking |
| EDIT | Pi code editor |

## Invocation

/gsd-toolkit-fda <feature description>

Example: /gsd-toolkit-fda "add toolkit variant support for multi-Pi SEMANTIC_HARDWARE conflicts"
