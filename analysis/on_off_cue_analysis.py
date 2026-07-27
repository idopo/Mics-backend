#!/usr/bin/env python3
"""On-cue vs off-cue behaviour, lick density, and ITI timing for the appetitive
(tone) and generalization (light) tasks.

Three questions, one ES pass (reuses the loaders / trial segmentation in
appetitive_analysis / generalization_analysis so the trial set matches every
other analysis exactly). "On cue" = event while the cue was on (poke/lick time
in [0, cue_dur]); "off cue" = everything else (pre-cue wait + post-cue ITI).

1. ON/OFF SPLIT — every poke and lick is labelled on-cue or off-cue; we report
   the on-cue share (and the on:off ratio) of pokes+licks per trial, averaged per
   session and per mouse. A rising on-cue share = licking/poking is becoming
   locked to the cue rather than scattered through the ITI.

2. LICK DENSITY — does the mouse lick harder when it just earned water than when
   it is only poking/licking off-cue? For every reward we count the licks in the
   MICS_LICK_DENSITY_WIN s after it (consummatory burst) and for every off-cue
   poke the licks in the same window after it, then compare. A lick-rate PSTH
   aligned to each event type shows the full time course.

3. ITI TIMING (anticipation) — the ITI is counted from DISENGAGEMENT, not cue
   offset: the moment the mouse has both stopped its post-cue/consummatory lick
   bout (a >MICS_LICK_BOUT_GAP s gap between licks) AND withdrawn its nose from
   the poke hole (IR1 level→0 poke-out event). From that moment we ask where the
   off-cue pokes and licks fall — early (just after disengagement) or late (just
   before the next cue = anticipatory) — and when each is most probable. Output
   as a per-trial RASTER, a most-probable-time GRAPH, a per-mouse heat map, a
   group curve, and a first-half vs second-half summary. NB: the last ~10 s
   before each next trial is a fixed response lockout with no events (verified in
   the data); it is trimmed off (MICS_ITI_LOCKOUT_S) so the ITI end = lockout
   onset, not the next cue.

Outputs (under results/on_off_cue/<area>/, area = appetitive | generalization |
cross_task for --task both; override root with MICS_ONOFF_OUT):
    on_off_share_curve.png          on-cue share of events across sessions
    on_off_composition_by_mouse.png per-mouse on/off split of pokes & licks
    lick_density_reward_vs_offcue.png  burst size + lick PSTH, reward vs off-cue
    iti_raster.png                  per-trial raster of pokes/licks across the ITI
    iti_event_probability.png       when a poke/lick is most probable in the ITI
    iti_timing_map.png              heat map: poke/lick density x ITI position x mouse
    iti_timing_curve.png            group graph: events/trial across the ITI
    iti_begin_vs_end_by_mouse.png   off-cue pokes & licks, first vs second ITI half
    on_off_by_session.csv / on_off_by_mouse.csv
    lick_density_by_mouse.csv / iti_timing_by_mouse.csv
    on_off_cue_summary.txt

Usage:
    python3 on_off_cue_analysis.py --task appetitive
    python3 on_off_cue_analysis.py --task both
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
from matplotlib.lines import Line2D
from matplotlib.ticker import MaxNLocator, PercentFormatter
import numpy as np

import appetitive_analysis as A
import generalization_analysis as G
import trial_history_analysis as TH  # task constants / colours / labels (reused)

NAN = float("nan")
_RESULTS_ROOT = Path(__file__).resolve().parent / "results"
_TASK_AREA = {"appetitive": "appetitive", "generalization": "generalization", "both": "cross_task"}
_ENV_OUT = os.environ.get("MICS_ONOFF_OUT")
OUT_ROOT = _ENV_OUT or str(_RESULTS_ROOT / "on_off_cue" / "cross_task")

# licks counted in this window (s) after a reward / off-cue poke = burst density
LICK_DENSITY_WINDOW_S = float(os.environ.get("MICS_LICK_DENSITY_WIN", "1.0"))
N_ITI_BINS = int(os.environ.get("MICS_ITI_BINS", "10"))  # ITI normalised into this many bins
# a gap longer than this (s) between consecutive licks ends the consummatory bout
LICK_BOUT_GAP = float(os.environ.get("MICS_LICK_BOUT_GAP", "1.0"))
# fixed response-lockout (s) at the end of each trial: no poke/lick ever occurs in
# the last ~10s before the next trial onset (verified in the data), so the ITI's
# usable end is the next onset minus this quiet tail — trimmed off so it can't
# create a boundary pile-up in the timing plots.
ITI_LOCKOUT_S = float(os.environ.get("MICS_ITI_LOCKOUT_S", "10.0"))
# absolute-time ITI plots run from 0 to this percentile of ITI length (s)
ITI_ABS_PCTL = float(os.environ.get("MICS_ITI_ABS_PCTL", "90"))
ITI_ABS_BIN_S = 0.5  # bin width for the absolute-time poke/lick probability plots
# lick-rate PSTH window around an anchoring event
PSTH_PRE_S, PSTH_POST_S, PSTH_BIN_S = 1.0, 3.0, 0.25

ON_COLOR = "#1f77b4"
OFF_COLOR = "#ff7f0e"
POKE_COLOR = "#2ca02c"
LICK_COLOR = "#444444"


# --- loaders (keep the raw trial lists so poke/lick/reward times survive) ---
def load_appetitive(only_mouse: str | None) -> list[dict]:
    records = []
    for subject in A.discover_subjects():
        mouse = A.short_name(subject)
        if only_mouse and mouse != only_mouse:
            continue
        by_session = A.group_by_day_session(A.fetch_events(subject))
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


# --- shared helpers --------------------------------------------------------
def split_on_off(tr: dict, dur_key: str) -> tuple[list, list, list, list]:
    """(on_pokes, off_pokes, on_licks, off_licks) for one trial. On-cue = event
    time within [0, cue_dur]; off-cue = pre-cue (t<0) or post-cue (t>cue_dur)."""
    dur = tr[dur_key]
    on_p = [p for p in tr["nose_pokes"] if 0 <= p <= dur]
    off_p = [p for p in tr["nose_pokes"] if p < 0 or p > dur]
    on_l = [lk for lk in tr["licks"] if 0 <= lk <= dur]
    off_l = [lk for lk in tr["licks"] if lk < 0 or lk > dur]
    return on_p, off_p, on_l, off_l


def _count_in_window(times: list[float], start: float, width: float) -> int:
    return sum(1 for t in times if start <= t <= start + width)


def _mean_sem(values) -> tuple[float, float]:
    vals = [v for v in values if not np.isnan(v)]
    if not vals:
        return NAN, 0.0
    m = float(np.mean(vals))
    sem = float(np.std(vals, ddof=1) / np.sqrt(len(vals))) if len(vals) > 1 else 0.0
    return m, sem


def _sorted_mice(names) -> list[str]:
    return sorted(names, key=lambda m: int("".join(filter(str.isdigit, m)) or 0))


def group_by_task_mouse(records: list[dict]) -> dict[str, dict[str, list[dict]]]:
    out: dict[str, dict[str, list[dict]]] = {}
    for r in records:
        out.setdefault(r["task"], {}).setdefault(r["mouse"], []).append(r)
    for by_mouse in out.values():
        for recs in by_mouse.values():
            recs.sort(key=lambda r: r["session"])
    return out


# --- (1) on/off split ------------------------------------------------------
def session_on_off(record: dict) -> dict:
    """Per-session on/off tallies; on-cue share is the mean of per-trial shares."""
    dur_key = record["dur_key"]
    on_p = off_p = on_l = off_l = 0
    trial_share = []
    for tr in record["trials"]:
        a, b, c, d = split_on_off(tr, dur_key)
        on_p += len(a); off_p += len(b); on_l += len(c); off_l += len(d)
        on, off = len(a) + len(c), len(b) + len(d)
        if on + off:
            trial_share.append(100.0 * on / (on + off))
    tot_on, tot_off = on_p + on_l, off_p + off_l
    return {
        "task": record["task"], "mouse": record["mouse"], "session": record["session"],
        "n_trials": len(record["trials"]),
        "on_pokes": on_p, "off_pokes": off_p, "on_licks": on_l, "off_licks": off_l,
        "mean_oncue_share": float(np.mean(trial_share)) if trial_share else NAN,
        "poke_oncue_share": 100.0 * on_p / (on_p + off_p) if (on_p + off_p) else NAN,
        "lick_oncue_share": 100.0 * on_l / (on_l + off_l) if (on_l + off_l) else NAN,
        "on_off_ratio": (tot_on / tot_off) if tot_off else NAN,
    }


def on_off_by_task_mouse(records: list[dict]) -> dict:
    out: dict = {}
    for r in records:
        s = session_on_off(r)
        out.setdefault(s["task"], {}).setdefault(s["mouse"], []).append(s)
    for by_mouse in out.values():
        for ss in by_mouse.values():
            ss.sort(key=lambda s: s["session"])
    return out


def fig_share_curve(on_off: dict, out_path: str) -> None:
    tasks = list(on_off)
    fig, axes = plt.subplots(1, len(tasks), figsize=(6.5 * len(tasks), 5.2),
                             sharey=True, squeeze=False)
    cmap = plt.get_cmap("tab10")
    for ax, task in zip(axes[0], tasks):
        by_mouse = on_off[task]
        mice = _sorted_mice(by_mouse)
        max_s = max((s["session"] for ss in by_mouse.values() for s in ss), default=1)
        for i, m in enumerate(mice):
            ss = by_mouse[m]
            ax.plot([s["session"] for s in ss], [s["mean_oncue_share"] for s in ss],
                    "-o", color=cmap(i % 10), lw=1.4, ms=4, alpha=0.65, label=m)
        xs, means, sems = [], [], []
        for day in range(1, max_s + 1):
            mean, sem = _mean_sem([s["mean_oncue_share"] for ss in by_mouse.values()
                                   for s in ss if s["session"] == day])
            if np.isnan(mean):
                continue
            xs.append(day); means.append(mean); sems.append(sem)
        xs, means, sems = np.array(xs), np.array(means), np.array(sems)
        ax.plot(xs, means, "-", color="black", lw=2.8, zorder=5, label="group mean")
        ax.fill_between(xs, means - sems, means + sems, color="black", alpha=0.15, zorder=4)
        ax.set_title(TH.TASK_LABELS.get(task, task))
        ax.set_xlabel("session #")
        ax.set_ylim(0, 100)
        ax.set_xlim(0.5, max_s + 0.5)
        ax.xaxis.set_major_locator(MaxNLocator(integer=True))
        ax.yaxis.set_major_formatter(PercentFormatter(xmax=100))
        ax.grid(axis="y", alpha=0.3)
        ax.legend(fontsize=8, ncol=2, framealpha=0.9)
    axes[0][0].set_ylabel("on-cue share of pokes + licks")
    fig.suptitle("On-cue share of all pokes+licks across sessions "
                 "(high = behaviour locked to the cue)")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


def fig_composition(on_off: dict, out_path: str) -> None:
    """Per-mouse split of all events into on-poke / off-poke / on-lick / off-lick
    (normalised to 100%). One panel per task."""
    tasks = list(on_off)
    all_mice = _sorted_mice(set().union(*[set(on_off[t]) for t in tasks]))
    panel_w = max(6.0, 0.8 * len(all_mice))
    fig, axes = plt.subplots(1, len(tasks), figsize=(panel_w * len(tasks), 5.0),
                             squeeze=False, sharey=True)
    cats = [("on_pokes", "on-cue poke", ON_COLOR, None),
            ("off_pokes", "off-cue poke", OFF_COLOR, None),
            ("on_licks", "on-cue lick", ON_COLOR, "//"),
            ("off_licks", "off-cue lick", OFF_COLOR, "//")]
    for ax, task in zip(axes[0], tasks):
        by_mouse = on_off[task]
        mice = _sorted_mice(by_mouse)
        x = np.arange(len(mice), dtype=float)
        totals = []
        for m in mice:
            ss = by_mouse[m]
            totals.append(sum(s[c] for s in ss for c, *_ in cats) or 1)
        bottom = np.zeros(len(mice))
        for key, _, color, hatch in cats:
            vals = np.array([100.0 * sum(s[key] for s in by_mouse[m]) / tot
                             for m, tot in zip(mice, totals)])
            ax.bar(x, vals, bottom=bottom, color=color, hatch=hatch,
                   edgecolor="white", linewidth=0.4, width=0.8)
            bottom += vals
        ax.set_xticks(x)
        ax.set_xticklabels(mice, rotation=45, ha="right")
        ax.set_title(TH.TASK_LABELS.get(task, task))
        ax.set_ylim(0, 100)
        ax.yaxis.set_major_formatter(PercentFormatter(xmax=100))
    axes[0][0].set_ylabel("share of all pokes + licks")
    handles = [mpatches.Patch(facecolor=c, hatch=h, edgecolor="white", label=lbl)
               for _, lbl, c, h in cats]
    fig.legend(handles=handles, loc="upper right", fontsize=8, framealpha=0.9)
    fig.suptitle("Where the mouse's pokes and licks fell — on-cue vs off-cue")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


# --- (2) lick density ------------------------------------------------------
def lick_density(recs: list[dict]) -> tuple[list[int], list[int]]:
    """(licks-after-reward, licks-after-offcue-poke) counted in the density
    window, pooled over one mouse's trials."""
    reward_d, offcue_d = [], []
    for r in recs:
        dur_key = r["dur_key"]
        for tr in r["trials"]:
            dur = tr[dur_key]
            off_pokes = [p for p in tr["nose_pokes"] if p < 0 or p > dur]
            for rt in tr["rewards"]:
                reward_d.append(_count_in_window(tr["licks"], rt, LICK_DENSITY_WINDOW_S))
            for pt in off_pokes:
                offcue_d.append(_count_in_window(tr["licks"], pt, LICK_DENSITY_WINDOW_S))
    return reward_d, offcue_d


def lick_psth(recs: list[dict], anchor: str) -> tuple[np.ndarray, np.ndarray, int]:
    """Mean lick rate (licks/s) in bins around each anchor event across records."""
    edges = np.arange(-PSTH_PRE_S, PSTH_POST_S + PSTH_BIN_S / 2, PSTH_BIN_S)
    counts = np.zeros(len(edges) - 1)
    n_anchor = 0
    for r in recs:
        dur_key = r["dur_key"]
        for tr in r["trials"]:
            dur = tr[dur_key]
            anchors = (tr["rewards"] if anchor == "reward"
                       else [p for p in tr["nose_pokes"] if p < 0 or p > dur])
            for a in anchors:
                n_anchor += 1
                rel = [lk - a for lk in tr["licks"] if -PSTH_PRE_S <= lk - a <= PSTH_POST_S]
                counts += np.histogram(rel, bins=edges)[0]
    centers = (edges[:-1] + edges[1:]) / 2
    rate = counts / (n_anchor * PSTH_BIN_S) if n_anchor else counts
    return centers, rate, n_anchor


def fig_lick_density(by_task: dict, out_path: str) -> dict:
    """Left: per-mouse mean licks in the window after reward vs after an off-cue
    poke. Right: lick-rate PSTH aligned to each event type (group). Returns the
    per-mouse means for the CSV/summary."""
    tasks = list(by_task)
    nrow = len(tasks)
    fig, axes = plt.subplots(nrow, 2, figsize=(13, 4.4 * nrow), squeeze=False)
    per_mouse_rows: dict = {}
    for ti, task in enumerate(tasks):
        by_mouse = by_task[task]
        mice = _sorted_mice(by_mouse)
        ax_bar, ax_psth = axes[ti][0], axes[ti][1]
        x = np.arange(len(mice), dtype=float)
        rew_means, off_means = [], []
        for m in mice:
            rd, od = lick_density(by_mouse[m])
            rm = float(np.mean(rd)) if rd else NAN
            om = float(np.mean(od)) if od else NAN
            rew_means.append(rm); off_means.append(om)
            per_mouse_rows.setdefault(task, []).append(
                {"task": task, "mouse": m, "n_rewards": len(rd), "n_offcue_pokes": len(od),
                 "licks_after_reward": rm, "licks_after_offcue": om})
        ax_bar.bar(x - 0.2, rew_means, width=0.4, color="#2ca02c", label="after reward")
        ax_bar.bar(x + 0.2, off_means, width=0.4, color=OFF_COLOR, label="after off-cue poke")
        ax_bar.set_xticks(x); ax_bar.set_xticklabels(mice, rotation=45, ha="right")
        ax_bar.set_ylabel(f"mean licks in {LICK_DENSITY_WINDOW_S:g}s window")
        ax_bar.set_title(f"{TH.TASK_LABELS.get(task, task)} — lick burst size")
        ax_bar.grid(axis="y", alpha=0.3)
        ax_bar.legend(fontsize=8)

        all_recs = [rr for m in mice for rr in by_mouse[m]]
        c, r_rate, n_r = lick_psth(all_recs, "reward")
        _, o_rate, n_o = lick_psth(all_recs, "offcue")
        ax_psth.plot(c, r_rate, "-", color="#2ca02c", lw=2, label=f"reward (n={n_r})")
        ax_psth.plot(c, o_rate, "-", color=OFF_COLOR, lw=2, label=f"off-cue poke (n={n_o})")
        ax_psth.axvline(0, color="grey", ls=":", lw=1)
        ax_psth.set_xlabel("time from event (s)")
        ax_psth.set_ylabel("lick rate (licks/s)")
        ax_psth.set_title(f"{TH.TASK_LABELS.get(task, task)} — lick PSTH")
        ax_psth.legend(fontsize=8)
        ax_psth.grid(alpha=0.3)
    fig.suptitle("Lick density: consummatory (post-reward) vs off-cue licking")
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(out_path, dpi=140)
    plt.close(fig)
    return per_mouse_rows


# --- (3) ITI timing --------------------------------------------------------
def iti_start_time(tr: dict, dur_key: str) -> float:
    """Disengagement time (rel. cue onset) = when the mouse has BOTH stopped its
    post-cue/consummatory lick bout AND withdrawn its nose from the poke hole.
    The ITI (the off-cue waiting period) is counted from here, not from cue
    offset — so the consummatory drinking is excluded from the ITI entirely."""
    dur = tr[dur_key]
    # end of the first lick bout at/after cue onset: extend while consecutive
    # licks stay within LICK_BOUT_GAP; the last such lick ends the bout.
    bout_licks = sorted(lk for lk in tr["licks"] if lk >= 0)
    lick_end = 0.0
    if bout_licks:
        lick_end = bout_licks[0]
        for lk in bout_licks[1:]:
            if lk - lick_end > LICK_BOUT_GAP:
                break
            lick_end = lk
    # nose withdrawal: first poke-out at/after the lick bout ends; else the last
    # poke-out seen; else the lick-bout end.
    outs = sorted(tr.get("nose_pokes_out", []))
    after = [po for po in outs if po >= lick_end]
    poke_out = after[0] if after else (outs[-1] if outs else lick_end)
    return max(dur, lick_end, poke_out)


def iti_trials(recs: list[dict]) -> list[dict]:
    """Per-trial ITI event lists with poke/lick times relative to the ITI start
    (disengagement). Trials with no real waiting period (span<=0.5s) are dropped."""
    out = []
    for r in recs:
        dur_key = r["dur_key"]
        for tr in r["trials"]:
            start = iti_start_time(tr, dur_key)
            end = tr["iti_end"] - ITI_LOCKOUT_S  # drop the fixed quiet lockout tail
            span = end - start
            if span <= 0.5:
                continue
            out.append({
                "span": span,
                "pokes": [p - start for p in tr["nose_pokes"] if start <= p <= end],
                "licks": [lk - start for lk in tr["licks"] if start <= lk <= end],
            })
    return out


def iti_profile(recs: list[dict]) -> tuple[np.ndarray, np.ndarray, int]:
    """Per-bin poke & lick counts per trial across the normalised [0,1] ITI
    (bin 0 = just after disengagement, last bin = just before the next cue)."""
    poke_bins = np.zeros(N_ITI_BINS)
    lick_bins = np.zeros(N_ITI_BINS)
    trials = iti_trials(recs)
    for t in trials:
        span = t["span"]
        for p in t["pokes"]:
            poke_bins[min(int(p / span * N_ITI_BINS), N_ITI_BINS - 1)] += 1
        for lk in t["licks"]:
            lick_bins[min(int(lk / span * N_ITI_BINS), N_ITI_BINS - 1)] += 1
    n_trials = len(trials)
    if n_trials:
        return poke_bins / n_trials, lick_bins / n_trials, n_trials
    return poke_bins, lick_bins, 0


def _iti_matrices(by_mouse: dict) -> tuple[list[str], np.ndarray, np.ndarray]:
    mice = _sorted_mice(by_mouse)
    poke_mat = np.zeros((len(mice), N_ITI_BINS))
    lick_mat = np.zeros((len(mice), N_ITI_BINS))
    for i, m in enumerate(mice):
        pk, lk, _ = iti_profile(by_mouse[m])
        poke_mat[i] = pk
        lick_mat[i] = lk
    return mice, poke_mat, lick_mat


def fig_iti_map(by_task: dict, out_path: str) -> None:
    """Heat MAP: for each mouse (rows) the poke / lick density across the ITI
    (columns, early -> late). One row-block of two heatmaps per task."""
    tasks = list(by_task)
    fig, axes = plt.subplots(len(tasks), 2, figsize=(12, 3.6 * len(tasks)), squeeze=False)
    xticks = np.linspace(0, N_ITI_BINS, 3)
    for ti, task in enumerate(tasks):
        mice, poke_mat, lick_mat = _iti_matrices(by_task[task])
        for col, (mat, name, cmap) in enumerate([(poke_mat, "off-cue pokes", "viridis"),
                                                 (lick_mat, "licks", "magma")]):
            ax = axes[ti][col]
            im = ax.imshow(mat, aspect="auto", cmap=cmap, origin="upper",
                           extent=(0, N_ITI_BINS, len(mice) - 0.5, -0.5))
            ax.set_yticks(range(len(mice)))
            ax.set_yticklabels(mice, fontsize=8)
            ax.set_xticks(xticks)
            ax.set_xticklabels(["ITI\nstart", "mid ITI", "ITI\nend"], fontsize=8)
            ax.set_title(f"{TH.TASK_LABELS.get(task, task)} — {name} / trial")
            fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.suptitle("ITI density map — where pokes & licks fall between cues "
                 "(left→right = start→end of ITI)")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


def fig_iti_curve(by_task: dict, out_path: str) -> None:
    """Group GRAPH: mean events/trial across the normalised ITI (mean ± SEM over
    mice), pokes and licks. One panel per task."""
    tasks = list(by_task)
    centers = (np.arange(N_ITI_BINS) + 0.5) / N_ITI_BINS
    fig, axes = plt.subplots(1, len(tasks), figsize=(6.2 * len(tasks), 4.8),
                             squeeze=False, sharey=True)
    for ax, task in zip(axes[0], tasks):
        _, poke_mat, lick_mat = _iti_matrices(by_task[task])
        for mat, name, color in [(poke_mat, "off-cue pokes", POKE_COLOR),
                                 (lick_mat, "licks", LICK_COLOR)]:
            mean = mat.mean(axis=0)
            sem = mat.std(axis=0, ddof=1) / np.sqrt(mat.shape[0]) if mat.shape[0] > 1 else np.zeros(N_ITI_BINS)
            ax.plot(centers, mean, "-o", color=color, ms=4, lw=1.8, label=name)
            ax.fill_between(centers, mean - sem, mean + sem, color=color, alpha=0.18)
        ax.axvspan(0, 0.5, color="grey", alpha=0.05)
        ax.set_title(TH.TASK_LABELS.get(task, task))
        ax.set_xlabel("position in ITI  (0 = disengagement → 1 = ITI end / next trial)")
        ax.set_xlim(0, 1)
        ax.grid(alpha=0.3)
        ax.legend(fontsize=9)
    axes[0][0].set_ylabel("events per trial (per bin)")
    fig.suptitle("Anticipatory timing — events across the ITI "
                 "(rise toward 1 = anticipating the next trial)")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


def _pool_iti_trials(by_mouse: dict) -> list[dict]:
    return iti_trials([rr for m in by_mouse for rr in by_mouse[m]])


def iti_event_rates(trials: list[dict], aligned: str):
    """Marginal poke & lick distribution across absolute ITI time: mean events
    per trial per second in each time bin (counts / total trials / bin width).
    aligned='start' measures seconds since disengagement; aligned='end' measures
    seconds before the next cue. Dividing by the total trial count (not just the
    trials still ongoing) means the long-ITI tail decays naturally, so the peak
    marks where an event is genuinely most likely to be observed."""
    spans = np.array([t["span"] for t in trials], dtype=float)
    if spans.size == 0:
        return None
    cap = max(float(np.percentile(spans, ITI_ABS_PCTL)), 2.0)
    edges = np.arange(0, cap + ITI_ABS_BIN_S, ITI_ABS_BIN_S)
    centers = (edges[:-1] + edges[1:]) / 2
    poke_c = np.zeros(len(centers))
    lick_c = np.zeros(len(centers))
    for t in trials:
        for p in t["pokes"]:
            x = p if aligned == "start" else (t["span"] - p)
            if 0 <= x < cap:
                poke_c[min(int(x / ITI_ABS_BIN_S), len(centers) - 1)] += 1
        for lk in t["licks"]:
            x = lk if aligned == "start" else (t["span"] - lk)
            if 0 <= x < cap:
                lick_c[min(int(x / ITI_ABS_BIN_S), len(centers) - 1)] += 1
    n = float(len(trials))
    return centers, poke_c / n / ITI_ABS_BIN_S, lick_c / n / ITI_ABS_BIN_S, cap


def fig_iti_event_probability(by_task: dict, out_path: str) -> dict:
    """GRAPH answering 'when is a poke / lick most probable in the ITI?'. Left
    column = time since ITI start, right = time before the next cue. Returns the
    peak (most-probable) times per task for the summary."""
    tasks = list(by_task)
    fig, axes = plt.subplots(len(tasks), 2, figsize=(13, 4.2 * len(tasks)), squeeze=False)
    peaks: dict = {}
    for ti, task in enumerate(tasks):
        trials = _pool_iti_trials(by_task[task])
        for col, aligned in enumerate(["start", "end"]):
            ax = axes[ti][col]
            res = iti_event_rates(trials, aligned)
            if res is None:
                continue
            centers, poke_rate, lick_rate, cap = res
            xs = centers if aligned == "start" else -centers
            ax.plot(xs, poke_rate, "-o", color=POKE_COLOR, ms=3, lw=1.7, label="off-cue poke")
            ax.plot(xs, lick_rate, "-o", color=LICK_COLOR, ms=3, lw=1.7, label="lick")
            ax.grid(alpha=0.3)
            ax.legend(fontsize=8)
            if aligned == "start":
                pk_p = float(centers[int(np.nanargmax(poke_rate))]) if np.any(~np.isnan(poke_rate)) else NAN
                pk_l = float(centers[int(np.nanargmax(lick_rate))]) if np.any(~np.isnan(lick_rate)) else NAN
                peaks[task] = {"poke_peak_s": pk_p, "lick_peak_s": pk_l, "n_trials": len(trials)}
                ax.axvline(pk_p, color=POKE_COLOR, ls=":", lw=1)
                ax.axvline(pk_l, color=LICK_COLOR, ls=":", lw=1)
                ax.set_title(f"{TH.TASK_LABELS.get(task, task)} — since ITI start "
                             f"(poke peak {pk_p:.1f}s, lick peak {pk_l:.1f}s)", fontsize=9)
                ax.set_xlabel("time since ITI start / disengagement (s)")
            else:
                ax.set_title(f"{TH.TASK_LABELS.get(task, task)} — before ITI end", fontsize=9)
                ax.set_xlabel("time before ITI end / response lockout (s)")
            ax.set_ylabel("events / trial-second")
    fig.suptitle("When in the ITI are pokes and licks most probable?")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(out_path, dpi=140)
    plt.close(fig)
    return peaks


def fig_iti_raster(by_task: dict, out_path: str) -> None:
    """RASTER: each row is one trial's ITI (t=0 = disengagement), pokes green and
    licks black; the blue dot marks the ITI end (start of the fixed response
    lockout before the next trial). Trials are sorted by ITI length so the end
    markers form a curve — early events cluster at the left, late/anticipatory
    events would crowd toward each trial's blue marker."""
    panels = [(task, m) for task in by_task for m in _sorted_mice(by_task[task])]
    all_spans = [t["span"] for task in by_task for m in by_task[task]
                 for t in iti_trials(by_task[task][m])]
    xcap = max(float(np.percentile(all_spans, 97)), 3.0) if all_spans else 10.0
    ncol = 5
    nrow = (len(panels) + ncol - 1) // ncol
    fig, axes = plt.subplots(nrow, ncol, figsize=(3.5 * ncol, 2.9 * nrow), squeeze=False)
    axes = axes.reshape(-1)
    max_rows = 120
    for ax, (task, mouse) in zip(axes, panels):
        trials = sorted(iti_trials(by_task[task][mouse]), key=lambda t: t["span"])
        if len(trials) > max_rows:  # even subsample to keep the raster legible
            idx = np.linspace(0, len(trials) - 1, max_rows).astype(int)
            trials = [trials[i] for i in idx]
        for y, t in enumerate(trials):
            if t["pokes"]:
                ax.scatter(t["pokes"], [y] * len(t["pokes"]), marker="|", s=14,
                           linewidths=0.7, color=POKE_COLOR, zorder=2)
            if t["licks"]:
                ax.scatter(t["licks"], [y] * len(t["licks"]), marker="|", s=14,
                           linewidths=0.6, color=LICK_COLOR, zorder=1)
            ax.plot(t["span"], y, ".", color="#3a7ca5", ms=3, zorder=3)
        ax.set_xlim(0, xcap)
        ax.set_ylim(-1, len(trials))
        ax.set_title(f"{mouse} · {'tone' if task == TH.TASK_APP else 'light'} "
                     f"({len(trials)} tr)", fontsize=8)
        ax.tick_params(labelsize=7)
    for ax in axes[len(panels):]:
        ax.axis("off")
    handles = [Line2D([], [], color=POKE_COLOR, marker="|", ls="None", label="off-cue poke"),
               Line2D([], [], color=LICK_COLOR, marker="|", ls="None", label="lick"),
               Line2D([], [], color="#3a7ca5", marker=".", ls="None", label="ITI end (lockout)")]
    fig.legend(handles=handles, loc="upper right", fontsize=8, framealpha=0.9)
    fig.supxlabel("time since ITI start / disengagement (s)  —  trials sorted by ITI length")
    fig.supylabel("trial (sorted)")
    fig.suptitle("ITI raster — pokes vs licks from disengagement to ITI end (lockout)")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(out_path, dpi=145)
    plt.close(fig)


def iti_begin_end(by_task: dict) -> list[dict]:
    """Per mouse: mean off-cue pokes & licks per trial in the first vs second
    half of the ITI (the crisp 'beginning or end?' answer)."""
    rows = []
    for task, by_mouse in by_task.items():
        for m in _sorted_mice(by_mouse):
            pk, lk, n = iti_profile(by_mouse[m])
            half = N_ITI_BINS // 2
            rows.append({
                "task": task, "mouse": m, "n_trials": n,
                "pokes_first_half": float(pk[:half].sum()),
                "pokes_second_half": float(pk[half:].sum()),
                "licks_first_half": float(lk[:half].sum()),
                "licks_second_half": float(lk[half:].sum()),
            })
    return rows


def fig_begin_vs_end(rows: list[dict], by_task: dict, out_path: str) -> None:
    tasks = list(by_task)
    fig, axes = plt.subplots(len(tasks), 2, figsize=(12, 3.8 * len(tasks)), squeeze=False)
    for ti, task in enumerate(tasks):
        trows = [r for r in rows if r["task"] == task]
        mice = [r["mouse"] for r in trows]
        x = np.arange(len(mice), dtype=float)
        for col, (a, b, name) in enumerate([("pokes_first_half", "pokes_second_half", "off-cue pokes"),
                                            ("licks_first_half", "licks_second_half", "licks")]):
            ax = axes[ti][col]
            ax.bar(x - 0.2, [r[a] for r in trows], width=0.4, color="#8c8c8c", label="first half (early)")
            ax.bar(x + 0.2, [r[b] for r in trows], width=0.4, color="#d62728", label="second half (late)")
            ax.set_xticks(x); ax.set_xticklabels(mice, rotation=45, ha="right")
            ax.set_ylabel("events / trial")
            ax.set_title(f"{TH.TASK_LABELS.get(task, task)} — {name}")
            ax.grid(axis="y", alpha=0.3)
            ax.legend(fontsize=8)
    fig.suptitle("ITI first half (early / consummatory) vs second half (late / anticipatory)")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


# --- CSV / summary ---------------------------------------------------------
def write_session_csv(on_off: dict, path: str) -> None:
    cols = ["task", "mouse", "session", "n_trials", "on_pokes", "off_pokes",
            "on_licks", "off_licks", "mean_oncue_share", "poke_oncue_share",
            "lick_oncue_share", "on_off_ratio"]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for by_mouse in on_off.values():
            for ss in by_mouse.values():
                for s in ss:
                    w.writerow({c: s[c] for c in cols})


def write_onoff_mouse_csv(on_off: dict, path: str) -> list[dict]:
    rows = []
    for task, by_mouse in on_off.items():
        for m in _sorted_mice(by_mouse):
            ss = by_mouse[m]
            mean, sem = _mean_sem([s["mean_oncue_share"] for s in ss])
            rows.append({
                "task": task, "mouse": m, "n_sessions": len(ss),
                "mean_oncue_share": mean, "sem_oncue_share": sem,
                "on_pokes": sum(s["on_pokes"] for s in ss),
                "off_pokes": sum(s["off_pokes"] for s in ss),
                "on_licks": sum(s["on_licks"] for s in ss),
                "off_licks": sum(s["off_licks"] for s in ss),
            })
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["task"])
        w.writeheader()
        w.writerows(rows)
    return rows


def write_density_csv(density_rows: dict, path: str) -> None:
    flat = [r for rows in density_rows.values() for r in rows]
    cols = ["task", "mouse", "n_rewards", "n_offcue_pokes",
            "licks_after_reward", "licks_after_offcue"]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(flat)


def write_iti_csv(rows: list[dict], path: str) -> None:
    cols = ["task", "mouse", "n_trials", "pokes_first_half", "pokes_second_half",
            "licks_first_half", "licks_second_half"]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)


def write_summary(onoff_rows: list[dict], density_rows: dict, iti_rows: list[dict],
                  peaks: dict, path: str) -> None:
    lines = ["# On-cue vs off-cue, lick density, and ITI timing\n"]
    by_task_onoff: dict = {}
    for r in onoff_rows:
        by_task_onoff.setdefault(r["task"], []).append(r)
    for task, trs in by_task_onoff.items():
        lines.append(f"\n## {TH.TASK_LABELS.get(task, task)}")
        shares = [r["mean_oncue_share"] for r in trs if not np.isnan(r["mean_oncue_share"])]
        if shares:
            lines.append(f"on-cue share of pokes+licks: group mean {np.mean(shares):.1f}% "
                         f"(range {min(shares):.1f}–{max(shares):.1f}%)")
        dens = density_rows.get(task, [])
        rew = [d["licks_after_reward"] for d in dens if not np.isnan(d["licks_after_reward"])]
        off = [d["licks_after_offcue"] for d in dens if not np.isnan(d["licks_after_offcue"])]
        if rew and off:
            lines.append(f"licks in {LICK_DENSITY_WINDOW_S:g}s after reward: {np.mean(rew):.2f} "
                         f"vs after off-cue poke: {np.mean(off):.2f} "
                         f"(reward = {np.mean(rew) / np.mean(off):.1f}x denser)"
                         if np.mean(off) else "")
        itr = [r for r in iti_rows if r["task"] == task]
        pf = sum(r["pokes_first_half"] for r in itr)
        ps = sum(r["pokes_second_half"] for r in itr)
        lf = sum(r["licks_first_half"] for r in itr)
        ls = sum(r["licks_second_half"] for r in itr)
        lines.append(f"ITI (from disengagement) off-cue pokes  early:late = {pf:.0f}:{ps:.0f} "
                     f"({'more LATE (anticipatory)' if ps > pf else 'more EARLY'})")
        lines.append(f"ITI (from disengagement) licks          early:late = {lf:.0f}:{ls:.0f} "
                     f"({'more LATE (anticipatory)' if ls > lf else 'more EARLY'})")
        pk = peaks.get(task)
        if pk:
            lines.append(f"most probable time after ITI start — poke: {pk['poke_peak_s']:.1f}s, "
                         f"lick: {pk['lick_peak_s']:.1f}s (n={pk['n_trials']} ITIs)")
    Path(path).write_text("\n".join(x for x in lines if x is not None) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--task", choices=["appetitive", "generalization", "both"], default="both")
    parser.add_argument("--mouse", default=None, help="restrict to one mouse, e.g. m102")
    args = parser.parse_args()

    global OUT_ROOT
    if not _ENV_OUT:
        OUT_ROOT = str(_RESULTS_ROOT / "on_off_cue" / _TASK_AREA[args.task])

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

    by_task = group_by_task_mouse(records)
    on_off = on_off_by_task_mouse(records)
    os.makedirs(OUT_ROOT, exist_ok=True)

    write_session_csv(on_off, os.path.join(OUT_ROOT, "on_off_by_session.csv"))
    onoff_rows = write_onoff_mouse_csv(on_off, os.path.join(OUT_ROOT, "on_off_by_mouse.csv"))
    fig_share_curve(on_off, os.path.join(OUT_ROOT, "on_off_share_curve.png"))
    fig_composition(on_off, os.path.join(OUT_ROOT, "on_off_composition_by_mouse.png"))

    density_rows = fig_lick_density(by_task, os.path.join(OUT_ROOT, "lick_density_reward_vs_offcue.png"))
    write_density_csv(density_rows, os.path.join(OUT_ROOT, "lick_density_by_mouse.csv"))

    fig_iti_map(by_task, os.path.join(OUT_ROOT, "iti_timing_map.png"))
    fig_iti_curve(by_task, os.path.join(OUT_ROOT, "iti_timing_curve.png"))
    fig_iti_raster(by_task, os.path.join(OUT_ROOT, "iti_raster.png"))
    peaks = fig_iti_event_probability(by_task, os.path.join(OUT_ROOT, "iti_event_probability.png"))
    iti_rows = iti_begin_end(by_task)
    fig_begin_vs_end(iti_rows, by_task, os.path.join(OUT_ROOT, "iti_begin_vs_end_by_mouse.png"))
    write_iti_csv(iti_rows, os.path.join(OUT_ROOT, "iti_timing_by_mouse.csv"))

    write_summary(onoff_rows, density_rows, iti_rows, peaks,
                  os.path.join(OUT_ROOT, "on_off_cue_summary.txt"))

    n_sess = sum(len(ss) for by_mouse in on_off.values() for ss in by_mouse.values())
    print(f"\nWrote 4 CSVs, 8 figures, and summary.txt under '{OUT_ROOT}/' "
          f"({n_sess} sessions, {len(records)} records).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
