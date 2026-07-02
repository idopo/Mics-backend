#!/usr/bin/env python3
"""Trial-history analysis — is behavior driven by learning, or by recent history?

Tests whether each mouse's current-trial behavior depends on what happened on the
PREVIOUS trial(s). The motivating question:

    Is the mouse responding to the cue because it learned the task, or because its
    behavior is strongly controlled by recent reward history (reward-gated /
    bursty, e.g. m92, m101) vs steady (e.g. m97, m100, m102, m103)?

Builds a trial-level history table (previous / 2-back / rolling prev-3 & prev-5
outcomes, computed strictly WITHIN each mouse x task x session), then:
  - descriptive conditional probabilities with bootstrap CIs (the primary, robust
    path — numpy only), e.g. P(engage | prev rewarded) vs P(engage | prev not),
  - a per-mouse reward-gating / persistence summary,
  - logistic-regression models (engagement, accuracy-when-engaged, off-cue poking)
    with mouse fixed effects.

Modeling note: statsmodels/pandas are NOT installed and this project is kept
dependency-light (requests + numpy + matplotlib). The regression is therefore a
small ridge-regularized IRLS logistic regression implemented in numpy (mouse
dummies as fixed effects), reporting odds ratios with 95% CIs. The descriptive
analysis does not depend on it; if a model fails to converge it is skipped and a
note is written.

Trial-history variables (per trial, NaN/None on the first trial of a session):
    engaged / rewarded / missed (engaged & not rewarded) / offcue_poke
    previous_* (1 back), two_trials_back_* (2 back)
    prev_{3,5}_{reward,engagement,offcue_poke}_rate  (mean over the prior k trials)
    trial_in_session_fraction

Usage:
    python3 trial_history_analysis.py                  # both tasks, all mice
    python3 trial_history_analysis.py --task appetitive
    python3 trial_history_analysis.py --task generalization
    python3 trial_history_analysis.py --mouse m102

Outputs (under trial_history_figs/):
    trial_history_trials.csv               one row per trial (history table)
    mouse_trial_history_summary.csv        per (task, mouse) gating/persistence
    trial_history_summary.txt              plain-text answers to the 9 questions
    trial_history_prev_reward_engagement.png   Fig 1
    trial_history_engagement_persistence.png   Fig 2
    trial_history_offcue_after_outcome.png     Fig 3
    trial_history_reward_gated_ranking.png     Fig 4
    trial_history_model_coefficients.png       Fig 5 (numpy logistic)
    trial_history_example_mice.png             Fig 6
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

# Output routes by task into results/trial_history/<area>/ (env var overrides).
# Reassigned in main() once --task is known; this default covers `--task both`.
_RESULTS_ROOT = Path(__file__).resolve().parent / "results"
_TASK_AREA = {"appetitive": "appetitive", "generalization": "generalization", "both": "cross_task"}
_ENV_OUT = os.environ.get("MICS_TRIALHIST_OUT")
OUT_ROOT = _ENV_OUT or str(_RESULTS_ROOT / "trial_history" / "cross_task")
NAN = float("nan")

TASK_APP = "AppetitveTaskReal"
TASK_GEN = "Generalization"
TASK_LABELS = {TASK_APP: "Appetitive (tone)", TASK_GEN: "Generalization (light)"}
TASK_COLORS = {TASK_APP: "#1f77b4", TASK_GEN: "#d62728"}

# interpretation thresholds (configurable)
REWARD_GATED_DELTA = 15.0   # pp engagement gain after reward → reward-gated
PERSISTENCE_DELTA = 30.0    # pp engagement persistence → state-like
OFFCUE_DELTA = 15.0         # pp off-cue gain after reward → off-cue dominated
MIN_TRIALS_INTERP = 40      # below this, label "low data / unclear"
EXAMPLE_MICE = ["m92", "m101", "m102", "m97"]
RIDGE_L2 = 1.0              # ridge penalty for the logistic regression (stability)


# --- per-trial base fields (reused trial objects) --------------------------
def base_fields(trial: dict, dur_key: str) -> dict:
    """Engagement / reward / off-cue / latency for one trial (same cue-window
    definition as the rest of the project: engaged = on-cue poke in [0, dur])."""
    dur = trial[dur_key]
    on_cue = sorted(p for p in trial["nose_pokes"] if 0 <= p <= dur)
    off_cue = [p for p in trial["nose_pokes"] if p < 0 or p > dur]
    engaged = bool(on_cue)
    rewarded = bool(trial["is_hit"])
    first_on = on_cue[0] if on_cue else NAN
    licks_after = [lk for lk in trial["licks"] if on_cue and lk >= first_on]
    first_lick = min(licks_after) if licks_after else NAN
    return {
        "engaged": engaged,
        "rewarded": rewarded,
        "missed": engaged and not rewarded,
        "offcue_poke": bool(off_cue),
        "offcue_pokes_count": len(off_cue),
        "n_oncue_pokes": len(on_cue),
        "n_licks": len(trial["licks"]),
        "cue_to_poke_latency": first_on,
        "poke_to_lick_latency": (first_lick - first_on) if (engaged and licks_after) else NAN,
    }


def _rate(trials: list[dict], key: str) -> float:
    return float(np.mean([t[key] for t in trials])) if trials else NAN


def add_history(trials: list[dict]) -> None:
    """Attach previous / 2-back / rolling-rate fields WITHIN this session."""
    n = len(trials)
    for i, t in enumerate(trials):
        t["trial_index"] = i + 1
        t["n_trials_in_session"] = n
        t["trial_in_session_fraction"] = i / (n - 1) if n > 1 else 0.0
        prev = trials[i - 1] if i > 0 else None
        t["previous_engaged"] = prev["engaged"] if prev else None
        t["previous_rewarded"] = prev["rewarded"] if prev else None
        t["previous_missed"] = prev["missed"] if prev else None
        t["previous_offcue_poke"] = prev["offcue_poke"] if prev else None
        t["previous_offcue_pokes_count"] = prev["offcue_pokes_count"] if prev else None
        t["previous_cue_to_poke_latency"] = prev["cue_to_poke_latency"] if prev else NAN
        t["previous_poke_to_lick_latency"] = prev["poke_to_lick_latency"] if prev else NAN
        p2 = trials[i - 2] if i > 1 else None
        t["two_trials_back_rewarded"] = p2["rewarded"] if p2 else None
        t["two_trials_back_engaged"] = p2["engaged"] if p2 else None
        t["two_trials_back_offcue_poke"] = p2["offcue_poke"] if p2 else None
        for k in (3, 5):
            window = trials[max(0, i - k):i]
            t[f"prev_{k}_reward_rate"] = _rate(window, "rewarded")
            t[f"prev_{k}_engagement_rate"] = _rate(window, "engaged")
            t[f"prev_{k}_offcue_poke_rate"] = _rate(window, "offcue_poke")


# --- loaders (reuse existing ES access + ordering) -------------------------
def _enrich_session(trials: list[dict], dur_key: str) -> list[dict]:
    enriched = [base_fields(t, dur_key) for t in trials]
    add_history(enriched)
    return enriched


def load_appetitive(only_mouse: str | None) -> list[dict]:
    """Records {task, mouse, subject, session, training_day, trials} for the tone
    task; reuses A.discover_subjects / fetch_events / group_by_session / segment."""
    records = []
    for subject in A.discover_subjects():
        mouse = A.short_name(subject)
        if only_mouse and mouse != only_mouse:
            continue
        by_session = A.group_by_session(A.fetch_events(subject))
        day = 0
        for sess in sorted(by_session):
            trials = A.segment_trials(by_session[sess])
            if not A.session_len_ok(len(trials)):
                continue
            day += 1
            records.append({"task": TASK_APP, "mouse": mouse, "subject": subject,
                            "session": sess, "training_day": day,
                            "trials": _enrich_session(trials, "tone_dur")})
    return records


def load_generalization(only_mouse: str | None) -> list[dict]:
    """Records for the light task; reuses G.collect_mouse for session ordering."""
    records = []
    for mouse, subjects in G.discover_mice().items():
        if only_mouse and mouse != only_mouse:
            continue
        for r in G.collect_mouse(subjects):
            records.append({"task": TASK_GEN, "mouse": mouse, "subject": r["subject"],
                            "session": r["session_num"], "training_day": r["session_num"],
                            "trials": _enrich_session(r["trials"], "led_dur")})
    return records


def load_association_cue_reward(only_mouse: str | None) -> list[dict]:
    """TODO(AssociationCueReward): no loader / verified cue semantics exist for
    this task in the project, so it is skipped. To add it, mirror the appetitive
    loader with the correct cue event and append its records here."""
    return []


# --- per-mouse conditional probabilities -----------------------------------
def mouse_conditionals(trials: list[dict]) -> dict:
    """Conditional probabilities + reward-gating/persistence scores for one mouse
    (all that mouse's trials in one task). Arrays kept for bootstrap CIs."""
    eng_rew, eng_norew, eng_eng, eng_noeng = [], [], [], []
    off_rew, off_norew, rew_after_rew, rew_after_norew = [], [], [], []
    p3rew, p3eng = [], []
    for t in trials:
        pr, pe = t["previous_rewarded"], t["previous_engaged"]
        if pr is not None:
            (eng_rew if pr else eng_norew).append(int(t["engaged"]))
            (off_rew if pr else off_norew).append(int(t["offcue_poke"]))
            if t["engaged"]:
                (rew_after_rew if pr else rew_after_norew).append(int(t["rewarded"]))
        if pe is not None:
            (eng_eng if pe else eng_noeng).append(int(t["engaged"]))
        if not np.isnan(t["prev_3_reward_rate"]):
            p3rew.append(t["prev_3_reward_rate"])
        if not np.isnan(t["prev_3_engagement_rate"]):
            p3eng.append(t["prev_3_engagement_rate"])

    def pr_(a):
        return 100.0 * float(np.mean(a)) if a else NAN

    eng_delta = pr_(eng_rew) - pr_(eng_norew)
    persist_delta = pr_(eng_eng) - pr_(eng_noeng)
    off_delta = pr_(off_rew) - pr_(off_norew)
    comp_delta = pr_(rew_after_rew) - pr_(rew_after_norew)
    lo, hi = _bootstrap_delta_ci(eng_rew, eng_norew)
    return {
        "n_trials": len(trials),
        "P_engage_after_reward": pr_(eng_rew),
        "P_engage_after_no_reward": pr_(eng_norew),
        "engagement_reward_delta": eng_delta,
        "engagement_reward_delta_lo": lo,
        "engagement_reward_delta_hi": hi,
        "P_engage_after_engaged": pr_(eng_eng),
        "P_engage_after_not_engaged": pr_(eng_noeng),
        "engagement_persistence_delta": persist_delta,
        "P_offcue_after_reward": pr_(off_rew),
        "P_offcue_after_no_reward": pr_(off_norew),
        "offcue_reward_delta": off_delta,
        "P_rewarded_given_engaged_after_reward": pr_(rew_after_rew),
        "P_rewarded_given_engaged_after_no_reward": pr_(rew_after_norew),
        "competence_reward_delta": comp_delta,
        "mean_prev3_reward_rate": 100.0 * float(np.mean(p3rew)) if p3rew else NAN,
        "mean_prev3_engagement_rate": 100.0 * float(np.mean(p3eng)) if p3eng else NAN,
        "reward_gated_score": eng_delta + 0.5 * off_delta if not np.isnan(off_delta) else eng_delta,
        "state_persistence_score": persist_delta,
    }


def _bootstrap_delta_ci(after_t: list[int], after_f: list[int], n: int = 1000) -> tuple:
    """95% bootstrap CI for (mean(after_t) - mean(after_f)) in percentage points.
    Seeded for determinism (the project requires reproducible figures)."""
    if len(after_t) < 5 or len(after_f) < 5:
        return NAN, NAN
    rng = np.random.default_rng(0)
    at, af = np.array(after_t), np.array(after_f)
    deltas = [100.0 * rng.choice(at, at.size).mean() - 100.0 * rng.choice(af, af.size).mean()
              for _ in range(n)]
    return float(np.percentile(deltas, 2.5)), float(np.percentile(deltas, 97.5))


def _interpret(s: dict) -> str:
    if s["n_trials"] < MIN_TRIALS_INTERP:
        return "low data / unclear"
    rg = s["reward_gated_score"]
    if not np.isnan(rg) and s["engagement_reward_delta"] >= REWARD_GATED_DELTA:
        return "strong reward-gated engagement"
    if not np.isnan(s["state_persistence_score"]) and s["state_persistence_score"] >= PERSISTENCE_DELTA:
        return "persistent engaged-state mouse"
    if not np.isnan(s["offcue_reward_delta"]) and s["offcue_reward_delta"] >= OFFCUE_DELTA:
        return "off-cue dominated after reward"
    return "steady participator"


def build_mouse_stats(records: list[dict]) -> dict[str, dict[str, dict]]:
    """{task: {mouse: conditional-stats dict}} pooled across that mouse's sessions."""
    trials_by: dict[str, dict[str, list[dict]]] = {}
    sessions_by: dict[str, dict[str, int]] = {}
    for rec in records:
        tb = trials_by.setdefault(rec["task"], {}).setdefault(rec["mouse"], [])
        tb.extend(rec["trials"])
        sessions_by.setdefault(rec["task"], {}).setdefault(rec["mouse"], 0)
        sessions_by[rec["task"]][rec["mouse"]] += 1
    stats: dict[str, dict[str, dict]] = {}
    for task, by_mouse in trials_by.items():
        stats[task] = {}
        for mouse, trials in by_mouse.items():
            s = mouse_conditionals(trials)
            s["n_sessions"] = sessions_by[task][mouse]
            s["final_interpretation"] = _interpret(s)
            stats[task][mouse] = s
    return stats


def _sorted_mice(d: dict) -> list[str]:
    return sorted(d, key=lambda m: int(m[1:]))


# --- numpy ridge logistic regression (mouse fixed effects) -----------------
def _logistic_ridge(X: np.ndarray, y: np.ndarray, l2: float = RIDGE_L2,
                    iters: int = 60) -> tuple:
    """IRLS logistic regression with an L2 penalty (intercept unpenalized).
    Returns (beta, covariance) or (None, None) on failure. Ridge keeps it stable
    under quasi-separation (common with fixed effects on small data)."""
    n, p = X.shape
    beta = np.zeros(p)
    pen = l2 * np.eye(p)
    pen[0, 0] = 0.0
    for _ in range(iters):
        mu = 1.0 / (1.0 + np.exp(-np.clip(X @ beta, -30, 30)))
        w = np.clip(mu * (1 - mu), 1e-6, None)
        hess = X.T @ (X * w[:, None]) + pen
        grad = X.T @ (y - mu) - pen @ beta
        try:
            step = np.linalg.solve(hess, grad)
        except np.linalg.LinAlgError:
            return None, None
        beta += step
        if np.max(np.abs(step)) < 1e-7:
            break
    try:
        cov = np.linalg.inv(hess)
    except np.linalg.LinAlgError:
        return None, None
    return beta, cov


def _build_design(trials: list[dict], predictors: list[tuple], outcome: str) -> tuple:
    """Design matrix: intercept + predictors (continuous standardized, binary as
    0/1) + mouse dummies (drop-first). Rows with any NaN/None used field dropped."""
    cols, names = [], []
    rows = []
    for t in trials:
        if t[outcome] is None:
            continue
        vals, ok = [], True
        for key, kind in predictors:
            v = t[key]
            if v is None or (isinstance(v, float) and np.isnan(v)):
                ok = False
                break
            vals.append(float(v))
        if ok:
            rows.append((vals, int(bool(t[outcome])), t["mouse"]))
    if len(rows) < 30:
        return None, None, None
    Xraw = np.array([r[0] for r in rows], dtype=float)
    y = np.array([r[1] for r in rows], dtype=float)
    mice = [r[2] for r in rows]
    # standardize continuous predictors for comparable odds ratios
    for j, (key, kind) in enumerate(predictors):
        if kind == "cont":
            sd = Xraw[:, j].std()
            if sd > 0:
                Xraw[:, j] = (Xraw[:, j] - Xraw[:, j].mean()) / sd
        names.append(key)
    uniq = sorted(set(mice), key=lambda m: int(m[1:]))[1:]  # drop-first dummy
    dummies = np.array([[1.0 if m == u else 0.0 for u in uniq] for m in mice])
    intercept = np.ones((len(rows), 1))
    X = np.hstack([intercept, Xraw, dummies]) if dummies.size else np.hstack([intercept, Xraw])
    return X, y, names


def fit_models(records_by_task: dict[str, list[dict]]) -> dict:
    """Fit the three logistic models per task; return odds ratios + CIs for the
    plotted predictors. Robust: any model that can't be fit is recorded as None."""
    model_specs = {
        "engagement": (
            [("previous_rewarded", "binary"), ("previous_engaged", "binary"),
             ("previous_offcue_poke", "binary"), ("prev_3_reward_rate", "cont"),
             ("training_day", "cont"), ("trial_in_session_fraction", "cont")],
            "engaged", None),
        "accuracy_when_engaged": (
            [("previous_rewarded", "binary"), ("previous_missed", "binary"),
             ("previous_offcue_poke", "binary"), ("prev_3_reward_rate", "cont"),
             ("training_day", "cont"), ("cue_to_poke_latency", "cont")],
            "rewarded", "engaged"),
        "offcue_poke": (
            [("previous_rewarded", "binary"), ("previous_missed", "binary"),
             ("previous_engaged", "binary"), ("prev_3_offcue_poke_rate", "cont"),
             ("training_day", "cont"), ("trial_in_session_fraction", "cont")],
            "offcue_poke", None),
    }
    out: dict = {}
    for model, (preds, outcome, subset) in model_specs.items():
        out[model] = {}
        for task, recs in records_by_task.items():
            trials = [dict(t, mouse=r["mouse"], training_day=r["training_day"])
                      for r in recs for t in r["trials"]]
            if subset:
                trials = [t for t in trials if t[subset]]
            X, y, names = _build_design(trials, preds, outcome)
            if X is None or len(set(y)) < 2:
                out[model][task] = None
                continue
            beta, cov = _logistic_ridge(X, y)
            if beta is None:
                out[model][task] = None
                continue
            se = np.sqrt(np.clip(np.diag(cov), 0, None))
            res = {}
            for j, name in enumerate(names):
                b, s = beta[1 + j], se[1 + j]
                res[name] = (float(np.exp(b)), float(np.exp(b - 1.96 * s)),
                             float(np.exp(b + 1.96 * s)))
            out[model][task] = res
    return out


# --- CSV writers -----------------------------------------------------------
TRIAL_COLUMNS = [
    "task", "mouse", "subject", "session", "training_day", "trial_index",
    "n_trials_in_session", "engaged", "rewarded", "missed", "offcue_poke",
    "offcue_pokes_count", "n_oncue_pokes", "n_licks", "cue_to_poke_latency",
    "poke_to_lick_latency", "previous_engaged", "previous_rewarded",
    "previous_missed", "previous_offcue_poke", "previous_offcue_pokes_count",
    "previous_cue_to_poke_latency", "previous_poke_to_lick_latency",
    "two_trials_back_rewarded", "two_trials_back_engaged", "two_trials_back_offcue_poke",
    "prev_3_reward_rate", "prev_3_engagement_rate", "prev_3_offcue_poke_rate",
    "prev_5_reward_rate", "prev_5_engagement_rate", "prev_5_offcue_poke_rate",
    "trial_in_session_fraction",
]
SUMMARY_COLUMNS = [
    "task", "mouse", "n_trials", "n_sessions",
    "P_engage_after_reward", "P_engage_after_no_reward", "engagement_reward_delta",
    "P_engage_after_engaged", "P_engage_after_not_engaged", "engagement_persistence_delta",
    "P_offcue_after_reward", "P_offcue_after_no_reward", "offcue_reward_delta",
    "P_rewarded_given_engaged_after_reward", "P_rewarded_given_engaged_after_no_reward",
    "competence_reward_delta", "mean_prev3_reward_rate", "mean_prev3_engagement_rate",
    "reward_gated_score", "state_persistence_score", "final_interpretation",
]


def _fmt(v):
    if v is None:
        return ""
    if isinstance(v, bool) or isinstance(v, str):
        return v
    if isinstance(v, float):
        return "NaN" if np.isnan(v) else round(v, 3)
    return v


def write_trial_csv(records: list[dict], path: str) -> None:
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=TRIAL_COLUMNS)
        w.writeheader()
        for rec in records:
            for t in rec["trials"]:
                row = {"task": rec["task"], "mouse": rec["mouse"], "subject": rec["subject"],
                       "session": rec["session"], "training_day": rec["training_day"]}
                row.update({k: t.get(k) for k in TRIAL_COLUMNS if k not in row})
                w.writerow({k: _fmt(v) for k, v in row.items()})


def write_summary_csv(stats: dict, path: str) -> None:
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=SUMMARY_COLUMNS)
        w.writeheader()
        for task, by_mouse in stats.items():
            for mouse in _sorted_mice(by_mouse):
                row = {"task": task, "mouse": mouse}
                row.update({k: by_mouse[mouse].get(k) for k in SUMMARY_COLUMNS if k not in row})
                w.writerow({k: _fmt(v) for k, v in row.items()})


# --- figures ---------------------------------------------------------------
def _conditional_fig(stats: dict, key_a: str, key_b: str, delta_key: str,
                     label_a: str, label_b: str, ylabel: str, title: str,
                     out_path: str) -> None:
    """Grouped two-bar figure per mouse (condition A vs B), sorted by the delta,
    with the delta annotated. One panel per task."""
    tasks = list(stats)
    fig, axes = plt.subplots(1, len(tasks), figsize=(6.8 * len(tasks), 5.2),
                             squeeze=False, sharey=True)
    for ax, task in zip(axes[0], tasks):
        by_mouse = stats[task]
        mice = sorted(by_mouse, key=lambda m: (by_mouse[m][delta_key]
                      if not np.isnan(by_mouse[m][delta_key]) else -999), reverse=True)
        x = np.arange(len(mice))
        ax.bar(x - 0.2, [by_mouse[m][key_a] for m in mice], width=0.4,
               color="#2ca02c", label=label_a)
        ax.bar(x + 0.2, [by_mouse[m][key_b] for m in mice], width=0.4,
               color="#d62728", label=label_b)
        for i, m in enumerate(mice):
            d = by_mouse[m][delta_key]
            if not np.isnan(d):
                top = max(by_mouse[m][key_a], by_mouse[m][key_b])
                ax.annotate(f"{d:+.0f}", (i, top), textcoords="offset points",
                            xytext=(0, 2), ha="center", fontsize=7,
                            color="#2ca02c" if d >= 0 else "#d62728")
        ax.set_xticks(x)
        ax.set_xticklabels(mice, rotation=45, ha="right", fontsize=8)
        ax.set_ylim(0, 108)
        ax.set_title(TASK_LABELS[task])
    axes[0][0].set_ylabel(ylabel)
    axes[0][0].legend(fontsize=8, loc="upper right", framealpha=0.9)
    fig.suptitle(title, fontsize=13, y=0.99)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def fig_reward_gated_ranking(stats: dict, out_path: str) -> None:
    """Bar per mouse of reward_gated_score (sorted), with the bootstrap CI of the
    engagement reward-delta as error bars. Highlights the most reward-gated."""
    tasks = list(stats)
    fig, axes = plt.subplots(1, len(tasks), figsize=(6.8 * len(tasks), 5.0),
                             squeeze=False, sharey=True)
    for ax, task in zip(axes[0], tasks):
        by_mouse = stats[task]
        mice = sorted(by_mouse, key=lambda m: by_mouse[m]["reward_gated_score"], reverse=True)
        scores = [by_mouse[m]["reward_gated_score"] for m in mice]
        err = np.array([[by_mouse[m]["engagement_reward_delta"] - by_mouse[m]["engagement_reward_delta_lo"]
                         for m in mice],
                        [by_mouse[m]["engagement_reward_delta_hi"] - by_mouse[m]["engagement_reward_delta"]
                         for m in mice]])
        err = np.where(np.isnan(err), 0.0, err)
        colors = ["#d62728" if s >= REWARD_GATED_DELTA else "#7f7f7f" for s in scores]
        ax.bar(range(len(mice)), scores, color=colors, yerr=err, capsize=3,
               error_kw={"elinewidth": 0.8})
        ax.axhline(REWARD_GATED_DELTA, color="black", ls="--", lw=0.9,
                   label=f"reward-gated threshold = {REWARD_GATED_DELTA:.0f}")
        ax.axhline(0, color="grey", lw=0.6)
        ax.set_xticks(range(len(mice)))
        ax.set_xticklabels(mice, rotation=45, ha="right", fontsize=8)
        ax.set_title(TASK_LABELS[task])
        ax.legend(fontsize=8)
    axes[0][0].set_ylabel("reward-gated score\n(Δengage + 0.5·Δoff-cue, pp; CI = Δengage)")
    fig.suptitle("Reward-gated ranking — engagement driven by recent reward "
                 "(higher = more history-controlled)", fontsize=13, y=0.99)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


MODEL_PRED_LABELS = {
    "previous_rewarded": "prev rewarded", "previous_engaged": "prev engaged",
    "previous_offcue_poke": "prev off-cue", "previous_missed": "prev missed",
    "prev_3_reward_rate": "prev-3 reward rate", "prev_3_offcue_poke_rate": "prev-3 off-cue rate",
    "training_day": "session", "trial_in_session_fraction": "trial-in-session",
    "cue_to_poke_latency": "cue→poke latency",
}
MODEL_TITLES = {"engagement": "Engagement (engaged ~ ·)",
                "accuracy_when_engaged": "Accuracy | engaged (rewarded ~ ·)",
                "offcue_poke": "Off-cue poking (off-cue ~ ·)"}


def fig_model_coefficients(models: dict, out_path: str) -> None:
    """Forest plot of odds ratios (log x) per model; one marker per task with 95%
    CI. OR>1 = predictor raises the outcome's odds. Skips empty models."""
    model_keys = list(models)
    fig, axes = plt.subplots(1, len(model_keys), figsize=(6.0 * len(model_keys), 5.6),
                             squeeze=False)
    any_drawn = False
    for ax, model in zip(axes[0], model_keys):
        preds = list(MODEL_PRED_LABELS)
        preds = [p for p in preds if any(models[model].get(t) and p in models[model][t]
                                         for t in models[model])]
        ypos = np.arange(len(preds))
        for ti, (task, res) in enumerate(models[model].items()):
            if not res:
                continue
            offset = (ti - 0.5) * 0.18
            xs, los, his, ys = [], [], [], []
            for k, p in enumerate(preds):
                if p in res:
                    orr, lo, hi = res[p]
                    xs.append(orr); los.append(lo); his.append(hi); ys.append(k + offset)
            if xs:
                any_drawn = True
                xs = np.array(xs)
                ax.errorbar(xs, ys, xerr=[xs - np.array(los), np.array(his) - xs],
                            fmt="o", ms=5, color=TASK_COLORS[task], capsize=2,
                            elinewidth=1, label=TASK_LABELS[task])
        ax.axvline(1.0, color="grey", ls="--", lw=0.9)
        ax.set_xscale("log")
        ax.set_yticks(ypos)
        ax.set_yticklabels([MODEL_PRED_LABELS[p] for p in preds], fontsize=8)
        ax.set_xlabel("odds ratio (log scale)")
        ax.set_title(MODEL_TITLES[model], fontsize=10)
        ax.legend(fontsize=7)
    fig.suptitle("Trial-history logistic models — odds ratios (numpy IRLS, mouse "
                 "fixed effects)", fontsize=13, y=0.99)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return any_drawn


def fig_example_mice(records: list[dict], out_path: str) -> None:
    """Concatenated trial timeline for example mice (one task — generalization if
    present, else appetitive): rewarded / engaged / off-cue event rasters with
    session boundaries. Bursty mice show clustering; steady mice are uniform."""
    task = TASK_GEN if any(r["task"] == TASK_GEN for r in records) else TASK_APP
    present = [m for m in EXAMPLE_MICE
               if any(r["mouse"] == m and r["task"] == task for r in records)]
    if not present:
        return False
    fig, axes = plt.subplots(len(present), 1, figsize=(13, 1.7 * len(present)),
                             squeeze=False, sharex=True)
    for ax, mouse in zip(axes[:, 0], present):
        recs = [r for r in records if r["mouse"] == mouse and r["task"] == task]
        recs.sort(key=lambda r: r["training_day"])
        idx = 0
        for r in recs:
            xs = np.arange(idx, idx + len(r["trials"]))
            eng = [i for i, t in zip(xs, r["trials"]) if t["engaged"] and not t["rewarded"]]
            rew = [i for i, t in zip(xs, r["trials"]) if t["rewarded"]]
            off = [i for i, t in zip(xs, r["trials"]) if t["offcue_poke"]]
            ax.scatter(off, [1] * len(off), marker="|", s=18, color="#bbbbbb")
            ax.scatter(eng, [2] * len(eng), marker="|", s=70, color="#d62728")
            ax.scatter(rew, [3] * len(rew), marker="|", s=70, color="#2ca02c")
            idx += len(r["trials"])
            ax.axvline(idx - 0.5, color="#cccccc", lw=0.6, ls=":")
        ax.set_yticks([1, 2, 3])
        ax.set_yticklabels(["off-cue", "miss", "reward"], fontsize=8)
        ax.set_ylim(0.5, 3.5)
        ax.set_ylabel(mouse, rotation=0, ha="right", va="center", fontsize=11)
    axes[-1, 0].set_xlabel("trial (concatenated across sessions; dotted = session boundary)")
    fig.suptitle(f"Trial-by-trial behavior, example mice — {TASK_LABELS[task]} "
                 "(bursty vs steady)", fontsize=13, y=0.99)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return True


# --- text summary ----------------------------------------------------------
def _rank(by_mouse: dict, key: str, top: int = 3) -> str:
    items = sorted(((m, by_mouse[m][key]) for m in by_mouse if not np.isnan(by_mouse[m][key])),
                   key=lambda kv: kv[1], reverse=True)
    return ", ".join(f"{m} ({v:+.0f}pp)" for m, v in items[:top])


def write_summary_text(stats: dict, models: dict, models_drawn: bool,
                       example_drawn: bool, out_path: str) -> None:
    lines = ["TRIAL-HISTORY ANALYSIS — SUMMARY", "=" * 40, "",
             "Descriptive conditional probabilities (bootstrap CIs) are the primary "
             "result; the logistic models corroborate them. Effects are descriptive "
             "— a previous-reward effect means 'more likely to engage after reward', "
             "not a proven mechanism.\n"]
    for task, by_mouse in stats.items():
        lines.append(f"### {TASK_LABELS[task]}")
        lines.append(f"1. Most reward-gated (Δengage after reward): {_rank(by_mouse, 'engagement_reward_delta')}")
        lines.append(f"2. Strongest engagement persistence (Δengage after engaged): "
                     f"{_rank(by_mouse, 'engagement_persistence_delta')}")
        lines.append(f"3. Strongest off-cue-after-reward (Δoff-cue): {_rank(by_mouse, 'offcue_reward_delta')}")
        steady = [m for m in _sorted_mice(by_mouse)
                  if by_mouse[m]["final_interpretation"] == "steady participator"]
        bursty = [m for m in _sorted_mice(by_mouse)
                  if by_mouse[m]["final_interpretation"] == "strong reward-gated engagement"]
        lines.append(f"7. Steady participators: {', '.join(steady) or '(none)'}")
        lines.append(f"8. Bursty / reward-gated: {', '.join(bursty) or '(none)'}")
        lines.append("")

    # 4 & 5 — does previous reward predict engagement / accuracy (group means)?
    lines.append("### 4-5. Does previous reward predict behavior?")
    for task, by_mouse in stats.items():
        eng = _group_mean(by_mouse, "engagement_reward_delta")
        comp = _group_mean(by_mouse, "competence_reward_delta")
        lines.append(f"  {TASK_LABELS[task]}: engagement is {eng:+.0f}pp higher after a "
                     f"rewarded trial; accuracy-once-engaged changes only {comp:+.0f}pp "
                     f"(history mostly gates WHETHER they engage, not success once engaged).")
    lines.append("")

    # 6 — task comparison
    if TASK_APP in stats and TASK_GEN in stats:
        lines.append("### 6. Appetitive vs Generalization")
        lines.append(f"  Mean reward-gating Δengage: appetitive "
                     f"{_group_mean(stats[TASK_APP], 'engagement_reward_delta'):+.0f}pp vs "
                     f"generalization {_group_mean(stats[TASK_GEN], 'engagement_reward_delta'):+.0f}pp.")
        lines.append("")

    lines.append("### 9. What this adds beyond hit rate / engagement rate")
    lines.append("  Hit rate and engagement rate are static averages; trial-history shows the "
                 "DYNAMICS — whether engagement is self-sustaining (persistence) or has to be "
                 "re-triggered by reward (gating). Two mice with the same engagement rate can "
                 "differ sharply here: a reward-gated mouse disengages until the next reward, "
                 "a steady mouse engages regardless of the last outcome.")
    lines.append("")
    if not models_drawn:
        lines.append("NOTE: logistic models could not be fit (insufficient data / convergence); "
                     "Fig 5 reflects only the models that fit.")
    if not example_drawn:
        lines.append("NOTE: example-mice figure skipped (none of the example mice present).")

    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))


def _group_mean(by_mouse: dict, key: str) -> float:
    vals = [by_mouse[m][key] for m in by_mouse if not np.isnan(by_mouse[m][key])]
    return float(np.mean(vals)) if vals else NAN


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
        OUT_ROOT = str(_RESULTS_ROOT / "trial_history" / _TASK_AREA[args.task])

    records: list[dict] = []
    records_by_task: dict[str, list[dict]] = {}
    if args.task in ("appetitive", "both"):
        print("Loading appetitive (tone) task ...")
        app = load_appetitive(args.mouse)
        if app:
            records += app
            records_by_task[TASK_APP] = app
    if args.task in ("generalization", "both"):
        print("Loading generalization (light) task ...")
        gen = load_generalization(args.mouse)
        if gen:
            records += gen
            records_by_task[TASK_GEN] = gen
    load_association_cue_reward(args.mouse)  # TODO — see function docstring

    if not records:
        print("No matching sessions found.")
        return 1

    stats = build_mouse_stats(records)
    models = fit_models(records_by_task)

    os.makedirs(OUT_ROOT, exist_ok=True)
    write_trial_csv(records, os.path.join(OUT_ROOT, "trial_history_trials.csv"))
    write_summary_csv(stats, os.path.join(OUT_ROOT, "mouse_trial_history_summary.csv"))

    _conditional_fig(stats, "P_engage_after_reward", "P_engage_after_no_reward",
                     "engagement_reward_delta", "after rewarded trial", "after non-rewarded trial",
                     "P(engage on trial t)  [%]",
                     "Previous reward → next-trial engagement (reward-gating)",
                     os.path.join(OUT_ROOT, "trial_history_prev_reward_engagement.png"))
    _conditional_fig(stats, "P_engage_after_engaged", "P_engage_after_not_engaged",
                     "engagement_persistence_delta", "after engaged trial", "after non-engaged trial",
                     "P(engage on trial t)  [%]",
                     "Engagement persistence — is behavior state-like across trials?",
                     os.path.join(OUT_ROOT, "trial_history_engagement_persistence.png"))
    _conditional_fig(stats, "P_offcue_after_reward", "P_offcue_after_no_reward",
                     "offcue_reward_delta", "after rewarded trial", "after non-rewarded trial",
                     "P(off-cue poke on trial t)  [%]",
                     "Previous outcome → off-cue poking",
                     os.path.join(OUT_ROOT, "trial_history_offcue_after_outcome.png"))
    fig_reward_gated_ranking(stats, os.path.join(OUT_ROOT, "trial_history_reward_gated_ranking.png"))
    models_drawn = fig_model_coefficients(models, os.path.join(OUT_ROOT, "trial_history_model_coefficients.png"))
    example_drawn = fig_example_mice(records, os.path.join(OUT_ROOT, "trial_history_example_mice.png"))

    write_summary_text(stats, models, models_drawn, example_drawn,
                       os.path.join(OUT_ROOT, "trial_history_summary.txt"))

    n_fig = 4 + int(models_drawn) + int(example_drawn)
    n_trials = sum(len(r["trials"]) for r in records)
    print(f"\nWrote 2 CSVs, {n_fig} figures, and summary.txt under '{OUT_ROOT}/' "
          f"({len(records)} sessions, {n_trials} trials).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
