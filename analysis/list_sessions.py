"""List day-based sessions per mouse and task: date and trial count.

Uses the canonical day-based session grouping (A.group_by_day_session): one
session == one subject + one lab-local calendar day, same-day files merged.
Writes results/session_inventory.csv and prints a per-mouse/per-task table.
"""

from __future__ import annotations

import csv
from pathlib import Path

import appetitive_analysis as A
import generalization_analysis as G
import extinction_analysis as E

RESULTS = Path(__file__).resolve().parent / "results"
OUT = RESULTS / "session_inventory.csv"
DOC = RESULTS / "SESSIONS.md"

TASKS = ("appetitive", "generalization", "extinction")


def _rows_for(task_label, subjects_by_mouse, fetch, segment):
    """One row per (mouse, day-session): date, n_trials, valid-band flag.

    All of a mouse's subject strings are pooled BEFORE grouping, so events from
    different files/subject-strings on the same calendar day merge into one
    session (a mouse is identified by name, one session per day)."""
    rows = []
    for mouse in sorted(subjects_by_mouse, key=lambda m: int(m[1:])):
        events = []
        for subject in subjects_by_mouse[mouse]:
            events += fetch(subject)
        by_session = A.group_by_day_session(events)
        for idx in sorted(by_session):  # keys are chronological 1..N
            evs = by_session[idx]
            n = len(segment(evs))
            rows.append({
                "task": task_label, "mouse": mouse, "session": idx,
                "date": A._lab_day(evs[0]["epoch"]), "n_trials": n,
                "valid": "yes" if A.session_len_ok(n) else "no",
            })
    return rows


def collect() -> list[dict]:
    rows = []
    # Appetitive (tone): one subject string per mouse.
    app = {A.short_name(s): [s] for s in A.discover_subjects()}
    rows += _rows_for("appetitive", app, A.fetch_events, A.segment_trials)
    # Generalization (light): mouse -> its GenLight subject strings.
    rows += _rows_for("generalization", G.discover_mice(),
                      G.fetch_events, G.segment_trials)
    # Extinction (LED2, no reward).
    rows += _rows_for(
        "extinction", E.discover_mice(),
        lambda s: G.fetch_events(s, task_type=E.TASK_TYPE, pilot=E.PILOT),
        G.segment_trials)
    return rows


def write_markdown(rows: list[dict]) -> None:
    """Canonical, human-readable session reference for Gili & Noa's work."""
    mice = sorted({r["mouse"] for r in rows}, key=lambda m: int(m[1:]))
    lines = [
        "# Session list — canonical reference (this dataset)",
        "",
        "**This is the authoritative session list for this dataset. Use these",
        "sessions for all analyses going forward (Gili & Noa).**",
        "",
        "## How a session is defined",
        "",
        "A **session = one mouse + one lab-local calendar day** (Asia/Jerusalem).",
        "",
        "- Sessions are derived from the subject/mouse name, then split by the day",
        "  each trial ran — not by the Elasticsearch `session` counter, which is",
        "  unreliable (it sometimes fails to advance and merges two different days",
        "  under one number — e.g. m100 appetitive had four 122-trial \"double days\").",
        "- Any files or subject-strings from the **same calendar day merge into one",
        "  session** (e.g. a morning + afternoon run, or `_2` continuation strings).",
        "- A same-day aborted false-start is trimmed; sessions are numbered 1..N in",
        "  chronological order per mouse per task.",
        "- A session is **valid** when its trial count is within the 50-72 band",
        "  (nominal 60). Out-of-band days are listed but excluded from analyses.",
        "",
        f"Source of truth: `session_inventory.csv`  ·  {len(rows)} sessions total.",
        "",
        "## Counts per mouse x task (valid / total)",
        "",
        "| mouse | " + " | ".join(TASKS) + " |",
        "|---|" + "---|" * len(TASKS),
    ]
    for m in mice:
        cells = []
        for t in TASKS:
            mr = [r for r in rows if r["mouse"] == m and r["task"] == t]
            valid = sum(r["valid"] == "yes" for r in mr)
            cells.append(f"{valid} / {len(mr)}" if mr else "-")
        lines.append(f"| {m} | " + " | ".join(cells) + " |")

    oob = [r for r in rows if r["valid"] == "no"]
    lines += ["", "## Out-of-band sessions (excluded from analyses)", ""]
    if oob:
        lines += ["| task | mouse | session | date | trials |",
                  "|---|---|---|---|---|"]
        lines += [f"| {r['task']} | {r['mouse']} | {r['session']} | {r['date']} "
                  f"| {r['n_trials']} |" for r in oob]
    else:
        lines.append("_None._")

    for task in TASKS:
        trs = [r for r in rows if r["task"] == task]
        if not trs:
            continue
        lines += ["", f"## {task.capitalize()} — full session list", ""]
        for m in sorted({r["mouse"] for r in trs}, key=lambda x: int(x[1:])):
            mr = [r for r in trs if r["mouse"] == m]
            lines.append(f"**{m}** ({len(mr)} sessions): " + ", ".join(
                f"s{r['session']}={r['date']}({r['n_trials']}t"
                + ("" if r["valid"] == "yes" else ",oob") + ")" for r in mr))
    DOC.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    rows = collect()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["task", "mouse", "session", "date",
                                          "n_trials", "valid"])
        w.writeheader()
        w.writerows(rows)
    write_markdown(rows)

    # Printed per-mouse/per-task summary.
    for task in TASKS:
        trs = [r for r in rows if r["task"] == task]
        if not trs:
            continue
        print(f"\n===== {task.upper()} =====")
        for mouse in sorted({r["mouse"] for r in trs}, key=lambda m: int(m[1:])):
            mrows = [r for r in trs if r["mouse"] == mouse]
            valid = sum(r["valid"] == "yes" for r in mrows)
            print(f"\n{mouse}  ({len(mrows)} day-sessions, {valid} in valid band):")
            for r in mrows:
                flag = "" if r["valid"] == "yes" else "  <-- out of band"
                print(f"    session {r['session']:>2}  {r['date']}  "
                      f"{r['n_trials']:>3} trials{flag}")
    print(f"\nWrote {OUT}  ({len(rows)} sessions).")
    print(f"Wrote {DOC}  (canonical reference).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
