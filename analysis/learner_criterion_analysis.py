#!/usr/bin/env python3
"""Formal learner-criterion analysis — did each mouse LEARN, or just not PARTICIPATE?

A low hit rate is ambiguous: a mouse can fail because it does not understand the
task (low competence) or because it rarely engages the cue (low participation).
This script separates the two and classifies every mouse with several explicit
rules, so "non-learner" is never assigned on hit rate alone.

The four orthogonal axes (project definitions, computed per trial):
    engaged                 = nose-poke while the cue (tone / LED2) was on
    rewarded                = trial delivered water
    accuracy_when_engaged   = rewarded / engaged            (COMPETENCE)
    engagement_rate         = engaged / all trials          (PARTICIPATION)
    hit_rate                = rewarded / all trials          (the ambiguous number)
    offcue_pokes_per_trial  = pokes outside the cue window / trial (impulsivity)

Three rule sets are computed and compared per mouse:
    A. hit-rate only            >=50% hit rate for >=2 consecutive sessions
    B. engagement + competence  >=50% engagement AND >=70% accuracy, >=2 consec.
    C. late-session             same thresholds on the mean of the last 3 sessions
A robust cohort rule flags impulsive / off-cue-dominated mice
(late off-cue pokes/trial above cohort median + 1 MAD).

Final categories (one per mouse, from the late-session metrics + impulsive flag):
    strong_learner               accurate AND engages at/above the task's strong-
                                 participation bar (see below)
    competent_low_participation  accurate when engaged (>=80%) but engages <50%
    partial_learner              learned the rule (>=70% acc) but engages moderately
    non_learner                  low accuracy when engaged, low engagement, no gain
    impulsive_offcue_dominated   low competence whose poking is off-cue-dominated

The "strong-participation bar" is TASK-RELATIVE: max(50%, the task cohort's
median late engagement). Engagement regimes differ by task — the tone is hard to
engage (median ~25%), the light is easy (median ~66%) — so a single absolute 50%
bar would label every generalization mouse a strong learner and hide the real
variation, which in generalization is participation DEGREE (all mice are equally
competent once engaged). The relative bar keeps the appetitive result unchanged
(floor binds at 50%) while separating high vs moderate participators in the light.

Reuses the existing loaders (`appetitive_analysis`, `generalization_analysis`,
`config`) — same ES setup and env vars, no new ES client.

Usage:
    python3 learner_criterion_analysis.py                  # both tasks, all mice
    python3 learner_criterion_analysis.py --task appetitive
    python3 learner_criterion_analysis.py --task generalization
    python3 learner_criterion_analysis.py --mouse m102

Outputs (under learner_criterion_figs/):
    session_learning_metrics.csv          per (task, mouse, session) metrics
    mouse_learning_classification.csv     per (task, mouse) rules + final class
    learner_classification_summary.png    who is in each category, per task
    engagement_vs_competence_map.png      the core participation/competence map
    hit_rate_vs_competence.png            why hit rate alone misleads
    hit_rate_decomposition.png            hit rate = engagement x competence per mouse
    learning_trajectory_by_classification.png  session trajectories by class
    offcue_behavior_by_classification.png      off-cue poking by class
    learner_classification_heatmap.png    mouse x metric heatmap (optional)
    learner_criterion_summary.txt         plain-text answers to the 8 questions
"""
from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.ticker import MaxNLocator
import numpy as np

import appetitive_analysis as A
import generalization_analysis as G

# Output routes by task into results/<area>/learner_criterion/ (env var overrides).
# Reassigned in main() once --task is known; this default covers `--task both`.
_RESULTS_ROOT = Path(__file__).resolve().parent / "results"
_TASK_AREA = {"appetitive": "appetitive", "generalization": "generalization", "both": "cross_task"}
_ENV_OUT = os.environ.get("MICS_LEARNER_OUT")
OUT_ROOT = _ENV_OUT or str(_RESULTS_ROOT / "cross_task" / "learner_criterion")
NAN = float("nan")

TASK_APP = "AppetitveTaskReal"
TASK_GEN = "Generalization"
TASK_LABELS = {TASK_APP: "Appetitive (tone)", TASK_GEN: "Generalization (light)"}

# --- classification thresholds (configurable) ------------------------------
ENGAGE_THRESH = 50.0       # % engagement that counts as "participating"
ACC_STRONG = 70.0          # % accuracy-when-engaged for a learner
ACC_COMPETENT = 80.0       # % accuracy for "knows the rule" (low-participation)
ACC_NONLEARNER = 60.0      # % accuracy below which competence is judged absent
HIT_THRESH = 50.0          # % hit rate for the traditional rule
CONSEC = 2                 # consecutive sessions required for rules A & B
LATE_N = 3                 # number of trailing sessions for late-session metrics
IMPROVE_MIN = 10.0         # pp hit-rate gain (early->late) that counts as improvement
MAD_K = 1.0                # robust impulsivity threshold = median + MAD_K * MAD
MIN_LATE_ENGAGED = 15      # engaged trials in the late window below which accuracy-
                           # when-engaged is too noisy to trust (confidence flag)

# final categories: key -> (label, color)
CLASSES = {
    "strong_learner": ("strong learner", "#2ca02c"),
    "partial_learner": ("partial learner", "#98df8a"),
    "competent_low_participation": ("competent, low participation", "#1f77b4"),
    "non_learner": ("non-learner", "#d62728"),
    "impulsive_offcue_dominated": ("impulsive / off-cue", "#ff7f0e"),
}
CLASS_ORDER = list(CLASSES)


# --- per-session metrics (from reused trial objects) -----------------------
def _median(vals: list[float]) -> float:
    arr = np.array(vals, dtype=float)
    arr = arr[~np.isnan(arr)]
    return float(np.median(arr)) if arr.size else NAN


def _mean(vals: list[float]) -> float:
    arr = np.array(vals, dtype=float)
    arr = arr[~np.isnan(arr)]
    return float(np.mean(arr)) if arr.size else NAN


def session_metrics(trials: list[dict], dur_key: str) -> dict:
    """All per-session metrics from one session's trials. `dur_key` is the
    cue-duration field of the trial object (tone_dur / led_dur). A trial is
    'engaged' iff a nose poke fell inside the cue window [0, cue_duration]."""
    n = len(trials)
    n_engaged = n_rewarded = n_acc = offcue_total = 0
    cue_to_poke, poke_to_lick = [], []
    for t in trials:
        dur = t[dur_key]
        on_cue = [p for p in t["nose_pokes"] if 0 <= p <= dur]
        offcue_total += sum(1 for p in t["nose_pokes"] if p < 0 or p > dur)
        engaged = bool(on_cue)
        n_engaged += engaged
        n_rewarded += t["is_hit"]
        if engaged and t["is_hit"]:
            n_acc += 1
        if on_cue:
            first = min(on_cue)
            cue_to_poke.append(first)
            after = [lk for lk in t["licks"] if lk >= first]
            if after:
                poke_to_lick.append(min(after) - first)
    return {
        "n_trials": n,
        "n_engaged": n_engaged,
        "n_rewarded": n_rewarded,
        "hit_rate": 100.0 * n_rewarded / n,
        "engagement_rate": 100.0 * n_engaged / n,
        "accuracy_when_engaged": 100.0 * n_acc / n_engaged if n_engaged else NAN,
        "offcue_pokes": offcue_total,
        "offcue_pokes_per_trial": offcue_total / n,
        "cue_to_poke_latency_median": _median(cue_to_poke),
        "poke_to_lick_latency_median": _median(poke_to_lick),
    }


# --- loaders (reuse existing ES access + ordering) -------------------------
def load_appetitive(only_mouse: str | None) -> dict[str, list[dict]]:
    """{mouse: [session metric dicts]} for the tone task; session index = 1..K
    over qualifying sessions (>= A.MIN_TRIALS), in ES-session order."""
    out: dict[str, list[dict]] = {}
    for subject in A.discover_subjects():
        mouse = A.short_name(subject)
        if only_mouse and mouse != only_mouse:
            continue
        by_session = A.group_by_session(A.fetch_events(subject))
        rows = []
        for sess in sorted(by_session):
            trials = A.segment_trials(by_session[sess])
            if not A.session_len_ok(len(trials)):
                continue
            m = session_metrics(trials, "tone_dur")
            m["session"] = len(rows) + 1
            rows.append(m)
        if rows:
            out[mouse] = rows
    return out


def load_generalization(only_mouse: str | None) -> dict[str, list[dict]]:
    """{mouse: [session metric dicts]} for the light task; reuses
    G.collect_mouse for the canonical session ordering / re-indexing / cap."""
    out: dict[str, list[dict]] = {}
    for mouse, subjects in G.discover_mice().items():
        if only_mouse and mouse != only_mouse:
            continue
        rows = []
        for r in G.collect_mouse(subjects):
            m = session_metrics(r["trials"], "led_dur")
            m["session"] = r["session_num"]
            rows.append(m)
        if rows:
            out[mouse] = sorted(rows, key=lambda d: d["session"])
    return out


def load_association_cue_reward(only_mouse: str | None) -> dict[str, list[dict]]:
    """TODO(AssociationCueReward): no loader, subject pattern, or verified cue
    semantics exist for this task in the project yet, so it is not loaded here.
    To add it as a pre-training section, mirror appetitive_analysis (discover +
    fetch + segment with the correct cue event) and append its rows."""
    return {}


# --- mouse-level classification --------------------------------------------
def _consecutive(flags: list[bool], k: int) -> bool:
    run = 0
    for f in flags:
        run = run + 1 if f else 0
        if run >= k:
            return True
    return False


def _first_session(rows: list[dict], predicate) -> int | None:
    for r in rows:
        if predicate(r):
            return r["session"]
    return None


def _robust_impulsive_threshold(values: list[float]) -> float:
    """Cohort median + MAD_K * MAD (robust outlier cutoff). Falls back to the
    median when MAD = 0 so identical cohorts don't flag everyone."""
    arr = np.array([v for v in values if not np.isnan(v)], dtype=float)
    if arr.size == 0:
        return NAN
    med = float(np.median(arr))
    mad = float(np.median(np.abs(arr - med)))
    return med + MAD_K * mad if mad > 0 else med


def classify_mouse(rows: list[dict], impulsive_threshold: float,
                   strong_engage: float) -> dict:
    """All rule outputs + a single final classification with a reason string.

    `strong_engage` is the TASK-RELATIVE bar for "strong" (consistent)
    participation: max(ENGAGE_THRESH, the task cohort's median late engagement).
    Because engagement regimes differ by task (the tone is hard to engage, the
    light is easy), a single absolute bar would call every generalization mouse a
    strong learner; the task-relative bar instead separates the cohort's high
    participators from those that learned the rule but engage moderately."""
    late = rows[-LATE_N:]
    early = rows[:max(1, min(2, len(rows)))]

    late_eng = _mean([r["engagement_rate"] for r in late])
    late_acc = _mean([r["accuracy_when_engaged"] for r in late])
    late_hit = _mean([r["hit_rate"] for r in late])
    late_off = _mean([r["offcue_pokes_per_trial"] for r in late])
    early_hit = _mean([r["hit_rate"] for r in early])
    improvement = late_hit - early_hit
    acc_val = 0.0 if np.isnan(late_acc) else late_acc
    n_late_engaged = sum(r["n_engaged"] for r in late)
    low_confidence = n_late_engaged < MIN_LATE_ENGAGED

    # Rule A — traditional hit-rate criterion
    hit_flags = [r["hit_rate"] >= HIT_THRESH for r in rows]
    hit_rate_learner = _consecutive(hit_flags, CONSEC)
    # Rule B — engagement + competence
    ec_flags = [(r["engagement_rate"] >= ENGAGE_THRESH
                 and not np.isnan(r["accuracy_when_engaged"])
                 and r["accuracy_when_engaged"] >= ACC_STRONG) for r in rows]
    engagement_competence_learner = _consecutive(ec_flags, CONSEC)
    # Rule C — late-session
    late_session_learner = late_eng >= ENGAGE_THRESH and acc_val >= ACC_STRONG
    competent_low_participation = acc_val >= ACC_COMPETENT and late_eng < ENGAGE_THRESH
    is_impulsive = (not np.isnan(late_off) and not np.isnan(impulsive_threshold)
                    and late_off > impulsive_threshold)
    non_learner_flag = (acc_val < ACC_NONLEARNER and late_eng < ENGAGE_THRESH
                        and improvement < IMPROVE_MIN)

    # final classification (first match wins; impulsive only for low competence)
    if late_eng >= strong_engage and acc_val >= ACC_STRONG:
        final = "strong_learner"
        reason = (f"High engagement ({late_eng:.0f}%, at/above the task's strong-"
                  f"participation bar of {strong_engage:.0f}%) and high accuracy-when-"
                  f"engaged ({acc_val:.0f}%); strong learner.")
    elif acc_val >= ACC_COMPETENT and late_eng < ENGAGE_THRESH:
        final = "competent_low_participation"
        reason = (f"High accuracy when engaged ({acc_val:.0f}%) but low engagement "
                  f"({late_eng:.0f}%); low hit rate is mainly participation-limited.")
    elif is_impulsive and acc_val < ACC_STRONG:
        final = "impulsive_offcue_dominated"
        reason = (f"Off-cue poking ({late_off:.1f}/trial) above cohort threshold with "
                  f"low competence ({acc_val:.0f}%); off-cue-dominated, not a clean "
                  f"non-learner.")
    elif acc_val >= ACC_STRONG:
        final = "partial_learner"
        reason = (f"Learned the rule (accuracy {acc_val:.0f}%) but engages moderately "
                  f"({late_eng:.0f}%, below the task's strong-participation bar of "
                  f"{strong_engage:.0f}%); partial learner.")
    elif acc_val >= ACC_NONLEARNER:
        final = "partial_learner"
        reason = (f"Moderate competence ({acc_val:.0f}%) and low engagement "
                  f"({late_eng:.0f}%); partial learner.")
    elif non_learner_flag:
        final = "non_learner"
        reason = (f"Low accuracy when engaged ({acc_val:.0f}%) and low engagement "
                  f"({late_eng:.0f}%) with no clear improvement; non-learner.")
    else:
        final = "partial_learner"
        reason = (f"Low late competence ({acc_val:.0f}%) but improving across sessions "
                  f"(+{improvement:.0f}pp hit rate); partial learner.")

    if low_confidence:
        reason += (f" (Low confidence: accuracy estimated from only {n_late_engaged} "
                   f"engaged trials in the late window.)")

    return {
        "n_sessions": len(rows),
        "max_hit_rate": max(r["hit_rate"] for r in rows),
        "max_engagement_rate": max(r["engagement_rate"] for r in rows),
        "max_accuracy_when_engaged": _max_nan([r["accuracy_when_engaged"] for r in rows]),
        "late_hit_rate": late_hit,
        "late_engagement_rate": late_eng,
        "late_accuracy_when_engaged": late_acc,
        "late_offcue_pokes_per_trial": late_off,
        "first_session_50_hit_rate": _first_session(rows, lambda r: r["hit_rate"] >= HIT_THRESH),
        "first_session_50_engagement": _first_session(rows, lambda r: r["engagement_rate"] >= ENGAGE_THRESH),
        "first_session_70_accuracy_when_engaged": _first_session(
            rows, lambda r: not np.isnan(r["accuracy_when_engaged"]) and r["accuracy_when_engaged"] >= ACC_STRONG),
        "hit_rate_learner": hit_rate_learner,
        "engagement_competence_learner": engagement_competence_learner,
        "late_session_learner": late_session_learner,
        "competent_low_participation": competent_low_participation,
        "non_learner": non_learner_flag,
        "impulsive_offcue_dominated": is_impulsive,
        "n_late_engaged": n_late_engaged,
        "low_confidence_competence": low_confidence,
        "strong_participation_bar": strong_engage,
        "final_classification": final,
        "classification_reason": reason,
    }


def _max_nan(vals: list[float]) -> float:
    arr = np.array(vals, dtype=float)
    arr = arr[~np.isnan(arr)]
    return float(np.max(arr)) if arr.size else NAN


def classify_task(sessions_by_mouse: dict[str, list[dict]]) -> dict[str, dict]:
    late_eng = [_mean([r["engagement_rate"] for r in rows[-LATE_N:]])
                for rows in sessions_by_mouse.values()]
    # Task-relative strong-participation bar: the cohort median engagement, but
    # never below the absolute ENGAGE_THRESH floor. Adapts to each task's regime.
    strong_engage = max(ENGAGE_THRESH, _median(late_eng))
    threshold = _robust_impulsive_threshold(
        [_mean([r["offcue_pokes_per_trial"] for r in rows[-LATE_N:]])
         for rows in sessions_by_mouse.values()])
    return {m: classify_mouse(rows, threshold, strong_engage)
            for m, rows in sessions_by_mouse.items()}


# --- CSV output ------------------------------------------------------------
SESSION_COLUMNS = [
    "task", "mouse", "session", "n_trials", "n_engaged", "n_rewarded",
    "hit_rate", "engagement_rate", "accuracy_when_engaged", "offcue_pokes",
    "offcue_pokes_per_trial", "cue_to_poke_latency_median", "poke_to_lick_latency_median",
]
MOUSE_COLUMNS = [
    "task", "mouse", "n_sessions", "max_hit_rate", "max_engagement_rate",
    "max_accuracy_when_engaged", "late_hit_rate", "late_engagement_rate",
    "late_accuracy_when_engaged", "late_offcue_pokes_per_trial",
    "first_session_50_hit_rate", "first_session_50_engagement",
    "first_session_70_accuracy_when_engaged", "hit_rate_learner",
    "engagement_competence_learner", "late_session_learner",
    "competent_low_participation", "non_learner", "impulsive_offcue_dominated",
    "n_late_engaged", "low_confidence_competence", "strong_participation_bar",
    "final_classification", "classification_reason",
]


def _fmt(v):
    if v is None:
        return ""
    if isinstance(v, bool) or isinstance(v, str):
        return v
    if isinstance(v, float):
        return "NaN" if np.isnan(v) else round(v, 3)
    return v


def write_session_csv(sessions: dict[str, dict[str, list[dict]]], path: str) -> None:
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=SESSION_COLUMNS)
        w.writeheader()
        for task, by_mouse in sessions.items():
            for mouse in _sorted_mice(by_mouse):
                for r in by_mouse[mouse]:
                    row = {"task": task, "mouse": mouse}
                    row.update({k: r.get(k) for k in SESSION_COLUMNS if k not in row})
                    w.writerow({k: _fmt(v) for k, v in row.items()})


def write_mouse_csv(classes: dict[str, dict[str, dict]], path: str) -> None:
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=MOUSE_COLUMNS)
        w.writeheader()
        for task, by_mouse in classes.items():
            for mouse in _sorted_mice(by_mouse):
                row = {"task": task, "mouse": mouse}
                row.update({k: by_mouse[mouse].get(k) for k in MOUSE_COLUMNS if k not in row})
                w.writerow({k: _fmt(v) for k, v in row.items()})


def _sorted_mice(d: dict) -> list[str]:
    return sorted(d, key=lambda m: int(m[1:]))


# --- figures ---------------------------------------------------------------
def _class_color(cls: str) -> str:
    return CLASSES[cls][1]


def fig_classification_summary(classes: dict, out_path: str) -> None:
    """One panel per task: each category is a row, its member mice plotted as
    labeled chips — read a row to see exactly which mice are in that category."""
    tasks = list(classes)
    fig, axes = plt.subplots(len(tasks), 1, figsize=(11, 3.6 * len(tasks)), squeeze=False)
    for ax, task in zip(axes[:, 0], tasks):
        by_mouse = classes[task]
        members = {cls: [m for m in _sorted_mice(by_mouse)
                         if by_mouse[m]["final_classification"] == cls]
                   for cls in CLASS_ORDER}
        max_n = max((len(v) for v in members.values()), default=1)
        for yi, cls in enumerate(CLASS_ORDER):
            ax.axhspan(yi - 0.45, yi + 0.45, color=_class_color(cls), alpha=0.10)
            for xi, m in enumerate(members[cls]):
                ax.scatter(xi, yi, s=520, color=_class_color(cls), edgecolor="white",
                           linewidths=1.0, zorder=3)
                ax.text(xi, yi, m, ha="center", va="center", fontsize=8,
                        color="white", fontweight="bold", zorder=4)
        ax.set_yticks(range(len(CLASS_ORDER)))
        ax.set_yticklabels([CLASSES[c][0] for c in CLASS_ORDER])
        ax.set_ylim(-0.6, len(CLASS_ORDER) - 0.4)
        ax.set_xlim(-0.6, max(max_n, 1) - 0.4 + 0.6)
        ax.set_xticks([])
        ax.set_title(TASK_LABELS[task], fontsize=12)
        ax.invert_yaxis()
    fig.suptitle("Learner classification — which mice fall in each category", fontsize=13)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def _scatter_mice(ax, by_mouse: dict, xkey: str, ykey: str, size_key: str | None) -> None:
    for m in _sorted_mice(by_mouse):
        d = by_mouse[m]
        x, y = d[xkey], d[ykey]
        if np.isnan(x) or np.isnan(y):
            continue
        s = 110 if size_key is None else 40 + 3.2 * (0 if np.isnan(d[size_key]) else d[size_key])
        ax.scatter(x, y, s=s, color=_class_color(d["final_classification"]),
                   edgecolor="white", linewidths=0.7, zorder=3, alpha=0.9)
        ax.annotate(m, (x, y), textcoords="offset points", xytext=(6, 4), fontsize=7)


def fig_engagement_vs_competence(classes: dict, out_path: str) -> None:
    tasks = list(classes)
    fig, axes = plt.subplots(1, len(tasks), figsize=(6.8 * len(tasks), 6),
                             squeeze=False, sharey=True)
    for ax, task in zip(axes[0], tasks):
        _scatter_mice(ax, classes[task], "late_engagement_rate",
                      "late_accuracy_when_engaged", None)
        ax.axvline(ENGAGE_THRESH, color="grey", ls="--", lw=1)
        ax.axhline(ACC_STRONG, color="grey", ls="--", lw=1)
        ax.set_xlim(0, 100)
        ax.set_ylim(0, 105)
        ax.set_xlabel("late engagement rate (%)  →  participation")
        ax.set_title(TASK_LABELS[task])
        ax.text(75, 102, "strong learners", fontsize=8, color="#2ca02c", ha="center")
        ax.text(22, 102, "knows rule,\nlow participation", fontsize=8, color="#1f77b4", ha="center")
        ax.text(22, 30, "non-learners", fontsize=8, color="#d62728", ha="center")
    axes[0][0].set_ylabel("late accuracy when engaged (%)  →  competence")
    _legend_classes(fig)
    fig.suptitle("Participation vs competence — the core learner map "
                 "(each point = one mouse)", fontsize=13, y=0.99)
    fig.tight_layout(rect=(0, 0, 1, 0.88))
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def fig_hit_rate_vs_competence(classes: dict, out_path: str) -> None:
    """Why hit rate alone misleads: x = hit rate, y = accuracy-when-engaged,
    point SIZE = engagement. Mice with similar low hit rate split into competent
    (high y, small) vs truly poor (low y)."""
    tasks = list(classes)
    fig, axes = plt.subplots(1, len(tasks), figsize=(6.8 * len(tasks), 6),
                             squeeze=False, sharey=True)
    for ax, task in zip(axes[0], tasks):
        _scatter_mice(ax, classes[task], "late_hit_rate",
                      "late_accuracy_when_engaged", "late_engagement_rate")
        ax.axhline(ACC_STRONG, color="grey", ls="--", lw=1)
        ax.set_xlim(0, 100)
        ax.set_ylim(0, 105)
        ax.set_xlabel("late hit rate (% of all trials)")
        ax.set_title(TASK_LABELS[task])
    axes[0][0].set_ylabel("late accuracy when engaged (%)")
    _legend_classes(fig, extra=[plt.Line2D([], [], marker="o", linestyle="None",
                                           color="grey", markersize=10,
                                           label="point size ∝ engagement rate")])
    fig.suptitle("Hit rate is misleading — low hit rate can mean low competence "
                 "OR low participation", fontsize=13, y=0.99)
    fig.tight_layout(rect=(0, 0, 1, 0.88))
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def fig_trajectory_by_classification(sessions: dict, classes: dict, out_path: str) -> None:
    metrics = [("hit_rate", "hit rate (%)"),
               ("engagement_rate", "engagement rate (%)"),
               ("accuracy_when_engaged", "accuracy when engaged (%)")]
    tasks = list(sessions)
    fig, axes = plt.subplots(len(metrics), len(tasks),
                             figsize=(6.5 * len(tasks), 3.4 * len(metrics)),
                             squeeze=False, sharex="col")
    for col, task in enumerate(tasks):
        by_mouse = sessions[task]
        max_s = max((r["session"] for rows in by_mouse.values() for r in rows), default=1)
        for row, (key, ylabel) in enumerate(metrics):
            ax = axes[row][col]
            for m in _sorted_mice(by_mouse):
                cls = classes[task][m]["final_classification"]
                rows = by_mouse[m]
                ax.plot([r["session"] for r in rows], [r[key] for r in rows],
                        "-o", color=_class_color(cls), lw=1.4, ms=3, alpha=0.8)
            ax.set_ylim(0, 105)
            ax.set_xlim(0.5, max_s + 0.5)
            ax.xaxis.set_major_locator(MaxNLocator(integer=True))
            ax.set_ylabel(ylabel)
            if row == 0:
                ax.set_title(TASK_LABELS[task])
            if row == len(metrics) - 1:
                ax.set_xlabel("session #")
    _legend_classes(fig)
    fig.suptitle("Learning trajectories colored by final classification",
                 fontsize=13, y=0.99)
    fig.tight_layout(rect=(0, 0, 1, 0.9))
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def fig_offcue_by_classification(classes: dict, out_path: str) -> None:
    tasks = list(classes)
    fig, axes = plt.subplots(1, len(tasks), figsize=(6.8 * len(tasks), 5), squeeze=False)
    for ax, task in zip(axes[0], tasks):
        by_mouse = classes[task]
        mice = sorted(by_mouse, key=lambda m: by_mouse[m]["late_offcue_pokes_per_trial"],
                      reverse=True)
        vals = [by_mouse[m]["late_offcue_pokes_per_trial"] for m in mice]
        colors = [_class_color(by_mouse[m]["final_classification"]) for m in mice]
        thr = _robust_impulsive_threshold(vals)
        ax.bar(range(len(mice)), vals, color=colors, edgecolor="white", linewidth=0.4)
        ax.axhline(thr, color="black", ls="--", lw=1, label=f"impulsive threshold = {thr:.1f}")
        ax.set_xticks(range(len(mice)))
        ax.set_xticklabels(mice, rotation=45, ha="right", fontsize=8)
        ax.set_ylabel("late off-cue pokes per trial")
        ax.set_title(TASK_LABELS[task])
        ax.legend(fontsize=8)
    _legend_classes(fig)
    fig.suptitle("Off-cue poking by classification — who is impulsive vs a true "
                 "non-learner", fontsize=13, y=0.99)
    fig.tight_layout(rect=(0, 0, 1, 0.88))
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def fig_hit_rate_decomposition(classes: dict, out_path: str) -> None:
    """The single clearest demonstration that hit rate misleads. Because
    hit_rate = engagement_rate x accuracy_when_engaged exactly, each mouse's
    faded bar is its COMPETENCE ceiling (accuracy when engaged = the rate it
    reaches on the trials it engages) and the solid bar is the ACTUAL hit rate
    over all trials. The gap between them is reward lost purely to
    under-participation; the engagement % is annotated. A short solid bar under a
    tall faded bar = a participation problem, not a competence problem; a low
    faded bar = a genuine competence problem."""
    tasks = list(classes)
    fig, axes = plt.subplots(1, len(tasks), figsize=(6.8 * len(tasks), 5.8),
                             squeeze=False, sharey=True)
    for ax, task in zip(axes[0], tasks):
        by_mouse = classes[task]
        mice = sorted(by_mouse, reverse=True,
                      key=lambda m: np.nan_to_num(by_mouse[m]["late_accuracy_when_engaged"], nan=-1.0))
        for i, m in enumerate(mice):
            d = by_mouse[m]
            color = _class_color(d["final_classification"])
            ceiling = 0.0 if np.isnan(d["late_accuracy_when_engaged"]) else d["late_accuracy_when_engaged"]
            ax.bar(i, ceiling, width=0.72, color=color, alpha=0.28, zorder=1)
            ax.bar(i, d["late_hit_rate"], width=0.72, color=color, alpha=0.95, zorder=2)
            ax.annotate(f"{d['late_engagement_rate']:.0f}%", (i, ceiling),
                        textcoords="offset points", xytext=(0, 3), ha="center",
                        fontsize=7, color="#333333")
        ax.set_xticks(range(len(mice)))
        ax.set_xticklabels(mice, rotation=45, ha="right", fontsize=8)
        ax.set_ylim(0, 108)
        ax.set_title(TASK_LABELS[task])
    axes[0][0].set_ylabel("%  —  competence ceiling (faded) vs actual hit rate (solid)")
    class_handles = [plt.Line2D([], [], marker="o", linestyle="None", color=c, label=lab)
                     for lab, c in CLASSES.values()]
    fig.legend(handles=class_handles, loc="upper center", ncol=len(CLASSES),
               fontsize=8, bbox_to_anchor=(0.5, 0.9))
    fig.suptitle("Why hit rate misleads:  hit rate = engagement × competence",
                 fontsize=13, y=0.995)
    fig.text(0.5, 0.945, "faded bar = accuracy when engaged (competence ceiling)  ·  "
             "solid bar = actual hit rate  ·  number = engagement %;  the gap is "
             "reward lost to under-participation", ha="center", fontsize=8.5, color="#555555")
    fig.tight_layout(rect=(0, 0, 1, 0.86))
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


HEATMAP_METRICS = [
    ("late_hit_rate", "late\nhit rate"),
    ("late_engagement_rate", "late\nengagement"),
    ("late_accuracy_when_engaged", "late\naccuracy"),
    ("late_offcue_pokes_per_trial", "late off-cue\npokes/trial"),
    ("max_hit_rate", "max\nhit rate"),
    ("max_engagement_rate", "max\nengagement"),
    ("max_accuracy_when_engaged", "max\naccuracy"),
]


def fig_classification_heatmap(classes: dict, out_path: str) -> None:
    """Optional: rows = mice, columns = metrics, colored by z-score within each
    column (per task), raw value annotated. Raw values stay in the CSV."""
    tasks = list(classes)
    fig, axes = plt.subplots(1, len(tasks), figsize=(7.0 * len(tasks), 6), squeeze=False)
    keys = [k for k, _ in HEATMAP_METRICS]
    for ax, task in zip(axes[0], tasks):
        mice = _sorted_mice(classes[task])
        raw = np.array([[classes[task][m][k] for k in keys] for m in mice], dtype=float)
        mean = np.nanmean(raw, axis=0)
        std = np.nanstd(raw, axis=0)
        std[std == 0] = 1.0
        z = (raw - mean) / std
        ax.imshow(z, cmap="RdBu_r", aspect="auto", vmin=-2, vmax=2)
        ax.set_xticks(range(len(keys)))
        ax.set_xticklabels([lab for _, lab in HEATMAP_METRICS], fontsize=8)
        ax.set_yticks(range(len(mice)))
        ax.set_yticklabels(mice, fontsize=9)
        for i in range(len(mice)):
            for j in range(len(keys)):
                v = raw[i, j]
                ax.text(j, i, "—" if np.isnan(v) else f"{v:.0f}", ha="center",
                        va="center", fontsize=8)
        ax.set_title(TASK_LABELS[task])
    fig.suptitle("Per-mouse learning metrics (color = z-score within column; "
                 "raw value shown)", fontsize=13)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def _legend_classes(fig, extra: list | None = None) -> None:
    handles = [plt.Line2D([], [], marker="o", linestyle="None", color=c, label=lab)
               for lab, c in CLASSES.values()]
    if extra:
        handles += extra
    fig.legend(handles=handles, loc="upper center", ncol=len(handles),
               fontsize=8, bbox_to_anchor=(0.5, 0.93))


# --- text summary ----------------------------------------------------------
def _members(by_mouse: dict, cls: str) -> list[str]:
    return [m for m in _sorted_mice(by_mouse) if by_mouse[m]["final_classification"] == cls]


def write_summary_text(classes: dict, out_path: str) -> None:
    lines = ["FORMAL LEARNER-CRITERION ANALYSIS — SUMMARY", "=" * 46, "",
             f"Thresholds: engagement >= {ENGAGE_THRESH:.0f}%, accuracy(strong) >= "
             f"{ACC_STRONG:.0f}%, accuracy(competent) >= {ACC_COMPETENT:.0f}%, "
             f"non-learner accuracy < {ACC_NONLEARNER:.0f}%. Late = last {LATE_N} sessions.",
             "Learning is judged on PARTICIPATION (engagement) and COMPETENCE "
             "(accuracy-when-engaged), never on hit rate alone.\n"]

    def fmt(ms: list[str]) -> str:
        return ", ".join(ms) if ms else "(none)"

    if TASK_APP in classes:
        a = classes[TASK_APP]
        lines.append(f"### {TASK_LABELS[TASK_APP]}")
        lines.append(f"1. Strong learners: {fmt(_members(a, 'strong_learner'))}")
        lines.append(f"2. Partial learners: {fmt(_members(a, 'partial_learner'))}")
        lines.append(f"3. Competent but low-participation: "
                     f"{fmt(_members(a, 'competent_low_participation'))}")
        lines.append(f"4. Non-learners: {fmt(_members(a, 'non_learner'))}")
        lines.append(f"5. Impulsive / off-cue-dominated: "
                     f"{fmt([m for m in _sorted_mice(a) if a[m]['impulsive_offcue_dominated']])}")
        lines.append("")

    if TASK_GEN in classes:
        g = classes[TASK_GEN]
        generalized = [m for m in _sorted_mice(g)
                       if not np.isnan(g[m]["late_accuracy_when_engaged"])
                       and g[m]["late_accuracy_when_engaged"] >= ACC_STRONG]
        high_part = [m for m in _sorted_mice(g) if g[m]["final_classification"] == "strong_learner"]
        mod_part = [m for m in _sorted_mice(g) if g[m]["final_classification"] == "partial_learner"]
        bar = next(iter(g.values()))["strong_participation_bar"]
        lines.append(f"### {TASK_LABELS[TASK_GEN]}")
        lines.append(f"6. Generalized to the light (learned the rule = accuracy >= "
                     f"{ACC_STRONG:.0f}% when engaged): {fmt(generalized)}")
        lines.append(f"   ALL mice generalized — competence is uniformly high, so they "
                     f"differ only in PARTICIPATION (task strong-participation bar = "
                     f"{bar:.0f}% engagement):")
        lines.append(f"   - high participators (strong learners): {fmt(high_part)}")
        lines.append(f"   - moderate participators (learned the rule, engage less, "
                     f"slower to ramp): {fmt(mod_part)}")
        lines.append("")

    # 7. failure attribution per task
    lines.append("### 7. Did failures come from low competence or low participation?")
    for task, by_mouse in classes.items():
        part_limited, comp_limited = [], []
        for m in _sorted_mice(by_mouse):
            d = by_mouse[m]
            if d["final_classification"] in ("strong_learner",):
                continue
            acc = 0.0 if np.isnan(d["late_accuracy_when_engaged"]) else d["late_accuracy_when_engaged"]
            if acc >= ACC_STRONG and d["late_engagement_rate"] < ENGAGE_THRESH:
                part_limited.append(m)
            elif acc < ACC_NONLEARNER:
                comp_limited.append(m)
        if not part_limited and not comp_limited:
            lines.append(f"  {TASK_LABELS[task]}: no failures — every mouse learned the "
                         f"rule; the only variation is participation degree.")
        else:
            lines.append(f"  {TASK_LABELS[task]}: participation-limited (knows rule, "
                         f"under-engages) = {fmt(part_limited)}; competence-limited "
                         f"(fails when engaged) = {fmt(comp_limited)}.")
    lines.append("")

    # 8. where the traditional hit-rate rule disagrees with participation+competence
    lines.append("### 8. Where hit-rate-alone disagrees with the engagement+competence view")
    lines.append("   (hit-rate rule = >=50% for 2 consecutive sessions; it writes off any")
    lines.append("    mouse that engages little, even one that is accurate when it does.)")
    for task, by_mouse in classes.items():
        missed = []
        for m in _sorted_mice(by_mouse):
            d = by_mouse[m]
            acc = 0.0 if np.isnan(d["late_accuracy_when_engaged"]) else d["late_accuracy_when_engaged"]
            if (not d["hit_rate_learner"]) and acc >= ACC_COMPETENT:
                tag = " [low-confidence]" if d["low_confidence_competence"] else ""
                missed.append(f"{m} (accuracy {acc:.0f}%, hit rate {d['late_hit_rate']:.0f}%, "
                              f"{CLASSES[d['final_classification']][0]}){tag}")
        lines.append(f"  {TASK_LABELS[task]}: hit-rate-only fails to credit these competent "
                     f"mice → {fmt(missed)}")
    lines.append("")

    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))


# --- driver ----------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--task", choices=["appetitive", "generalization", "both"],
                        default="both")
    parser.add_argument("--mouse", default=None, help="restrict to one mouse, e.g. m102")
    args = parser.parse_args()

    if not _ENV_OUT:
        global OUT_ROOT
        OUT_ROOT = str(_RESULTS_ROOT / _TASK_AREA[args.task] / "learner_criterion")

    sessions: dict[str, dict[str, list[dict]]] = {}
    if args.task in ("appetitive", "both"):
        print("Loading appetitive (tone) task ...")
        app = load_appetitive(args.mouse)
        if app:
            sessions[TASK_APP] = app
    if args.task in ("generalization", "both"):
        print("Loading generalization (light) task ...")
        gen = load_generalization(args.mouse)
        if gen:
            sessions[TASK_GEN] = gen
    load_association_cue_reward(args.mouse)  # TODO — see function docstring

    if not sessions:
        print("No matching sessions found.")
        return 1

    classes = {task: classify_task(by_mouse) for task, by_mouse in sessions.items()}

    os.makedirs(OUT_ROOT, exist_ok=True)
    write_session_csv(sessions, os.path.join(OUT_ROOT, "session_learning_metrics.csv"))
    write_mouse_csv(classes, os.path.join(OUT_ROOT, "mouse_learning_classification.csv"))

    fig_classification_summary(classes, os.path.join(OUT_ROOT, "learner_classification_summary.png"))
    fig_engagement_vs_competence(classes, os.path.join(OUT_ROOT, "engagement_vs_competence_map.png"))
    fig_hit_rate_vs_competence(classes, os.path.join(OUT_ROOT, "hit_rate_vs_competence.png"))
    fig_trajectory_by_classification(sessions, classes,
                                     os.path.join(OUT_ROOT, "learning_trajectory_by_classification.png"))
    fig_offcue_by_classification(classes, os.path.join(OUT_ROOT, "offcue_behavior_by_classification.png"))
    fig_hit_rate_decomposition(classes, os.path.join(OUT_ROOT, "hit_rate_decomposition.png"))
    fig_classification_heatmap(classes, os.path.join(OUT_ROOT, "learner_classification_heatmap.png"))

    write_summary_text(classes, os.path.join(OUT_ROOT, "learner_criterion_summary.txt"))

    n_mice = sum(len(v) for v in classes.values())
    print(f"\nWrote 2 CSVs, 7 figures, and summary.txt under '{OUT_ROOT}/' "
          f"({n_mice} mouse-task classifications).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
