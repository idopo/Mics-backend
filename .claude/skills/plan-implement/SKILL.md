---
name: plan-implement
description: Orchestrated plan → review → implement workflow for non-trivial features. Spawns a Plan sub-agent to design the implementation, a Review sub-agent to challenge it, then synthesizes and implements. Use for any feature or refactor that touches multiple files or services.
disable-model-invocation: false
context: fork
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, Agent
---

You are running a structured Plan → Review → Implement workflow for the MICS backend project.

## Workflow

### Step 1: Parse the request
Read the user's argument. If it's a backlog ID (e.g., `MICS-007`), read `.claude/backlog/<ID>-*.md` for full context. Otherwise use the description directly.

### Step 2: Plan (sub-agent)
Spawn an `Explore` sub-agent with this prompt:

```
You are the PLAN agent for a software engineering task on the MICS backend project.

Task: <TASK_DESCRIPTION>

Your job:
1. Explore the relevant code (use Glob, Grep, Read)
2. Produce a concrete implementation plan with:
   - Files to create or modify (with specific line numbers where insertions go)
   - Data model changes (if any)
   - API changes (if any)
   - Frontend changes (if any)
   - Order of operations (what to do first)
   - Risks or dependencies to watch for
3. Be specific — reference actual function names, line numbers, variable names
4. Do NOT write any code yet

Project context: see CLAUDE.md and .claude/docs/architectural_patterns.md
```

### Step 3: Review (sub-agent)
Spawn a second `Explore` sub-agent with the plan from Step 2:

```
You are the REVIEW agent for the MICS backend project. Your job is to challenge a proposed implementation plan.

Original task: <TASK_DESCRIPTION>

Proposed plan:
<PLAN_FROM_STEP_2>

Review this plan and identify:
1. Correctness issues — will this actually work given the codebase?
2. Missing steps — what did the plan forget?
3. Over-engineering — what is unnecessary?
4. Risks — what could break existing functionality?
5. Better alternatives — if there's a simpler way, say so

Be direct and specific. Reference file paths and line numbers where relevant.
End with: APPROVED (minor concerns noted), NEEDS_REVISION (specific changes needed), or REJECTED (fundamental problem).
```

### Step 4: Synthesize
Show the user:
- The Plan (summarized)
- The Review verdict and key concerns
- Your synthesized final plan (incorporating valid feedback)

Ask: **"Proceed with implementation? (yes / modify / cancel)"**

### Step 5: Implement
If approved, implement the synthesized plan using Edit/Write/Bash tools directly. Work through the plan step by step, announcing each file change. At the end, summarize what was done and whether the backlog task (if any) should be marked done.

## Context Tips

- Always read `.claude/docs/architectural_patterns.md` before planning — it describes 13 key patterns
- The dual ORM pattern (pattern 1) is the most common source of mistakes — check which ORM owns each table
- React API shapes in memory/MEMORY.md are verified; don't assume REST conventions
- If the task came from the backlog, update its status to `in-progress` before implementing
