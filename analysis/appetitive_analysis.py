#!/usr/bin/env python3
"""Behavioral analysis for the AppetitveTaskReal appetitive-tone task.

One script, three analyses, sharing a single ES fetch + trial-segmentation pass:

  1. RASTERS       per (subject, session): when the mouse nose-poked / licked,
                   relative to tone onset, with rewarded (HIT) licks in yellow
                   and a per-trial light-blue band for the actual tone duration.
  2. LEARNING CURVE hit rate across training sessions, per mouse + group mean.
  3. POKE BARS     per-mouse grids of per-session bar plots (one figure each):
                   total nose pokes, nose pokes during the tone cue, and
                   poked-but-no-lick vs poked-and-licked trials.

Data source: Elasticsearch (RecordingBox pilot, Nov-Dec 2025, 10 mice). Event
semantics, verified against the raw stream:
  - tone onset : mixer.AUDIO  func_name=set_by_filename, level=1   (t=0)
  - tone off   : mixer.AUDIO  func_name=mute  (HIT cuts tone short; a MISS plays
                 the full audio file, which is the TONE_FILE_LENGTH_S fallback)
  - trial mark : state_transition "trial_onset"
  - nose poke  : gpio.Digital_In  id=IR1, level=1 (rising edge)
  - lick       : gpio.Digital_In  id=TOUCH_INT
  - reward/HIT : gpio.Solenoid_mics id=open, func_name=store_series (valve fires)

Dependency-light on purpose: only `requests`, `numpy`, `matplotlib`.

Usage:
    python3 appetitive_analysis.py                      # everything, all mice
    python3 appetitive_analysis.py --analysis rasters   # rasters only
    python3 appetitive_analysis.py --analysis curve     # learning curve only
    python3 appetitive_analysis.py --analysis pokes     # poke bar grids only
    python3 appetitive_analysis.py --subject m90_AppetitiveTone_150 --session 7
    python3 appetitive_analysis.py --max-sessions 1     # one session/mouse (quick)
    python3 appetitive_analysis.py --min-trials 20      # stricter session filter
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import sys
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.ticker import MaxNLocator
import numpy as np
import requests

import participation

# --- configuration (override via env; never hardcode in the body) ---------
from config import ES_URL, ES_INDEX  # noqa: E402  (ES host/index, env-overridable)

TASK_TYPE = os.environ.get("MICS_TASK", "AppetitveTaskReal")
PILOT = os.environ.get("MICS_PILOT", "RecordingBox")
DATE_GTE = os.environ.get("MICS_DATE_GTE", "2025-11-01")
DATE_LTE = os.environ.get("MICS_DATE_LTE", "2025-12-31T23:59:59")

# The 10 mice are the descriptive ES subjects matching this pattern
# (m90, m92, m93, m97, m98, m100..m104 -> "<id>_AppetitiveTone_150";
#  note m93 carries a double underscore).
SUBJECT_PATTERN = re.compile(r"^m\d+_+AppetitiveTone_150$")

# Fallback tone length (= audio-file length) for trials with no explicit mute:
# on a MISS the tone is never muted early, it just plays out and stops here.
TONE_FILE_LENGTH_S = float(os.environ.get("MICS_TONE_S", "8.0"))
REWARD_LICK_WINDOW_S = 0.5  # a lick within this much before a reward = the HIT lick
# A valid "session" has a trial count around the nominal 60. Sessions outside
# [MIN_TRIALS, MAX_TRIALS] are aborted partials or merged double-sessions (~120)
# and are excluded from every analysis. Override the band via env if needed.
MIN_TRIALS = int(os.environ.get("MICS_MIN_TRIALS", "50"))
MAX_TRIALS = int(os.environ.get("MICS_MAX_TRIALS", "72"))


def session_len_ok(n_trials: int) -> bool:
    """True if a session's trial count is within the valid ~60-trial band."""
    return MIN_TRIALS <= n_trials <= MAX_TRIALS
OUT_ROOT = os.environ.get("MICS_OUT") or str(
    Path(__file__).resolve().parent / "results" / "appetitive" / "overview")

# Event-type / id constants (verified against the data)
ET_AUDIO = "mixer.AUDIO"
ET_DIGITAL_IN = "gpio.Digital_In"
ET_SOLENOID = "gpio.Solenoid_mics"
ET_STATE = "state_transition"
ET_TRIAL = "Trial_Tracker"
RELEVANT_EVENT_TYPES = [ET_AUDIO, ET_DIGITAL_IN, ET_SOLENOID, ET_STATE, ET_TRIAL]

ID_NOSEPOKE = "IR1"
ID_LICK = "TOUCH_INT"
ID_REWARD = "open"


# --- Elasticsearch access -------------------------------------------------
def _iso_to_epoch(ts: str) -> float:
    """ISO8601 (with tz) -> POSIX seconds."""
    return datetime.fromisoformat(ts).timestamp()


def _base_query(subject: str | None = None) -> dict:
    must: list[dict] = [
        {"term": {"task_type.keyword": TASK_TYPE}},
        {"term": {"pilot.keyword": PILOT}},
        {"range": {"timestamp": {"gte": DATE_GTE, "lte": DATE_LTE}}},
    ]
    if subject is not None:
        must.append({"term": {"subject.keyword": subject}})
    return {"bool": {"must": must}}


def discover_subjects() -> list[str]:
    """Descriptive ES subjects for this task/pilot/date that look like the 10
    study mice (sorted by mouse number)."""
    body = {
        "size": 0,
        "query": _base_query(),
        "aggs": {"subjects": {"terms": {"field": "subject.keyword", "size": 200}}},
    }
    r = requests.post(f"{ES_URL}/{ES_INDEX}/_search", json=body, timeout=60)
    r.raise_for_status()
    keys = [b["key"] for b in r.json()["aggregations"]["subjects"]["buckets"]]
    matched = [k for k in keys if SUBJECT_PATTERN.match(k)]

    def mouse_num(name: str) -> int:
        m = re.match(r"^m(\d+)", name)
        return int(m.group(1)) if m else 0

    return sorted(matched, key=mouse_num)


def _flatten(src: dict) -> dict:
    e = src.get("event", {})
    ed = e.get("event_data", {})
    return {
        "session": src.get("session"),
        "epoch": _iso_to_epoch(src["timestamp"]),
        "etype": e.get("event_type"),
        "id": ed.get("id"),
        "state": ed.get("current_state"),
        "func": ed.get("func_name"),
        "level": e.get("level"),
    }


def fetch_events(subject: str, page: int = 5000) -> list[dict]:
    """Scroll all relevant events for a subject, as flat dicts sorted by
    (session, epoch)."""
    query = {
        "bool": {
            "must": _base_query(subject)["bool"]["must"]
            + [{"terms": {"event.event_type.keyword": RELEVANT_EVENT_TYPES}}]
        }
    }
    src = [
        "timestamp", "session", "event.event_type",
        "event.event_data.id", "event.event_data.current_state",
        "event.event_data.func_name", "event.level",
    ]
    body = {"size": page, "_source": src, "query": query,
            "sort": [{"session": "asc"}, {"timestamp": "asc"}]}
    r = requests.post(f"{ES_URL}/{ES_INDEX}/_search?scroll=2m", json=body, timeout=120)
    r.raise_for_status()
    data = r.json()
    scroll_id = data.get("_scroll_id")
    out: list[dict] = []
    try:
        while True:
            hits = data["hits"]["hits"]
            if not hits:
                break
            out.extend(_flatten(h["_source"]) for h in hits)
            r = requests.post(f"{ES_URL}/_search/scroll",
                              json={"scroll": "2m", "scroll_id": scroll_id}, timeout=120)
            r.raise_for_status()
            data = r.json()
            scroll_id = data.get("_scroll_id")
    finally:
        if scroll_id:
            requests.delete(f"{ES_URL}/_search/scroll",
                            json={"scroll_id": [scroll_id]}, timeout=30)
    out.sort(key=lambda e: (e["session"], e["epoch"]))
    return out


def group_by_session(events: list[dict]) -> dict[int, list[dict]]:
    by_session: dict[int, list[dict]] = {}
    for e in events:
        by_session.setdefault(e["session"], []).append(e)
    return by_session


# --- trial segmentation ---------------------------------------------------
def segment_trials(events: list[dict]) -> list[dict]:
    """Split one session's chronological events into trials, each aligned to its
    tone onset (t=0) with nose-poke / lick / rewarded-lick times relative to it."""
    onsets = [e["epoch"] for e in events
              if e["etype"] == ET_STATE and e["state"] == "trial_onset"]
    if not onsets:
        return []
    bounds = onsets + [float("inf")]

    trials: list[dict] = []
    for i in range(len(onsets)):
        lo, hi = bounds[i], bounds[i + 1]
        window = [e for e in events if lo <= e["epoch"] < hi]

        tone = next((e for e in window if e["etype"] == ET_AUDIO
                     and e["func"] == "set_by_filename" and e["level"] == 1), None)
        t0 = tone["epoch"] if tone else lo  # fall back to trial_onset

        # actual tone duration: onset -> first mute (HIT cuts tone short); if the
        # tone is never muted (MISS) it plays the full audio file and stops there.
        mute = next((e for e in window if e["etype"] == ET_AUDIO
                     and e["func"] == "mute" and e["epoch"] > t0), None)
        tone_dur = (mute["epoch"] - t0) if mute else TONE_FILE_LENGTH_S

        nose_pokes, nose_pokes_out, licks, rewards = [], [], [], []
        for e in window:
            if e["etype"] == ET_DIGITAL_IN and e["id"] == ID_NOSEPOKE and e["level"] == 1:
                nose_pokes.append(e["epoch"] - t0)  # beam broken = nose in
            elif e["etype"] == ET_DIGITAL_IN and e["id"] == ID_NOSEPOKE and e["level"] == 0:
                nose_pokes_out.append(e["epoch"] - t0)  # beam restored = nose out
            elif e["etype"] == ET_DIGITAL_IN and e["id"] == ID_LICK:
                licks.append(e["epoch"] - t0)
            elif (e["etype"] == ET_SOLENOID and e["id"] == ID_REWARD
                  and e["func"] == "store_series"):
                # store_series = the valve-open command (one per water delivery);
                # its paired "series" event and the level field are not reliable.
                rewards.append(e["epoch"] - t0)

        rewards = _dedupe(rewards)
        # trial window end (= next trial onset) rel. to tone onset; used to place
        # events within the post-cue ITI. Last trial has no next onset -> last event.
        win_end = hi if hi != float("inf") else (window[-1]["epoch"] if window else t0)
        # false alarm = a nose poke during the ITI countdown; each one resets the
        # ITI timer (punishment). Logged as the state_ITI_nose_poke transition.
        false_alarms = sum(1 for e in window
                           if e["etype"] == ET_STATE and e["state"] == "state_ITI_nose_poke")
        trials.append({
            "tone_dur": tone_dur,
            "iti_end": win_end - t0,
            "n_false_alarms": false_alarms,
            "punished": false_alarms > 0,
            "nose_pokes": nose_pokes,
            "nose_pokes_out": nose_pokes_out,
            "licks": licks,
            "rewards": rewards,  # deduped water-delivery times (rel. to tone onset)
            "rewarded_licks": _rewarded_licks(licks, rewards),
            "is_hit": bool(rewards),
        })
    return trials


def _dedupe(times: list[float], gap: float = 0.3) -> list[float]:
    """Collapse near-simultaneous events to one."""
    kept: list[float] = []
    for t in sorted(times):
        if not kept or t - kept[-1] > gap:
            kept.append(t)
    return kept


def _rewarded_licks(licks: list[float], rewards: list[float]) -> list[float]:
    """For each reward, the lick immediately preceding it (the lick that earned
    the water) is the HIT lick."""
    hit: list[float] = []
    for rt in rewards:
        candidates = [lt for lt in licks if rt - REWARD_LICK_WINDOW_S <= lt <= rt]
        hit.append(max(candidates) if candidates else rt)
    return hit


def short_name(subject: str) -> str:
    """'m90_AppetitiveTone_150' -> 'm90' for compact labels."""
    return subject.split("_", 1)[0]


# --- raster plotting ------------------------------------------------------
def plot_raster(subject: str, session: int, trials: list[dict], out_path: str) -> None:
    n = len(trials)
    fig_h = max(3.0, min(0.18 * n + 1.5, 30))
    fig, ax = plt.subplots(figsize=(10, fig_h))
    ax.axvline(0, color="#3a7ca5", lw=0.8, zorder=1)

    for idx, tr in enumerate(trials):
        y = n - idx  # trial 1 at top
        # per-trial tone band: width = how long the tone actually played
        ax.barh(y, tr["tone_dur"], left=0, height=0.95, align="center",
                color="#add8e6", alpha=0.55, zorder=0, edgecolor="none")
        rewarded = set(tr["rewarded_licks"])
        plain_licks = [t for t in tr["licks"] if t not in rewarded]
        if plain_licks:
            ax.scatter(plain_licks, [y] * len(plain_licks), marker="|",
                       s=120, linewidths=1.0, color="black", zorder=3)
        if tr["nose_pokes"]:
            ax.scatter(tr["nose_pokes"], [y] * len(tr["nose_pokes"]), marker="|",
                       s=120, linewidths=1.6, color="#2ca02c", zorder=2)
        if tr["rewarded_licks"]:
            ax.scatter(tr["rewarded_licks"], [y] * len(tr["rewarded_licks"]),
                       marker="|", s=200, linewidths=2.2, color="#f5c518", zorder=4)

    n_hits = sum(t["is_hit"] for t in trials)
    ax.set_xlabel("Trial time (s)  —  0 = tone onset")
    ax.set_ylabel("Trial #")
    ax.set_ylim(0.5, n + 0.5)
    ax.set_xlim(-2, max(TONE_FILE_LENGTH_S + 4, 12))
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.set_title(f"{subject}  ·  session {session}  ·  "
                 f"{n} trials, {n_hits} hits ({100 * n_hits / n:.0f}%)")
    handles = [
        mpatches.Patch(color="#add8e6", alpha=0.55, label="tone (while playing)"),
        plt.Line2D([], [], color="#2ca02c", marker="|", linestyle="None", label="nose poke"),
        plt.Line2D([], [], color="black", marker="|", linestyle="None", label="lick"),
        plt.Line2D([], [], color="#f5c518", marker="|", linestyle="None", label="rewarded lick (HIT)"),
    ]
    ax.legend(handles=handles, loc="upper right", fontsize=8, framealpha=0.9)
    fig.tight_layout()
    fig.savefig(out_path, dpi=130)
    plt.close(fig)


# --- learning-curve plotting ----------------------------------------------
def plot_curve_group(per_mouse: dict[str, list[dict]], out_path: str) -> None:
    fig, ax = plt.subplots(figsize=(10, 6.5))
    cmap = plt.get_cmap("tab10")
    max_day = max((r["training_day"] for rows in per_mouse.values() for r in rows),
                  default=1)

    for i, (subject, rows) in enumerate(sorted(per_mouse.items())):
        ax.plot([r["training_day"] for r in rows], [r["hit_rate"] for r in rows],
                "-o", color=cmap(i % 10), alpha=0.5, lw=1.2, ms=3.5,
                label=short_name(subject))

    xs, means, sems = [], [], []
    for day in range(1, max_day + 1):
        vals = [r["hit_rate"] for rows in per_mouse.values()
                for r in rows if r["training_day"] == day]
        if not vals:
            continue
        xs.append(day)
        means.append(float(np.mean(vals)))
        sems.append(float(np.std(vals, ddof=1) / np.sqrt(len(vals))) if len(vals) > 1 else 0.0)
    xs, means, sems = np.array(xs), np.array(means), np.array(sems)
    ax.plot(xs, means, "-", color="black", lw=2.6, zorder=5, label="group mean")
    ax.fill_between(xs, means - sems, means + sems, color="black", alpha=0.15, zorder=4)

    ax.axhline(50, color="grey", ls="--", lw=0.8, alpha=0.7)
    ax.set_xlabel("session #")
    ax.set_ylabel("Hit rate (%)")
    ax.set_title("AppetitveTaskReal — learning curve (hit rate across sessions)")
    ax.set_ylim(0, 100)
    ax.set_xlim(0.5, max_day + 0.5)
    ax.set_xticks(range(1, max_day + 1))
    ax.legend(loc="upper left", fontsize=8, ncol=2, framealpha=0.9)
    fig.tight_layout()
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


def plot_curve_grid(per_mouse: dict[str, list[dict]], out_path: str) -> None:
    subjects = sorted(per_mouse)
    ncol = 5
    nrow = (len(subjects) + ncol - 1) // ncol
    fig, axes = plt.subplots(nrow, ncol, figsize=(3 * ncol, 2.6 * nrow),
                             sharex=True, sharey=True)
    axes = np.array(axes).reshape(-1)
    max_day = max((r["training_day"] for rows in per_mouse.values() for r in rows),
                  default=1)

    for ax, subject in zip(axes, subjects):
        rows = per_mouse[subject]
        ax.plot([r["training_day"] for r in rows], [r["hit_rate"] for r in rows],
                "-o", color="#1f77b4", ms=3.5, lw=1.4)
        ax.axhline(50, color="grey", ls="--", lw=0.7, alpha=0.6)
        ax.set_title(short_name(subject), fontsize=10)
        ax.set_ylim(0, 100)
        ax.set_xlim(0.5, max_day + 0.5)
        ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    for ax in axes[len(subjects):]:
        ax.axis("off")

    fig.supxlabel("session #")
    fig.supylabel("Hit rate (%)")
    fig.suptitle("AppetitveTaskReal — learning curve per mouse", fontsize=12)
    fig.tight_layout(rect=(0.02, 0.02, 1, 0.97))
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


def write_session_csv(per_mouse: dict[str, list[dict]], out_path: str) -> None:
    cols = ["subject", "session", "training_day", "n_trials", "n_hits", "hit_rate",
            "total_pokes", "pokes_during_tone", "n_poked_licked", "n_poked_nolick"]
    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for subject in sorted(per_mouse):
            for row in per_mouse[subject]:
                w.writerow({c: row.get(c) for c in cols})


# --- poke metrics + bar grids ---------------------------------------------
def poke_metrics(events: list[dict], trials: list[dict]) -> dict:
    """Per-session nose-poke counts derived once from a session's events/trials.

    total_pokes        : every IR1 beam-break (rising edge) in the session.
    pokes_during_tone  : IR1 rising edges that land while the tone is playing.
    n_poked_licked     : trials where the mouse poked during the tone AND licked.
    n_poked_nolick     : trials where it poked during the tone but did NOT lick.
    """
    total = sum(1 for e in events if e["etype"] == ET_DIGITAL_IN
                and e["id"] == ID_NOSEPOKE and e["level"] == 1)
    during_tone = poked_licked = poked_nolick = 0
    for tr in trials:
        pokes_in_tone = [p for p in tr["nose_pokes"] if 0 <= p <= tr["tone_dur"]]
        licks_in_tone = [lk for lk in tr["licks"] if 0 <= lk <= tr["tone_dur"]]
        during_tone += len(pokes_in_tone)
        if pokes_in_tone:
            if licks_in_tone:
                poked_licked += 1
            else:
                poked_nolick += 1
    return {"total_pokes": total, "pokes_during_tone": during_tone,
            "n_poked_licked": poked_licked, "n_poked_nolick": poked_nolick}


def engagement_metrics(trials: list[dict]) -> dict:
    """Per-trial engagement (on-cue poke = poke while tone plays) for the shared
    participation analyses. Engaged trial -> reaction time = first on-cue poke."""
    engaged_seq, rt_list, n_hits_eng = [], [], 0
    for tr in trials:
        on_cue = [p for p in tr["nose_pokes"] if 0 <= p <= tr["tone_dur"]]
        engaged_seq.append(bool(on_cue))
        if on_cue:
            rt_list.append(min(on_cue))
            if tr["is_hit"]:
                n_hits_eng += 1
    n_engaged = sum(engaged_seq)
    return {
        "n_engaged": n_engaged,
        "engaged_seq": engaged_seq,
        "rt_list": rt_list,
        "engaged_rate": 100.0 * n_engaged / len(trials) if trials else 0.0,
        "acc_given_engaged": 100.0 * n_hits_eng / n_engaged if n_engaged else 0.0,
    }


def _bar_grid(per_mouse: dict[str, list[dict]], out_path: str, suptitle: str,
              ylabel: str, draw_panel, legend_handles=None) -> None:
    """Generic 2x5 grid: one panel per mouse, `draw_panel(ax, rows)` fills it."""
    subjects = sorted(per_mouse)
    ncol = 5
    nrow = (len(subjects) + ncol - 1) // ncol
    fig, axes = plt.subplots(nrow, ncol, figsize=(3 * ncol, 2.6 * nrow),
                             sharex=True, sharey=True)
    axes = np.array(axes).reshape(-1)
    max_day = max((r["training_day"] for rows in per_mouse.values() for r in rows),
                  default=1)
    for ax, subject in zip(axes, subjects):
        draw_panel(ax, per_mouse[subject])
        ax.set_title(short_name(subject), fontsize=10)
        ax.set_xlim(0.5, max_day + 0.5)
        ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    for ax in axes[len(subjects):]:
        ax.axis("off")

    fig.supxlabel("session #")
    fig.supylabel(ylabel)
    fig.suptitle(suptitle, fontsize=12)
    if legend_handles:
        fig.legend(handles=legend_handles, loc="upper right", fontsize=9,
                   framealpha=0.9)
    fig.tight_layout(rect=(0.02, 0.02, 1, 0.96))
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


def plot_poke_single(per_mouse: dict[str, list[dict]], key: str, color: str,
                     suptitle: str, ylabel: str, out_path: str) -> None:
    def draw(ax, rows):
        ax.bar([r["training_day"] for r in rows], [r[key] for r in rows],
               color=color, width=0.8)
    _bar_grid(per_mouse, out_path, suptitle, ylabel, draw)


def plot_poke_compare(per_mouse: dict[str, list[dict]], out_path: str) -> None:
    c_lick, c_nolick = "#2ca02c", "#d62728"
    w = 0.4

    def draw(ax, rows):
        days = np.array([r["training_day"] for r in rows], dtype=float)
        ax.bar(days - w / 2, [r["n_poked_licked"] for r in rows], width=w, color=c_lick)
        ax.bar(days + w / 2, [r["n_poked_nolick"] for r in rows], width=w, color=c_nolick)

    handles = [
        mpatches.Patch(color=c_lick, label="poked & licked"),
        mpatches.Patch(color=c_nolick, label="poked, no lick"),
    ]
    _bar_grid(per_mouse, out_path,
              "Poked-during-tone outcome per session (trial counts)",
              "Trials", draw, legend_handles=handles)


def plot_stacked_grid(per_mouse: dict[str, list[dict]], out_path: str, suptitle: str,
                      frac_fn, labels: list[str], colors: list[str]) -> None:
    """One stacked 0-100% bar per session: frac_fn(row) -> tuple of segment %."""
    def draw(ax, rows):
        days = [r["training_day"] for r in rows]
        seg = np.array([frac_fn(r) for r in rows])  # shape (n_sessions, n_segments)
        bottom = np.zeros(len(rows))
        for i, color in enumerate(colors):
            ax.bar(days, seg[:, i], bottom=bottom, color=color, width=0.8)
            bottom += seg[:, i]
        ax.set_ylim(0, 100)

    handles = [mpatches.Patch(color=c, label=l) for l, c in zip(labels, colors)]
    _bar_grid(per_mouse, out_path, suptitle, "% of nose pokes", draw,
              legend_handles=handles)


def poke_breakdown_fracs(row: dict) -> tuple[float, float, float]:
    """Three-way split of all session nose pokes (sums to 100%):
    (% rewarded on-cue, % on-cue but not rewarded, % off-cue during ITI)."""
    total = row["total_pokes"]
    if not total:
        return 0.0, 0.0, 0.0
    rewarded = row["n_hits"]
    on_cue_miss = max(0, row["pokes_during_tone"] - rewarded)
    off_cue = max(0, total - row["pokes_during_tone"])
    return (100.0 * rewarded / total, 100.0 * on_cue_miss / total,
            100.0 * off_cue / total)


def ontone_reward_fracs(row: dict) -> tuple[float, float]:
    """Among on-cue (during-tone) nose pokes only: (% rewarded, % not rewarded).
    Denominator is the during-tone pokes — a learning-sensitive measure."""
    on_cue = row["pokes_during_tone"]
    if not on_cue:
        return 0.0, 0.0
    rewarded = min(100.0, 100.0 * row["n_hits"] / on_cue)
    return rewarded, 100.0 - rewarded


# --- driver ---------------------------------------------------------------
def select_sessions(by_session: dict[int, list[dict]], only_session: int | None,
                    max_sessions: int | None) -> list[int]:
    sessions = sorted(by_session)
    if only_session is not None:
        return [s for s in sessions if s == only_session]
    if max_sessions is not None:
        return sessions[:max_sessions]
    return sessions


def run(args: argparse.Namespace) -> int:
    do_rasters = args.analysis in ("all", "rasters")
    do_curve = args.analysis in ("all", "curve")
    do_pokes = args.analysis in ("all", "pokes")
    do_participation = args.analysis in ("all", "participation")

    subjects = [args.subject] if args.subject else discover_subjects()
    if not subjects:
        print("No matching subjects found.", file=sys.stderr)
        return 1
    print(f"Subjects ({len(subjects)}): {', '.join(short_name(s) for s in subjects)}")

    per_mouse: dict[str, list[dict]] = {}
    n_rasters = 0
    for subject in subjects:
        print(f"{short_name(subject)} ...")
        by_session = group_by_session(fetch_events(subject))  # one fetch, both analyses
        # segment every session once and reuse for rasters + hit rates
        trials_by_session = {s: segment_trials(evs) for s, evs in by_session.items()}

        if do_rasters:
            out_dir = os.path.join(OUT_ROOT, subject)
            os.makedirs(out_dir, exist_ok=True)
            for s in select_sessions(by_session, args.session, args.max_sessions):
                trials = trials_by_session[s]
                if not trials:
                    continue
                out_path = os.path.join(out_dir, f"session_{s:02d}.png")
                plot_raster(subject, s, trials, out_path)
                n_rasters += 1

        if do_curve or do_pokes or do_participation:
            rows = []
            for s in sorted(trials_by_session):
                trials = trials_by_session[s]
                if not (args.min_trials <= len(trials) <= MAX_TRIALS):
                    continue
                n_hits = sum(t["is_hit"] for t in trials)
                row = {"subject": subject, "session": s,
                       "n_trials": len(trials), "n_hits": n_hits,
                       "hit_rate": 100.0 * n_hits / len(trials)}
                row.update(poke_metrics(by_session[s], trials))
                row.update(engagement_metrics(trials))
                rows.append(row)
            for day, row in enumerate(rows, start=1):
                row["training_day"] = day
                row["session_num"] = day  # shared participation key
            per_mouse[subject] = rows
            if rows:
                rates = ", ".join(f"{r['hit_rate']:.0f}" for r in rows)
                print(f"  {len(rows)} sessions  hit% = [{rates}]")
            else:
                print("  (no qualifying sessions)")

    os.makedirs(OUT_ROOT, exist_ok=True)
    if do_rasters:
        print(f"\nRasters: {n_rasters} written under '{OUT_ROOT}/<subject>/'.")
    if (do_curve or do_pokes) and per_mouse:
        csv_path = os.path.join(OUT_ROOT, "session_metrics.csv")
        write_session_csv(per_mouse, csv_path)
        print(f"Session metrics table: {csv_path}")
    if do_curve and per_mouse:
        group_path = os.path.join(OUT_ROOT, "learning_curve_group.png")
        grid_path = os.path.join(OUT_ROOT, "learning_curve_grid.png")
        plot_curve_group(per_mouse, group_path)
        plot_curve_grid(per_mouse, grid_path)
        print(f"Learning curve:\n  {group_path}\n  {grid_path}")
    if do_pokes and per_mouse:
        total_path = os.path.join(OUT_ROOT, "pokes_total_per_session.png")
        tone_path = os.path.join(OUT_ROOT, "pokes_during_tone_per_session.png")
        cmp_path = os.path.join(OUT_ROOT, "pokes_lick_vs_nolick_per_session.png")
        plot_poke_single(per_mouse, "total_pokes", "#1f77b4",
                         "Total nose pokes per session", "Nose pokes", total_path)
        plot_poke_single(per_mouse, "pokes_during_tone", "#3a7ca5",
                         "Nose pokes during the tone cue, per session",
                         "Nose pokes (during tone)", tone_path)
        plot_poke_compare(per_mouse, cmp_path)
        breakdown_path = os.path.join(OUT_ROOT, "pokes_breakdown_per_session.png")
        ontone_path = os.path.join(OUT_ROOT, "pokes_ontone_reward_ratio_per_session.png")
        plot_stacked_grid(per_mouse, breakdown_path,
                          "Nose-poke breakdown per session (% of all pokes)",
                          poke_breakdown_fracs,
                          ["rewarded (on-cue)", "on-cue, not rewarded", "off-cue (ITI)"],
                          ["#2ca02c", "#ff7f0e", "#999999"])
        plot_stacked_grid(per_mouse, ontone_path,
                          "On-cue nose pokes: rewarded vs not rewarded, per session (%)",
                          ontone_reward_fracs,
                          ["rewarded", "not rewarded"],
                          ["#2ca02c", "#d62728"])
        print(f"Poke bars:\n  {total_path}\n  {tone_path}\n  {cmp_path}\n"
              f"  {breakdown_path}\n  {ontone_path}")
    if do_participation and per_mouse:
        paths = participation.plot_all(per_mouse, OUT_ROOT, "appetitive_",
                                       "Appetitive tone task")
        print("Participation figures:\n  " + "\n  ".join(paths))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--analysis", choices=["all", "rasters", "curve", "pokes", "participation"],
                    default="all", help="which analysis to run (default: all)")
    ap.add_argument("--subject", help="single ES subject (default: all 10 mice)")
    ap.add_argument("--session", type=int, help="single session number (rasters)")
    ap.add_argument("--max-sessions", type=int,
                    help="cap sessions per mouse for rasters (e.g. 1 for a quick look)")
    ap.add_argument("--min-trials", type=int, default=MIN_TRIALS,
                    help=f"drop sessions with fewer trials from the curve (default {MIN_TRIALS})")
    return run(ap.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
