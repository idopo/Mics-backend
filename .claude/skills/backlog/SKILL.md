---
name: backlog
description: Manage the MICS project task backlog. Add new tasks with full context, list current items, update status, or view a specific task. Use this for any backlog/task management request.
disable-model-invocation: false
context: fork
allowed-tools: Read, Write, Edit, Glob, Bash
---

You are managing the MICS backend project backlog stored in `.claude/backlog/`.

## Backlog Structure

- `.claude/backlog/BACKLOG.md` — index file with all tasks (one line per task: ID, status, title)
- `.claude/backlog/<ID>-<slug>.md` — individual task file with full context

## Task File Format

```markdown
---
id: MICS-XXX
title: Short title
status: todo | in-progress | done | blocked
priority: high | medium | low
area: api | orchestrator | web_ui | react | pi | infra | design
created: YYYY-MM-DD
---

## Goal
One paragraph: what needs to be done and why.

## Context
What you need to know to implement this without re-exploring the codebase.
Include: relevant file paths, line numbers, API shapes, constraints, related tasks.

## Acceptance Criteria
- [ ] Specific, verifiable outcome
- [ ] Another outcome

## Implementation Notes
Optional: preferred approach, gotchas, things to avoid.
```

## Commands

Parse the user's argument to determine the command:

### `/backlog add <description>`
1. Read `BACKLOG.md` to determine the next ID (e.g., MICS-007)
2. Ask the user for any missing info (area, priority) if not obvious from description
3. Create the task file with full context — research the codebase to fill in relevant file paths and constraints
4. Append a line to `BACKLOG.md`: `| MICS-XXX | todo | <title> | <area> | <priority> |`
5. Confirm creation with the task ID

### `/backlog list`
Read `BACKLOG.md` and display all tasks grouped by status (in-progress first, then todo, then blocked, then done).

### `/backlog view <ID>`
Read the task file for that ID and display it fully.

### `/backlog update <ID> <status>`
Update the `status:` field in the task file and the status column in `BACKLOG.md`.

### `/backlog done <ID>`
Set status to `done` in both task file and `BACKLOG.md`.

### No argument / help
Show a brief usage summary of available commands.

## Context Preservation Principles

When adding a task, be generous with context in the task file:
- Link to specific files and line numbers (e.g., `api/main.py:634`)
- Include relevant API shapes or data structures
- Note which architectural patterns (from `.claude/docs/architectural_patterns.md`) apply
- Cross-reference related tasks by ID
- Include any decisions or constraints discussed in this conversation

The goal: a future Claude session should be able to pick up the task file and implement it with zero additional exploration.
