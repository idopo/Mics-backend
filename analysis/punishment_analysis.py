#!/usr/bin/env python3
"""ITI-punishment (false-alarm) analysis for the appetitive (tone) and
generalization (light) tasks.

Task structure (from the Pi FSM, AppetitiveTaskReal / Genralization):
after the response the mouse must wait out an inter-trial interval drawn from
ITI_center ± ITI_range (= 30 ± 5 → 25–35 s). If it nose-pokes DURING that wait
it is a FALSE ALARM: the ITI timer is cancelled and restarted with a punishment
(the remaining time, but at least min_punish_time = 10 s), so poking early makes
the wait longer. Each such poke is logged as a `state_ITI_nose_poke` transition.

A trial is PUNISHED here if it contains at least one `state_ITI_nose_poke`
(i.e. the mouse poked before its ITI finished and had time added). We count them
directly from that state transition, segmented into trials, so the number is
exactly what the task scored — not inferred from poke timing.

Reuses the ES access / session ordering in appetitive_analysis /
generalization_analysis (the false-alarm count now rides along on each
segmented trial), so the session set matches every other analysis.

Outputs (under results/punishment/<area>/, area = appetitive | generalization |
cross_task for --task both; override root with MICS_PUNISH_OUT):
    punishment_rate_curve.png   % punished trials across sessions (per mouse + group)
    punishment_by_mouse.png     per-mouse mean % punished (dots = sessions)
    punishment_map.png          heat map: % punished trials per mouse x session
    punishment_by_trial_curve.png  % punished + FA/trial vs trial position in session
    punishment_by_trial_per_mouse.png  same, one panel per mouse (tone + light)
    punishment_trial_session_map.png  per mouse: FA count per trial x session
    punishment_by_session.csv / punishment_by_mouse.csv / punishment_by_trial_position.csv
    punishment_summary.txt

Usage:
    python3 punishment_analysis.py --task appetitive
    python3 punishment_analysis.py --task both
"""
from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator, PercentFormatter
import numpy as np

import appetitive_analysis as A
import generalization_analysis as G
import trial_history_analysis as TH  # task constants / colours / labels (reused)

NAN = float("nan")
_RESULTS_ROOT = Path(__file__).resolve().parent / "results"
_TASK_AREA = {"appetitive": "appetitive", "generalization": "generalization", "both": "cross_task"}
_ENV_OUT = os.environ.get("MICS_PUNISH_OUT")
OUT_ROOT = _ENV_OUT or str(_RESULTS_ROOT / "punishment" / "cross_task")


# --- loaders (keep raw trials so the punished / n_false_alarms fields survive) --
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
            records.append({"task": TH.TASK_APP, "mouse": mouse, "session": day, "trials": trials})
    return records


def load_generalization(only_mouse: str | None) -> list[dict]:
    records = []
    for mouse, subjects in G.discover_mice().items():
        if only_mouse and mouse != only_mouse:
            continue
        for r in G.collect_mouse(subjects):
            records.append({"task": TH.TASK_GEN, "mouse": mouse,
                            "session": r["session_num"], "trials": r["trials"]})
    return records


# --- per-session punishment tally ------------------------------------------
def session_punishment(record: dict) -> dict:
    trials = record["trials"]
    n = len(trials)
    n_punished = sum(1 for t in trials if t["punished"])
    n_fa = sum(t["n_false_alarms"] for t in trials)
    return {
        "task": record["task"], "mouse": record["mouse"], "session": record["session"],
        "n_trials": n,
        "n_punished": n_punished,
        "pct_punished": 100.0 * n_punished / n if n else NAN,
        "total_false_alarms": n_fa,
        "false_alarms_per_trial": n_fa / n if n else NAN,
    }


def by_task_mouse(records: list[dict]) -> dict:
    out: dict = {}
    for r in records:
        s = session_punishment(r)
        out.setdefault(s["task"], {}).setdefault(s["mouse"], []).append(s)
    for by_mouse in out.values():
        for ss in by_mouse.values():
            ss.sort(key=lambda s: s["session"])
    return out


def _sorted_mice(names) -> list[str]:
    return sorted(names, key=lambda m: int("".join(filter(str.isdigit, m)) or 0))


def _mean_sem(values) -> tuple[float, float]:
    vals = [v for v in values if not np.isnan(v)]
    if not vals:
        return NAN, 0.0
    m = float(np.mean(vals))
    sem = float(np.std(vals, ddof=1) / np.sqrt(len(vals))) if len(vals) > 1 else 0.0
    return m, sem


# --- figures ---------------------------------------------------------------
def fig_rate_curve(by_task: dict, out_path: str) -> None:
    """% punished trials across sessions: per-mouse lines + group mean ± SEM."""
    tasks = list(by_task)
    fig, axes = plt.subplots(1, len(tasks), figsize=(6.5 * len(tasks), 5.2),
                             sharey=True, squeeze=False)
    cmap = plt.get_cmap("tab10")
    for ax, task in zip(axes[0], tasks):
        bm = by_task[task]
        mice = _sorted_mice(bm)
        max_s = max((s["session"] for ss in bm.values() for s in ss), default=1)
        for i, m in enumerate(mice):
            ss = bm[m]
            ax.plot([s["session"] for s in ss], [s["pct_punished"] for s in ss],
                    "-o", color=cmap(i % 10), lw=1.4, ms=4, alpha=0.7, label=m)
        xs, means, sems = [], [], []
        for day in range(1, max_s + 1):
            mean, sem = _mean_sem([s["pct_punished"] for ss in bm.values()
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
    axes[0][0].set_ylabel("punished trials (poked during ITI)")
    fig.suptitle("ITI punishment rate across sessions — trials where the mouse "
                 "poked before the ITI ended")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


def fig_by_mouse(by_task: dict, out_path: str) -> None:
    """Per-mouse mean % punished trials (bar = mean over sessions, dots = sessions)."""
    tasks = list(by_task)
    mice = _sorted_mice(set().union(*[set(by_task[t]) for t in tasks]))
    x = np.arange(len(mice), dtype=float)
    width = 0.8 / max(len(tasks), 1)
    fig, ax = plt.subplots(figsize=(max(9, 1.1 * len(mice)), 5.2))
    for ti, task in enumerate(tasks):
        color = TH.TASK_COLORS.get(task, "#555555")
        offs = x + (ti - (len(tasks) - 1) / 2) * width
        means, sems = [], []
        for xi, m in zip(offs, mice):
            per = [s["pct_punished"] for s in by_task[task].get(m, [])]
            mean, sem = _mean_sem(per)
            means.append(mean); sems.append(sem)
            vals = [v for v in per if not np.isnan(v)]
            jit = (np.arange(len(vals)) - (len(vals) - 1) / 2) * (width * 0.12)
            ax.scatter(np.full(len(vals), xi) + jit, vals, s=10, color=color,
                       alpha=0.35, zorder=3, linewidths=0)
        ax.bar(offs, means, width=width * 0.9, color=color, alpha=0.55,
               yerr=sems, capsize=2, zorder=2, label=TH.TASK_LABELS.get(task, task))
    ax.set_xticks(x); ax.set_xticklabels(mice, rotation=45, ha="right")
    ax.set_ylabel("punished trials (poked during ITI)")
    ax.set_ylim(0, 100)
    ax.yaxis.set_major_formatter(PercentFormatter(xmax=100))
    ax.grid(axis="y", alpha=0.3)
    if len(tasks) > 1:
        ax.legend(fontsize=9, loc="upper left")
    ax.set_title("Per-mouse ITI-punishment rate (bar = mean over sessions, dots = sessions)")
    fig.tight_layout()
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


def fig_map(by_task: dict, out_path: str) -> None:
    """Heat MAP: % punished trials per mouse (rows) x session (cols). One map per
    task. Grey = no session for that mouse at that number."""
    tasks = list(by_task)
    fig, axes = plt.subplots(len(tasks), 1, figsize=(11, 3.4 * len(tasks) + 1), squeeze=False)
    for ti, task in enumerate(tasks):
        bm = by_task[task]
        mice = _sorted_mice(bm)
        max_s = max((s["session"] for ss in bm.values() for s in ss), default=1)
        mat = np.full((len(mice), max_s), np.nan)
        for i, m in enumerate(mice):
            for s in bm[m]:
                mat[i, s["session"] - 1] = s["pct_punished"]
        ax = axes[ti][0]
        cmap = plt.get_cmap("Reds").copy()
        cmap.set_bad("#e8e8e8")
        im = ax.imshow(np.ma.masked_invalid(mat), aspect="auto", cmap=cmap,
                       vmin=0, vmax=max(np.nanmax(mat), 1), origin="upper")
        ax.set_yticks(range(len(mice)))
        ax.set_yticklabels(mice, fontsize=9)
        ax.set_xticks(range(max_s))
        ax.set_xticklabels(range(1, max_s + 1), fontsize=8)
        ax.set_xlabel("session #")
        ax.set_title(f"{TH.TASK_LABELS.get(task, task)} — % punished trials")
        for i in range(len(mice)):  # annotate each cell
            for j in range(max_s):
                if not np.isnan(mat[i, j]):
                    ax.text(j, i, f"{mat[i, j]:.0f}", ha="center", va="center",
                            fontsize=6.5, color="black" if mat[i, j] < 55 else "white")
        fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02, label="% punished")
    fig.suptitle("Which mice got punished, per session (poked during the ITI → ITI extended)")
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


# --- (by trial position within a session) ----------------------------------
def records_by_task_mouse(records: list[dict]) -> dict:
    out: dict = {}
    for r in records:
        out.setdefault(r["task"], {}).setdefault(r["mouse"], []).append(r)
    for bm in out.values():
        for rs in bm.values():
            rs.sort(key=lambda r: r["session"])
    return out


def _trial_position_matrix(records: list[dict], field: str, max_i: int) -> np.ndarray:
    """Per-session vector (len max_i) of `field` at each trial index, NaN-padded."""
    rows = []
    for r in records:
        v = np.full(max_i, np.nan)
        for i, t in enumerate(r["trials"]):
            v[i] = (1.0 if t["punished"] else 0.0) if field == "punished" else t["n_false_alarms"]
        rows.append(v)
    return np.array(rows) if rows else np.zeros((0, max_i))


def _group_by_index(bm: dict, field: str, scale: float):
    """Per trial index: group mean ± SEM (computed across mice) and session
    coverage, for either the punished fraction (scale=100) or FA count."""
    mice = _sorted_mice(bm)
    max_i = max((len(r["trials"]) for rs in bm.values() for r in rs), default=1)
    per_mouse = np.full((len(mice), max_i), np.nan)
    cov = np.zeros(max_i)
    for mi, m in enumerate(mice):
        mat = _trial_position_matrix(bm[m], field, max_i)
        cov += np.sum(~np.isnan(mat), axis=0)
        with np.errstate(invalid="ignore"):
            per_mouse[mi] = np.nanmean(mat, axis=0) * scale
    with np.errstate(invalid="ignore"):
        mean = np.nanmean(per_mouse, axis=0)
        n = np.sum(~np.isnan(per_mouse), axis=0)
        sd = np.nanstd(per_mouse, axis=0, ddof=1)
    sem = np.where(n > 1, sd / np.sqrt(np.maximum(n, 1)), 0.0)
    return np.arange(1, max_i + 1), mean, sem, cov, sum(len(rs) for rs in bm.values())


def fig_by_trial_curve(rec_bt: dict, out_path: str) -> None:
    """Punishment across trial position in the session: % punished (top) and
    mean false alarms per trial = how much ITI is added (bottom). Group mean ±
    SEM over mice; only trial indices reached by >=40% of sessions are drawn."""
    tasks = list(rec_bt)
    fig, axes = plt.subplots(2, len(tasks), figsize=(6.4 * len(tasks), 7.4),
                             squeeze=False, sharex=True)
    specs = [("punished", 100.0, "punished trials", True),
             ("n_false_alarms", 1.0, "false alarms per trial (ITI additions)", False)]
    for col, task in enumerate(tasks):
        for row, (field, scale, ylabel, is_pct) in enumerate(specs):
            ax = axes[row][col]
            x, mean, sem, cov, total = _group_by_index(rec_bt[task], field, scale)
            valid = cov >= 0.4 * total
            xv, mv, sv = x[valid], mean[valid], sem[valid]
            color = TH.TASK_COLORS.get(task, "#555555")
            ax.plot(xv, mv, "-o", color=color, ms=3, lw=1.7)
            ax.fill_between(xv, mv - sv, mv + sv, color=color, alpha=0.18)
            ax.grid(alpha=0.3)
            if row == 0:
                ax.set_title(TH.TASK_LABELS.get(task, task))
                ax.set_ylim(0, 100)
                ax.yaxis.set_major_formatter(PercentFormatter(xmax=100))
            else:
                ax.set_ylim(bottom=0)
                ax.set_xlabel("trial # within session")
            if col == 0:
                ax.set_ylabel(ylabel)
    fig.suptitle("ITI punishment by trial position in the session "
                 "(are they punished more on early or late trials?)")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


def fig_trial_session_map(rec_bt: dict, out_path: str) -> None:
    """Per (task, mouse) panel: sessions (rows) x trial index (cols), coloured by
    false-alarm count — literally which trials of which session added ITI."""
    panels = [(task, m) for task in rec_bt for m in _sorted_mice(rec_bt[task])]
    max_i = max((len(r["trials"]) for bm in rec_bt.values()
                 for rs in bm.values() for r in rs), default=1)
    allfa = [t["n_false_alarms"] for bm in rec_bt.values() for rs in bm.values()
             for r in rs for t in r["trials"]]
    vmax = max(2.0, float(np.percentile(allfa, 97))) if allfa else 2.0
    ncol = 5
    nrow = (len(panels) + ncol - 1) // ncol
    fig, axes = plt.subplots(nrow, ncol, figsize=(3.5 * ncol, 2.7 * nrow), squeeze=False)
    axes = axes.reshape(-1)
    cmap = plt.get_cmap("Reds").copy()
    cmap.set_bad("#e8e8e8")
    im = None
    for ax, (task, mouse) in zip(axes, panels):
        rs = rec_bt[task][mouse]
        mat = np.full((len(rs), max_i), np.nan)
        for si, r in enumerate(rs):
            for i, t in enumerate(r["trials"]):
                mat[si, i] = t["n_false_alarms"]
        im = ax.imshow(np.ma.masked_invalid(mat), aspect="auto", cmap=cmap,
                       vmin=0, vmax=vmax, origin="upper",
                       extent=(0.5, max_i + 0.5, len(rs) + 0.5, 0.5))
        ax.set_title(f"{mouse} · {'tone' if task == TH.TASK_APP else 'light'}", fontsize=8)
        ax.set_yticks(range(1, len(rs) + 1))
        ax.tick_params(labelsize=6)
    for ax in axes[len(panels):]:
        ax.axis("off")
    if im is not None:
        fig.colorbar(im, ax=axes.tolist(), fraction=0.015, pad=0.01,
                     label="false alarms in trial (ITI additions)")
    fig.supxlabel("trial # within session")
    fig.supylabel("session #")
    fig.suptitle("ITI punishment per trial, for each session (hotter = more ITI added)")
    fig.savefig(out_path, dpi=145, bbox_inches="tight")
    plt.close(fig)


def _mouse_index_curve(records: list[dict], field: str, scale: float, max_i: int):
    """Per trial index: mean of `field` across one mouse's sessions + coverage."""
    mat = _trial_position_matrix(records, field, max_i)
    cov = np.sum(~np.isnan(mat), axis=0)
    with np.errstate(invalid="ignore"):
        mean = np.nanmean(mat, axis=0) * scale
    return mean, cov


def fig_by_trial_per_mouse(rec_bt: dict, out_path: str) -> None:
    """Per-mouse small multiples of % punished vs trial position in the session
    (tone and light overlaid). Each line is that mouse's mean across its sessions;
    only indices reached by >=half of the mouse's sessions are drawn."""
    tasks = list(rec_bt)
    mice = _sorted_mice(set().union(*[set(rec_bt[t]) for t in tasks]))
    max_i = max((len(r["trials"]) for bm in rec_bt.values()
                 for rs in bm.values() for r in rs), default=1)
    ncol = 5
    nrow = (len(mice) + ncol - 1) // ncol
    fig, axes = plt.subplots(nrow, ncol, figsize=(3.4 * ncol, 2.6 * nrow),
                             squeeze=False, sharex=True, sharey=True)
    axes = axes.reshape(-1)
    x = np.arange(1, max_i + 1)
    for ax, mouse in zip(axes, mice):
        for task in tasks:
            if mouse not in rec_bt[task]:
                continue
            recs = rec_bt[task][mouse]
            mean, cov = _mouse_index_curve(recs, "punished", 100.0, max_i)
            valid = cov >= max(2, 0.5 * len(recs))
            ax.plot(x[valid], mean[valid], "-", color=TH.TASK_COLORS.get(task, "#555"),
                    lw=1.3, alpha=0.9, label=TH.TASK_LABELS.get(task, task))
        ax.set_title(mouse, fontsize=9)
        ax.set_ylim(0, 100)
        ax.yaxis.set_major_formatter(PercentFormatter(xmax=100))
        ax.grid(alpha=0.3)
    for ax in axes[len(mice):]:
        ax.axis("off")
    if len(tasks) > 1:
        axes[0].legend(fontsize=7, loc="lower right")
    fig.supxlabel("trial # within session")
    fig.supylabel("punished trials (poked during ITI)")
    fig.suptitle("ITI punishment by trial position — per mouse "
                 "(mean over that mouse's sessions)")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


def write_trial_position_csv(rec_bt: dict, path: str) -> None:
    cols = ["task", "trial_index", "n_sessions_reaching", "pct_punished",
            "mean_false_alarms"]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for task, bm in rec_bt.items():
            x, pun, _, cov, _ = _group_by_index(bm, "punished", 100.0)
            _, fa, _, _, _ = _group_by_index(bm, "n_false_alarms", 1.0)
            for i in range(len(x)):
                w.writerow({"task": task, "trial_index": int(x[i]),
                            "n_sessions_reaching": int(cov[i]),
                            "pct_punished": round(float(pun[i]), 2) if not np.isnan(pun[i]) else "",
                            "mean_false_alarms": round(float(fa[i]), 3) if not np.isnan(fa[i]) else ""})


# --- CSV / summary ---------------------------------------------------------
def write_session_csv(by_task: dict, path: str) -> None:
    cols = ["task", "mouse", "session", "n_trials", "n_punished", "pct_punished",
            "total_false_alarms", "false_alarms_per_trial"]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for bm in by_task.values():
            for ss in bm.values():
                for s in ss:
                    w.writerow({c: s[c] for c in cols})


def mouse_rows(by_task: dict) -> list[dict]:
    rows = []
    for task, bm in by_task.items():
        for m in _sorted_mice(bm):
            ss = bm[m]
            mean, sem = _mean_sem([s["pct_punished"] for s in ss])
            n_tr = sum(s["n_trials"] for s in ss)
            n_pun = sum(s["n_punished"] for s in ss)
            rows.append({
                "task": task, "mouse": m, "n_sessions": len(ss),
                "n_trials": n_tr, "n_punished": n_pun,
                "pct_punished_pooled": 100.0 * n_pun / n_tr if n_tr else NAN,
                "mean_pct_punished": mean, "sem_pct_punished": sem,
                "total_false_alarms": sum(s["total_false_alarms"] for s in ss),
            })
    return rows


def write_mouse_csv(rows: list[dict], path: str) -> None:
    cols = ["task", "mouse", "n_sessions", "n_trials", "n_punished",
            "pct_punished_pooled", "mean_pct_punished", "sem_pct_punished",
            "total_false_alarms"]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)


def write_summary(rows: list[dict], path: str) -> None:
    lines = ["# ITI punishment — trials where the mouse poked before the ITI ended\n",
             "punished trial = contains >=1 state_ITI_nose_poke (false alarm); "
             "ITI = 25-35s, each false alarm adds >=10s\n"]
    by_task: dict = {}
    for r in rows:
        by_task.setdefault(r["task"], []).append(r)
    for task, trs in by_task.items():
        lines.append(f"\n## {TH.TASK_LABELS.get(task, task)}  ({len(trs)} mice)")
        pooled = [r["pct_punished_pooled"] for r in trs if not np.isnan(r["pct_punished_pooled"])]
        if pooled:
            lines.append(f"group: {np.mean(pooled):.1f}% of trials punished "
                         f"(range {min(pooled):.1f}–{max(pooled):.1f}%)")
        for r in sorted(trs, key=lambda r: r["pct_punished_pooled"], reverse=True):
            lines.append(f"  {r['mouse']:>5}: {r['pct_punished_pooled']:5.1f}% of trials "
                         f"({r['n_punished']}/{r['n_trials']}) | {r['total_false_alarms']} "
                         f"false alarms over {r['n_sessions']} sessions")
    Path(path).write_text("\n".join(lines) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--task", choices=["appetitive", "generalization", "both"], default="both")
    parser.add_argument("--mouse", default=None, help="restrict to one mouse, e.g. m102")
    args = parser.parse_args()

    global OUT_ROOT
    if not _ENV_OUT:
        OUT_ROOT = str(_RESULTS_ROOT / "punishment" / _TASK_AREA[args.task])

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

    grouped = by_task_mouse(records)
    os.makedirs(OUT_ROOT, exist_ok=True)
    write_session_csv(grouped, os.path.join(OUT_ROOT, "punishment_by_session.csv"))
    rows = mouse_rows(grouped)
    write_mouse_csv(rows, os.path.join(OUT_ROOT, "punishment_by_mouse.csv"))
    fig_rate_curve(grouped, os.path.join(OUT_ROOT, "punishment_rate_curve.png"))
    fig_by_mouse(grouped, os.path.join(OUT_ROOT, "punishment_by_mouse.png"))
    fig_map(grouped, os.path.join(OUT_ROOT, "punishment_map.png"))

    rec_bt = records_by_task_mouse(records)
    fig_by_trial_curve(rec_bt, os.path.join(OUT_ROOT, "punishment_by_trial_curve.png"))
    fig_by_trial_per_mouse(rec_bt, os.path.join(OUT_ROOT, "punishment_by_trial_per_mouse.png"))
    fig_trial_session_map(rec_bt, os.path.join(OUT_ROOT, "punishment_trial_session_map.png"))
    write_trial_position_csv(rec_bt, os.path.join(OUT_ROOT, "punishment_by_trial_position.csv"))

    write_summary(rows, os.path.join(OUT_ROOT, "punishment_summary.txt"))

    n_sess = sum(len(ss) for bm in grouped.values() for ss in bm.values())
    print(f"\nWrote 3 CSVs, 6 figures, and summary.txt under '{OUT_ROOT}/' "
          f"({n_sess} sessions, {len(rows)} mouse-task rows).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
