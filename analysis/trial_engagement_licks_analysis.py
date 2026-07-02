#!/usr/bin/env python3
"""EXPLORATORY — lick-level signal-detection view of engagement.

Standalone / read-only: imports the existing loaders but changes no other
analysis. A different, lick-level scoring of each trial, using the FSM's own ITI
boundary (start_timer_ITI / state_ITI, ~8 s after cue onset) to separate
consummatory licking from impulsive licking:

  * HIT lick   = a reward-related lick — any lick on a REWARDED trial before the
                 ITI starts (the whole response + drinking bout; all "rewarded").
  * FALSE ALARM lick = an off-cue lick during the ITI (from ITI start to the
                 trial's end) — impulsive dry-spout licking.
  * CATCH trial = the mouse poked on-cue, then licked, but got NO reward though it
                 should have (a probe / reward-omission-like trial). Trial-level,
                 tracked separately.

    trial_engagement = hits / (hits + FA)   (reward-related licks / all scored licks, %)

A mouse/session is ENGAGED when trial_engagement is at or above the per-task
COHORT MEDIAN (no lick-based split reaches a fixed 50%, since impulsive ITI
licking outnumbers drinking ~3:1). Competence on the engagement×competence map is
the project-standard accuracy-when-engaged (on-cue poke → reward).

Outputs (under results/trial_engagement_licks/<area>/):
    trial_engagement_heatmap.png      mouse x session grid of the ratio (per task)
    trial_engagement_by_mouse.png     per-mouse small multiples (tone + light)
    trial_engagement_group.png        group mean +- SEM + cohort-median line
    engagement_vs_competence_first_last.png  lick-engagement (x) vs competence (y)
    catch_rate_heatmap.png            catch-trial rate, mouse x session (per task)
    catch_rate_by_mouse.png           per-mouse catch-trial rate (tone vs light)
    oncue_lick_reward_split.png       on-cue licks split: got reward vs no reward
    trial_engagement_by_session.csv / trial_engagement_by_mouse.csv
    engagement_vs_competence_first_last.csv / trial_engagement_summary.txt

Usage:
    python3 trial_engagement_licks_analysis.py --task both
"""
from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
import numpy as np

import appetitive_analysis as A
import generalization_analysis as G
import trial_history_analysis as TH  # task constants / colours / labels (read-only)

NAN = float("nan")
_RESULTS_ROOT = Path(__file__).resolve().parent / "results"
_TASK_AREA = {"appetitive": "appetitive", "generalization": "generalization", "both": "cross_task"}
_ENV_OUT = os.environ.get("MICS_TRIALENG_OUT")
OUT_ROOT = _ENV_OUT or str(_RESULTS_ROOT / "trial_engagement_licks" / "cross_task")
_TASK_LS = {TH.TASK_APP: "-", TH.TASK_GEN: "--"}


# --- loaders (read-only; keep raw trials so lick/reward/ITI times survive) --
def load_appetitive(only_mouse: str | None) -> list[dict]:
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
            records.append({"task": TH.TASK_APP, "mouse": mouse, "session": day,
                            "dur_key": "tone_dur", "trials": trials})
    return records


def load_generalization(only_mouse: str | None) -> list[dict]:
    records = []
    for mouse, subjects in G.discover_mice().items():
        if only_mouse and mouse != only_mouse:
            continue
        for r in G.collect_mouse(subjects):
            records.append({"task": TH.TASK_GEN, "mouse": mouse, "session": r["session_num"],
                            "dur_key": "led_dur", "trials": r["trials"]})
    return records


# --- per-session scoring ---------------------------------------------------
def session_scores(record: dict) -> dict:
    dur_key = record["dur_key"]
    hit_licks = fa_licks = 0
    oncue_rew = oncue_norew = 0
    n_engaged = n_engaged_hit = n_rewarded = n_catch = 0
    for t in record["trials"]:
        dur, iti0, iti1 = t[dur_key], t["iti_start"], t["iti_end"]
        response_licks = [lk for lk in t["licks"] if 0 <= lk < iti0]   # pre-ITI licks
        iti_licks = sum(1 for lk in t["licks"] if iti0 <= lk <= iti1)  # ITI licks = FA
        fa_licks += iti_licks
        # on-cue licks (within the cue window) split by whether the trial earned water
        oncue_licks = sum(1 for lk in t["licks"] if 0 <= lk <= dur)
        if t["is_hit"]:
            hit_licks += len(response_licks)                          # reward-related = HIT
            oncue_rew += oncue_licks
        else:
            oncue_norew += oncue_licks
        on_cue = any(0 <= p <= dur for p in t["nose_pokes"])
        n_engaged += on_cue
        n_engaged_hit += on_cue and t["is_hit"]
        n_rewarded += t["is_hit"]
        # catch = poked on-cue, then licked, but no reward
        if on_cue and response_licks and not t["is_hit"]:
            n_catch += 1
    n = len(record["trials"])
    scored = hit_licks + fa_licks
    oncue_total = oncue_rew + oncue_norew
    return {
        "task": record["task"], "mouse": record["mouse"], "session": record["session"],
        "n_hit_licks": hit_licks, "n_fa_licks": fa_licks,
        "trial_engagement": 100.0 * hit_licks / scored if scored else NAN,
        "n_oncue_lick_rew": oncue_rew, "n_oncue_lick_norew": oncue_norew,
        "oncue_reward_rate": 100.0 * oncue_rew / oncue_total if oncue_total else NAN,
        "n_catch": n_catch, "n_trials": n,
        "catch_rate": 100.0 * n_catch / n if n else NAN,
        "accuracy_when_engaged": 100.0 * n_engaged_hit / n_engaged if n_engaged else NAN,
        "hit_rate": 100.0 * n_rewarded / n if n else NAN,
    }


def group(records: list[dict]) -> dict:
    out: dict = {}
    for r in records:
        s = session_scores(r)
        out.setdefault(s["task"], {}).setdefault(s["mouse"], []).append(s)
    for bm in out.values():
        for ss in bm.values():
            ss.sort(key=lambda s: s["session"])
    return out


def cohort_medians(by_task: dict, key: str) -> dict:
    med = {}
    for task, bm in by_task.items():
        vals = [s[key] for ss in bm.values() for s in ss if not np.isnan(s[key])]
        med[task] = float(np.median(vals)) if vals else NAN
    return med


def _sorted_mice(names) -> list[str]:
    return sorted(names, key=lambda m: int("".join(filter(str.isdigit, m)) or 0))


def _mean_sem(values) -> tuple[float, float]:
    vals = [v for v in values if not np.isnan(v)]
    if not vals:
        return NAN, 0.0
    sem = float(np.std(vals, ddof=1) / np.sqrt(len(vals))) if len(vals) > 1 else 0.0
    return float(np.mean(vals)), sem


def _matrix(by_task: dict, task: str, key: str):
    bm = by_task[task]
    mice = _sorted_mice(bm)
    max_s = max((s["session"] for ss in bm.values() for s in ss), default=1)
    mat = np.full((len(mice), max_s), np.nan)
    for i, m in enumerate(mice):
        for s in bm[m]:
            mat[i, s["session"] - 1] = s[key]
    return mice, mat, max_s


# --- figures: engagement ---------------------------------------------------
def _heatmap(by_task: dict, key: str, med: dict, title: str, cbar: str,
             out_path: str, fmt: str = "{:.0f}") -> None:
    tasks = list(by_task)
    vals = [s[key] for bm in by_task.values() for ss in bm.values() for s in ss
            if not np.isnan(s[key])]
    vmin, vmax = (min(vals), max(vals)) if vals else (0.0, 1.0)
    fig, axes = plt.subplots(len(tasks), 1, figsize=(11, 3.2 * len(tasks) + 1), squeeze=False)
    cmap = plt.get_cmap("viridis").copy()
    cmap.set_bad("#e8e8e8")
    for ti, task in enumerate(tasks):
        mice, mat, max_s = _matrix(by_task, task, key)
        ax = axes[ti][0]
        im = ax.imshow(np.ma.masked_invalid(mat), aspect="auto", cmap=cmap,
                       vmin=vmin, vmax=vmax, origin="upper")
        ax.set_yticks(range(len(mice))); ax.set_yticklabels(mice, fontsize=9)
        ax.set_xticks(range(max_s)); ax.set_xticklabels(range(1, max_s + 1), fontsize=8)
        ax.set_xlabel("session #")
        mtxt = f" (cohort median {med[task]:.1f}%)" if not np.isnan(med.get(task, NAN)) else ""
        ax.set_title(f"{TH.TASK_LABELS.get(task, task)} — {title}{mtxt}")
        span = max(vmax - vmin, 1e-9)
        for i in range(len(mice)):
            for j in range(max_s):
                if not np.isnan(mat[i, j]):
                    ax.text(j, i, fmt.format(mat[i, j]), ha="center", va="center", fontsize=7,
                            color="white" if (mat[i, j] - vmin) / span < 0.5 else "black")
        fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02, label=cbar)
    fig.suptitle(title)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


def fig_by_mouse(by_task: dict, med: dict, out_path: str) -> None:
    tasks = list(by_task)
    mice = _sorted_mice({m for bm in by_task.values() for m in bm})
    max_s = max((s["session"] for bm in by_task.values() for ss in bm.values()
                 for s in ss), default=1)
    ncol = 5
    nrow = (len(mice) + ncol - 1) // ncol
    fig, axes = plt.subplots(nrow, ncol, figsize=(3.2 * ncol, 2.6 * nrow),
                             squeeze=False, sharex=True, sharey=True)
    axes = axes.reshape(-1)
    for ax, mouse in zip(axes, mice):
        for task in tasks:
            if mouse not in by_task[task]:
                continue
            ss = by_task[task][mouse]
            ax.plot([s["session"] for s in ss], [s["trial_engagement"] for s in ss],
                    marker="o", ms=4, lw=1.6, color=TH.TASK_COLORS.get(task, "#555"),
                    ls=_TASK_LS.get(task, "-"), label=TH.TASK_LABELS.get(task, task))
        for task in tasks:
            ax.axhline(med[task], color=TH.TASK_COLORS.get(task, "#555"), ls=":", lw=1, alpha=0.7)
        ax.set_title(mouse, fontsize=9)
        ax.set_xlim(0.5, max_s + 0.5); ax.set_ylim(bottom=0)
        ax.xaxis.set_major_locator(plt.MaxNLocator(integer=True))
        ax.grid(alpha=0.3)
    for ax in axes[len(mice):]:
        ax.axis("off")
    if len(tasks) > 1:
        axes[0].legend(fontsize=7, loc="upper right")
    fig.supxlabel("session #")
    fig.supylabel("trial engagement (reward-related licks %)")
    fig.suptitle("Lick-based trial engagement — per mouse (dotted = cohort median)")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


def fig_group(by_task: dict, med: dict, out_path: str) -> None:
    fig, ax = plt.subplots(figsize=(8.4, 5.2))
    for task in by_task:
        bm = by_task[task]
        max_s = max((s["session"] for ss in bm.values() for s in ss), default=1)
        xs, means, sems = [], [], []
        for day in range(1, max_s + 1):
            mean, sem = _mean_sem([s["trial_engagement"] for ss in bm.values()
                                   for s in ss if s["session"] == day])
            if np.isnan(mean):
                continue
            xs.append(day); means.append(mean); sems.append(sem)
        xs, means, sems = np.array(xs), np.array(means), np.array(sems)
        color = TH.TASK_COLORS.get(task, "#555")
        ax.plot(xs, means, "-o", color=color, lw=2.8, ms=6, zorder=5,
                label=TH.TASK_LABELS.get(task, task))
        ax.fill_between(xs, means - sems, means + sems, color=color, alpha=0.18, zorder=4)
        ax.axhline(med[task], color=color, ls=":", lw=1.4,
                   label=f"{TH.TASK_LABELS.get(task, task)} cohort median")
    ax.set_xlabel("session #"); ax.set_ylabel("trial engagement (reward-related licks %)")
    ax.set_ylim(bottom=0)
    ax.xaxis.set_major_locator(plt.MaxNLocator(integer=True))
    ax.grid(alpha=0.3); ax.legend(fontsize=9)
    ax.set_title("Lick-based trial engagement — group mean ± SEM")
    fig.tight_layout()
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


# --- figure: engagement vs competence, first -> last -----------------------
def first_last(by_task: dict) -> dict:
    out: dict = {}
    for task, bm in by_task.items():
        for m, ss in bm.items():
            if ss:
                out.setdefault(task, {})[m] = (ss[0], ss[-1])
    return out


def fig_engagement_vs_competence(by_task: dict, med: dict, out_path: str) -> None:
    fl = first_last(by_task)
    tasks = list(fl)
    fig, axes = plt.subplots(1, len(tasks), figsize=(6.8 * len(tasks), 6.4),
                             squeeze=False, sharey=True)
    cmap = plt.get_cmap("tab10")
    for ax, task in zip(axes[0], tasks):
        mice = _sorted_mice(fl[task])
        ax.axvline(med[task], color="grey", ls="--", lw=1,
                   label=f"cohort-median engagement ({med[task]:.0f}%)")
        ax.axhline(70, color="grey", ls=":", lw=1)
        xmax = 10.0
        for i, m in enumerate(mice):
            first, last = fl[task][m]
            xf, xl = first["trial_engagement"], last["trial_engagement"]
            if np.isnan(xf) or np.isnan(xl):
                continue
            yf = 0.0 if np.isnan(first["accuracy_when_engaged"]) else first["accuracy_when_engaged"]
            yl = 0.0 if np.isnan(last["accuracy_when_engaged"]) else last["accuracy_when_engaged"]
            xmax = max(xmax, xf, xl)
            color = cmap(i % 10)
            ax.annotate("", xy=(xl, yl), xytext=(xf, yf),
                        arrowprops=dict(arrowstyle="-|>", color="#888", lw=1.4, alpha=0.85,
                                        shrinkA=6, shrinkB=8), zorder=2)
            ax.scatter([xf], [yf], s=95, facecolors="white", edgecolors=color, linewidths=2, zorder=3)
            ax.scatter([xl], [yl], s=135, color=color, edgecolors="white", linewidths=0.9, zorder=4)
            ax.annotate(m, (xl, yl), textcoords="offset points", xytext=(7, 4), fontsize=8, zorder=5)
        ax.set_title(TH.TASK_LABELS.get(task, task))
        ax.set_xlabel("trial engagement  (reward-related licks %)")
        ax.set_xlim(0, xmax * 1.12); ax.set_ylim(0, 105)
        ax.grid(alpha=0.3); ax.legend(fontsize=8, loc="lower right")
    axes[0][0].set_ylabel("accuracy when engaged (%)  →  competence")
    handles = [plt.Line2D([], [], marker="o", ls="", mfc="white", mec="black", mew=1.5,
                          ms=9, label="first session"),
               plt.Line2D([], [], marker="o", ls="", color="black", ms=9, label="last session")]
    fig.legend(handles=handles, loc="upper center", ncol=2, fontsize=9, bbox_to_anchor=(0.5, 0.945))
    fig.suptitle("Lick-based engagement vs competence — first → last session per task",
                 y=0.995, fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.90))
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


# --- figure: catch trials --------------------------------------------------
def fig_catch_by_mouse(by_task: dict, out_path: str) -> None:
    tasks = list(by_task)
    mice = _sorted_mice({m for bm in by_task.values() for m in bm})
    x = np.arange(len(mice), dtype=float)
    width = 0.8 / max(len(tasks), 1)
    fig, ax = plt.subplots(figsize=(max(9, 1.1 * len(mice)), 5.0))
    for ti, task in enumerate(tasks):
        color = TH.TASK_COLORS.get(task, "#555")
        offs = x + (ti - (len(tasks) - 1) / 2) * width
        means, sems = [], []
        for xi, m in zip(offs, mice):
            per = [s["catch_rate"] for s in by_task[task].get(m, [])]
            mean, sem = _mean_sem(per)
            means.append(mean); sems.append(sem)
            vals = [v for v in per if not np.isnan(v)]
            jit = (np.arange(len(vals)) - (len(vals) - 1) / 2) * (width * 0.12)
            ax.scatter(np.full(len(vals), xi) + jit, vals, s=10, color=color,
                       alpha=0.35, zorder=3, linewidths=0)
        ax.bar(offs, means, width=width * 0.9, color=color, alpha=0.55, yerr=sems,
               capsize=2, zorder=2, label=TH.TASK_LABELS.get(task, task))
    ax.set_xticks(x); ax.set_xticklabels(mice, rotation=45, ha="right")
    ax.set_ylabel("catch trials (poked on-cue + licked, no reward)  %")
    ax.set_ylim(bottom=0); ax.grid(axis="y", alpha=0.3)
    if len(tasks) > 1:
        ax.legend(fontsize=9, loc="upper right")
    ax.set_title("Catch-trial rate per mouse (bar = mean over sessions, dots = sessions)")
    fig.tight_layout()
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


def fig_oncue_lick_split(by_task: dict, out_path: str) -> None:
    """On-cue licks (licks during the cue window) split by whether the trial
    earned water: reward-earning (green) vs no-reward (red = the catch/miss
    licking). 100%-stacked per mouse so the small no-reward slice is visible; the
    count of no-reward on-cue licks is printed on each bar."""
    tasks = list(by_task)
    fig, axes = plt.subplots(1, len(tasks), figsize=(6.6 * len(tasks), 5.0),
                             squeeze=False, sharey=True)
    for ax, task in zip(axes[0], tasks):
        bm = by_task[task]
        mice = _sorted_mice(bm)
        x = np.arange(len(mice), dtype=float)
        rew = np.array([sum(s["n_oncue_lick_rew"] for s in bm[m]) for m in mice], dtype=float)
        nor = np.array([sum(s["n_oncue_lick_norew"] for s in bm[m]) for m in mice], dtype=float)
        tot = np.maximum(rew + nor, 1)
        pr, pn = 100 * rew / tot, 100 * nor / tot
        ax.bar(x, pr, color="#2ca02c", width=0.75, label="got reward")
        ax.bar(x, pn, bottom=pr, color="#d62728", width=0.75, label="no reward")
        for xi, p, cnt in zip(x, pr, nor.astype(int)):
            ax.text(xi, min(p + 1.5, 99), str(cnt), ha="center", va="bottom", fontsize=7)
        ax.set_xticks(x); ax.set_xticklabels(mice, rotation=45, ha="right")
        ax.set_ylim(0, 100)
        ax.set_title(f"{TH.TASK_LABELS.get(task, task)}  "
                     f"({int(nor.sum())} of {int((rew + nor).sum())} on-cue licks got no reward)")
    axes[0][0].set_ylabel("% of on-cue licks")
    axes[0][0].legend(fontsize=8, loc="lower left")
    fig.suptitle("On-cue licks split by outcome — reward-earning vs no-reward "
                 "(number on bar = no-reward on-cue licks)")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


def fig_hit_rate_first_last(by_task: dict, out_path: str) -> None:
    """Hit rate = hits/(hits+FA) for each mouse's FIRST vs LAST session of a task
    (top row), and the last-minus-first difference (bottom row). One column per
    task; green/red difference bars = increase/decrease."""
    fl = first_last(by_task)
    tasks = list(fl)
    fig, axes = plt.subplots(2, len(tasks), figsize=(6.6 * len(tasks), 7.2),
                             squeeze=False, sharex="col")
    for ti, task in enumerate(tasks):
        mice = _sorted_mice(fl[task])
        firsts = np.array([fl[task][m][0]["trial_engagement"] for m in mice])
        lasts = np.array([fl[task][m][1]["trial_engagement"] for m in mice])
        diffs = lasts - firsts
        x = np.arange(len(mice), dtype=float)
        ax0 = axes[0][ti]
        ax0.bar(x - 0.2, firsts, 0.4, color="#c6dbef", label="first session")
        ax0.bar(x + 0.2, lasts, 0.4, color="#2171b5", label="last session")
        ax0.set_ylim(bottom=0)
        ax0.set_title(TH.TASK_LABELS.get(task, task))
        ax0.grid(axis="y", alpha=0.3)
        if ti == 0:
            ax0.set_ylabel("hit rate  hits/(hits+FA)  %")
            ax0.legend(fontsize=8, loc="upper left")
        ax1 = axes[1][ti]
        ax1.bar(x, diffs, 0.6, color=["#2ca02c" if d >= 0 else "#d62728" for d in diffs])
        ax1.axhline(0, color="black", lw=0.8)
        ax1.set_xticks(x); ax1.set_xticklabels(mice, rotation=45, ha="right")
        ax1.grid(axis="y", alpha=0.3)
        if ti == 0:
            ax1.set_ylabel("Δ hit rate  (last − first, pp)")
    fig.suptitle("Hit rate = hits/(hits+FA) — first vs last session per task, "
                 "and the change")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


def write_hit_rate_first_last_csv(by_task: dict, path: str) -> None:
    fl = first_last(by_task)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["task", "mouse", "hit_rate_first", "hit_rate_last", "hit_rate_diff"])
        for task in fl:
            for m in _sorted_mice(fl[task]):
                a, b = fl[task][m][0]["trial_engagement"], fl[task][m][1]["trial_engagement"]
                fmt = lambda v: "" if np.isnan(v) else f"{v:.2f}"
                diff = "" if (np.isnan(a) or np.isnan(b)) else f"{b - a:.2f}"
                w.writerow([task, m, fmt(a), fmt(b), diff])


# --- writers ---------------------------------------------------------------
def write_session_csv(by_task: dict, med: dict, path: str) -> None:
    cols = ["task", "mouse", "session", "n_trials", "n_hit_licks", "n_fa_licks",
            "trial_engagement", "engaged", "n_oncue_lick_rew", "n_oncue_lick_norew",
            "oncue_reward_rate", "n_catch", "catch_rate", "accuracy_when_engaged"]
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for task, bm in by_task.items():
            for m in _sorted_mice(bm):
                for s in bm[m]:
                    te = s["trial_engagement"]
                    eng = "" if np.isnan(te) else ("yes" if te >= med[task] else "no")
                    w.writerow([task, m, s["session"], s["n_trials"], s["n_hit_licks"],
                                s["n_fa_licks"], "" if np.isnan(te) else f"{te:.2f}", eng,
                                s["n_oncue_lick_rew"], s["n_oncue_lick_norew"],
                                "" if np.isnan(s["oncue_reward_rate"]) else f"{s['oncue_reward_rate']:.2f}",
                                s["n_catch"], f"{s['catch_rate']:.2f}",
                                "" if np.isnan(s["accuracy_when_engaged"]) else f"{s['accuracy_when_engaged']:.1f}"])


def write_mouse_csv(by_task: dict, med: dict, path: str) -> list[dict]:
    rows = []
    for task, bm in by_task.items():
        for m in _sorted_mice(bm):
            ss = bm[m]
            mean_te, _ = _mean_sem([s["trial_engagement"] for s in ss])
            n_eng = sum(1 for s in ss if not np.isnan(s["trial_engagement"]) and s["trial_engagement"] >= med[task])
            rows.append({"task": task, "mouse": m, "n_sessions": len(ss),
                         "mean_trial_engagement": mean_te,
                         "pct_sessions_engaged": 100.0 * n_eng / len(ss) if ss else NAN,
                         "mouse_engaged": "yes" if (not np.isnan(mean_te) and mean_te >= med[task]) else "no",
                         "mean_catch_rate": _mean_sem([s["catch_rate"] for s in ss])[0]})
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["task", "mouse", "n_sessions", "mean_trial_engagement",
                    "pct_sessions_engaged", "mouse_engaged", "mean_catch_rate"])
        for r in rows:
            w.writerow([r["task"], r["mouse"], r["n_sessions"],
                        "" if np.isnan(r["mean_trial_engagement"]) else f"{r['mean_trial_engagement']:.2f}",
                        "" if np.isnan(r["pct_sessions_engaged"]) else f"{r['pct_sessions_engaged']:.0f}",
                        r["mouse_engaged"],
                        "" if np.isnan(r["mean_catch_rate"]) else f"{r['mean_catch_rate']:.2f}"])
    return rows


def write_first_last_csv(by_task: dict, path: str) -> None:
    fl = first_last(by_task)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["task", "mouse", "engagement_first", "competence_first",
                    "engagement_last", "competence_last"])
        for task in fl:
            for m in _sorted_mice(fl[task]):
                first, last = fl[task][m]
                fmt = lambda v: "" if np.isnan(v) else f"{v:.1f}"
                w.writerow([task, m, fmt(first["trial_engagement"]), fmt(first["accuracy_when_engaged"]),
                            fmt(last["trial_engagement"]), fmt(last["accuracy_when_engaged"])])


def write_summary(rows: list[dict], med: dict, catch_med: dict, path: str) -> None:
    lines = ["# Lick-based trial engagement + catch trials (EXPLORATORY)",
             "hit lick = reward-related (rewarded trial, before ITI); "
             "FA lick = off-cue lick during the ITI",
             "trial_engagement = hits/(hits+FA); engaged = >= cohort median (per task)\n"]
    by_task: dict = {}
    for r in rows:
        by_task.setdefault(r["task"], []).append(r)
    for task, trs in by_task.items():
        lines.append(f"## {TH.TASK_LABELS.get(task, task)}  "
                     f"(engagement median {med[task]:.1f}%, catch median {catch_med[task]:.1f}%)")
        for r in sorted(trs, key=lambda r: r["mean_trial_engagement"] if not np.isnan(r["mean_trial_engagement"]) else -1, reverse=True):
            lines.append(f"  {r['mouse']:>5}: engagement {r['mean_trial_engagement']:5.1f}% "
                         f"| {r['pct_sessions_engaged']:.0f}% sessions engaged "
                         f"| catch {r['mean_catch_rate']:.1f}% "
                         f"| mouse {'ENGAGED' if r['mouse_engaged'] == 'yes' else 'below'}")
        lines.append("")
    Path(path).write_text("\n".join(lines))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--task", choices=["appetitive", "generalization", "both"], default="both")
    parser.add_argument("--mouse", default=None)
    args = parser.parse_args()

    global OUT_ROOT
    if not _ENV_OUT:
        OUT_ROOT = str(_RESULTS_ROOT / "trial_engagement_licks" / _TASK_AREA[args.task])

    records: list[dict] = []
    if args.task in ("appetitive", "both"):
        print("Loading appetitive (tone) task ...")
        records += load_appetitive(args.mouse)
    if args.task in ("generalization", "both"):
        print("Loading generalization (light) task ...")
        records += load_generalization(args.mouse)
    if not records:
        print("No sessions found — nothing to do.")
        return 1

    by_task = group(records)
    med = cohort_medians(by_task, "trial_engagement")
    catch_med = cohort_medians(by_task, "catch_rate")
    os.makedirs(OUT_ROOT, exist_ok=True)

    _heatmap(by_task, "trial_engagement", med, "trial engagement %",
             "reward-related licks %", os.path.join(OUT_ROOT, "trial_engagement_heatmap.png"))
    fig_by_mouse(by_task, med, os.path.join(OUT_ROOT, "trial_engagement_by_mouse.png"))
    fig_group(by_task, med, os.path.join(OUT_ROOT, "trial_engagement_group.png"))
    fig_engagement_vs_competence(by_task, med,
                                 os.path.join(OUT_ROOT, "engagement_vs_competence_first_last.png"))
    _heatmap(by_task, "catch_rate", catch_med, "catch-trial rate %",
             "% catch trials", os.path.join(OUT_ROOT, "catch_rate_heatmap.png"), fmt="{:.1f}")
    fig_catch_by_mouse(by_task, os.path.join(OUT_ROOT, "catch_rate_by_mouse.png"))
    fig_oncue_lick_split(by_task, os.path.join(OUT_ROOT, "oncue_lick_reward_split.png"))
    fig_hit_rate_first_last(by_task, os.path.join(OUT_ROOT, "hit_rate_first_vs_last.png"))

    write_session_csv(by_task, med, os.path.join(OUT_ROOT, "trial_engagement_by_session.csv"))
    write_first_last_csv(by_task, os.path.join(OUT_ROOT, "engagement_vs_competence_first_last.csv"))
    write_hit_rate_first_last_csv(by_task, os.path.join(OUT_ROOT, "hit_rate_first_vs_last.csv"))
    rows = write_mouse_csv(by_task, med, os.path.join(OUT_ROOT, "trial_engagement_by_mouse.csv"))
    write_summary(rows, med, catch_med, os.path.join(OUT_ROOT, "trial_engagement_summary.txt"))

    n_sess = sum(len(ss) for bm in by_task.values() for ss in bm.values())
    print(f"\nWrote 4 CSVs, 8 figures, and summary.txt under '{OUT_ROOT}/' "
          f"({n_sess} sessions; engagement medians "
          f"{', '.join(f'{k.split()[0]}={v:.1f}%' for k, v in med.items())}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
