#!/usr/bin/env python3
"""Action-sequence analysis — where in the behavioral chain each mouse succeeds
or fails, per mouse / session / task.

The usual hit-rate hides *why* a mouse fails. This script decomposes every trial
into the behavioral chain and asks, at each link:

    cue presented -> on-cue poke -> lick after poke -> reward -> (off-cue noise)

so a low hit rate can be attributed to low engagement, poke-without-lick,
lick-without-reward, slow reward collection, off-cue impulsivity, or
reward-gated participation.

Data loading is reused from the existing scripts (same Elasticsearch setup and
env vars): `appetitive_analysis` (tone task) and `generalization_analysis`
(light task) supply the ES fetch / subject discovery / session ordering. The
event semantics are identical to those scripts (verified against the raw
stream); see `_appetitive_cue` / `_generalization_cue`.

We re-segment trials here (rather than calling their `segment_trials`) only
because this analysis needs the absolute cue-onset time and the reward time,
which their lean trial objects drop. The segmentation *logic* is the same.

Trial categories (mutually exclusive, used for the stacked bars + transitions):
    no_response                  cue, but no poke during the cue window
    cue_poke_no_lick             on-cue poke, but no lick afterwards
    cue_poke_lick_no_reward      on-cue poke + lick, but no reward
    complete_sequence_rewarded   on-cue poke + lick + reward
    offcue_poke_only             no on-cue poke, but poke(s) outside the cue

LIMITATION — "mixed_offcue_and_oncue": off-cue / ITI poking is near-universal in
this dataset (most engaged trials also have an ITI poke), so treating "mixed" as
a sixth *exclusive* slice would cannibalise the chain categories and make the
figures unreadable. We therefore keep the five chain categories exclusive
(they sum to 100%) and report `mixed` as a separate, overlapping diagnostic
(`percent_mixed_offcue_and_oncue` + the P(off-cue poke | trial) trajectory).

Usage:
    python3 action_sequence_analysis.py                  # both tasks, all mice
    python3 action_sequence_analysis.py --task appetitive
    python3 action_sequence_analysis.py --task generalization
    python3 action_sequence_analysis.py --mouse m102
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

# Output routes by task into results/action_sequence/<area>/ (env var overrides).
# Reassigned in main() once --task is known; this default covers `--task both`.
_RESULTS_ROOT = Path(__file__).resolve().parent / "results"
_TASK_AREA = {"appetitive": "appetitive", "generalization": "generalization", "both": "cross_task"}
_ENV_OUT = os.environ.get("MICS_ACTSEQ_OUT")
OUT_ROOT = _ENV_OUT or str(_RESULTS_ROOT / "action_sequence" / "cross_task")
NAN = float("nan")

TASK_APP = "AppetitveTaskReal"
TASK_GEN = "Generalization"
TASK_LABELS = {TASK_APP: "Appetitive (tone)", TASK_GEN: "Generalization (light)"}

# shared event-id constants (identical across both existing scripts)
ID_NOSEPOKE, ID_LICK, ID_REWARD = "IR1", "TOUCH_INT", "open"
REWARD_DEDUPE_GAP_S = 0.3

# stacked-bar order: bottom (best) -> top (worst/noise); (key, label, color)
CATEGORIES = [
    ("complete_sequence_rewarded", "complete: poke -> lick -> reward", "#2ca02c"),
    ("cue_poke_lick_no_reward", "poke + lick, no reward", "#fee08b"),
    ("cue_poke_no_lick", "on-cue poke, no lick", "#fdae6b"),
    ("no_response", "no response (cue, no on-cue poke)", "#bdbdbd"),
    ("offcue_poke_only", "off-cue poke only", "#6baed6"),
]
CATEGORY_KEYS = [k for k, _, _ in CATEGORIES]


# --- trial enrichment & classification ------------------------------------
def _dedupe(times: list[float], gap: float = REWARD_DEDUPE_GAP_S) -> list[float]:
    """Collapse near-simultaneous events (reuses the existing scripts' rule)."""
    kept: list[float] = []
    for t in sorted(times):
        if not kept or t - kept[-1] > gap:
            kept.append(t)
    return kept


def _appetitive_cue(window: list[dict], fallback: float) -> tuple[float, float]:
    """Tone onset (t=0) and actual tone duration for one appetitive trial."""
    tone = next((e for e in window if e["etype"] == A.ET_AUDIO
                 and e["func"] == "set_by_filename" and e["level"] == 1), None)
    t0 = tone["epoch"] if tone else window[0]["epoch"]
    mute = next((e for e in window if e["etype"] == A.ET_AUDIO
                 and e["func"] == "mute" and e["epoch"] > t0), None)
    return t0, (mute["epoch"] - t0) if mute else fallback


def _generalization_cue(window: list[dict], fallback: float) -> tuple[float, float]:
    """LED2 onset (t=0) and actual cue duration for one generalization trial."""
    led_on = next((e for e in window if e["etype"] == G.ET_DIGITAL_OUT
                   and e["id"] == G.ID_LED and e["level"] == 1), None)
    if led_on is None:
        stim = next((e for e in window if e["etype"] == A.ET_STATE
                     and e["state"] == "stimulus"), None)
        t0 = stim["epoch"] if stim else window[0]["epoch"]
    else:
        t0 = led_on["epoch"]
    led_off = next((e for e in window if e["etype"] == G.ET_DIGITAL_OUT
                    and e["id"] == G.ID_LED and e["level"] == 0 and e["epoch"] > t0), None)
    return t0, (led_off["epoch"] - t0) if led_off else fallback


def _classify(engaged: bool, licked: bool, rewarded: bool, has_offcue: bool) -> str:
    """One of the five mutually-exclusive chain categories (see module docstring)."""
    if engaged:
        if rewarded and licked:
            return "complete_sequence_rewarded"
        if licked:
            return "cue_poke_lick_no_reward"
        return "cue_poke_no_lick"
    return "offcue_poke_only" if has_offcue else "no_response"


def _build_trial(t0: float, dur: float, pokes: list[float],
                 licks: list[float], rewards: list[float]) -> dict:
    """Compute every per-trial metric from cue-relative event times."""
    on_cue = sorted(p for p in pokes if 0 <= p <= dur)
    off_cue = sorted(p for p in pokes if p < 0 or p > dur)  # before cue or after offset/ITI
    # off-cue licks: symmetric with off-cue pokes (outside the cue window). NOTE
    # these include reward-consumption licks during the post-cue/ITI period.
    off_cue_licks = [lk for lk in licks if lk < 0 or lk > dur]
    first_on = on_cue[0] if on_cue else NAN
    first_off = off_cue[0] if off_cue else NAN
    licks_after = [lk for lk in licks if on_cue and lk >= first_on]
    first_lick_after = min(licks_after) if licks_after else NAN
    reward_time = min(rewards) if rewards else NAN

    engaged = bool(on_cue)
    licked_after = bool(licks_after)
    rewarded = bool(rewards)
    return {
        "cue_on_time": t0,
        "cue_duration": dur,
        "n_oncue_pokes": len(on_cue),
        "n_offcue_pokes": len(off_cue),
        "n_offcue_licks": len(off_cue_licks),
        "first_oncue_poke_time": first_on,
        "first_offcue_poke_time": first_off,
        "first_lick_after_oncue_poke_time": first_lick_after,
        "reward_time": reward_time,
        "action_sequence_category": _classify(engaged, licked_after, rewarded, bool(off_cue)),
        "engaged": engaged,
        "licked_after_poke": licked_after,
        "rewarded": rewarded,
        "mixed": engaged and bool(off_cue),  # overlapping diagnostic, not a stack slice
        "cue_to_first_oncue_poke_latency": first_on,  # cue onset is t=0
        "poke_to_first_lick_latency": (first_lick_after - first_on) if (engaged and licked_after) else NAN,
        "lick_to_reward_latency": (reward_time - first_lick_after) if (licked_after and rewarded) else NAN,
    }


def enrich_trials(events: list[dict], find_cue, fallback_dur: float) -> list[dict]:
    """Segment one session's flat events into enriched trials (same trial_onset
    boundaries and event semantics as the existing scripts)."""
    events = sorted(events, key=lambda e: e["epoch"])
    onsets = [i for i, e in enumerate(events)
              if e["etype"] == A.ET_STATE and e["state"] == "trial_onset"]
    if not onsets:
        return []
    bounds = onsets + [len(events)]
    trials: list[dict] = []
    for k in range(len(onsets)):
        window = events[bounds[k]:bounds[k + 1]]
        t0, dur = find_cue(window, fallback_dur)
        pokes, licks, rewards = [], [], []
        for e in window:
            if e["etype"] == A.ET_DIGITAL_IN and e["id"] == ID_NOSEPOKE and e["level"] == 1:
                pokes.append(e["epoch"] - t0)
            elif e["etype"] == A.ET_DIGITAL_IN and e["id"] == ID_LICK:
                licks.append(e["epoch"] - t0)
            elif (e["etype"] == A.ET_SOLENOID and e["id"] == ID_REWARD
                  and e["func"] == "store_series"):
                rewards.append(e["epoch"] - t0)
        trials.append(_build_trial(t0, dur, pokes, licks, _dedupe(rewards)))
    _add_history(trials)
    return trials


def _add_history(trials: list[dict]) -> None:
    """Attach previous-trial fields (NaN/None on the first trial of a session)."""
    for i, t in enumerate(trials):
        prev = trials[i - 1] if i > 0 else None
        t["previous_trial_category"] = prev["action_sequence_category"] if prev else None
        t["previous_trial_rewarded"] = prev["rewarded"] if prev else None
        t["previous_trial_engaged"] = prev["engaged"] if prev else None


# --- per-task loaders (reuse existing ES access + ordering) ----------------
def load_appetitive(only_mouse: str | None) -> list[dict]:
    """Session records for the appetitive task; reuses A.discover_subjects /
    A.fetch_events / A.group_by_session. training_day = qualifying-session index."""
    records: list[dict] = []
    for subject in A.discover_subjects():
        mouse = A.short_name(subject)
        if only_mouse and mouse != only_mouse:
            continue
        by_session = A.group_by_session(A.fetch_events(subject))
        day = 0
        for sess in sorted(by_session):
            trials = enrich_trials(by_session[sess], _appetitive_cue, A.TONE_FILE_LENGTH_S)
            if not A.session_len_ok(len(trials)):
                continue
            day += 1
            records.append({"task": TASK_APP, "mouse": mouse, "subject": subject,
                            "raw_session": sess, "session": day, "training_day": day,
                            "trials": trials})
    return records


def load_generalization(only_mouse: str | None) -> list[dict]:
    """Session records for the generalization task; mirrors
    generalization_analysis.collect_mouse ordering (merge the two GenLight subject
    strings, drop short sessions, sort by start time, reindex 1..N, cap at 4)."""
    records: list[dict] = []
    for mouse, subjects in G.discover_mice().items():
        if only_mouse and mouse != only_mouse:
            continue
        sessions: list[dict] = []
        for subject in subjects:
            by_session: dict[int, list[dict]] = {}
            for e in G.fetch_events(subject):
                by_session.setdefault(e["session"], []).append(e)
            for evs in by_session.values():
                trials = enrich_trials(evs, _generalization_cue, G.LED_WINDOW_S)
                if not G.session_len_ok(len(trials)):
                    continue
                sessions.append({"subject": subject, "raw_session": evs[0]["session"],
                                 "start": min(e["epoch"] for e in evs), "trials": trials})
        sessions.sort(key=lambda r: r["start"])
        for i, r in enumerate(sessions, start=1):
            if i > G.MAX_SESSION:
                break
            records.append({"task": TASK_GEN, "mouse": mouse, "subject": r["subject"],
                            "raw_session": r["raw_session"], "session": i, "training_day": i,
                            "trials": r["trials"]})
    return records


def load_association_cue_reward(only_mouse: str | None) -> list[dict]:
    """TODO(AssociationCueReward): the existing scripts have no loader, subject
    pattern, or verified cue semantics for this task, so it is not loaded here.
    To add it: confirm its cue event (tone vs LED) and subject-string pattern
    against the raw ES stream, then add a discover/fetch pair (mirroring
    appetitive_analysis) and a cue-finder, and append its records below."""
    return []


# --- session summary -------------------------------------------------------
def _nanmedian(vals: list[float]) -> float:
    arr = np.array(vals, dtype=float)
    arr = arr[~np.isnan(arr)]
    return float(np.median(arr)) if arr.size else NAN


def summarize_session(rec: dict) -> dict:
    """One row per (task, mouse, session): category %, conditional chain rates,
    median latencies. The five percent_* chain categories sum to 100;
    percent_mixed_offcue_and_oncue is an overlapping diagnostic."""
    trials = rec["trials"]
    n = len(trials)
    cats = [t["action_sequence_category"] for t in trials]
    engaged = [t for t in trials if t["engaged"]]
    eng_licked = [t for t in engaged if t["licked_after_poke"]]

    def pct(key: str) -> float:
        return 100.0 * cats.count(key) / n

    return {
        "task": rec["task"], "mouse": rec["mouse"], "session": rec["session"],
        "n_trials": n,
        "percent_no_response": pct("no_response"),
        "percent_cue_poke_no_lick": pct("cue_poke_no_lick"),
        "percent_cue_poke_lick_no_reward": pct("cue_poke_lick_no_reward"),
        "percent_complete_sequence_rewarded": pct("complete_sequence_rewarded"),
        "percent_offcue_poke_only": pct("offcue_poke_only"),
        "percent_mixed_offcue_and_oncue": 100.0 * sum(t["mixed"] for t in trials) / n,
        "engagement_rate": 100.0 * len(engaged) / n,
        "lick_given_oncue_poke_rate": 100.0 * len(eng_licked) / len(engaged) if engaged else NAN,
        "reward_given_oncue_poke_rate":
            100.0 * sum(t["rewarded"] for t in engaged) / len(engaged) if engaged else NAN,
        "reward_given_poke_and_lick_rate":
            100.0 * sum(t["rewarded"] for t in eng_licked) / len(eng_licked) if eng_licked else NAN,
        "median_cue_to_poke_latency": _nanmedian([t["cue_to_first_oncue_poke_latency"] for t in trials]),
        "median_poke_to_lick_latency": _nanmedian([t["poke_to_first_lick_latency"] for t in trials]),
        "median_lick_to_reward_latency": _nanmedian([t["lick_to_reward_latency"] for t in trials]),
        # extra diagnostics used by figures (not in the CSV column list)
        "offcue_trial_rate": 100.0 * sum(t["n_offcue_pokes"] > 0 for t in trials) / n,
        "offcue_pokes_per_trial": float(np.mean([t["n_offcue_pokes"] for t in trials])),
        "offcue_licks_per_trial": float(np.mean([t["n_offcue_licks"] for t in trials])),
    }


# --- CSV writers -----------------------------------------------------------
TRIAL_COLUMNS = [
    "task", "mouse", "subject", "session", "training_day", "trial_index",
    "cue_on_time", "cue_duration", "n_oncue_pokes", "n_offcue_pokes", "n_offcue_licks",
    "first_oncue_poke_time", "first_offcue_poke_time",
    "first_lick_after_oncue_poke_time", "reward_time", "action_sequence_category",
    "engaged", "licked_after_poke", "rewarded",
    "cue_to_first_oncue_poke_latency", "poke_to_first_lick_latency",
    "lick_to_reward_latency", "previous_trial_category",
    "previous_trial_rewarded", "previous_trial_engaged",
]
SUMMARY_COLUMNS = [
    "task", "mouse", "session", "n_trials",
    "percent_no_response", "percent_cue_poke_no_lick",
    "percent_cue_poke_lick_no_reward", "percent_complete_sequence_rewarded",
    "percent_offcue_poke_only", "percent_mixed_offcue_and_oncue",
    "engagement_rate", "lick_given_oncue_poke_rate", "reward_given_oncue_poke_rate",
    "reward_given_poke_and_lick_rate", "median_cue_to_poke_latency",
    "median_poke_to_lick_latency", "median_lick_to_reward_latency",
]


def _fmt(v):
    if isinstance(v, bool) or v is None or isinstance(v, str):
        return "" if v is None else v
    if isinstance(v, float):
        return "NaN" if np.isnan(v) else round(v, 3)
    return v


def write_trial_csv(records: list[dict], out_path: str) -> None:
    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=TRIAL_COLUMNS)
        w.writeheader()
        for rec in records:
            for idx, t in enumerate(rec["trials"], start=1):
                row = {"task": rec["task"], "mouse": rec["mouse"], "subject": rec["subject"],
                       "session": rec["raw_session"], "training_day": rec["training_day"],
                       "trial_index": idx}
                row.update({k: t.get(k) for k in TRIAL_COLUMNS if k not in row})
                w.writerow({k: _fmt(v) for k, v in row.items()})


def write_summary_csv(summaries: list[dict], out_path: str) -> None:
    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=SUMMARY_COLUMNS)
        w.writeheader()
        for s in summaries:
            w.writerow({k: _fmt(s[k]) for k in SUMMARY_COLUMNS})


# --- figure helpers --------------------------------------------------------
def _by_task_mouse(summaries: list[dict]) -> dict[str, dict[str, list[dict]]]:
    """{task: {mouse: [session summaries sorted by session]}}."""
    out: dict[str, dict[str, list[dict]]] = {}
    for s in summaries:
        out.setdefault(s["task"], {}).setdefault(s["mouse"], []).append(s)
    for by_mouse in out.values():
        for rows in by_mouse.values():
            rows.sort(key=lambda r: r["session"])
    return out


def _sorted_mice(by_mouse: dict[str, list[dict]]) -> list[str]:
    return sorted(by_mouse, key=lambda m: int(m[1:]))


def _mean_sem(values: list[float]) -> tuple[float, float]:
    arr = np.array(values, dtype=float)
    arr = arr[~np.isnan(arr)]
    if arr.size == 0:
        return NAN, NAN
    sem = float(np.std(arr, ddof=1) / np.sqrt(arr.size)) if arr.size > 1 else 0.0
    return float(np.mean(arr)), sem


# --- Figure 1: stacked action-sequence bars per mouse ----------------------
def fig_stacked_by_mouse(by_task: dict, out_path: str) -> None:
    ncol = 5
    blocks = [(task, _sorted_mice(by_task[task])) for task in by_task]
    rows_per = [(len(m) + ncol - 1) // ncol for _, m in blocks]
    total_rows = sum(rows_per)
    fig, axes = plt.subplots(total_rows, ncol, figsize=(3.1 * ncol, 2.5 * total_rows),
                             squeeze=False)
    for ax in axes.reshape(-1):
        ax.axis("off")
    r0 = 0
    for (task, mice), nrow in zip(blocks, rows_per):
        for j, mouse in enumerate(mice):
            ax = axes[r0 + j // ncol][j % ncol]
            ax.axis("on")
            rows = by_task[task][mouse]
            x = [r["session"] for r in rows]
            bottom = np.zeros(len(rows))
            for key, _, color in CATEGORIES:
                vals = np.array([r[f"percent_{key}"] for r in rows])
                ax.bar(x, vals, bottom=bottom, color=color, width=0.8,
                       edgecolor="white", linewidth=0.3)
                bottom += vals
            ax.set_ylim(0, 100)
            ax.set_xticks(x)
            ax.xaxis.set_major_locator(MaxNLocator(integer=True))
            ax.tick_params(labelsize=7)
            ax.set_title(mouse, fontsize=10)
        axes[r0][0].set_ylabel(f"{TASK_LABELS[task]}\n% of trials", fontsize=9)
        r0 += nrow
    handles = [mpatches.Patch(color=c, label=lab) for _, lab, c in CATEGORIES]
    fig.legend(handles=handles, loc="upper center", ncol=len(CATEGORIES),
               fontsize=8, bbox_to_anchor=(0.5, 1.0))
    fig.suptitle("Action-sequence breakdown per mouse & session "
                 "(where the behavioral chain breaks)", y=1.04, fontsize=13)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


# --- Figure 2: group action-sequence trajectory ----------------------------
TRAJECTORY_METRICS = [
    ("engagement_rate", "P(on-cue poke | cue)", "#1f77b4"),
    ("lick_given_oncue_poke_rate", "P(lick | on-cue poke)", "#ff7f0e"),
    ("reward_given_oncue_poke_rate", "P(reward | on-cue poke)", "#2ca02c"),
    ("reward_given_poke_and_lick_rate", "P(reward | poke + lick)", "#9467bd"),
    ("offcue_trial_rate", "P(off-cue poke | trial)", "#8c8c8c"),
]


def fig_group_trajectory(by_task: dict, out_path: str) -> None:
    tasks = list(by_task)
    fig, axes = plt.subplots(1, len(tasks), figsize=(7 * len(tasks), 5.4),
                             squeeze=False, sharey=True)
    for ax, task in zip(axes[0], tasks):
        by_mouse = by_task[task]
        max_s = max((r["session"] for rows in by_mouse.values() for r in rows), default=1)
        sessions = list(range(1, max_s + 1))
        for key, label, color in TRAJECTORY_METRICS:
            means, sems = [], []
            for s in sessions:
                vals = [r[key] for rows in by_mouse.values() for r in rows if r["session"] == s]
                m, e = _mean_sem(vals)
                means.append(m)
                sems.append(e)
            means, sems = np.array(means), np.array(sems)
            ax.plot(sessions, means, "-o", color=color, lw=2, ms=4, label=label)
            ax.fill_between(sessions, means - sems, means + sems, color=color, alpha=0.15)
        ax.set_ylim(0, 100)
        ax.set_xlim(0.5, max_s + 0.5)
        ax.xaxis.set_major_locator(MaxNLocator(integer=True))
        ax.set_xlabel("session #")
        ax.set_title(TASK_LABELS[task])
    axes[0][0].set_ylabel("probability (%)")
    axes[0][0].legend(fontsize=8, loc="lower left", framealpha=0.9)
    fig.suptitle("Group action-sequence trajectory — which chain link improves "
                 "across sessions?", fontsize=13)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


# --- Figure 3: per-mouse behavioral funnel (late sessions) -----------------
def _avg_late(rows: list[dict], key: str, k: int = 2) -> float:
    return _mean_sem([r[key] for r in rows[-k:]])[0]


def fig_action_chain_by_mouse(by_task: dict, out_path: str) -> None:
    """Per-mouse dynamics across sessions. Left axis (% of trials): on-cue poke,
    on-cue poke + lick afterwards. Right axis (events per trial): off-cue pokes,
    off-cue licks. One panel per mouse; line style/marker distinguishes task when
    more than one is present. Off-cue licks include reward-consumption licking."""
    all_mice = sorted({m for by_mouse in by_task.values() for m in by_mouse},
                      key=lambda m: int(m[1:]))
    ncol = 5
    nrow = (len(all_mice) + ncol - 1) // ncol
    fig, axes = plt.subplots(nrow, ncol, figsize=(3.2 * ncol, 2.7 * nrow),
                             squeeze=False, sharey=True)
    # (label, color, summary key) — first two on the left % axis, last two on right.
    pct_metrics = [("on-cue poke", "#1f77b4", "engagement_rate"),
                   ("on-cue poke + lick", "#ff7f0e", None)]
    cnt_metrics = [("off-cue pokes/trial (right)", "#2ca02c", "offcue_pokes_per_trial"),
                   ("off-cue licks/trial (right)", "#d62728", "offcue_licks_per_trial")]
    task_style = {TASK_APP: "-", TASK_GEN: "--"}
    task_marker = {TASK_APP: "o", TASK_GEN: "s"}
    multi_task = len(by_task) > 1
    max_s = max((r["session"] for bm in by_task.values() for rows in bm.values()
                 for r in rows), default=1)
    max_cnt = max((r[k] for bm in by_task.values() for rows in bm.values()
                   for r in rows for _, _, k in cnt_metrics), default=1.0) * 1.08
    for ax in axes.reshape(-1):
        ax.axis("off")
    for i, mouse in enumerate(all_mice):
        ax = axes[i // ncol][i % ncol]
        ax.axis("on")
        ax2 = ax.twinx()
        last_col = i % ncol == ncol - 1
        for task in by_task:
            rows = by_task[task].get(mouse)
            if not rows:
                continue
            x = [r["session"] for r in rows]
            oncue = [r["engagement_rate"] for r in rows]
            oncue_lick = [r["percent_complete_sequence_rewarded"]
                          + r["percent_cue_poke_lick_no_reward"] for r in rows]
            for vals, (_, color, _) in zip((oncue, oncue_lick), pct_metrics):
                ax.plot(x, vals, task_style[task], color=color,
                        marker=task_marker[task], lw=1.8, ms=4, zorder=3)
            for _, color, key in cnt_metrics:
                ax2.plot(x, [r[key] for r in rows], task_style[task], color=color,
                         marker=task_marker[task], lw=1.3, ms=3, alpha=0.8, zorder=2)
        ax.set_ylim(0, 100)
        ax.set_xlim(0.5, max_s + 0.5)
        ax2.set_ylim(0, max_cnt)
        ax.xaxis.set_major_locator(MaxNLocator(integer=True))
        ax.set_xlabel("session #", fontsize=8)
        ax.set_title(mouse, fontsize=10)
        ax.tick_params(labelsize=7)
        ax2.tick_params(labelsize=7, colors="#555555")
        if not last_col:
            ax2.tick_params(labelright=False, right=False)
        elif i == ncol - 1:
            ax2.set_ylabel("off-cue events / trial", fontsize=9, color="#555555")
    axes[0][0].set_ylabel("% of trials")
    handles = [mpatches.Patch(color=c, label=lab) for lab, c, _ in pct_metrics + cnt_metrics]
    if multi_task:
        handles += [plt.Line2D([], [], color="#555555", linestyle=task_style[t],
                               marker=task_marker[t], label=TASK_LABELS[t])
                    for t in by_task]
    fig.legend(handles=handles, loc="upper center", ncol=len(handles),
               fontsize=8, bbox_to_anchor=(0.5, 1.0))
    fig.suptitle("On-cue poke & off-cue activity dynamics per mouse across sessions",
                 y=1.05, fontsize=13)
    fig.text(0.5, -0.01, "off-cue licks include reward-consumption licking during the "
             "post-cue / ITI period (not purely impulsive)", ha="center",
             fontsize=8, color="#777777")
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


# --- Figure 4: latency trajectories ----------------------------------------
LATENCY_METRICS = [
    ("median_cue_to_poke_latency", "cue -> first on-cue poke"),
    ("median_poke_to_lick_latency", "poke -> first lick"),
    ("median_lick_to_reward_latency", "lick -> reward"),
]


def fig_latencies(by_task: dict, out_path: str) -> None:
    """Group-level: per-session median latency (mean +/- SEM across mice), one
    panel per latency stage, one line per task."""
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.6), squeeze=False)
    task_colors = {TASK_APP: "#1f77b4", TASK_GEN: "#d62728"}
    for ax, (key, label) in zip(axes[0], LATENCY_METRICS):
        for task in by_task:
            by_mouse = by_task[task]
            max_s = max((r["session"] for rows in by_mouse.values() for r in rows), default=1)
            sessions = list(range(1, max_s + 1))
            means, sems = [], []
            for s in sessions:
                vals = [r[key] for rows in by_mouse.values() for r in rows if r["session"] == s]
                m, e = _mean_sem(vals)
                means.append(m)
                sems.append(e)
            means, sems = np.array(means), np.array(sems)
            ax.plot(sessions, means, "-o", color=task_colors[task], lw=2, ms=4,
                    label=TASK_LABELS[task])
            ax.fill_between(sessions, means - sems, means + sems,
                            color=task_colors[task], alpha=0.15)
        ax.set_xlabel("session #")
        ax.set_ylabel("median latency (s)")
        ax.set_title(label)
        ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    axes[0][0].legend(fontsize=8, framealpha=0.9)
    fig.suptitle("Action latencies across sessions (group mean of per-session medians)",
                 fontsize=13)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


# --- Figure 5: trial-history effect ----------------------------------------
def _history_rates(records: list[dict], task: str, mouse: str) -> dict:
    """Pool a mouse's trials across sessions: P(engage / off-cue | prev rewarded
    vs not). Identifies reward-gated mice."""
    eng_after = {True: [], False: []}
    off_after = {True: [], False: []}
    for rec in records:
        if rec["task"] != task or rec["mouse"] != mouse:
            continue
        for t in rec["trials"]:
            prev = t["previous_trial_rewarded"]
            if prev is None:
                continue
            eng_after[prev].append(t["engaged"])
            off_after[prev].append(t["n_offcue_pokes"] > 0)
    rate = lambda xs: 100.0 * float(np.mean(xs)) if xs else NAN
    return {"eng_rew": rate(eng_after[True]), "eng_norew": rate(eng_after[False]),
            "off_rew": rate(off_after[True]), "off_norew": rate(off_after[False])}


def _gating_gap(hist_task: dict, mouse: str, key_rew: str, key_norew: str) -> float:
    h = hist_task.get(mouse)
    return (h[key_rew] - h[key_norew]) if h else NAN


def fig_trial_history(records: list[dict], by_task: dict, out_path: str) -> None:
    """Reward-gating as a dumbbell plot: per mouse, the probability of engaging
    (and of off-cue poking) on trial t after a REWARDED vs NON-REWARDED trial.
    Each line connects the two; its length is the gating strength. Mice are
    sorted by the engagement gap, so reward-gated mice (long green-ward lines)
    rise to the top — far easier to read than 80 grouped bars."""
    tasks = list(by_task)
    hist = {task: {m: _history_rates(records, task, m) for m in by_task[task]}
            for task in tasks}
    order_task = TASK_GEN if TASK_GEN in hist else tasks[0]
    mice = sorted({m for t in tasks for m in by_task[t]}, key=lambda m: int(m[1:]))

    def _sort_key(m: str) -> float:
        g = _gating_gap(hist[order_task], m, "eng_rew", "eng_norew")
        return -g if not np.isnan(g) else 1e9  # most-gated first, missing last

    mice.sort(key=_sort_key)
    rows_cfg = [("eng_rew", "eng_norew", "P(engage on trial t)  [%]"),
                ("off_rew", "off_norew", "P(off-cue poke on trial t)  [%]")]
    fig, axes = plt.subplots(len(rows_cfg), len(tasks),
                             figsize=(6.2 * len(tasks), 8.4), squeeze=False)
    for col, task in enumerate(tasks):
        for row, (k_rew, k_norew, xlabel) in enumerate(rows_cfg):
            ax = axes[row][col]
            for i, m in enumerate(mice):
                h = hist[task].get(m)
                if not h or np.isnan(h[k_rew]) or np.isnan(h[k_norew]):
                    continue
                xr, xn = h[k_rew], h[k_norew]
                ax.plot([xn, xr], [i, i], color="#c8c8c8", lw=2.2, zorder=1)
                ax.scatter(xn, i, color="#d62728", s=46, zorder=2)
                ax.scatter(xr, i, color="#2ca02c", s=46, zorder=2)
                d = xr - xn
                ax.annotate(f"{d:+.0f}", (max(xr, xn), i), textcoords="offset points",
                            xytext=(6, 0), va="center", fontsize=7,
                            color="#2ca02c" if d >= 0 else "#d62728")
            ax.set_yticks(range(len(mice)))
            ax.set_yticklabels(mice, fontsize=8)
            ax.invert_yaxis()
            ax.set_xlim(0, 112)
            ax.set_xlabel(xlabel)
            ax.grid(axis="x", alpha=0.25)
            if row == 0:
                ax.set_title(TASK_LABELS[task])
    handles = [plt.Line2D([], [], marker="o", linestyle="None", color="#2ca02c",
                          label="after a rewarded trial"),
               plt.Line2D([], [], marker="o", linestyle="None", color="#d62728",
                          label="after a non-rewarded trial")]
    fig.legend(handles=handles, loc="upper center", ncol=2, fontsize=9,
               bbox_to_anchor=(0.5, 0.915))
    fig.suptitle("Reward-gating — does the previous trial's outcome change "
                 "behavior on the next trial?", fontsize=13, y=0.99)
    fig.text(0.5, 0.945, "line length = gating strength (Δ percentage points); "
             "mice sorted by engagement gap, most-gated on top",
             ha="center", fontsize=9, color="#555555")
    fig.tight_layout(rect=(0, 0, 1, 0.89))
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


# --- transition matrix on a 3-level engagement ladder ----------------------
# Collapsing the five categories onto an ordered ladder makes the 5x5x2 grid
# (50 abstract cells) readable: 3 intuitive states whose diagonal = persistence.
LADDER = [
    ("complete\n(rewarded)", ["complete_sequence_rewarded"]),
    ("engaged,\nno reward", ["cue_poke_no_lick", "cue_poke_lick_no_reward"]),
    ("disengaged", ["no_response", "offcue_poke_only"]),
]


def fig_transition_matrix(records: list[dict], by_task: dict, out_path: str) -> None:
    """Row-normalized trial-to-trial transitions on the engagement ladder
    (complete -> engaged-but-no-reward -> disengaged). Reads directly as: do mice
    stay stuck (disengaged->disengaged), hold success (complete->complete), or
    recover? Diagonal (persistence) cells are boxed; colour is scaled to the data
    so differences are visible."""
    state_of = {c: i for i, (_, cats) in enumerate(LADDER) for c in cats}
    labels = [lab for lab, _ in LADDER]
    n = len(LADDER)
    tasks = list(by_task)

    mats: dict[str, np.ndarray] = {}
    for task in tasks:
        counts = np.zeros((n, n))
        for rec in records:
            if rec["task"] != task:
                continue
            for t in rec["trials"]:
                prev = t["previous_trial_category"]
                if prev is None:
                    continue
                counts[state_of[prev], state_of[t["action_sequence_category"]]] += 1
        row_sums = counts.sum(axis=1, keepdims=True)
        mats[task] = np.divide(counts, row_sums, out=np.zeros_like(counts), where=row_sums > 0)

    vmax = max(m.max() for m in mats.values())
    fig, axes = plt.subplots(1, len(tasks), figsize=(5.6 * len(tasks), 5.2), squeeze=False)
    im = None
    for col, (ax, task) in enumerate(zip(axes[0], tasks)):
        norm = mats[task]
        im = ax.imshow(norm, cmap="YlGnBu", vmin=0, vmax=vmax, aspect="auto")
        ax.set_xticks(range(n))
        ax.set_xticklabels(labels, fontsize=9)
        ax.set_yticks(range(n))
        ax.set_yticklabels(labels if col == 0 else [], fontsize=9)
        ax.set_xlabel("next trial →")
        if col == 0:
            ax.set_ylabel("previous trial")
        ax.set_title(TASK_LABELS[task])
        for i in range(n):
            for j in range(n):
                ax.text(j, i, f"{norm[i, j]:.0%}", ha="center", va="center",
                        fontsize=12, fontweight="bold" if i == j else "normal",
                        color="white" if norm[i, j] > vmax * 0.6 else "black")
            ax.add_patch(mpatches.Rectangle((i - 0.5, i - 0.5), 1, 1, fill=False,
                                            edgecolor="#d62728", lw=2.0))
    fig.colorbar(im, ax=axes[0].tolist(), fraction=0.046, pad=0.04,
                 label="P(next state | previous state)")
    fig.suptitle("Trial-to-trial transitions on the engagement ladder\n"
                 "(row-normalized; boxed diagonal = how sticky each state is)",
                 fontsize=13, y=1.08)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


# --- interpretation text ---------------------------------------------------
def _mouse_means(by_mouse: dict[str, list[dict]], key: str) -> dict[str, float]:
    return {m: _mean_sem([r[key] for r in rows])[0] for m, rows in by_mouse.items()}


def _rank_line(scores: dict[str, float], reverse: bool, unit: str, top: int = 4) -> str:
    items = sorted(((m, v) for m, v in scores.items() if not np.isnan(v)),
                   key=lambda kv: kv[1], reverse=reverse)
    return ", ".join(f"{m} ({v:.0f}{unit})" for m, v in items[:top])


def write_summary_text(records: list[dict], by_task: dict, out_path: str) -> None:
    lines: list[str] = ["ACTION-SEQUENCE ANALYSIS — INTERPRETATION", "=" * 48, ""]
    lines.append("NOTE: the five chain categories are mutually exclusive and sum to "
                 "100%. 'mixed_offcue_and_oncue' overlaps them (off-cue/ITI poking "
                 "is near-universal) and is reported separately, not as a stack slice.\n")

    for task in by_task:
        by_mouse = by_task[task]
        complete = _mouse_means(by_mouse, "percent_complete_sequence_rewarded")
        lick_given = _mouse_means(by_mouse, "lick_given_oncue_poke_rate")
        engagement = _mouse_means(by_mouse, "engagement_rate")
        offcue = _mouse_means(by_mouse, "offcue_pokes_per_trial")
        gating = {m: _history_rates(records, task, m) for m in by_mouse}
        gate_delta = {m: gating[m]["eng_rew"] - gating[m]["eng_norew"] for m in by_mouse}

        lines.append(f"### {TASK_LABELS[task]} ({task})")
        lines.append(f"1. Most reliable full poke->lick->reward sequence: "
                     f"{_rank_line(complete, True, '%')}")
        lines.append(f"2. Poke on-cue but fail to lick (lowest P(lick|poke)): "
                     f"{_rank_line(lick_given, False, '%')}")
        lines.append(f"3. Mostly fail at engagement (lowest engagement): "
                     f"{_rank_line(engagement, False, '%')}")
        lines.append(f"4. Highest off-cue poking (pokes/trial): "
                     f"{_rank_line(offcue, True, '')}")
        lines.append(f"5. Most reward-gated (engage more after reward; "
                     f"P(engage|prev hit) - P(engage|prev miss)): "
                     f"{_rank_line(gate_delta, True, 'pp')}")
        lines.append("")

    if TASK_APP in by_task and TASK_GEN in by_task:
        def grand(task, key):
            return _mean_sem([r[key] for rows in by_task[task].values() for r in rows])[0]
        lines.append("### Appetitive vs Generalization")
        lines.append(f"6. Group means — complete-sequence %: "
                     f"appetitive {grand(TASK_APP, 'percent_complete_sequence_rewarded'):.0f}% "
                     f"vs generalization {grand(TASK_GEN, 'percent_complete_sequence_rewarded'):.0f}%; "
                     f"engagement: {grand(TASK_APP, 'engagement_rate'):.0f}% vs "
                     f"{grand(TASK_GEN, 'engagement_rate'):.0f}%; "
                     f"accuracy when engaged: {grand(TASK_APP, 'reward_given_oncue_poke_rate'):.0f}% "
                     f"vs {grand(TASK_GEN, 'reward_given_oncue_poke_rate'):.0f}%.")
        # participation vs competence trajectory in generalization
        gen = by_task[TASK_GEN]
        s1 = [r for rows in gen.values() for r in rows if r["session"] == 1]
        smax = max(r["session"] for rows in gen.values() for r in rows)
        sN = [r for rows in gen.values() for r in rows if r["session"] == smax]
        eng1, _ = _mean_sem([r["engagement_rate"] for r in s1])
        engN, _ = _mean_sem([r["engagement_rate"] for r in sN])
        acc1, _ = _mean_sem([r["reward_given_oncue_poke_rate"] for r in s1])
        accN, _ = _mean_sem([r["reward_given_oncue_poke_rate"] for r in sN])
        lines.append(f"7. Generalization improvement is driven by PARTICIPATION, not "
                     f"accuracy: engagement {eng1:.0f}% -> {engN:.0f}% (s1->s{smax}) while "
                     f"accuracy-when-engaged stays high/flat {acc1:.0f}% -> {accN:.0f}%.")
        lines.append("")

    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))


# --- driver ----------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--task", choices=["appetitive", "generalization", "both"],
                        default="both", help="which task(s) to analyze")
    parser.add_argument("--mouse", default=None, help="restrict to one mouse, e.g. m102")
    args = parser.parse_args()

    if not _ENV_OUT:
        global OUT_ROOT
        OUT_ROOT = str(_RESULTS_ROOT / "action_sequence" / _TASK_AREA[args.task])

    records: list[dict] = []
    if args.task in ("appetitive", "both"):
        print("Loading appetitive (tone) task ...")
        records += load_appetitive(args.mouse)
    if args.task in ("generalization", "both"):
        print("Loading generalization (light) task ...")
        records += load_generalization(args.mouse)
    # Optional 3rd task — see TODO in load_association_cue_reward.
    records += load_association_cue_reward(args.mouse)

    if not records:
        print("No matching sessions found.")
        return 1

    summaries = [summarize_session(r) for r in records]
    by_task = _by_task_mouse(summaries)

    os.makedirs(OUT_ROOT, exist_ok=True)
    write_trial_csv(records, os.path.join(OUT_ROOT, "action_sequence_trials.csv"))
    write_summary_csv(summaries, os.path.join(OUT_ROOT, "action_sequence_session_summary.csv"))

    fig_stacked_by_mouse(by_task, os.path.join(OUT_ROOT, "action_sequence_stacked_by_mouse.png"))
    fig_group_trajectory(by_task, os.path.join(OUT_ROOT, "action_sequence_group_trajectory.png"))
    fig_action_chain_by_mouse(by_task, os.path.join(OUT_ROOT, "action_chain_by_mouse.png"))
    fig_latencies(by_task, os.path.join(OUT_ROOT, "action_sequence_latencies.png"))
    fig_trial_history(records, by_task, os.path.join(OUT_ROOT, "action_sequence_trial_history.png"))
    fig_transition_matrix(records, by_task, os.path.join(OUT_ROOT, "action_sequence_transition_matrix.png"))

    write_summary_text(records, by_task, os.path.join(OUT_ROOT, "action_sequence_summary.txt"))

    n_trials = sum(len(r["trials"]) for r in records)
    print(f"\nWrote 2 CSVs, 6 figures, and summary.txt under '{OUT_ROOT}/' "
          f"({len(records)} sessions, {n_trials} trials).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
