# Phase 33 — RETIRED 2026-09-06

Merged into **Phase 32: Unattended operation — fail-safe outputs, crash classification, and
policy-driven resume**, at the user's direction.

Phase 32 and 33 were two halves of one problem and were being designed against each other. The
binding argument: **you must not resume onto a rig whose outputs are in an unknown state.**
`_set_initial_state()` only touches what the *new* run instantiates, so a pin or motor energised by
the crashed run that the resumed task does not declare survives the resume untouched. De-energising
is a precondition for a safe resume, not cleanup after a crash.

This phase's content is now Phase 32 Slices 2-4, requirements **RECOV-01…06**.

**One correction carried across:** the old Phase 33 entry claimed *"`session_runs` today has only
`RUNNING`"*. That was stale. `SessionRunStatus` already has `RUNNING/STOPPED/COMPLETED/ERROR/PENDING`,
`error_type`/`error_message` already exist and carry `TaskError`/`OrchGatewayError`/`WatchdogTimeout`,
the orchestrator watchdog already marks abrupt ends, `run_progress` already records trial and step,
and `start-on-pilot` already accepts `mode: "resume"`. See the ROADMAP's "What already exists" table.

Nothing here is planned or executed. Do not plan phase 33 — plan phase 32.
