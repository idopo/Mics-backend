#!/usr/bin/env python3
"""Hit / false-alarm learning TRAJECTORY in accuracy x success-rate space.

For each mouse, watch where it sits — and where it moves — session to session in
a signal-detection plane built from LICK BOUTS (a run of licks; a gap longer than
LICK_BOUT_GAP starts a new bout), using the FSM's own ITI boundary to say when a
bout is a cue response vs impulsive ITI licking:

    HIT          = a lick BOUT whose onset is in the response window [0, iti_start)
                   (cue + reward consumption; the tone mutes early on a hit, so the
                   drinking bout lands after cue_dur but before ITI — still a hit).
    FALSE ALARM  = a lick BOUT whose onset is in the ITI window [iti_start, iti_end]
                   (impulsive dry-spout licking outside the cue window).

    x = accuracy      = hits / (hits + false alarms)   -> temporal precision
    y = success rate  = hits / trials                  -> how often it scored

Both axes share the SAME hit count (lick-bout count), so a mouse that licks
precisely on-cue AND often sits top-right; an impulsive ITI-licker sits bottom-
left; a precise-but-rare responder sits top-left.

Figure (results/hit_fa_trajectory/<area>/):
  hit_fa_trajectory.png   one panel per task. Each mouse = one hue; each session
                          is a dot shaded from DARK (first session) -> BRIGHT (last
                          session), and consecutive sessions are joined by an arrow,
                          so both the mouse's path and its direction are visible.
  hit_fa_trajectory_facets.png  one small panel PER MOUSE (shared axes) with every
                          other mouse drawn as a faint grey ghost — the same dark->
                          bright path, but de-cluttered so each trajectory is legible.
  hit_fa_trajectory_dashboard.html  self-contained interactive dashboard: switch the
                          X and Y axis between ~10 metrics, restrict to a session subset
                          (first & last / first N / last N / ordinal range / thirds /
                          custom list), toggle/isolate mice, hover for the numbers.
                          Built by hit_fa_dashboard.py.
  hit_fa_trajectory_by_session.csv   per (task, mouse, session) hits / FA / trials /
                          accuracy / success rate.
  hit_fa_trajectory_summary.txt      per-mouse first -> last change.

Usage:
  python3 hit_fa_trajectory_analysis.py --task appetitive
  python3 hit_fa_trajectory_analysis.py --task both
"""
from __future__ import annotations

import argparse
import colorsys
import csv
import os
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.lines import Line2D
import numpy as np

import trial_history_analysis as TH  # task constants / labels (read-only)
import trial_engagement_licks_analysis as TEL  # raw-trial loaders (keep ITI times)
import learning_trajectories_analysis as LT  # lick-bout + colour/label helpers
import hit_fa_dashboard as HD  # interactive multi-metric HTML dashboard

NAN = float("nan")
_RESULTS_ROOT = Path(__file__).resolve().parent / "results"
_TASK_AREA = {"appetitive": "appetitive", "generalization": "generalization", "both": "cross_task"}
_ENV_OUT = os.environ.get("MICS_HITFA_OUT")
OUT_ROOT = _ENV_OUT or str(_RESULTS_ROOT / "hit_fa_trajectory" / "cross_task")


# --- per-session scoring ---------------------------------------------------
def session_hit_fa(record: dict) -> dict:
    """Bout-level hits / false alarms for one session, split by the ITI boundary."""
    hits = false_alarms = 0
    for tr in record["trials"]:
        iti0, iti1 = tr["iti_start"], tr["iti_end"]
        for onset in LT._lick_bout_onsets(tr["licks"]):
            if 0 <= onset < iti0:
                hits += 1
            elif iti0 <= onset <= iti1:
                false_alarms += 1
            # onset < 0 (pre-cue) is neither a cue response nor ITI licking -> ignored
    n = len(record["trials"])
    responded = hits + false_alarms
    return {
        "task": record["task"], "mouse": record["mouse"], "session": record["session"],
        "hits": hits, "false_alarms": false_alarms, "n_trials": n,
        "accuracy": 100.0 * hits / responded if responded else NAN,
        "success_rate": 100.0 * hits / n if n else NAN,
    }


def build(records: list[dict]) -> dict[str, dict[str, list[dict]]]:
    """{task: {mouse: [per-session score dicts ordered by session]}}."""
    out: dict[str, dict[str, list[dict]]] = {}
    for r in records:
        s = session_hit_fa(r)
        out.setdefault(s["task"], {}).setdefault(s["mouse"], []).append(s)
    for by_mouse in out.values():
        for sessions in by_mouse.values():
            sessions.sort(key=lambda d: d["session"])
    return out


# --- figure ----------------------------------------------------------------
def _session_shade(base, frac: float, l_lo: float = 0.28, l_hi: float = 0.80):
    """The mouse's hue at a lightness that grows with `frac` (0 = first session,
    dark; 1 = last session, bright), so progression reads as brightening."""
    h, _, s = colorsys.rgb_to_hls(*base[:3])
    return colorsys.hls_to_rgb(h, l_lo + (l_hi - l_lo) * frac, s)


def _valid_points(sessions: list[dict]) -> list[dict]:
    return [s for s in sessions
            if not (np.isnan(s["accuracy"]) or np.isnan(s["success_rate"]))]


def _padded_limits(values: list[float], pad_frac: float = 0.08) -> tuple[float, float]:
    """Data range with a margin, floored at 0. Values cluster in a narrow band, so
    data-driven limits keep the motion legible. The upper bound is NOT capped at 100:
    success rate (hits/trials, lick-bout count) can exceed 100% when a mouse averages
    more than one response-window lick bout per trial."""
    if not values:
        return 0.0, 100.0
    lo, hi = min(values), max(values)
    pad = max((hi - lo) * pad_frac, 2.0)
    return max(0.0, lo - pad), hi + pad


def fig_trajectory(by_task: dict, out_path: str) -> None:
    """One panel per task: per-mouse session-to-session path in accuracy x success
    space, dots shaded dark->bright over sessions, arrows between consecutive ones."""
    tasks = list(by_task)
    if not tasks:
        return
    mcolors, _ = LT._mouse_colors(by_task)  # stable hue per mouse across panels
    fig, axes = plt.subplots(1, len(tasks), figsize=(7.2 * len(tasks), 6.8),
                             squeeze=False)  # per-panel limits: tasks span different ranges
    for ax, task in zip(axes[0], tasks):
        pts_all = [p for sessions in by_task[task].values() for p in _valid_points(sessions)]
        xlim = _padded_limits([p["accuracy"] for p in pts_all])
        ylim = _padded_limits([p["success_rate"] for p in pts_all])
        label_items = []
        for m in LT._sorted_mice(by_task[task]):
            pts = _valid_points(by_task[task][m])
            if not pts:
                continue
            base = mcolors[m]
            xs = [p["accuracy"] for p in pts]
            ys = [p["success_rate"] for p in pts]
            n = len(pts)
            for i in range(n - 1):  # arrows tail=earlier -> head=later session
                ax.annotate("", xy=(xs[i + 1], ys[i + 1]), xytext=(xs[i], ys[i]),
                            arrowprops=dict(arrowstyle="-|>", color=base, alpha=0.4,
                                            lw=1.2, shrinkA=5, shrinkB=5),
                            annotation_clip=True, zorder=3)
            for i in range(n):
                frac = i / (n - 1) if n > 1 else 1.0
                ax.scatter([xs[i]], [ys[i]], s=75 if i == n - 1 else 42,
                           color=_session_shade(base, frac), edgecolor=base,
                           linewidths=1.1, zorder=5 if i == n - 1 else 4)
            label_items.append((xs[-1], ys[-1], m, base))
        # label each mouse at its last (brightest) dot; point offset is zoom-independent
        for lx, ly, text, color in label_items:
            ax.annotate(text, (lx, ly), textcoords="offset points", xytext=(7, 4),
                        fontsize=8, color=color, fontweight="bold", zorder=6)
        ax.set_xlim(*xlim)
        ax.set_ylim(*ylim)
        ax.set_xlabel("accuracy = hits / (hits + false alarms)  (%)  →  precision")
        ax.set_title(TH.TASK_LABELS.get(task, task))
        ax.grid(alpha=0.3)
    axes[0][0].set_ylabel("success rate = hits / trials  (%)  →  how often it scored")

    grad_handles = [
        Line2D([], [], marker="o", ls="None", markerfacecolor=_session_shade((.45, .45, .45), 0.0),
               markeredgecolor="#333", ms=8, label="first session (dark)"),
        Line2D([], [], marker="o", ls="None", markerfacecolor=_session_shade((.45, .45, .45), 1.0),
               markeredgecolor="#333", ms=8, label="last session (bright)"),
        Line2D([], [], marker=r"$\rightarrow$", ls="None", color="#555", ms=11,
               label="arrow → next session"),
    ]
    fig.legend(handles=grad_handles, loc="upper center", ncol=3, fontsize=9,
               frameon=False, bbox_to_anchor=(0.5, 0.925))
    tasklabel = " / ".join(TH.TASK_LABELS.get(t, t) for t in tasks)
    fig.suptitle(f"Hit / false-alarm learning trajectory — {tasklabel}\n"
                 "one hue = one mouse (labelled at its last session)", fontsize=13, y=0.995)
    fig.tight_layout(rect=(0, 0, 1, 0.88))
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def _gradient_segments(xs: list[float], ys: list[float], base) -> LineCollection:
    """Connect consecutive sessions with segments shaded dark (early) -> bright
    (late), so the path's own colour encodes progression without any arrows."""
    pts = np.column_stack([xs, ys])
    segs = np.stack([pts[:-1], pts[1:]], axis=1)
    n_seg = len(segs)
    seg_colors = [_session_shade(base, i / (n_seg - 1) if n_seg > 1 else 1.0)
                  for i in range(n_seg)]
    return LineCollection(segs, colors=seg_colors, linewidths=1.8, zorder=4)


def fig_facets(by_task: dict, out_dir: str) -> list[str]:
    """One small panel PER MOUSE (shared axes) so each trajectory is legible on its
    own, with every other mouse drawn as a faint grey ghost for spatial context.
    Writes one figure per task; returns the paths written."""
    mcolors, _ = LT._mouse_colors(by_task)
    written = []
    for task in by_task:
        mice = LT._sorted_mice(by_task[task])
        pts_by_mouse = {m: _valid_points(by_task[task][m]) for m in mice}
        all_pts = [p for pts in pts_by_mouse.values() for p in pts]
        if not all_pts:
            continue
        ghost_x = [p["accuracy"] for p in all_pts]
        ghost_y = [p["success_rate"] for p in all_pts]
        xlim = _padded_limits(ghost_x)
        ylim = _padded_limits(ghost_y)
        n = len(mice)
        ncols = min(5, n)
        nrows = -(-n // ncols)
        fig, axes = plt.subplots(nrows, ncols, figsize=(2.9 * ncols, 2.9 * nrows),
                                 sharex=True, sharey=True, squeeze=False)
        flat = [ax for row in axes for ax in row]
        for idx, ax in enumerate(flat):
            if idx >= n:
                ax.axis("off")
                continue
            m = mice[idx]
            base = mcolors[m]
            pts = pts_by_mouse[m]
            ax.scatter(ghost_x, ghost_y, s=7, color="0.86", alpha=0.7,
                       edgecolors="none", zorder=1)  # ghost of every mouse
            ax.grid(alpha=0.25)
            ax.set_title(m, color=base, fontweight="bold", fontsize=11)
            if not pts:
                continue
            xs = [p["accuracy"] for p in pts]
            ys = [p["success_rate"] for p in pts]
            ax.add_collection(_gradient_segments(xs, ys, base))
            if len(pts) > 1:  # arrowhead only on the final hop -> reads as "heading"
                ax.annotate("", xy=(xs[-1], ys[-1]), xytext=(xs[-2], ys[-2]),
                            arrowprops=dict(arrowstyle="-|>", color=base, lw=1.8,
                                            shrinkA=0, shrinkB=0), zorder=6)
            for i in range(len(pts)):
                frac = i / (len(pts) - 1) if len(pts) > 1 else 1.0
                ax.scatter([xs[i]], [ys[i]], s=70 if i == len(pts) - 1 else 34,
                           color=_session_shade(base, frac), edgecolor=base,
                           linewidths=1.0, zorder=5)
        for ax in flat[:n]:
            ax.set_xlim(*xlim)
            ax.set_ylim(*ylim)
        fig.supxlabel("accuracy = hits / (hits + false alarms)  (%)  →  precision", fontsize=11)
        fig.supylabel("success rate = hits / trials  (%)  →  how often it scored", fontsize=11)
        fig.suptitle(f"Hit / false-alarm trajectory per mouse — {TH.TASK_LABELS.get(task, task)}\n"
                     "dark dot = first session → bright dot = last; grey = all mice",
                     fontsize=13)
        fig.tight_layout(rect=(0.01, 0.01, 1, 0.94))
        suffix = "" if len(by_task) == 1 else f"_{task}"
        path = os.path.join(out_dir, f"hit_fa_trajectory_facets{suffix}.png")
        fig.savefig(path, dpi=150)
        plt.close(fig)
        written.append(path)
    return written


# --- writers ---------------------------------------------------------------
def write_session_csv(by_task: dict, path: str) -> None:
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["task", "mouse", "session", "hits", "false_alarms", "n_trials",
                    "accuracy_pct", "success_rate_pct"])
        for task in by_task:
            for m in LT._sorted_mice(by_task[task]):
                for s in by_task[task][m]:
                    w.writerow([task, m, s["session"], s["hits"], s["false_alarms"],
                                s["n_trials"],
                                "" if np.isnan(s["accuracy"]) else f"{s['accuracy']:.2f}",
                                "" if np.isnan(s["success_rate"]) else f"{s['success_rate']:.2f}"])


def write_summary(by_task: dict, path: str) -> None:
    lines = ["Hit/false-alarm trajectory: per-mouse first -> last session",
             "(accuracy = hits/(hits+FA); success = hits/trials; lick-bout based)", ""]
    for task in by_task:
        lines.append(f"## {TH.TASK_LABELS.get(task, task)}")
        for m in LT._sorted_mice(by_task[task]):
            pts = _valid_points(by_task[task][m])
            if not pts:
                continue
            a0, s0 = pts[0]["accuracy"], pts[0]["success_rate"]
            a1, s1 = pts[-1]["accuracy"], pts[-1]["success_rate"]
            lines.append(f"  {m:5}  accuracy {a0:5.1f} -> {a1:5.1f}   "
                         f"success {s0:5.1f} -> {s1:5.1f}   ({len(pts)} sessions)")
        lines.append("")
    Path(path).write_text("\n".join(lines))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--task", choices=["appetitive", "generalization", "both"], default="both")
    parser.add_argument("--mouse", default=None, help="restrict to one mouse, e.g. m102")
    args = parser.parse_args()

    global OUT_ROOT
    if not _ENV_OUT:
        OUT_ROOT = str(_RESULTS_ROOT / "hit_fa_trajectory" / _TASK_AREA[args.task])

    records: list[dict] = []
    if args.task in ("appetitive", "both"):
        print("Loading appetitive (tone) task ...")
        records += TEL.load_appetitive(args.mouse)
    if args.task in ("generalization", "both"):
        print("Loading generalization (light) task ...")
        records += TEL.load_generalization(args.mouse)
    if not records:
        print("No sessions found — nothing to do.")
        return 1

    by_task = build(records)
    os.makedirs(OUT_ROOT, exist_ok=True)
    fig_trajectory(by_task, os.path.join(OUT_ROOT, "hit_fa_trajectory.png"))
    facet_paths = fig_facets(by_task, OUT_ROOT)
    html_paths = HD.write_dashboard(records, OUT_ROOT)
    write_session_csv(by_task, os.path.join(OUT_ROOT, "hit_fa_trajectory_by_session.csv"))
    write_summary(by_task, os.path.join(OUT_ROOT, "hit_fa_trajectory_summary.txt"))

    n_sess = sum(len(s) for by_mouse in by_task.values() for s in by_mouse.values())
    print(f"\nWrote {1 + len(facet_paths)} PNGs (overlaid + {len(facet_paths)} per-mouse facet), "
          f"{len(html_paths)} interactive dashboard HTML, 1 CSV, and summary.txt under "
          f"'{OUT_ROOT}/' ({n_sess} sessions).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
