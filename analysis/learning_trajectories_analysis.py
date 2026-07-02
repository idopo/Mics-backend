#!/usr/bin/env python3
"""Learning-trajectory analysis: how each mouse's behavioural phenotype changes
across the learning process (within and between sessions), and early vs late.

The "phenotype" is the same multi-dimensional profile used elsewhere in the
project (engagement, competence, hit rate, persistence, latency, off-cue poking,
reward-gating), but here it is computed PER SESSION so we can watch it move,
rather than collapsing every session into one per-mouse number.

For each mouse / session it computes:
  engagement  : % of trials engaged on-cue
  competence  : hit rate among engaged trials (accuracy | engaged)
  hit_rate    : overall % of trials rewarded
  bout_len    : mean engagement-bout length (persistence; run of > 3 on-cue trials)
  latency     : median cue -> first on-cue poke latency (s; lower = faster)
  offcue      : off-cue pokes per trial (lower = less impulsive)
  win_stay    : P(engage | prev hit) - P(engage | prev miss) (reward-gating)

Figures (results/learning_trajectories/<area>/):
  trajectories_by_metric.png       each metric vs session, group mean +- SEM and
                                   faint per-mouse lines (the fluid trajectory)
  first_vs_last_slopes.png         early-phase vs late-phase per mouse, per metric
  phenotype_radar.png              group phenotype shape, early vs late overlaid
  learning_index_heatmap.png       per-mouse composite maturity across sessions
  cue_to_first_poke_latency_group.png       mean cue->first-on-cue-poke latency,
                                   group mean +- SEM per session, one line per task
  cue_to_first_poke_latency.csv    per-session mean latency + n engaged trials
  session_phenotype_metrics.csv    tidy per-session table
  first_vs_last_by_mouse.csv       early/late/delta per mouse and metric
  learning_trajectories_summary.txt

Usage:
  python3 learning_trajectories_analysis.py --task appetitive
  python3 learning_trajectories_analysis.py --task both
"""
from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np

import trial_history_analysis as TH  # loaders + task constants/colors (reused)

# distinct line style per task so a mouse's colour stays constant across tasks
_TASK_LS = {TH.TASK_APP: "-", TH.TASK_GEN: "--"}

NAN = float("nan")
_RESULTS_ROOT = Path(__file__).resolve().parent / "results"
_TASK_AREA = {"appetitive": "appetitive", "generalization": "generalization", "both": "cross_task"}
_ENV_OUT = os.environ.get("MICS_TRAJ_OUT")
OUT_ROOT = _ENV_OUT or str(_RESULTS_ROOT / "learning_trajectories" / "cross_task")

MIN_BOUT = int(os.environ.get("MICS_MIN_BOUT", "4"))

# (key, display label, mature_high) — mature_high=False means lower is "more learned"
# (latency, off-cue), which is inverted when orienting the radar / learning index.
METRICS = [
    ("engagement", "engagement %", True),
    ("competence", "accuracy | engaged %", True),
    ("hit_rate", "hit rate %", True),
    ("bout_coverage", "in-bout trials % (persistence)", True),
    ("latency", "latency to engage (s)", False),
    ("offcue", "off-cue pokes / trial", False),
    ("win_stay", "reward-gating (win-stay)", True),
]
# win-stay's "learned" direction is ambiguous, so it is shown in the trajectory
# grid but left out of the oriented radar / composite learning index.
RADAR_METRICS = [m for m in METRICS if m[0] != "win_stay"]


def _bout_lengths(engaged_seq: list[bool], min_len: int = MIN_BOUT) -> list[int]:
    """Lengths of maximal runs of consecutive engaged trials that are >= min_len."""
    runs, run = [], 0
    for e in list(engaged_seq) + [False]:
        if e:
            run += 1
        else:
            if run >= min_len:
                runs.append(run)
            run = 0
    return runs


def session_metrics(trials: list[dict]) -> dict:
    """Per-session phenotype metrics from enriched trial-history records."""
    n = len(trials)
    eng = [bool(t["engaged"]) for t in trials]
    n_eng = sum(eng)
    eng_rew = [t["rewarded"] for t in trials if t["engaged"]]
    lat = [t["cue_to_poke_latency"] for t in trials
           if t["engaged"] and not np.isnan(t["cue_to_poke_latency"])]
    after_hit = [t["engaged"] for t in trials if t["previous_rewarded"] is True]
    after_miss = [t["engaged"] for t in trials if t["previous_rewarded"] is False]
    lengths = _bout_lengths(eng)
    win_stay = (100 * np.mean(after_hit) - 100 * np.mean(after_miss)) \
        if after_hit and after_miss else NAN
    return {
        "engagement": 100.0 * n_eng / n if n else NAN,
        "competence": 100.0 * float(np.mean(eng_rew)) if eng_rew else NAN,
        "hit_rate": 100.0 * sum(t["rewarded"] for t in trials) / n if n else NAN,
        "bout_coverage": 100.0 * sum(lengths) / n if n else NAN,
        "latency": float(np.median(lat)) if lat else NAN,
        "offcue": float(np.mean([t["offcue_pokes_count"] for t in trials])) if n else NAN,
        "win_stay": float(win_stay),
    }


def build(records: list[dict]) -> dict[str, dict[str, list[dict]]]:
    """{task: {mouse: [per-session metric dicts ordered by session]}}."""
    out: dict[str, dict[str, list[dict]]] = {}
    for r in records:
        m = session_metrics(r["trials"])
        m["session"] = r["training_day"]
        out.setdefault(r["task"], {}).setdefault(r["mouse"], []).append(m)
    for by_mouse in out.values():
        for sessions in by_mouse.values():
            sessions.sort(key=lambda d: d["session"])
    return out


def _sorted_mice(by_mouse: dict) -> list[str]:
    return sorted(by_mouse, key=lambda m: int("".join(filter(str.isdigit, m)) or 0))


def first_poke_latency(records: list[dict]) -> dict[str, dict[str, list[dict]]]:
    """{task: {mouse: [{session, mean_latency, n_engaged}]}} — mean time from cue
    onset to the FIRST on-cue poke, averaged over that session's engaged trials
    (trials with a poke inside the cue window). Trials with no on-cue poke have no
    latency and are excluded, so this is the mean latency *when* the mouse engaged."""
    out: dict[str, dict[str, list[dict]]] = {}
    for r in records:
        lat = [t["cue_to_poke_latency"] for t in r["trials"]
               if t["engaged"] and not np.isnan(t["cue_to_poke_latency"])]
        out.setdefault(r["task"], {}).setdefault(r["mouse"], []).append({
            "session": r["training_day"],
            "mean_latency": float(np.mean(lat)) if lat else NAN,
            "n_engaged": len(lat),
        })
    for by_mouse in out.values():
        for sessions in by_mouse.values():
            sessions.sort(key=lambda d: d["session"])
    return out


def _window(n: int) -> int:
    """Early / late phase width: first & last quarter of sessions (>=1)."""
    return max(1, n // 4)


def early_late(sessions: list[dict], key: str) -> tuple[float, float]:
    vals = [s[key] for s in sessions if not np.isnan(s[key])]
    if not vals:
        return NAN, NAN
    w = _window(len(vals))
    return float(np.mean(vals[:w])), float(np.mean(vals[-w:]))


def _mean_sem(values: list[float]) -> tuple[float, float]:
    vals = [v for v in values if not np.isnan(v)]
    if not vals:
        return NAN, 0.0
    sem = float(np.std(vals, ddof=1) / np.sqrt(len(vals))) if len(vals) > 1 else 0.0
    return float(np.mean(vals)), sem


# --- figures ---------------------------------------------------------------
def _mouse_colors(by_task: dict) -> tuple[dict, list]:
    """A distinct, stable colour per mouse (tab10/tab20 by sorted mouse id)."""
    mice = sorted({m for by_mouse in by_task.values() for m in by_mouse},
                  key=lambda m: int("".join(filter(str.isdigit, m)) or 0))
    cmap = plt.get_cmap("tab10" if len(mice) <= 10 else "tab20")
    return {m: cmap(i % cmap.N) for i, m in enumerate(mice)}, mice


def _mouse_legend_handles(mcolors: dict, mice: list, tasks: list) -> list:
    handles = [Line2D([], [], color=mcolors[m], lw=2.5, label=m) for m in mice]
    if len(tasks) > 1:
        handles += [Line2D([], [], color="black", lw=2, ls=_TASK_LS.get(t, "-"),
                           label=TH.TASK_LABELS.get(t, t)) for t in tasks]
    handles.append(Line2D([], [], color="black", lw=3, label="group mean"))
    return handles


def _fill_legend_cell(axes, first_empty: int, ncol: int, handles: list) -> None:
    ax = axes[first_empty // ncol][first_empty % ncol]
    ax.axis("off")
    ax.legend(handles=handles, loc="center", ncol=2, fontsize=8, frameon=False,
              handlelength=1.6, columnspacing=1.0)


def fig_trajectories(by_task: dict, out_path: str) -> None:
    """Each metric vs session: one coloured line per mouse (task = line style),
    plus a bold black group-mean line."""
    mcolors, mice = _mouse_colors(by_task)
    ncol = 3
    nrow = int(np.ceil((len(METRICS) + 1) / ncol))  # +1 cell for the mouse legend
    fig, axes = plt.subplots(nrow, ncol, figsize=(4.8 * ncol, 3.1 * nrow), squeeze=False)
    single = len(by_task) == 1
    for idx, (key, label, _) in enumerate(METRICS):
        ax = axes[idx // ncol][idx % ncol]
        for task in by_task:
            ls = "-" if single else _TASK_LS.get(task, "-")
            per_session: dict[int, list] = {}
            for m, sessions in by_task[task].items():
                ax.plot([s["session"] for s in sessions], [s[key] for s in sessions],
                        color=mcolors[m], ls=ls, alpha=0.85, lw=1.3, marker="o", ms=2.5)
                for s in sessions:
                    if not np.isnan(s[key]):
                        per_session.setdefault(s["session"], []).append(s[key])
            xs = sorted(per_session)
            ax.plot(xs, [np.mean(per_session[sn]) for sn in xs], color="black",
                    ls=ls, lw=2.6, zorder=6)
        ax.set_title(label, fontsize=10)
        ax.set_xlabel("session", fontsize=8)
        ax.grid(alpha=0.3)
    for j in range(len(METRICS), nrow * ncol):
        axes[j // ncol][j % ncol].axis("off")
    _fill_legend_cell(axes, len(METRICS), ncol,
                      _mouse_legend_handles(mcolors, mice, list(by_task)))
    fig.suptitle("Phenotype trajectories across sessions (one colour = one mouse, "
                 "bold black = group mean)", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


def fig_slopes(by_task: dict, out_path: str) -> None:
    """Early-phase vs late-phase per mouse, per metric — one coloured line per
    mouse (task = line style), bold black = group mean."""
    mcolors, mice = _mouse_colors(by_task)
    ncol = 4
    nrow = int(np.ceil((len(METRICS) + 1) / ncol))  # +1 cell for the mouse legend
    fig, axes = plt.subplots(nrow, ncol, figsize=(3.2 * ncol, 3.0 * nrow), squeeze=False)
    single = len(by_task) == 1
    for idx, (key, label, _) in enumerate(METRICS):
        ax = axes[idx // ncol][idx % ncol]
        for task in by_task:
            ls = "-" if single else _TASK_LS.get(task, "-")
            for m, sessions in by_task[task].items():
                e, l = early_late(sessions, key)
                if np.isnan(e) or np.isnan(l):
                    continue
                ax.plot([0, 1], [e, l], ls=ls, color=mcolors[m], alpha=0.8, lw=1.5,
                        marker="o", ms=4)
            em, _ = _mean_sem([early_late(s, key)[0] for s in by_task[task].values()])
            lm, _ = _mean_sem([early_late(s, key)[1] for s in by_task[task].values()])
            ax.plot([0, 1], [em, lm], ls=ls, color="black", lw=3, marker="o", ms=6, zorder=6)
        ax.set_xticks([0, 1])
        ax.set_xticklabels(["early", "late"], fontsize=8)
        ax.set_title(label, fontsize=9)
        ax.grid(axis="y", alpha=0.3)
        ax.margins(x=0.2)
    for j in range(len(METRICS), nrow * ncol):
        axes[j // ncol][j % ncol].axis("off")
    _fill_legend_cell(axes, len(METRICS), ncol,
                      _mouse_legend_handles(mcolors, mice, list(by_task)))
    fig.suptitle("Early vs late phase per mouse (one colour = one mouse, "
                 "bold black = group mean)", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


def _metric_range(by_task: dict, key: str) -> tuple[float, float]:
    vals = [s[key] for by_mouse in by_task.values() for ms in by_mouse.values()
            for s in ms if not np.isnan(s[key])]
    return (min(vals), max(vals)) if vals else (0.0, 1.0)


def _orient(v: float, lo: float, hi: float, mature_high: bool) -> float:
    if np.isnan(v) or hi <= lo:
        return NAN
    z = (v - lo) / (hi - lo)
    return z if mature_high else 1.0 - z


def fig_radar(by_task: dict, out_path: str) -> None:
    """Group phenotype shape, early vs late. Every axis oriented so OUTWARD = more
    mature (latency & off-cue inverted). One polar panel per task."""
    tasks = list(by_task)
    ranges = {k: _metric_range(by_task, k) for k, _, _ in RADAR_METRICS}
    labels = [lbl for _, lbl, _ in RADAR_METRICS]
    angles = np.linspace(0, 2 * np.pi, len(RADAR_METRICS), endpoint=False)
    closed = np.concatenate([angles, angles[:1]])
    fig, axes = plt.subplots(1, len(tasks), subplot_kw={"polar": True},
                             figsize=(5.2 * len(tasks), 5.2), squeeze=False)
    for ax, task in zip(axes[0], tasks):
        for phase, style in (("early", dict(color="#8888ff")), ("late", dict(color=TH.TASK_COLORS.get(task, "#c00")))):
            profile = []
            for key, _, mature_high in RADAR_METRICS:
                idx = 0 if phase == "early" else 1
                vals = [early_late(s, key)[idx] for s in by_task[task].values()]
                m, _ = _mean_sem(vals)
                lo, hi = ranges[key]
                profile.append(_orient(m, lo, hi, mature_high))
            vals = np.array(profile + profile[:1])
            ax.plot(closed, vals, "-o", ms=4, label=phase, **style)
            ax.fill(closed, vals, alpha=0.12, color=style["color"])
        ax.set_xticks(angles)
        ax.set_xticklabels(labels, fontsize=7)
        ax.set_ylim(0, 1)
        ax.set_yticklabels([])
        ax.set_title(TH.TASK_LABELS.get(task, task), fontsize=10)
        ax.legend(loc="upper right", bbox_to_anchor=(1.15, 1.1), fontsize=8)
    fig.suptitle("Phenotype profile: early vs late (outward = more mature)", fontsize=12)
    fig.tight_layout()
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


def _learning_index(sessions: list[dict], ranges: dict) -> list[float]:
    """Composite maturity per session: mean of oriented-normalized core metrics."""
    out = []
    for s in sessions:
        oriented = [_orient(s[k], *ranges[k], mature_high) for k, _, mature_high in RADAR_METRICS]
        oriented = [v for v in oriented if not np.isnan(v)]
        out.append(float(np.mean(oriented)) if oriented else NAN)
    return out


def fig_learning_index(by_task: dict, out_path: str) -> None:
    """Per-mouse composite learning index across sessions (heatmap). Deepening
    colour left->right = the mouse maturing; one block of rows per task."""
    tasks = list(by_task)
    ranges = {k: _metric_range(by_task, k) for k, _, _ in RADAR_METRICS}
    rows, ylabels = [], []
    max_s = 1
    for task in tasks:
        for m in _sorted_mice(by_task[task]):
            sessions = by_task[task][m]
            idx = {s["session"]: v for s, v in zip(sessions, _learning_index(sessions, ranges))}
            max_s = max(max_s, max(idx, default=1))
            rows.append(idx)
            ylabels.append(f"{m}" if len(tasks) == 1 else f"{'A' if task == TH.TASK_APP else 'G'}·{m}")
    mat = np.full((len(rows), max_s), np.nan)
    for r, idx in enumerate(rows):
        for sn, v in idx.items():
            mat[r, sn - 1] = v
    fig, ax = plt.subplots(figsize=(max(7, 0.5 * max_s + 2), 0.42 * len(rows) + 1.6))
    im = ax.imshow(np.ma.masked_invalid(mat), aspect="auto", cmap="viridis", vmin=0, vmax=1)
    ax.set_xticks(range(max_s))
    ax.set_xticklabels(range(1, max_s + 1), fontsize=7)
    ax.set_yticks(range(len(ylabels)))
    ax.set_yticklabels(ylabels, fontsize=7)
    ax.set_xlabel("session")
    fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02, label="learning index (0 = early-like, 1 = mature)")
    ax.set_title("Composite learning index per mouse across sessions")
    fig.tight_layout()
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


def _latency_bounds(lat_bt: dict) -> tuple[float, float]:
    vals = [s["mean_latency"] for bm in lat_bt.values() for ss in bm.values()
            for s in ss if not np.isnan(s["mean_latency"])]
    return (min(vals), max(vals)) if vals else (0.0, 1.0)


def fig_latency_group(lat_bt: dict, out_path: str) -> None:
    """Group mean ± SEM latency vs session, one bold line per task — the clean
    overall-trend view, no per-mouse clutter."""
    fig, ax = plt.subplots(figsize=(8.4, 5.2))
    for task in lat_bt:
        bm = lat_bt[task]
        max_s = max((s["session"] for ss in bm.values() for s in ss), default=1)
        xs, means, sems = [], [], []
        for day in range(1, max_s + 1):
            mean, sem = _mean_sem([s["mean_latency"] for ss in bm.values()
                                   for s in ss if s["session"] == day])
            if np.isnan(mean):
                continue
            xs.append(day); means.append(mean); sems.append(sem)
        xs, means, sems = np.array(xs), np.array(means), np.array(sems)
        color = TH.TASK_COLORS.get(task, "#555")
        ax.plot(xs, means, "-o", color=color, lw=2.8, ms=6, zorder=5,
                label=TH.TASK_LABELS.get(task, task))
        ax.fill_between(xs, means - sems, means + sems, color=color, alpha=0.18, zorder=4)
    ax.set_xlabel("session #")
    ax.set_ylabel("latency to first on-cue poke (s)")
    ax.set_ylim(bottom=0)
    ax.xaxis.set_major_locator(plt.MaxNLocator(integer=True))
    ax.grid(alpha=0.3)
    ax.legend(fontsize=10)
    ax.set_title("Time from cue onset to first on-cue poke — group mean ± SEM")
    fig.tight_layout()
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


# --- writers ---------------------------------------------------------------
def write_latency_csv(lat_bt: dict, path: str) -> None:
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["task", "mouse", "session", "mean_latency_to_first_oncue_poke_s",
                    "n_engaged_trials"])
        for task in lat_bt:
            for m in _sorted_mice(lat_bt[task]):
                for s in lat_bt[task][m]:
                    w.writerow([task, m, s["session"],
                                "" if np.isnan(s["mean_latency"]) else f"{s['mean_latency']:.3f}",
                                s["n_engaged"]])


def write_session_csv(by_task: dict, path: str) -> None:
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["task", "mouse", "session"] + [k for k, _, _ in METRICS])
        for task in by_task:
            for m in _sorted_mice(by_task[task]):
                for s in by_task[task][m]:
                    w.writerow([task, m, s["session"]] +
                               [f"{s[k]:.3f}" if not np.isnan(s[k]) else "" for k, _, _ in METRICS])


def write_first_last_csv(by_task: dict, path: str) -> None:
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["task", "mouse", "metric", "early", "late", "delta"])
        for task in by_task:
            for m in _sorted_mice(by_task[task]):
                for key, _, _ in METRICS:
                    e, l = early_late(by_task[task][m], key)
                    delta = l - e if not (np.isnan(e) or np.isnan(l)) else NAN
                    w.writerow([task, m, key,
                                f"{e:.3f}" if not np.isnan(e) else "",
                                f"{l:.3f}" if not np.isnan(l) else "",
                                f"{delta:.3f}" if not np.isnan(delta) else ""])


def write_summary(by_task: dict, path: str) -> None:
    lines = ["Learning trajectories: group early-phase -> late-phase change",
             "(early/late = first/last quarter of each mouse's sessions)", ""]
    for task in by_task:
        lines.append(f"## {TH.TASK_LABELS.get(task, task)}")
        for key, label, mature_high in METRICS:
            es = [early_late(s, key)[0] for s in by_task[task].values()]
            ls = [early_late(s, key)[1] for s in by_task[task].values()]
            em, _ = _mean_sem(es)
            lm, _ = _mean_sem(ls)
            if np.isnan(em) or np.isnan(lm):
                continue
            arrow = "up" if lm > em else "down"
            good = "" if key == "win_stay" else (
                "  (toward mature)" if ((lm > em) == mature_high) else "  (away from mature)")
            lines.append(f"  {label:26} {em:7.1f} -> {lm:7.1f}  ({arrow} {abs(lm - em):.1f}){good}")
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
        OUT_ROOT = str(_RESULTS_ROOT / "learning_trajectories" / _TASK_AREA[args.task])

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

    by_task = build(records)
    os.makedirs(OUT_ROOT, exist_ok=True)
    write_session_csv(by_task, os.path.join(OUT_ROOT, "session_phenotype_metrics.csv"))
    write_first_last_csv(by_task, os.path.join(OUT_ROOT, "first_vs_last_by_mouse.csv"))
    fig_trajectories(by_task, os.path.join(OUT_ROOT, "trajectories_by_metric.png"))
    fig_slopes(by_task, os.path.join(OUT_ROOT, "first_vs_last_slopes.png"))
    fig_radar(by_task, os.path.join(OUT_ROOT, "phenotype_radar.png"))
    fig_learning_index(by_task, os.path.join(OUT_ROOT, "learning_index_heatmap.png"))

    lat_bt = first_poke_latency(records)
    fig_latency_group(lat_bt, os.path.join(OUT_ROOT, "cue_to_first_poke_latency_group.png"))
    write_latency_csv(lat_bt, os.path.join(OUT_ROOT, "cue_to_first_poke_latency.csv"))

    write_summary(by_task, os.path.join(OUT_ROOT, "learning_trajectories_summary.txt"))

    n_sess = sum(len(s) for by_mouse in by_task.values() for s in by_mouse.values())
    print(f"\nWrote 3 CSVs, 7 figures, and summary.txt under '{OUT_ROOT}/' "
          f"({n_sess} sessions).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
