#!/usr/bin/env python3
"""First-session vs last-session learner-phenotype transition (per task).

Classifies every mouse into a learning phenotype from its FIRST session alone,
then from its LAST session alone, and shows how each mouse moved. Phenotypes and
thresholds are the project's standard ones (reused from learner_criterion), but
evaluated on a single session instead of a multi-session trajectory:

  strong_learner              engages >= the task's strong bar AND accuracy >= 70%
  partial_learner             knows the rule (accuracy >= 60-70%), engages less
  competent_low_participation accurate when engaged (>= 80%) but engages < 50%
  impulsive_offcue_dominated  off-cue poking above cohort threshold, low competence
  non_learner                 low accuracy when engaged and low engagement

The phenotype lives in a 2-D map: x = engagement rate (participation),
y = accuracy-when-engaged (competence). Each mouse is drawn twice — an open
marker at its first session and a filled marker at its last — joined by an arrow,
so the picture is literally each mouse's movement through phenotype space.

Outputs (results/<area>/phenotype_transition/):
  phenotype_transition_map.png   engagement x competence map, first -> last arrows
  phenotype_transitions.csv      per-mouse first/last metrics + phenotype
  phenotype_transition_summary.txt

Usage:
  python3 phenotype_transition_analysis.py            # generalization (default)
  python3 phenotype_transition_analysis.py --task appetitive
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

import learner_criterion_analysis as LC  # loaders, thresholds, CLASSES (reused)

NAN = float("nan")
_RESULTS_ROOT = Path(__file__).resolve().parent / "results"
_TASK_AREA = {"appetitive": "appetitive", "generalization": "generalization"}
_ENV_OUT = os.environ.get("MICS_PHENO_OUT")
OUT_ROOT = _ENV_OUT or str(_RESULTS_ROOT / "generalization" / "phenotype_transition")


def first_last(by_mouse: dict) -> dict[str, tuple[dict, dict]]:
    """{mouse: (first_session_metrics, last_session_metrics)} (>= 2 sessions)."""
    out = {}
    for mouse, rows in by_mouse.items():
        if len(rows) >= 2:
            out[mouse] = (rows[0], rows[-1])
    return out


def _sorted_mice(mice) -> list[str]:
    return sorted(mice, key=lambda m: int("".join(filter(str.isdigit, m)) or 0))


# --- figure ----------------------------------------------------------------
def fig_transition_map(pheno: dict, task_label: str, out_path: str) -> None:
    """The core learner map (engagement x competence, styled like the
    learner_criterion map), with a first->last arrow per mouse: open marker =
    first session, filled coloured marker = last session (coloured by phenotype)."""
    fig, ax = plt.subplots(figsize=(8.4, 7.4))
    ax.axvline(LC.ENGAGE_THRESH, color="grey", ls="--", lw=1)
    ax.axhline(LC.ACC_STRONG, color="grey", ls="--", lw=1)
    ax.text(75, 102, "strong learners", fontsize=9, color="#2ca02c", ha="center")
    ax.text(22, 102, "knows rule,\nlow participation", fontsize=9, color="#1f77b4", ha="center")
    ax.text(25, 30, "non-learners", fontsize=9, color="#d62728", ha="center")

    for mouse in _sorted_mice(pheno):
        (ef, af, _, pf), (el, al, _, pl) = pheno[mouse]
        af_ = 0.0 if np.isnan(af) else af
        al_ = 0.0 if np.isnan(al) else al
        ax.annotate("", xy=(el, al_), xytext=(ef, af_),
                    arrowprops=dict(arrowstyle="-|>", color="#666", lw=1.4, alpha=0.85,
                                    shrinkA=7, shrinkB=9), zorder=2)
        ax.scatter([ef], [af_], s=95, facecolors="white",
                   edgecolors=LC.CLASSES[pf][1], linewidths=2, zorder=3)
        ax.scatter([el], [al_], s=135, color=LC.CLASSES[pl][1],
                   edgecolors="white", linewidths=0.9, zorder=4)
        ax.annotate(mouse, (el, al_), textcoords="offset points", xytext=(7, 4),
                    fontsize=8, zorder=5)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 105)
    ax.set_xlabel("engagement rate (%)  →  participation")
    ax.set_ylabel("accuracy when engaged (%)  →  competence")
    ax.set_title(task_label)
    handles = [Line2D([], [], marker="o", ls="", mfc="white", mec="black", mew=1.5,
                      markersize=9, label="first session"),
               Line2D([], [], marker="o", ls="", color="black", markersize=9,
                      label="last session")]
    handles += [Line2D([], [], marker="o", ls="", color=c, markersize=9, label=lab)
                for lab, c in LC.CLASSES.values()]
    fig.legend(handles=handles, loc="upper center", ncol=4, fontsize=8,
               bbox_to_anchor=(0.5, 0.95))
    fig.suptitle("Learner-phenotype shift: first → last session "
                 "(arrow = each mouse's move)", fontsize=13, y=1.0)
    fig.tight_layout(rect=(0, 0, 1, 0.88))
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


# --- writers ---------------------------------------------------------------
def write_csv(pheno: dict, path: str) -> None:
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["mouse", "engagement_first", "accuracy_first", "offcue_first",
                    "phenotype_first", "engagement_last", "accuracy_last",
                    "offcue_last", "phenotype_last", "changed"])
        for m in _sorted_mice(pheno):
            (ef, af, cf, pf), (el, al, cl, pl) = pheno[m]
            w.writerow([m, f"{ef:.1f}", "" if np.isnan(af) else f"{af:.1f}", f"{cf:.2f}", pf,
                        f"{el:.1f}", "" if np.isnan(al) else f"{al:.1f}", f"{cl:.2f}", pl,
                        "yes" if pf != pl else "no"])


def write_summary(pheno: dict, strong_engage: float, task_label: str, path: str) -> None:
    lines = [f"Phenotype transition (first -> last session) — {task_label}",
             f"strong-participation bar = {strong_engage:.0f}% engagement", ""]
    for m in _sorted_mice(pheno):
        (ef, af, cf, pf), (el, al, cl, pl) = pheno[m]
        moved = "  ==>  CHANGED" if pf != pl else ""
        lines.append(f"  {m:>5}: {LC.CLASSES[pf][0]:28} -> {LC.CLASSES[pl][0]:28}"
                     f"  (eng {ef:.0f}->{el:.0f}%, acc {af:.0f}->{al:.0f}%){moved}")
    Path(path).write_text("\n".join(lines))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--task", choices=["appetitive", "generalization"],
                        default="generalization")
    parser.add_argument("--mouse", default=None, help="restrict to one mouse")
    args = parser.parse_args()

    global OUT_ROOT
    if not _ENV_OUT:
        OUT_ROOT = str(_RESULTS_ROOT / _TASK_AREA[args.task] / "phenotype_transition")

    loader = LC.load_generalization if args.task == "generalization" else LC.load_appetitive
    by_mouse = loader(args.mouse)
    fl = first_last(by_mouse)
    if not fl:
        print("No mice with >= 2 sessions — nothing to do.")
        return 1

    # task-relative strong bar + impulsivity threshold from the LAST-session cohort
    # (identical frame to learner_criterion's engagement_vs_competence_last_session).
    last_eng = [last["engagement_rate"] for _, last in fl.values()]
    strong_engage = max(LC.ENGAGE_THRESH, float(np.median(last_eng)))
    impulsive_thr = LC._robust_impulsive_threshold(
        [last["offcue_pokes_per_trial"] for _, last in fl.values()])

    pheno: dict = {}
    for mouse, (first, last) in fl.items():
        pf = LC.classify_session(first["engagement_rate"], first["accuracy_when_engaged"],
                                 first["offcue_pokes_per_trial"], strong_engage, impulsive_thr)
        pl = LC.classify_session(last["engagement_rate"], last["accuracy_when_engaged"],
                                 last["offcue_pokes_per_trial"], strong_engage, impulsive_thr)
        pheno[mouse] = (
            (first["engagement_rate"], first["accuracy_when_engaged"],
             first["offcue_pokes_per_trial"], pf),
            (last["engagement_rate"], last["accuracy_when_engaged"],
             last["offcue_pokes_per_trial"], pl))

    task_label = {"generalization": "Generalization (light)",
                  "appetitive": "Appetitive (tone)"}[args.task]
    os.makedirs(OUT_ROOT, exist_ok=True)
    fig_transition_map(pheno, task_label,
                       os.path.join(OUT_ROOT, "phenotype_transition_map.png"))
    write_csv(pheno, os.path.join(OUT_ROOT, "phenotype_transitions.csv"))
    write_summary(pheno, strong_engage, task_label,
                  os.path.join(OUT_ROOT, "phenotype_transition_summary.txt"))
    n_moved = sum(1 for (_, _, _, pf), (_, _, _, pl) in pheno.values() if pf != pl)
    print(f"\nWrote 1 figure, 1 CSV, and summary.txt under '{OUT_ROOT}/' "
          f"({len(pheno)} mice, {n_moved} changed phenotype).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
