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
from datetime import datetime

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.ticker import MaxNLocator
import numpy as np
import requests

ES_URL = os.environ.get("ES_URL", "http://localhost:9200")
ES_INDEX = os.environ.get("ES_INDEX", "restored-event_log_v2")
TASK_TYPE = "Generalization"
PILOT = os.environ.get("MICS_PILOT", "RecordingBox")
OUT_ROOT = os.environ.get("MICS_GEN_OUT", "generalization_figs")

# Each mouse -> the ES subject strings holding its generalization sessions
# (main run + "_2" continuation), merged in chronological order.
MICE = {
    "m97": ["m97_GenLight_400", "m97_GenLight_400_2"],
    "m102": ["m102_GenLight_400", "m102_GenLight_400_2"],
}

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

        nose_pokes, licks, rewards = [], [], []
        for e in window:
            if e["etype"] == ET_DIGITAL_IN and e["id"] == ID_NOSEPOKE and e["level"] == 1:
                nose_pokes.append(e["epoch"] - t0)
            elif e["etype"] == ET_DIGITAL_IN and e["id"] == ID_LICK:
                licks.append(e["epoch"] - t0)
            elif (e["etype"] == ET_SOLENOID and e["id"] == ID_REWARD
                  and e["func"] == "store_series"):
                rewards.append(e["epoch"] - t0)
        rewards = _dedupe(rewards)
        engaged = any(0 <= p <= led_dur for p in nose_pokes)  # poke while LED2 on
        trials.append({
            "led_dur": led_dur,
            "nose_pokes": nose_pokes,
            "licks": licks,
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
            if not trials:
                continue
            rows.append({"subject": subject, "raw_session": sess,
                         "start": min(e["epoch"] for e in evs), "trials": trials})
    rows.sort(key=lambda r: r["start"])
    for i, r in enumerate(rows, start=1):
        trials = r["trials"]
        engaged = [t for t in trials if t["engaged"]]
        hits_e = sum(t["is_hit"] for t in engaged)
        r.update({
            "session_num": i,
            "n_trials": len(trials),
            "n_engaged": len(engaged),
            "hits": hits_e,
            "miss": len(engaged) - hits_e,
            "hit_rate": 100.0 * sum(t["is_hit"] for t in trials) / len(trials),
            "engaged_rate": 100.0 * len(engaged) / len(trials),
            "acc_given_engaged": 100.0 * hits_e / len(engaged) if engaged else 0.0,
        })
    return rows


# --- plots ----------------------------------------------------------------
def plot_learning_curve(per_mouse: dict[str, list[dict]], out_path: str) -> None:
    fig, ax = plt.subplots(figsize=(8, 5.5))
    colors = {"m97": "#1f77b4", "m102": "#d62728"}
    max_s = max((r["session_num"] for rows in per_mouse.values() for r in rows), default=1)
    for mouse, rows in per_mouse.items():
        xs = [r["session_num"] for r in rows]
        ax.plot(xs, [r["hit_rate"] for r in rows], "-o", color=colors.get(mouse),
                lw=2.2, ms=6, label=f"{mouse} — hit rate (all trials)")
        ax.plot(xs, [r["engaged_rate"] for r in rows], "--s", color=colors.get(mouse),
                lw=1.4, ms=4, alpha=0.6, label=f"{mouse} — engaged (poked on-cue)")
    ax.axhline(50, color="grey", ls=":", lw=0.8, alpha=0.7)
    ax.set_xlabel("session #")
    ax.set_ylabel("% of trials")
    ax.set_title("Generalization (light cue) — learning curve")
    ax.set_ylim(0, 100)
    ax.set_xlim(0.5, max_s + 0.5)
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.legend(fontsize=8, framealpha=0.9)
    fig.tight_layout()
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


def plot_engaged_hits_miss(per_mouse: dict[str, list[dict]], out_path: str) -> None:
    mice = list(per_mouse)
    fig, axes = plt.subplots(1, len(mice), figsize=(5.2 * len(mice), 4.4),
                             sharey=True, squeeze=False)
    axes = axes[0]
    for ax, mouse in zip(axes, mice):
        rows = per_mouse[mouse]
        x = np.array([r["session_num"] for r in rows], dtype=float)
        hits = [r["hits"] for r in rows]
        miss = [r["miss"] for r in rows]
        ax.bar(x, hits, width=0.6, color="#2ca02c", label="hit")
        ax.bar(x, miss, width=0.6, bottom=hits, color="#d62728", label="miss")
        ax.set_title(mouse, fontsize=11)
        ax.set_xlabel("session #")
        ax.set_xticks(x)
        ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    axes[0].set_ylabel("engaged trials (poked during LED2 on)")
    axes[0].legend(fontsize=8, framealpha=0.9)
    fig.suptitle("Generalization (light cue) — hits vs misses among engaged trials", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


def plot_raster(mouse: str, row: dict, out_path: str) -> None:
    trials = row["trials"]
    n = len(trials)
    fig_h = max(3.0, min(0.18 * n + 1.5, 30))
    fig, ax = plt.subplots(figsize=(10, fig_h))
    ax.axvline(0, color="#3a7ca5", lw=0.8, zorder=1)
    for idx, tr in enumerate(trials):
        y = n - idx  # trial 1 at top
        ax.barh(y, tr["led_dur"], left=0, height=0.95, align="center",
                color="#add8e6", alpha=0.55, zorder=0, edgecolor="none")
        rewarded = set(tr["rewarded_licks"])
        plain = [t for t in tr["licks"] if t not in rewarded]
        if plain:
            ax.scatter(plain, [y] * len(plain), marker="|", s=120, linewidths=1.0,
                       color="black", zorder=3)
        if tr["nose_pokes"]:
            ax.scatter(tr["nose_pokes"], [y] * len(tr["nose_pokes"]), marker="|",
                       s=120, linewidths=1.6, color="#2ca02c", zorder=2)
        if tr["rewarded_licks"]:
            ax.scatter(tr["rewarded_licks"], [y] * len(tr["rewarded_licks"]),
                       marker="|", s=200, linewidths=2.2, color="#f5c518", zorder=4)
    ax.set_xlabel("Trial time (s)  —  0 = LED2 (cue) onset")
    ax.set_ylabel("Trial #")
    ax.set_ylim(0.5, n + 0.5)
    ax.set_xlim(-2, max(LED_WINDOW_S + 4, 12))
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.set_title(f"{mouse} ({row['subject']} s{row['raw_session']})  ·  gen session "
                 f"{row['session_num']}  ·  {n} trials, {row['n_engaged']} engaged, "
                 f"{row['hits']} hits")
    handles = [
        mpatches.Patch(color="#add8e6", alpha=0.55, label="LED2 on (cue)"),
        plt.Line2D([], [], color="#2ca02c", marker="|", linestyle="None", label="nose poke"),
        plt.Line2D([], [], color="black", marker="|", linestyle="None", label="lick"),
        plt.Line2D([], [], color="#f5c518", marker="|", linestyle="None", label="rewarded lick (HIT)"),
    ]
    ax.legend(handles=handles, loc="upper right", fontsize=8, framealpha=0.9)
    fig.tight_layout()
    fig.savefig(out_path, dpi=130)
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
    per_mouse: dict[str, list[dict]] = {}
    for mouse, subjects in MICE.items():
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

    n_rasters = 0
    for mouse, rows in per_mouse.items():
        rdir = os.path.join(OUT_ROOT, "rasters", mouse)
        os.makedirs(rdir, exist_ok=True)
        for r in rows:
            plot_raster(mouse, r, os.path.join(rdir, f"gen_session_{r['session_num']}.png"))
            n_rasters += 1

    print(f"\nWrote figures + {n_rasters} rasters under '{OUT_ROOT}/'.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
