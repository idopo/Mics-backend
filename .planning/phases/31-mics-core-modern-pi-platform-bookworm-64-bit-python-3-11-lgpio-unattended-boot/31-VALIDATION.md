---
phase: 31
slug: mics-core-modern-pi-platform-bookworm-64-bit-python-3-11-lgpio-unattended-boot
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-16
---

# Phase 31 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
>
> **Source of truth for design:** `31-RESEARCH.md` → `## Validation Architecture`.
> **Hard constraint:** every hardware capture is **USER-RUN**. The agent supplies the exact
> command, the user runs it on the Pi, the agent analyses the committed artifact. Never start or
> stop the pilot process, never run a Python file on the Pi, never run git on the Pi.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (`~/mics_core/pytest.ini` + `conftest.py` exist) |
| **Config file** | `~/mics_core/pytest.ini` |
| **Quick run command** | {to be filled by planner} |
| **Full suite command** | {to be filled by planner} |
| **Estimated runtime** | ~{N} seconds |

> ⚠ Wave 0 is unusually heavy: the 23 existing Pi test modules in `~/mics_core/tests/` have
> **never been executed anywhere**. Getting `pytest` green on the dev machine is a prerequisite
> for every downstream gate.

---

## Sampling Rate

- **After every task commit:** Run `{quick run command}`
- **After every plan wave:** Run `{full suite command}`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** {N} seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| {N}-01-01 | 01 | 1 | PLAT-{XX} | unit | `{command}` | ✅ / ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] Make the 23 existing `~/mics_core/tests/` modules run green on the dev machine
- [ ] {additional stubs for PLAT-XX — planner to fill}
- [ ] {shared fixtures — planner to fill}

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| GPIO pulse-width accuracy + jitter (before/after) | PLAT-{XX} | Requires physical Pi + capture; hard rule forbids the agent running anything on the Pi | {planner: cite the capture method from RESEARCH `## Validation Architecture`} |
| Unattended boot → pilot connects | PLAT-{XX} | Requires a real reboot of physical hardware | {planner: fill} |
| Clock-step coherence (24/7 claim, without waiting 24 h) | PLAT-{XX} | Requires forcing a system clock step on hardware | {planner: fill} |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < {N}s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
