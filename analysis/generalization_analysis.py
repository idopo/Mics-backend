#!/usr/bin/env python3
"""Generalization-task analysis for the two good learners (m97, m102).

After learning the tone-cued appetitive task, these mice were tested on the
"Generalization" task (task_type=Generalization, "GenLight") where the cue is a
LIGHT (LED2) instead of a tone. This asks whether they generalized: do they
still nose-poke on-cue and earn reward when the cue modality changes?

The Generalization FDA matches AppetitveTaskReal except the cue is LED2:
  - trial onset : state_transition "trial_onset"
  - cue (t=0)   : gpio.Digital_Out id=LED2, func=set, level=1  (LED on)
                  the LED turns OFF (level=0) early on a hit, else after ~8 s
  - nose poke   : gpio.Digital_In id=IR1, level=1 (rising edge)
  - lick        : gpio.Digital_In id=TOUCH_INT
  - reward/HIT  : gpio.Solenoid_mics id=open, func=store_series

Engagement is scored exactly as requested: a trial is "engaged" only if the
mouse nose-poked WHILE LED2 was on (t in [0, LED-on duration]). The hits/miss
figure is then computed over engaged trials only (miss = engaged but no reward).

Each mouse's generalization sessions span two ES subject strings
(<id>_GenLight_400 then <id>_GenLight_400_2, a continuation); they are merged
and ordered chronologically into session # 1..N.

Outputs (under MICS_GEN_OUT, default 'generalization_figs/'):
    generalization_learning_curve.png     hit + engagement rate across sessions
    generalization_engaged_hits_miss.png  per mouse: engaged trials split hit/miss
    rasters/<mouse>/gen_session_N.png      per-session raster (pokes/licks/reward)
    generalization_metrics.csv             tidy per-session table

Usage:
    python3 generalization_analysis.py
"""
from __future__ import annotations

import csv
import os
import re
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

from config import ES_URL, ES_INDEX  # ES host/index, env-overridable (see config.py)

TASK_TYPE = "Generalization"
PILOT = os.environ.get("MICS_PILOT", "RecordingBox")
OUT_ROOT = os.environ.get("MICS_GEN_OUT", "generalization_figs")

# Each mouse's generalization sessions live in two ES subject strings
# (<id>_GenLight_400 + "_2" continuation); discovered dynamically below.
SUBJECT_RE = re.compile(r"^m(\d+)_GenLight_400(_2)?$")
# Rasters are only drawn for these highlighted learners (a 10-mouse raster grid
# is unreadable); the aggregate figures cover every discovered mouse.
RASTER_MICE = ["m97", "m102"]

ET_STATE = "state_transition"
ET_DIGITAL_IN = "gpio.Digital_In"
ET_DIGITAL_OUT = "gpio.Digital_Out"
ET_SOLENOID = "gpio.Solenoid_mics"
RELEVANT_EVENT_TYPES = [ET_STATE, ET_DIGITAL_IN, ET_DIGITAL_OUT, ET_SOLENOID]

ID_NOSEPOKE = "IR1"
ID_LICK = "TOUCH_INT"
ID_LED = "LED2"
ID_REWARD = "open"

LED_WINDOW_S = 8.0  # fallback cue length when no LED-off is seen (miss trials)
REWARD_LICK_WINDOW_S = 0.5
# A valid "session" has a trial count around the nominal 60; sessions outside
# [MIN_TRIALS, MAX_TRIALS] (aborted partials or merged double-sessions) are
# dropped before re-indexing. Shared band with appetitive_analysis (env-tunable).
MIN_TRIALS = int(os.environ.get("MICS_MIN_TRIALS", "50"))
MAX_TRIALS = int(os.environ.get("MICS_MAX_TRIALS", "72"))
MAX_SESSION = 4  # only the first 4 generalization sessions are common to all mice


def session_len_ok(n_trials: int) -> bool:
    """True if a session's trial count is within the valid ~60-trial band."""
    return MIN_TRIALS <= n_trials <= MAX_TRIALS


def _iso_to_epoch(ts: str) -> float:
    return datetime.fromisoformat(ts).timestamp()


def fetch_events(subject: str, page: int = 5000) -> list[dict]:
    """Scroll the relevant events for one ES subject, sorted by (session, time)."""
    query = {"bool": {"must": [
        {"term": {"task_type.keyword": TASK_TYPE}},
        {"term": {"pilot.keyword": PILOT}},
        {"term": {"subject.keyword": subject}},
        {"terms": {"event.event_type.keyword": RELEVANT_EVENT_TYPES}},
    ]}}
    src = ["timestamp", "session", "event.event_type", "event.event_data.id",
           "event.event_data.current_state", "event.event_data.func_name", "event.level"]
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
            for h in hits:
                s = h["_source"]
                e = s.get("event", {})
                ed = e.get("event_data", {})
                out.append({
                    "session": s.get("session"),
                    "epoch": _iso_to_epoch(s["timestamp"]),
                    "etype": e.get("event_type"),
                    "id": ed.get("id"),
                    "state": ed.get("current_state"),
                    "func": ed.get("func_name"),
                    "level": e.get("level"),
                })
            r = requests.post(f"{ES_URL}/_search/scroll",
                              json={"scroll": "2m", "scroll_id": scroll_id}, timeout=120)
            r.raise_for_status()
            data = r.json()
            scroll_id = data.get("_scroll_id")
    finally:
        if scroll_id:
            requests.delete(f"{ES_URL}/_search/scroll",
                            json={"scroll_id": [scroll_id]}, timeout=30)
    return out


def discover_mice() -> dict[str, list[str]]:
    """Map mouse id -> its GenLight subject strings, ordered (main then _2)."""
    body = {"size": 0, "query": {"bool": {"must": [
        {"term": {"task_type.keyword": TASK_TYPE}},
        {"term": {"pilot.keyword": PILOT}}]}},
        "aggs": {"subjects": {"terms": {"field": "subject.keyword", "size": 200}}}}
    r = requests.post(f"{ES_URL}/{ES_INDEX}/_search", json=body, timeout=60)
    r.raise_for_status()
    mice: dict[int, list[str]] = {}
    for b in r.json()["aggregations"]["subjects"]["buckets"]:
        m = SUBJECT_RE.match(b["key"])
        if m:
            mice.setdefault(int(m.group(1)), []).append(b["key"])
    return {f"m{n}": sorted(mice[n]) for n in sorted(mice)}


def _dedupe(times: list[float], gap: float = 0.3) -> list[float]:
    kept: list[float] = []
    for t in sorted(times):
        if not kept or t - kept[-1] > gap:
            kept.append(t)
    return kept


def _rewarded_licks(licks: list[float], rewards: list[float]) -> list[float]:
    hit: list[float] = []
    for rt in rewards:
        candidates = [lt for lt in licks if rt - REWARD_LICK_WINDOW_S <= lt <= rt]
        hit.append(max(candidates) if candidates else rt)
    return hit


def segment_trials(events: list[dict]) -> list[dict]:
    """Split one session's events into trials aligned to LED2 onset (t=0)."""
    events = sorted(events, key=lambda e: e["epoch"])
    onsets = [i for i, e in enumerate(events)
              if e["etype"] == ET_STATE and e["state"] == "trial_onset"]
    bounds = onsets + [len(events)]
    trials: list[dict] = []
    for k in range(len(onsets)):
        window = events[bounds[k]:bounds[k + 1]]
        led_on = next((e for e in window if e["etype"] == ET_DIGITAL_OUT
                       and e["id"] == ID_LED and e["level"] == 1), None)
        if led_on is None:
            stim = next((e for e in window if e["etype"] == ET_STATE
                         and e["state"] == "stimulus"), None)
            t0 = stim["epoch"] if stim else window[0]["epoch"]
        else:
            t0 = led_on["epoch"]
        led_off = next((e for e in window if e["etype"] == ET_DIGITAL_OUT
                        and e["id"] == ID_LED and e["level"] == 0 and e["epoch"] > t0), None)
        led_dur = (led_off["epoch"] - t0) if led_off else LED_WINDOW_S

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
                rewards.append(e["epoch"] - t0)
        rewards = _dedupe(rewards)
        engaged = any(0 <= p <= led_dur for p in nose_pokes)  # poke while LED2 on
        # trial window end (= next trial onset) rel. to LED2 onset; used to place
        # events within the post-cue ITI. Last trial has no next onset -> last event.
        win_end_epoch = (events[onsets[k + 1]]["epoch"] if k + 1 < len(onsets)
                         else (window[-1]["epoch"] if window else t0))
        # false alarm = a nose poke during the ITI countdown; each one resets the
        # ITI timer (punishment). Logged as the state_ITI_nose_poke transition.
        false_alarms = sum(1 for e in window
                           if e["etype"] == ET_STATE and e["state"] == "state_ITI_nose_poke")
        trials.append({
            "led_dur": led_dur,
            "iti_end": win_end_epoch - t0,
            "n_false_alarms": false_alarms,
            "punished": false_alarms > 0,
            "nose_pokes": nose_pokes,
            "nose_pokes_out": nose_pokes_out,
            "licks": licks,
            "rewards": rewards,  # deduped water-delivery times (rel. to LED2 onset)
            "rewarded_licks": _rewarded_licks(licks, rewards),
            "engaged": engaged,
            "is_hit": bool(rewards),
        })
    return trials


def collect_mouse(subjects: list[str]) -> list[dict]:
    """Per-session rows for one mouse, merged across subject strings, ordered
    chronologically into session # 1..N. Each row keeps its trial list."""
    rows: list[dict] = []
    for subject in subjects:
        events = fetch_events(subject)
        by_session: dict[int, list[dict]] = {}
        for e in events:
            by_session.setdefault(e["session"], []).append(e)
        for sess, evs in by_session.items():
            trials = segment_trials(evs)
            if not session_len_ok(len(trials)):
                continue
            rows.append({"subject": subject, "raw_session": sess,
                         "start": min(e["epoch"] for e in evs), "trials": trials})
    rows.sort(key=lambda r: r["start"])
    for i, r in enumerate(rows, start=1):
        trials = r["trials"]
        engaged = [t for t in trials if t["engaged"]]
        hits_e = sum(t["is_hit"] for t in engaged)
        rt_list = [min(p for p in t["nose_pokes"] if 0 <= p <= t["led_dur"])
                   for t in engaged]
        r.update({
            "session_num": i,
            "n_trials": len(trials),
            "n_engaged": len(engaged),
            "hits": hits_e,
            "miss": len(engaged) - hits_e,
            "hit_rate": 100.0 * sum(t["is_hit"] for t in trials) / len(trials),
            "engaged_rate": 100.0 * len(engaged) / len(trials),
            "acc_given_engaged": 100.0 * hits_e / len(engaged) if engaged else 0.0,
            "engaged_seq": [t["engaged"] for t in trials],
            "rt_list": rt_list,
        })
    return [r for r in rows if r["session_num"] <= MAX_SESSION]


# --- plots ----------------------------------------------------------------
def _sorted_mice(per_mouse: dict[str, list[dict]]) -> list[str]:
    return sorted(per_mouse, key=lambda m: int(m[1:]))


def plot_learning_curve(per_mouse: dict[str, list[dict]], out_path: str) -> None:
    """Hit rate (all trials) across sessions: one line per mouse + group mean."""
    fig, ax = plt.subplots(figsize=(9, 6))
    cmap = plt.get_cmap("tab10")
    mice = _sorted_mice(per_mouse)
    max_s = max((r["session_num"] for rows in per_mouse.values() for r in rows), default=1)
    for i, mouse in enumerate(mice):
        rows = per_mouse[mouse]
        ax.plot([r["session_num"] for r in rows], [r["hit_rate"] for r in rows],
                "-o", color=cmap(i % 10), lw=1.5, ms=4, alpha=0.7, label=mouse)

    xs, means, sems = [], [], []
    for day in range(1, max_s + 1):
        vals = [r["hit_rate"] for rows in per_mouse.values()
                for r in rows if r["session_num"] == day]
        if not vals:
            continue
        xs.append(day)
        means.append(float(np.mean(vals)))
        sems.append(float(np.std(vals, ddof=1) / np.sqrt(len(vals))) if len(vals) > 1 else 0.0)
    xs, means, sems = np.array(xs), np.array(means), np.array(sems)
    ax.plot(xs, means, "-", color="black", lw=2.8, zorder=5, label="group mean")
    ax.fill_between(xs, means - sems, means + sems, color="black", alpha=0.15, zorder=4)

    ax.axhline(50, color="grey", ls=":", lw=0.8, alpha=0.7)
    ax.set_xlabel("session #")
    ax.set_ylabel("hit rate (% of all trials)")
    ax.set_title("Generalization (light cue) — learning curve, all mice")
    ax.set_ylim(0, 100)
    ax.set_xlim(0.5, max_s + 0.5)
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.legend(fontsize=8, ncol=2, framealpha=0.9)
    fig.tight_layout()
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


def plot_engaged_hits_miss(per_mouse: dict[str, list[dict]], out_path: str) -> None:
    """Grid (one panel per mouse): per-session engaged trials split hit vs miss."""
    mice = _sorted_mice(per_mouse)
    ncol = 5
    nrow = (len(mice) + ncol - 1) // ncol
    fig, axes = plt.subplots(nrow, ncol, figsize=(3 * ncol, 2.6 * nrow),
                             sharex=True, sharey=True)
    axes = np.array(axes).reshape(-1)
    max_s = max((r["session_num"] for rows in per_mouse.values() for r in rows), default=1)
    for ax, mouse in zip(axes, mice):
        rows = per_mouse[mouse]
        x = np.array([r["session_num"] for r in rows], dtype=float)
        hits = [r["hits"] for r in rows]
        miss = [r["miss"] for r in rows]
        ax.bar(x, hits, width=0.7, color="#2ca02c")
        ax.bar(x, miss, width=0.7, bottom=hits, color="#d62728")
        ax.set_title(mouse, fontsize=10)
        ax.set_xlim(0.5, max_s + 0.5)
        ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    for ax in axes[len(mice):]:
        ax.axis("off")

    handles = [mpatches.Patch(color="#2ca02c", label="hit"),
               mpatches.Patch(color="#d62728", label="miss")]
    fig.legend(handles=handles, loc="upper right", fontsize=9, framealpha=0.9)
    fig.supxlabel("session #")
    fig.supylabel("engaged trials (poked during LED2 on)")
    fig.suptitle("Generalization (light cue) — hits vs misses among engaged trials", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


def _draw_trials(ax, trials: list[dict], scale: float = 1.0) -> None:
    """Render one session's trials into `ax` (trial 1 at top). `scale` shrinks
    the event ticks for use in small grid panels."""
    n = len(trials)
    ax.axvline(0, color="#3a7ca5", lw=0.8, zorder=1)
    for idx, tr in enumerate(trials):
        y = n - idx  # trial 1 at top
        ax.barh(y, tr["led_dur"], left=0, height=0.95, align="center",
                color="#add8e6", alpha=0.55, zorder=0, edgecolor="none")
        rewarded = set(tr["rewarded_licks"])
        plain = [t for t in tr["licks"] if t not in rewarded]
        if plain:
            ax.scatter(plain, [y] * len(plain), marker="|", s=120 * scale,
                       linewidths=1.0 * scale, color="black", zorder=3)
        if tr["nose_pokes"]:
            ax.scatter(tr["nose_pokes"], [y] * len(tr["nose_pokes"]), marker="|",
                       s=120 * scale, linewidths=1.6 * scale, color="#2ca02c", zorder=2)
        if tr["rewarded_licks"]:
            ax.scatter(tr["rewarded_licks"], [y] * len(tr["rewarded_licks"]),
                       marker="|", s=200 * scale, linewidths=2.2 * scale,
                       color="#f5c518", zorder=4)
    ax.set_ylim(0.5, n + 0.5)
    ax.set_xlim(-2, max(LED_WINDOW_S + 4, 12))
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))


def _raster_legend_handles():
    return [
        mpatches.Patch(color="#add8e6", alpha=0.55, label="LED2 on (cue)"),
        plt.Line2D([], [], color="#2ca02c", marker="|", linestyle="None", label="nose poke"),
        plt.Line2D([], [], color="black", marker="|", linestyle="None", label="lick"),
        plt.Line2D([], [], color="#f5c518", marker="|", linestyle="None", label="rewarded lick (HIT)"),
    ]


def plot_raster(mouse: str, row: dict, out_path: str) -> None:
    n = len(row["trials"])
    fig, ax = plt.subplots(figsize=(10, max(3.0, min(0.18 * n + 1.5, 30))))
    _draw_trials(ax, row["trials"])
    ax.set_xlabel("Trial time (s)  —  0 = LED2 (cue) onset")
    ax.set_ylabel("Trial #")
    ax.set_title(f"{mouse} ({row['subject']} s{row['raw_session']})  ·  gen session "
                 f"{row['session_num']}  ·  {n} trials, {row['n_engaged']} engaged, "
                 f"{row['hits']} hits")
    ax.legend(handles=_raster_legend_handles(), loc="upper right", fontsize=8, framealpha=0.9)
    fig.tight_layout()
    fig.savefig(out_path, dpi=130)
    plt.close(fig)


def plot_combined_rasters(per_mouse: dict[str, list[dict]], out_path: str) -> None:
    """One figure: rows = sessions, columns = mice (m97 left, m102 right)."""
    mice = list(per_mouse)
    nrows = max(len(rows) for rows in per_mouse.values())
    ncols = len(mice)
    fig, axes = plt.subplots(nrows, ncols, figsize=(7 * ncols, 3.0 * nrows),
                             sharex=True, squeeze=False)
    for c, mouse in enumerate(mice):
        rows = per_mouse[mouse]
        for r in range(nrows):
            ax = axes[r][c]
            if r >= len(rows):
                ax.axis("off")
                continue
            row = rows[r]
            _draw_trials(ax, row["trials"], scale=0.45)
            ax.set_title(f"{mouse} · gen s{row['session_num']} · "
                         f"{row['hits']}/{row['n_engaged']} engaged hits "
                         f"({row['n_trials']} trials)", fontsize=9)
            ax.set_ylabel("trial #")
            if r == nrows - 1:
                ax.set_xlabel("Trial time (s)  —  0 = LED2 onset")
    fig.legend(handles=_raster_legend_handles(), loc="upper center", ncol=4,
               fontsize=9, framealpha=0.9, bbox_to_anchor=(0.5, 0.995))
    fig.suptitle("Generalization rasters — all sessions (m97 left, m102 right)",
                 fontsize=13, y=0.965)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


def write_csv(per_mouse: dict[str, list[dict]], out_path: str) -> None:
    cols = ["mouse", "session_num", "subject", "raw_session", "n_trials",
            "n_engaged", "hits", "miss", "hit_rate", "engaged_rate", "acc_given_engaged"]
    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for mouse, rows in per_mouse.items():
            for r in rows:
                w.writerow({"mouse": mouse, **{c: r.get(c) for c in cols if c != "mouse"}})


def main() -> int:
    mice = discover_mice()
    print(f"Mice ({len(mice)}): {', '.join(mice)}")
    per_mouse: dict[str, list[dict]] = {}
    for mouse, subjects in mice.items():
        rows = collect_mouse(subjects)
        per_mouse[mouse] = rows
        print(f"{mouse}: {len(rows)} sessions")
        for r in rows:
            print(f"  s{r['session_num']} ({r['subject']} s{r['raw_session']}): "
                  f"{r['n_trials']} trials | engaged {r['n_engaged']} | "
                  f"hits {r['hits']} / miss {r['miss']} "
                  f"(accuracy when engaged {r['acc_given_engaged']:.0f}%)")

    os.makedirs(OUT_ROOT, exist_ok=True)
    plot_learning_curve(per_mouse, os.path.join(OUT_ROOT, "generalization_learning_curve.png"))
    plot_engaged_hits_miss(per_mouse, os.path.join(OUT_ROOT, "generalization_engaged_hits_miss.png"))
    write_csv(per_mouse, os.path.join(OUT_ROOT, "generalization_metrics.csv"))
    participation.plot_all(per_mouse, OUT_ROOT, "generalization_", "Generalization (light cue)")

    # rasters only for the highlighted learners (per-mouse files + combined grid)
    raster_mice = {m: per_mouse[m] for m in RASTER_MICE if m in per_mouse}
    n_rasters = 0
    for mouse, rows in raster_mice.items():
        rdir = os.path.join(OUT_ROOT, "rasters", mouse)
        os.makedirs(rdir, exist_ok=True)
        for r in rows:
            plot_raster(mouse, r, os.path.join(rdir, f"gen_session_{r['session_num']}.png"))
            n_rasters += 1
    if raster_mice:
        combined_path = os.path.join(OUT_ROOT, "generalization_all_rasters.png")
        plot_combined_rasters(raster_mice, combined_path)
        print(f"\nRasters: {n_rasters} ({', '.join(raster_mice)}) + combined grid {combined_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
