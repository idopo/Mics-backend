#!/usr/bin/env python3
"""Extinction (LED-cued, reward withheld): trial-by-trial response-persistence decay.

The extinction task (task_type=ExtinctionLED) presents the same LED2 cue as the
generalization task but delivers no water. With reward gone, the interesting signal
is not "did they learn" across sessions (there are only ~2 sessions/mouse) but how
fast the conditioned response DECAYS as the cue stops paying off — and whether it
recovers at the start of the next session.

Both sessions are laid out END TO END on ONE continuous trial-number X-axis
(session 1 = trials 1..SESSION_LEN, session 2 = trials SESSION_LEN+1..), with a
dashed divider at the boundary. The tracked metrics are response persistence, NOT
reward (there is none):

    on-cue poke rate  = % trials with a nose poke while LED2 is on   (the CR)
    on-cue lick rate  = % trials with a lick during the cue window

Per-trial on-cue poking is binary, so each session is split into ~equal blocks of
BIN_SIZE trials and the block's response rate is plotted (block count = round(
SESSION_LEN / BIN_SIZE); sizes differ by at most one, so there is no ragged 1-trial
tail). The group line is the mean across mice with a ±1 std band (drawn where
n≥MIN_BAND mice contribute). The 8 mice with exactly SESSION_LEN trials define the
boundary; m98 (65) and m103 (68) are truncated to SESSION_LEN so the single divider
line stays exact.

The interactive dashboard (extinction_decay_dashboard.html) embeds the raw per-trial
sequences and re-bins them in-browser, so the bin size N is a live control.

Reuses the generalization loader (identical LED2 hardware / trial segmentation);
extinction sessions for m98 and m103 span two ES subject strings and are merged
chronologically, exactly like the generalization "_2" continuations.

Outputs (results/extinction/within_session/):
  extinction_decay_dashboard.html   interactive: metric · bin size N · per-mouse/mean±std
  extinction_decay_oncue_poke.png   per-mouse binned curves + group mean ± std
  extinction_decay_oncue_lick.png   same, for on-cue licking
  extinction_session_split.png      session 1 vs session 2 overlaid (recovery?)
  extinction_by_bin.csv             per (block, metric) group mean / std / n

Usage:
  python3 extinction_analysis.py
  python3 extinction_analysis.py --bin-size 5     # finer blocks
  python3 extinction_analysis.py --session-len 61
"""
from __future__ import annotations

import argparse
import csv
import os
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
import numpy as np
import requests

import generalization_analysis as G  # LED2 loader + trial segmentation (reused)
import appetitive_analysis as A  # canonical day-based session grouping
import extinction_dashboard as ED  # interactive HTML (live bin-size control)
from config import ES_URL, ES_INDEX

TASK_TYPE = "ExtinctionLED"
PILOT = "RecordingBox"
# Real extinction subjects are "m<id>_...Light..." (m101_ExLight_400, m98_EXtLight,
# m103_ExtLight2). The task_type filter already excludes generalization's GenLight;
# requiring an m<digits> prefix + "light" drops the try_ext_led* / Extinction_Trial
# probe junk (which has no "light" token and no mouse-id prefix).
SUBJECT_RE = re.compile(r"^m(\d+)_.*light", re.IGNORECASE)
SESSION_LEN = 61  # nominal trials/session: sets the session-2 offset + divider x
BIN_SIZE = 10     # target trials per block (blocks per session = round(SESSION_LEN/N))
MIN_BAND = 3      # need >= this many mice contributing to draw a std band
NAN = float("nan")

_RESULTS_ROOT = Path(__file__).resolve().parent / "results"
OUT_ROOT = os.environ.get("MICS_EXT_OUT") or str(_RESULTS_ROOT / "extinction" / "within_session")

METRICS = [
    ("oncue_poke", "on-cue poke rate  (%)"),
    ("oncue_lick", "on-cue lick rate  (%)"),
]


# --- loaders (reuse generalization ES access + LED2 segmentation) ----------
def discover_mice() -> dict[str, list[str]]:
    """{m<id>: [its extinction subject strings]} on the extinction task/pilot."""
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


def collect_mouse(subjects: list[str]) -> list[dict]:
    """Per-session {subject, session_num, trials} for one mouse, merged across its
    subject strings and ordered chronologically (no MAX_SESSION cap — extinction is
    only ~2 sessions long)."""
    rows: list[dict] = []
    for subject in subjects:
        events = G.fetch_events(subject, task_type=TASK_TYPE, pilot=PILOT)
        by_session = A.group_by_day_session(events)
        for evs in by_session.values():
            trials = G.segment_trials(evs)
            if not G.session_len_ok(len(trials)):
                continue
            rows.append({"subject": subject, "start": min(e["epoch"] for e in evs),
                         "trials": trials})
    rows.sort(key=lambda r: r["start"])
    for i, r in enumerate(rows, start=1):
        r["session_num"] = i
    return rows


def load_extinction(only_mouse: str | None) -> list[dict]:
    """Records {mouse, subject, session, trials} for the extinction task."""
    records = []
    for mouse, subjects in discover_mice().items():
        if only_mouse and mouse != only_mouse:
            continue
        for r in collect_mouse(subjects):
            records.append({"mouse": mouse, "subject": r["subject"],
                            "session": r["session_num"], "trials": r["trials"]})
    return records


# --- raw per-trial series + binning ----------------------------------------
def _trial_flag(t: dict, key: str) -> float:
    """0/1 response flag for one trial (no reward metrics)."""
    if key == "oncue_poke":
        return 1.0 if t["engaged"] else 0.0                       # poke while LED2 on
    return 1.0 if any(0 <= lk <= t["led_dur"] for lk in t["licks"]) else 0.0  # oncue lick


def raw_series(records: list[dict], session_len: int) -> dict[str, dict[int, dict[str, list[float]]]]:
    """{mouse: {session: {metric: [per-trial 0/1, capped at session_len]}}}."""
    out: dict[str, dict[int, dict[str, list[float]]]] = {}
    for r in records:
        trials = r["trials"][:session_len]
        out.setdefault(r["mouse"], {})[r["session"]] = {
            k: [_trial_flag(t, k) for t in trials] for k, _ in METRICS}
    return out


def block_spans(length: int, bin_size: int) -> list[tuple[int, int, float]]:
    """Split `length` trials into round(length/bin_size) ~equal blocks.
    Returns (start, end, centre) with 0-based [start, end) and 1-based centre."""
    b = max(1, round(length / bin_size))
    spans, start = [], 0
    for i in range(b):
        size = length // b + (1 if i < length % b else 0)
        spans.append((start, start + size, start + (size + 1) / 2))
        start += size
    return spans


def _bin_rates(seq: list[float], spans: list[tuple]) -> list[float]:
    out = []
    for start, end, _ in spans:
        block = seq[start:min(end, len(seq))]
        out.append(100.0 * float(np.mean(block)) if block else NAN)
    return out


def _sorted_mice(raw: dict) -> list[str]:
    return sorted(raw, key=lambda m: int(re.sub(r"\D", "", m) or 0))


def _colors(mice: list[str]) -> dict[str, tuple]:
    cmap = plt.get_cmap("tab10" if len(mice) <= 10 else "tab20")
    return {m: cmap(i % cmap.N) for i, m in enumerate(mice)}


# --- figures ---------------------------------------------------------------
def _abs_x(session: int, centre: float, session_len: int) -> float:
    """Concatenated trial number (for the CSV's cross-session reference column)."""
    return (session - 1) * session_len + centre


def fig_decay(raw: dict, key: str, label: str, session_len: int, bin_size: int,
              out_path: str) -> None:
    """One panel per session (its own trial-1..N axis): per-mouse binned curves
    overlaid with the group mean ± std band."""
    mice = _sorted_mice(raw)
    colors = _colors(mice)
    spans = block_spans(session_len, bin_size)
    centres = [c for _, _, c in spans]
    max_session = max((s for sess in raw.values() for s in sess), default=1)
    fig, axes = plt.subplots(1, max_session, figsize=(5.4 * max_session, 5.2),
                             sharey=True, squeeze=False)
    for s, ax in enumerate(axes[0], 1):
        for m in mice:
            if s not in raw[m]:
                continue
            rates = _bin_rates(raw[m][s][key], spans)
            xy = [(c, r) for c, r in zip(centres, rates) if not np.isnan(r)]
            if xy:
                xs, ys = zip(*xy)
                ax.plot(xs, ys, color=colors[m], lw=0.9, alpha=0.4, marker="o", ms=2.5, zorder=2)
        xs, mean, lo, hi = [], [], [], []
        for i, c in enumerate(centres):
            vals = [_bin_rates(raw[m][s][key], spans)[i] for m in mice if s in raw[m]]
            vals = [v for v in vals if not np.isnan(v)]
            if not vals:
                continue
            mu = float(np.mean(vals))
            sd = float(np.std(vals, ddof=1)) if len(vals) > 1 else 0.0
            band = len(vals) >= MIN_BAND
            xs.append(c)
            mean.append(mu)
            lo.append(mu - sd if band else np.nan)
            hi.append(mu + sd if band else np.nan)
        if xs:
            ax.plot(xs, mean, color="black", lw=2.6, marker="o", ms=5, zorder=5)
            xa, la, ha = np.array(xs), np.array(lo), np.array(hi)
            m_ok = ~np.isnan(la)
            if m_ok.any():
                ax.fill_between(xa[m_ok], la[m_ok], ha[m_ok], color="black", alpha=0.14, zorder=1)
        ax.set_title(f"session {s}")
        ax.set_xlabel("trial number")
        ax.set_xlim(0, session_len + 1)
        ax.set_ylim(bottom=0)
        ax.grid(alpha=0.3)
    axes[0][0].set_ylabel(label)
    handles = [Line2D([0], [0], color=colors[m], lw=1.6, marker="o", ms=3, label=m) for m in mice]
    handles += [Line2D([0], [0], color="black", lw=2.6, label="group mean"),
                Patch(facecolor="black", alpha=0.14, label="±1 std")]
    axes[0][-1].legend(handles=handles, loc="center left", bbox_to_anchor=(1.01, 0.5),
                       fontsize=8, frameon=False, title="mouse")
    fig.suptitle(f"Extinction decay by trial — {label}\nbin = {bin_size} trials · "
                 f"faint = individual mice · bold = group mean ± std (band where n≥{MIN_BAND})",
                 fontsize=12)
    fig.tight_layout(rect=(0, 0, 0.9, 0.92))
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def fig_session_split(raw: dict, key: str, label: str, session_len: int, bin_size: int,
                      out_path: str) -> None:
    """Session 1 vs session 2 group mean ± std vs within-session trial number —
    does the CR recover at the next session's start (spontaneous recovery)?"""
    mice = _sorted_mice(raw)
    spans = block_spans(session_len, bin_size)
    palette = {1: "#1f77b4", 2: "#d62728"}
    fig, ax = plt.subplots(figsize=(7.6, 5.4))
    for sess in (1, 2):
        xs, mean, lo, hi = [], [], [], []
        for i, (_, _, c) in enumerate(spans):
            vals = [_bin_rates(raw[m][sess][key], spans)[i] for m in mice if sess in raw[m]]
            vals = [v for v in vals if not np.isnan(v)]
            if not vals:
                continue
            mu = float(np.mean(vals))
            sd = float(np.std(vals, ddof=1)) if len(vals) > 1 else 0.0
            xs.append(c)
            mean.append(mu)
            band = len(vals) >= MIN_BAND
            lo.append(mu - sd if band else np.nan)
            hi.append(mu + sd if band else np.nan)
        if not xs:
            continue
        n = max(sum(1 for m in mice if sess in raw[m]), 0)
        c = palette[sess]
        ax.plot(xs, mean, color=c, lw=2.4, marker="o", ms=5, zorder=5,
                label=f"session {sess}  (n={n} mice)")
        xa, la, ha = np.array(xs), np.array(lo), np.array(hi)
        m_ok = ~np.isnan(la)
        if m_ok.any():
            ax.fill_between(xa[m_ok], la[m_ok], ha[m_ok], color=c, alpha=0.13, zorder=1)
    ax.set_xlabel("trial number within session")
    ax.set_ylabel(label)
    ax.set_ylim(bottom=0)
    ax.grid(alpha=0.3)
    ax.legend(loc="best", fontsize=9, frameon=False)
    fig.suptitle(f"Extinction: session 1 vs session 2 — {label}\n"
                 f"bin = {bin_size} trials · group mean ± std (band where n≥{MIN_BAND})", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def write_csv(raw: dict, session_len: int, bin_size: int, path: str) -> None:
    """Group mean/std/n per block (both sessions), one column block per metric."""
    mice = _sorted_mice(raw)
    spans = block_spans(session_len, bin_size)
    keys = [k for k, _ in METRICS]
    max_session = max((s for sess in raw.values() for s in sess), default=1)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        head = ["abs_trial_centre", "session", "within_session_centre", "block"]
        for k in keys:
            head += [f"{k}_mean", f"{k}_std", f"{k}_n"]
        w.writerow(head)
        for s in range(1, max_session + 1):
            for i, (_, _, c) in enumerate(spans):
                row = [f"{_abs_x(s, c, session_len):.1f}", s, f"{c:.1f}", i + 1]
                any_data = False
                for k in keys:
                    vals = [_bin_rates(raw[m][s][k], spans)[i] for m in mice if s in raw[m]]
                    vals = [v for v in vals if not np.isnan(v)]
                    if vals:
                        any_data = True
                        sd = float(np.std(vals, ddof=1)) if len(vals) > 1 else 0.0
                        row += [f"{np.mean(vals):.2f}", f"{sd:.2f}", len(vals)]
                    else:
                        row += ["", "", "0"]
                if any_data:
                    w.writerow(row)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mouse", default=None, help="restrict to one mouse, e.g. m102")
    parser.add_argument("--bin-size", type=int, default=BIN_SIZE,
                        help=f"target trials per block (default {BIN_SIZE})")
    parser.add_argument("--session-len", type=int, default=SESSION_LEN,
                        help=f"nominal trials/session (session-2 offset + divider; default {SESSION_LEN})")
    args = parser.parse_args()

    print("Loading extinction (LED, reward withheld) task ...")
    records = load_extinction(args.mouse)
    if not records:
        print("No extinction sessions found — nothing to do.")
        return 1

    os.makedirs(OUT_ROOT, exist_ok=True)
    raw = raw_series(records, args.session_len)
    colors = _colors(_sorted_mice(raw))

    html = ED.write_dashboard(raw, colors, METRICS, args.session_len, args.bin_size,
                              MIN_BAND, OUT_ROOT)
    for key, label in METRICS:
        fig_decay(raw, key, label, args.session_len, args.bin_size,
                  os.path.join(OUT_ROOT, f"extinction_decay_{key}.png"))
    fig_session_split(raw, "oncue_poke", METRICS[0][1], args.session_len, args.bin_size,
                      os.path.join(OUT_ROOT, "extinction_session_split.png"))
    write_csv(raw, args.session_len, args.bin_size,
              os.path.join(OUT_ROOT, "extinction_by_bin.csv"))

    n_mice, n_sess = len(raw), len(records)
    print(f"\nWrote 1 dashboard ({os.path.basename(html)}), 3 PNGs and 1 CSV under "
          f"'{OUT_ROOT}/' ({n_mice} mice, {n_sess} sessions, bin={args.bin_size}, "
          f"session_len={args.session_len}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
