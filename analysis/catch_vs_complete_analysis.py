#!/usr/bin/env python3
"""Catch vs complete trials — consummatory licking and next-trial sequel.

Two questions, each per mouse and per task (appetitive tone / generalization
light):

  1. CONSUMMATORY LICKING — does the mouse lick more inside the response poke
     bout (poke-in -> poke-out) on a COMPLETE trial (reward delivered) than on a
     CATCH trial (on-cue poke + response lick, but no reward)? A reward should
     sustain licking; a catch should be cut short once the mouse finds the port
     empty. Uses the `bout_licks` metric from action_sequence_analysis.

  2. SEQUEL OUTCOME — after a catch trial, what does the mouse do on the *next*
     trial? Does it disengage (no on-cue poke) or engage? Compared against the
     next-trial distribution after a complete (rewarded) trial. Derived from each
     trial's `previous_trial_category`, so trial i+1 is scored by trial i's type.

Trial segmentation, categories, and `bout_licks` all come from
`action_sequence_analysis` (single source of truth). This script only aggregates
and plots.

Usage:
    python3 catch_vs_complete_analysis.py                  # both tasks
    python3 catch_vs_complete_analysis.py --task appetitive
    python3 catch_vs_complete_analysis.py --task generalization
"""
from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

import action_sequence_analysis as S

COMPLETE = "complete_sequence_rewarded"
CATCH = "cue_poke_lick_no_reward"
COLOR_COMPLETE = "#2ca02c"
COLOR_CATCH = "#e6a817"

_RESULTS_ROOT = Path(__file__).resolve().parent / "results"
_TASK_AREA = {"appetitive": "appetitive", "generalization": "generalization"}
_ENV_OUT = os.environ.get("MICS_CVC_OUT")

# category display order/colors for the sequel stacked bars (reuse the canonical set)
SEQUEL_ORDER = S.CATEGORY_KEYS
SEQUEL_COLORS = {k: c for k, _, c in S.CATEGORIES}
SEQUEL_LABELS = {k: lbl for k, lbl, _ in S.CATEGORIES}


def _mouse_num(mouse: str) -> int:
    digits = "".join(ch for ch in mouse if ch.isdigit())
    return int(digits) if digits else 0


def _load(task: str) -> dict[str, list[dict]]:
    """Return {mouse: [trials...]} for one task, mice sorted by number."""
    records = S.load_appetitive(None) if task == "appetitive" else S.load_generalization(None)
    by_mouse: dict[str, list[dict]] = {}
    for rec in records:
        by_mouse.setdefault(rec["mouse"], []).extend(rec["trials"])
    return {m: by_mouse[m] for m in sorted(by_mouse, key=_mouse_num)}


def _annotate_counts(ax, xs, heights, errs, counts) -> None:
    """Write trial-count labels just above each bar's error-bar cap."""
    for xi, h, e, n in zip(xs, heights, errs, counts):
        top = (0 if np.isnan(h) else h) + (0 if np.isnan(e) else e)
        ax.annotate(f"n={n}", (xi, top), textcoords="offset points", xytext=(0, 3),
                    ha="center", fontsize=7, color="#555")


def _sem(values: list[float]) -> float:
    return float(np.std(values, ddof=1) / np.sqrt(len(values))) if len(values) > 1 else 0.0


def _perm_pvalue(a: list[float], b: list[float], iters: int = 20000) -> float:
    """Two-sided permutation test on the difference of means (no scipy)."""
    if not a or not b:
        return float("nan")
    obs = abs(np.mean(a) - np.mean(b))
    pooled = np.array(a + b, dtype=float)
    n = len(a)
    rng = np.random.default_rng(0)
    hits = 0
    for _ in range(iters):
        rng.shuffle(pooled)
        if abs(pooled[:n].mean() - pooled[n:].mean()) >= obs:
            hits += 1
    return (hits + 1) / (iters + 1)


# --- analysis 1: consummatory licks ----------------------------------------
def consummatory_stats(by_mouse: dict[str, list[dict]]) -> list[dict]:
    """Per-mouse mean/SEM/n of bout_licks for complete vs catch trials."""
    rows: list[dict] = []
    for mouse, trials in by_mouse.items():
        comp = [t["bout_licks"] for t in trials if t["action_sequence_category"] == COMPLETE]
        catch = [t["bout_licks"] for t in trials if t["action_sequence_category"] == CATCH]
        rows.append({
            "mouse": mouse,
            "n_complete": len(comp), "mean_complete": np.mean(comp) if comp else float("nan"),
            "sem_complete": _sem(comp),
            "n_catch": len(catch), "mean_catch": np.mean(catch) if catch else float("nan"),
            "sem_catch": _sem(catch),
        })
    return rows


def plot_consummatory(rows: list[dict], task: str, out_dir: Path) -> None:
    """Grouped bars (complete vs catch mean bout licks) per mouse + pooled test."""
    mice = [r["mouse"] for r in rows]
    x = np.arange(len(mice))
    w = 0.38
    fig, ax = plt.subplots(figsize=(max(7, 1.1 * len(mice)), 5))
    ax.bar(x - w / 2, [r["mean_complete"] for r in rows], w, yerr=[r["sem_complete"] for r in rows],
           color=COLOR_COMPLETE, capsize=3, label="complete (rewarded)")
    ax.bar(x + w / 2, [r["mean_catch"] for r in rows], w, yerr=[r["sem_catch"] for r in rows],
           color=COLOR_CATCH, capsize=3, label="catch (no reward)")
    _annotate_counts(ax, x - w / 2, [r["mean_complete"] for r in rows],
                     [r["sem_complete"] for r in rows], [r["n_complete"] for r in rows])
    _annotate_counts(ax, x + w / 2, [r["mean_catch"] for r in rows],
                     [r["sem_catch"] for r in rows], [r["n_catch"] for r in rows])
    ax.set_xticks(x)
    ax.set_xticklabels(mice, rotation=45, ha="right")
    ax.set_ylabel("licks per response poke bout (poke-in → poke-out)")
    ax.set_title(f"Consummatory licking: complete vs catch — {S.TASK_LABELS.get(_task_key(task), task)}")
    ax.legend(frameon=False)
    ax.margins(y=0.15)
    fig.tight_layout()
    fig.savefig(out_dir / "consummatory_licks_by_mouse.png", dpi=150)
    plt.close(fig)


def plot_consummatory_paired(by_mouse: dict[str, list[dict]], rows: list[dict],
                             task: str, out_dir: Path) -> str:
    """Per-mouse slopegraph (complete vs catch) + pooled permutation p-value."""
    pooled_comp, pooled_catch = [], []
    for trials in by_mouse.values():
        pooled_comp += [t["bout_licks"] for t in trials if t["action_sequence_category"] == COMPLETE]
        pooled_catch += [t["bout_licks"] for t in trials if t["action_sequence_category"] == CATCH]
    p = _perm_pvalue(pooled_comp, pooled_catch)
    paired = [(r["mean_complete"], r["mean_catch"]) for r in rows
              if r["n_complete"] and r["n_catch"]]
    n_higher = sum(1 for c, k in paired if c > k)

    fig, ax = plt.subplots(figsize=(5, 5))
    for r in rows:
        if not (r["n_complete"] and r["n_catch"]):
            continue
        ax.plot([0, 1], [r["mean_complete"], r["mean_catch"]], "-o", color="#888", alpha=0.7, ms=4)
    if pooled_comp and pooled_catch:
        ax.plot([0, 1], [np.mean(pooled_comp), np.mean(pooled_catch)], "-o",
                color="#c0392b", lw=2.5, ms=7, label="pooled mean")
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["complete\n(rewarded)", "catch\n(no reward)"])
    ax.set_ylabel("mean licks per bout")
    subtitle = f"pooled p={p:.4f} (perm)  •  {n_higher}/{len(paired)} mice complete>catch"
    ax.set_title(f"{S.TASK_LABELS.get(_task_key(task), task)}\n{subtitle}", fontsize=10)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(out_dir / "consummatory_licks_paired.png", dpi=150)
    plt.close(fig)
    return (f"pooled complete n={len(pooled_comp)} mean={np.mean(pooled_comp):.2f}; "
            f"catch n={len(pooled_catch)} mean={np.mean(pooled_catch):.2f}; "
            f"perm p={p:.4f}; {n_higher}/{len(paired)} mice complete>catch")


# --- analysis 2: sequel outcome --------------------------------------------
def sequel_stats(by_mouse: dict[str, list[dict]]) -> list[dict]:
    """Per-mouse next-trial category distribution after complete vs after catch."""
    rows: list[dict] = []
    for mouse, trials in by_mouse.items():
        row: dict = {"mouse": mouse}
        for prev, tag in ((COMPLETE, "after_complete"), (CATCH, "after_catch")):
            nxt = [t for t in trials if t["previous_trial_category"] == prev]
            row[f"n_{tag}"] = len(nxt)
            row[f"p_engage_{tag}"] = (sum(1 for t in nxt if t["engaged"]) / len(nxt)) if nxt else float("nan")
            for key in SEQUEL_ORDER:
                frac = (sum(1 for t in nxt if t["action_sequence_category"] == key) / len(nxt)) if nxt else float("nan")
                row[f"{tag}__{key}"] = frac
        rows.append(row)
    return rows


def plot_sequel_distribution(rows: list[dict], task: str, out_dir: Path) -> None:
    """Per mouse: two stacked bars (after complete / after catch) over categories."""
    mice = [r["mouse"] for r in rows]
    x = np.arange(len(mice))
    w = 0.38
    fig, ax = plt.subplots(figsize=(max(8, 1.2 * len(mice)), 5.5))
    for offset, tag, hatch in ((-w / 2, "after_complete", None), (w / 2, "after_catch", "///")):
        bottom = np.zeros(len(mice))
        for key in SEQUEL_ORDER:
            vals = np.array([(r[f"{tag}__{key}"] if not np.isnan(r[f"{tag}__{key}"]) else 0.0) for r in rows])
            ax.bar(x + offset, vals, w, bottom=bottom, color=SEQUEL_COLORS[key], hatch=hatch,
                   edgecolor="white", linewidth=0.3)
            bottom += vals
    ax.set_xticks(x)
    ax.set_xticklabels([f"{m}" for m in mice], rotation=45, ha="right")
    ax.set_ylabel("P(next-trial category)")
    ax.set_ylim(0, 1)
    ax.set_title(f"Next-trial outcome after complete (left) vs catch (right, hatched) — "
                 f"{S.TASK_LABELS.get(_task_key(task), task)}", fontsize=10)
    handles = [plt.Rectangle((0, 0), 1, 1, color=SEQUEL_COLORS[k]) for k in SEQUEL_ORDER]
    ax.legend(handles, [SEQUEL_LABELS[k] for k in SEQUEL_ORDER], frameon=False,
              fontsize=7, loc="upper center", bbox_to_anchor=(0.5, -0.18), ncol=3)
    fig.tight_layout()
    fig.savefig(out_dir / "sequel_distribution.png", dpi=150)
    plt.close(fig)


def plot_sequel_engage(rows: list[dict], task: str, out_dir: Path) -> str:
    """Per mouse: P(engage next trial) after complete vs after catch + pooled note."""
    mice = [r["mouse"] for r in rows]
    x = np.arange(len(mice))
    w = 0.38
    fig, ax = plt.subplots(figsize=(max(7, 1.1 * len(mice)), 5))
    ax.bar(x - w / 2, [r["p_engage_after_complete"] for r in rows], w, color=COLOR_COMPLETE,
           label="after complete")
    ax.bar(x + w / 2, [r["p_engage_after_catch"] for r in rows], w, color=COLOR_CATCH,
           label="after catch")
    zeros = [0.0] * len(rows)
    _annotate_counts(ax, x - w / 2, [r["p_engage_after_complete"] for r in rows], zeros,
                     [r["n_after_complete"] for r in rows])
    _annotate_counts(ax, x + w / 2, [r["p_engage_after_catch"] for r in rows], zeros,
                     [r["n_after_catch"] for r in rows])
    ax.set_xticks(x)
    ax.set_xticklabels(mice, rotation=45, ha="right")
    ax.set_ylabel("P(engage on next trial = on-cue poke)")
    ax.set_ylim(0, 1)
    ax.set_title(f"Next-trial engagement after complete vs catch — "
                 f"{S.TASK_LABELS.get(_task_key(task), task)}", fontsize=10)
    ax.legend(frameon=False)
    ax.margins(y=0.15)
    fig.tight_layout()
    fig.savefig(out_dir / "sequel_engage_prob.png", dpi=150)
    plt.close(fig)

    tot = {tag: [0, 0] for tag in ("after_complete", "after_catch")}  # [engaged, total]
    for r in rows:
        for tag in tot:
            n = r[f"n_{tag}"]
            if n:
                tot[tag][0] += r[f"p_engage_{tag}"] * n
                tot[tag][1] += n
    parts = []
    for tag in ("after_complete", "after_catch"):
        eng, n = tot[tag]
        parts.append(f"{tag}: P(engage)={eng / n:.3f} (n={n})" if n else f"{tag}: n=0")
    return "; ".join(parts)


# --- orchestration ---------------------------------------------------------
def _task_key(task: str) -> str:
    return S.TASK_APP if task == "appetitive" else S.TASK_GEN


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def run_task(task: str) -> None:
    area = _TASK_AREA[task]
    out_dir = Path(_ENV_OUT) / area if _ENV_OUT else _RESULTS_ROOT / "catch_vs_complete" / area
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Loading {task} ...")
    by_mouse = _load(task)

    lick_rows = consummatory_stats(by_mouse)
    plot_consummatory(lick_rows, task, out_dir)
    lick_summary = plot_consummatory_paired(by_mouse, lick_rows, task, out_dir)
    _write_csv(out_dir / "consummatory_licks.csv", lick_rows)

    seq_rows = sequel_stats(by_mouse)
    plot_sequel_distribution(seq_rows, task, out_dir)
    seq_summary = plot_sequel_engage(seq_rows, task, out_dir)
    _write_csv(out_dir / "sequel_outcomes.csv", seq_rows)

    with open(out_dir / "summary.txt", "w") as f:
        f.write(f"CATCH vs COMPLETE — {S.TASK_LABELS.get(_task_key(task), task)}\n")
        f.write("=" * 60 + "\n\n")
        f.write("1. Consummatory licking (licks per response poke bout):\n   " + lick_summary + "\n\n")
        f.write("2. Next-trial engagement:\n   " + seq_summary + "\n")
    print(f"  {len(by_mouse)} mice — wrote 4 figures + 2 CSVs + summary.txt to {out_dir}")
    print("  [licks] " + lick_summary)
    print("  [sequel] " + seq_summary)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--task", choices=["appetitive", "generalization", "both"], default="both")
    args = ap.parse_args()
    tasks = ["appetitive", "generalization"] if args.task == "both" else [args.task]
    for t in tasks:
        run_task(t)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
