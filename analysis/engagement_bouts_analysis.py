#!/usr/bin/env python3
"""Engagement-bout analysis for the appetitive (tone) and generalization (light) tasks.

A *bout* is a run of consecutive trials in which the mouse engaged the cue, i.e.
nose-poked while the cue was on (engaged = on-cue poke in [0, cue_dur], the same
definition used everywhere else in the project). Within one session's trials, in
order, a bout is a maximal run of consecutive engaged==True trials that lasts
MORE THAN 3 trials (>= 4 in a row); shorter engaged runs are not counted as
bouts. Tune the minimum with MICS_MIN_BOUT (default 4).

For each mouse, for each session, this measures two things the user asked for:
  * how many trials in a row the mouse stayed engaged  -> bout LENGTH
  * how many such engaged periods happened             -> bout COUNT (n_bouts)
then averages each across that mouse's sessions to give one mean per mouse.

Reuses the loaders in trial_history_analysis (which reuse appetitive_analysis /
generalization_analysis) so the trial set and engagement definition match the
rest of the analysis exactly.

Outputs (under results/engagement_bouts/<area>/, area = appetitive |
generalization | cross_task for --task both; override root with MICS_BOUTS_OUT):
    engagement_bouts_summary.png        per-mouse mean bout count + mean length
    engagement_bouts_raster.png         all mice in a grid: bouts placed on the
                                        trial axis, one row per session (see timing)
    rasters/<mouse>.png                 one figure per mouse: every session as a
                                        raster row, with per-trial outcome markers
                                        (hit = o, engaged-miss = x) over the bouts
    engagement_bouts_by_session.csv     tidy per-session table
    engagement_bouts_by_mouse.csv       per-mouse means
    bout_hit_by_context.csv             hit rate table by bout-relative context
    engagement_bouts_summary.txt        text summary

Usage:
    python3 engagement_bouts_analysis.py --task generalization
    python3 engagement_bouts_analysis.py --task both
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
from matplotlib.colors import ListedColormap
from matplotlib.lines import Line2D
import numpy as np

import trial_history_analysis as TH  # loaders + task constants/colors (reused)

NAN = float("nan")
_RESULTS_ROOT = Path(__file__).resolve().parent / "results"
_TASK_AREA = {"appetitive": "appetitive", "generalization": "generalization", "both": "cross_task"}
_ENV_OUT = os.environ.get("MICS_BOUTS_OUT")
OUT_ROOT = _ENV_OUT or str(_RESULTS_ROOT / "engagement_bouts" / "cross_task")

# A bout must span more than 3 trials in a row (>= 4). Tune with MICS_MIN_BOUT.
MIN_BOUT = int(os.environ.get("MICS_MIN_BOUT", "4"))


# --- bout computation ------------------------------------------------------
def bout_spans(engaged_seq: list[bool], min_len: int = MIN_BOUT) -> list[tuple[int, int]]:
    """(start_index, length) of each maximal run of consecutive engaged==True
    trials that is at least min_len long. start_index is 0-based trial position."""
    spans, run_start = [], None
    for i, e in enumerate(engaged_seq):
        if e and run_start is None:
            run_start = i
        elif not e and run_start is not None:
            if i - run_start >= min_len:
                spans.append((run_start, i - run_start))
            run_start = None
    if run_start is not None and len(engaged_seq) - run_start >= min_len:
        spans.append((run_start, len(engaged_seq) - run_start))
    return spans


def session_stats(record: dict) -> dict:
    """Bout stats for one (mouse, session) record from the TH loaders."""
    seq = [bool(t["engaged"]) for t in record["trials"]]
    rewarded = [bool(t["rewarded"]) for t in record["trials"]]
    spans = bout_spans(seq)
    lengths = [length for _, length in spans]
    return {
        "task": record["task"],
        "mouse": record["mouse"],
        "session": record["training_day"],  # chronological session # (1..N)
        "n_trials": len(seq),
        "n_engaged": int(sum(seq)),
        "n_hits": int(sum(rewarded)),
        "n_bouts": len(lengths),
        "mean_bout_len": float(np.mean(lengths)) if lengths else NAN,
        "max_bout_len": max(lengths) if lengths else 0,
        "lengths": lengths,
        "spans": spans,
        "engaged_seq": seq,
        "rewarded_seq": rewarded,
    }


def group_by_task_mouse(records: list[dict]) -> dict[str, dict[str, list[dict]]]:
    """{task: {mouse: [session_stats sorted by session]}}."""
    out: dict[str, dict[str, list[dict]]] = {}
    for rec in records:
        s = session_stats(rec)
        out.setdefault(s["task"], {}).setdefault(s["mouse"], []).append(s)
    for by_mouse in out.values():
        for sessions in by_mouse.values():
            sessions.sort(key=lambda s: s["session"])
    return out


def _sorted_mice(by_mouse: dict[str, list[dict]]) -> list[str]:
    return sorted(by_mouse, key=lambda m: int("".join(filter(str.isdigit, m)) or 0))


def _all_mice(by_task: dict[str, dict[str, list[dict]]]) -> list[str]:
    mice: set[str] = set()
    for by_mouse in by_task.values():
        mice.update(by_mouse)
    return sorted(mice, key=lambda m: int("".join(filter(str.isdigit, m)) or 0))


def _mean_sem(values: list[float]) -> tuple[float, float]:
    vals = [v for v in values if not np.isnan(v)]
    if not vals:
        return NAN, 0.0
    m = float(np.mean(vals))
    sem = float(np.std(vals, ddof=1) / np.sqrt(len(vals))) if len(vals) > 1 else 0.0
    return m, sem


# --- figures ---------------------------------------------------------------
def fig_summary(by_task: dict, out_path: str) -> None:
    """Per-mouse mean bout count (left) and mean bout length (right), with the
    individual per-session values overlaid as dots. Bars = mean across sessions."""
    tasks = list(by_task)
    mice = _all_mice(by_task)
    x = np.arange(len(mice), dtype=float)
    width = 0.8 / max(len(tasks), 1)

    fig, axes = plt.subplots(1, 2, figsize=(max(9, 1.1 * len(mice)), 5.2))
    metrics = [("n_bouts", "bouts per session", "number of engaged periods"),
               ("mean_bout_len", "mean bout length (trials in a row)", "trials in a row per bout")]
    for ax, (key, ylabel, title) in zip(axes, metrics):
        for ti, task in enumerate(tasks):
            color = TH.TASK_COLORS.get(task, "#555555")
            offs = x + (ti - (len(tasks) - 1) / 2) * width
            means, sems = [], []
            for xi, m in zip(offs, mice):
                sessions = by_task[task].get(m, [])
                per_sess = [s[key] for s in sessions]
                mean, sem = _mean_sem(per_sess)
                means.append(mean)
                sems.append(sem)
                jit = (np.arange(len(per_sess)) - (len(per_sess) - 1) / 2) * (width * 0.12)
                ax.scatter(np.full(len(per_sess), xi) + jit, per_sess, s=9,
                           color=color, alpha=0.35, zorder=3, linewidths=0)
            ax.bar(offs, means, width=width * 0.9, color=color, alpha=0.55,
                   yerr=sems, capsize=2, zorder=2,
                   label=TH.TASK_LABELS.get(task, task) if ax is axes[0] else None)
        ax.set_xticks(x)
        ax.set_xticklabels(mice, rotation=45, ha="right")
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        ax.grid(axis="y", alpha=0.3)
    if len(tasks) > 1:
        axes[0].legend(fontsize=8, loc="upper right")
    fig.suptitle("Engagement bouts per mouse (bar = mean over sessions, dots = sessions)")
    fig.tight_layout()
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


def fig_bout_raster_per_mouse(by_task: dict, out_dir: str) -> int:
    """One figure PER mouse: every session as a raster row, with per-trial outcome
    markers (hit = o, miss = x) over the bouts. Returns the number written."""
    os.makedirs(out_dir, exist_ok=True)
    cmap = _bout_cmap()
    written = 0
    for m in _all_mice(by_task):
        rows, ylabels, bout_trials, sessions = _mouse_session_rows(by_task, m)
        if not rows:
            continue
        width = max(n for n, _ in rows)
        fig, ax = plt.subplots(figsize=(max(8.0, 0.15 * width + 2.4),
                                        max(2.4, 0.46 * len(rows) + 1.6)))
        _draw_mouse_raster(ax, sessions, rows, ylabels, bout_trials, cmap)
        ax.set_xlabel("trial in session")
        ax.set_ylabel("session")
        ax.set_title(f"{m} — engagement bouts + outcome by session "
                     f"(bout = > {MIN_BOUT - 1} trials in a row)")
        ax.legend(handles=_bout_legend_handles(with_outcome=True), loc="upper center",
                  bbox_to_anchor=(0.5, -0.14 - 0.5 / len(rows)), ncol=3, fontsize=7,
                  frameon=False)
        fig.tight_layout()
        fig.savefig(os.path.join(out_dir, f"{m}.png"), dpi=140, bbox_inches="tight")
        plt.close(fig)
        written += 1
    return written


def fig_bout_raster(by_task: dict, out_path: str) -> None:
    """All mice in ONE figure, each rendered like the per-mouse rasters: sessions
    as rows, trials on x, bout colouring + hit (o) / miss (x) markers and a per-row
    bout-trial count. For --task both, tone rows (blue) sit above light rows (red)."""
    mice = _all_mice(by_task)
    data = {m: _mouse_session_rows(by_task, m) for m in mice}
    cmap = _bout_cmap()
    ncol = min(2, len(mice)) or 1
    nrow = int(np.ceil(len(mice) / ncol))
    max_rows = max((len(data[m][0]) for m in mice), default=1)
    panel_h = min(3.8, max(2.6, 0.33 * max_rows + 1.3))
    fig, axes = plt.subplots(nrow, ncol, figsize=(7.6 * ncol, panel_h * nrow), squeeze=False)
    for idx, m in enumerate(mice):
        ax = axes[idx // ncol][idx % ncol]
        rows, ylabels, bout_trials, sessions = data[m]
        if not rows:
            ax.axis("off")
            continue
        _draw_mouse_raster(ax, sessions, rows, ylabels, bout_trials, cmap,
                           marker_scale=0.55, label_fs=6, ann_fs=6, ann_full=False)
        ax.set_title(m, fontsize=10)
        ax.set_xlabel("trial in session", fontsize=8)
        ax.tick_params(labelsize=7)
    for j in range(len(mice), nrow * ncol):
        axes[j // ncol][j % ncol].axis("off")
    fig.legend(handles=_bout_legend_handles(with_outcome=True), loc="lower center",
               ncol=6, fontsize=8, frameon=False)
    fig.suptitle(f"Engagement bouts + outcome by session — all mice "
                 f"(bout = > {MIN_BOUT - 1} trials in a row)", fontsize=12)
    fig.tight_layout(rect=(0, 0.03, 1, 0.97))
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


def write_hit_context_csv(by_task: dict, path: str) -> None:
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["task", "mouse", "context", "n_trials", "n_hits", "hit_rate"])
        for task in by_task:
            for m in _sorted_mice(by_task[task]) + ["GROUP"]:
                ctx = (_merge_ctx([_mouse_ctx(by_task, task, x) for x in by_task[task]])
                       if m == "GROUP" else _mouse_ctx(by_task, task, m))
                for c in _HIT_CTX:
                    vals = ctx[c]
                    label = c.replace("\n", " ")
                    rate = f"{100 * np.mean(vals):.1f}" if vals else ""
                    w.writerow([task, m, label, len(vals), int(sum(vals)), rate])


# --- writers ---------------------------------------------------------------
def write_session_csv(by_task: dict, path: str) -> None:
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["task", "mouse", "session", "n_trials", "n_engaged",
                    "n_bouts", "mean_bout_len", "max_bout_len", "engaged_rate"])
        for task in by_task:
            for m in _sorted_mice(by_task[task]):
                for s in by_task[task][m]:
                    rate = 100.0 * s["n_engaged"] / s["n_trials"] if s["n_trials"] else 0.0
                    w.writerow([task, m, s["session"], s["n_trials"], s["n_engaged"],
                                s["n_bouts"],
                                f"{s['mean_bout_len']:.3f}" if not np.isnan(s["mean_bout_len"]) else "",
                                s["max_bout_len"], f"{rate:.1f}"])


def mouse_means(by_task: dict) -> list[dict]:
    rows = []
    for task in by_task:
        for m in _sorted_mice(by_task[task]):
            sessions = by_task[task][m]
            nb_mean, nb_sem = _mean_sem([s["n_bouts"] for s in sessions])
            ml_mean, ml_sem = _mean_sem([s["mean_bout_len"] for s in sessions])
            longest = max((s["max_bout_len"] for s in sessions), default=0)
            rows.append({"task": task, "mouse": m, "n_sessions": len(sessions),
                         "mean_n_bouts": nb_mean, "sem_n_bouts": nb_sem,
                         "mean_bout_len": ml_mean, "sem_bout_len": ml_sem,
                         "longest_bout": longest})
    return rows


def write_mouse_csv(rows: list[dict], path: str) -> None:
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["task", "mouse", "n_sessions", "mean_n_bouts_per_session", "sem_n_bouts",
                    "mean_bout_length", "sem_bout_length", "longest_bout"])
        for r in rows:
            w.writerow([r["task"], r["mouse"], r["n_sessions"],
                        f"{r['mean_n_bouts']:.3f}", f"{r['sem_n_bouts']:.3f}",
                        f"{r['mean_bout_len']:.3f}" if not np.isnan(r["mean_bout_len"]) else "",
                        f"{r['sem_bout_len']:.3f}", r["longest_bout"]])


def write_summary(rows: list[dict], path: str) -> None:
    lines = ["Engagement bouts (consecutive on-cue-engaged trials)",
             f"Bout = run of more than {MIN_BOUT - 1} engaged trials in a row "
             f"(>= {MIN_BOUT}).", ""]
    for task in sorted({r["task"] for r in rows}):
        trs = [r for r in rows if r["task"] == task]
        lines.append(f"## {TH.TASK_LABELS.get(task, task)}  ({len(trs)} mice)")
        for r in sorted(trs, key=lambda r: (-r["mean_bout_len"] if not np.isnan(r["mean_bout_len"]) else 0)):
            ml = f"{r['mean_bout_len']:.1f}" if not np.isnan(r["mean_bout_len"]) else "n/a"
            lines.append(f"  {r['mouse']:>5}: {r['mean_n_bouts']:.1f} bouts/session, "
                         f"mean {ml} trials in a row, longest {r['longest_bout']} "
                         f"({r['n_sessions']} sessions)")
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
        OUT_ROOT = str(_RESULTS_ROOT / "engagement_bouts" / _TASK_AREA[args.task])

    records: list[dict] = []
    if args.task in ("appetitive", "both"):
        print("Loading appetitive (tone) task ...")
        records += TH.load_appetitive(args.mouse)
    if args.task in ("generalization", "both"):
        print("Loading generalization (light) task ...")
        records += TH.load_generalization(args.mouse)
    if not records:
        print("No sessions found — nothing to do.")
        return 1

    by_task = group_by_task_mouse(records)
    os.makedirs(OUT_ROOT, exist_ok=True)
    write_session_csv(by_task, os.path.join(OUT_ROOT, "engagement_bouts_by_session.csv"))
    rows = mouse_means(by_task)
    write_mouse_csv(rows, os.path.join(OUT_ROOT, "engagement_bouts_by_mouse.csv"))
    fig_summary(by_task, os.path.join(OUT_ROOT, "engagement_bouts_summary.png"))
    fig_bout_raster(by_task, os.path.join(OUT_ROOT, "engagement_bouts_raster.png"))
    n_rasters = fig_bout_raster_per_mouse(by_task, os.path.join(OUT_ROOT, "rasters"))
    write_hit_context_csv(by_task, os.path.join(OUT_ROOT, "bout_hit_by_context.csv"))
    write_summary(rows, os.path.join(OUT_ROOT, "engagement_bouts_summary.txt"))

    n_sess = sum(len(s) for by_mouse in by_task.values() for s in by_mouse.values())
    print(f"\nWrote 3 CSVs, 2 figures, {n_rasters} per-mouse rasters, and summary.txt "
          f"under '{OUT_ROOT}/' "
          f"({n_sess} sessions, {len(rows)} mouse-task rows).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
