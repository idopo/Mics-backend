#!/usr/bin/env python3
"""Cross-task transition: AppetitveTaskReal (tone) -> Generalization (light).

How much did each mouse shift when the cue modality changed, and how fast did it
crack the new (light) rule? Two views, both under results/cross_task/:

1. PHENOTYPE TRANSITION — each mouse's LAST appetitive session vs its FIRST
   generalization session, plotted in the project's engagement x competence
   learner space (reusing learner_criterion's metrics + single-session
   classifier). Open marker = last tone session, filled = first light session,
   arrow = the shift. A big down-left arrow = the mouse "lost" the rule when the
   cue changed; a short arrow = it transferred.

2. GENERALIZATION FIRST-SESSION LEARNING ONSET — a per-mouse raster of the very
   first light session, with three onset lines detected by a CUSUM step finder:
     * rule onset          — the trial from which the hit rate steps up
     * on-cue poke onset    — the trial from which on-cue poking steps up
     * on-cue poke+lick onset — the trial from which on-cue poke+lick steps up
   i.e. where the mouse started to figure out the new rule and to engage the cue.

Outputs (under results/cross_task/appetitive_to_generalization/):
    phenotype_transition_map.png   last-tone -> first-light arrows in learner space
    gen_first_session_raster.png   per-mouse first-light raster + onset lines
    phenotype_transition.csv       per-mouse endpoints + phenotypes + shift
    learning_onset.csv             per-mouse onset trials (rule / poke / poke+lick)
    cross_task_transition_summary.txt

Usage:
    python3 cross_task_transition_analysis.py
"""
from __future__ import annotations

import csv
import os
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np

import generalization_analysis as G
import learner_criterion_analysis as LC

NAN = float("nan")
OUT_ROOT = os.environ.get(
    "MICS_XT_OUT",
    str(Path(__file__).resolve().parent / "results" / "cross_task" / "appetitive_to_generalization"))

# onset lines (kept distinct from the raster's green pokes / black licks / yellow reward)
RULE_COLOR = "#9467bd"       # hit-rate step-up
POKE_COLOR = "#ff7f0e"       # on-cue poke step-up
POKELICK_COLOR = "#17becf"   # on-cue poke+lick step-up


def _sorted_mice(mice) -> list[str]:
    return sorted(mice, key=lambda m: int("".join(filter(str.isdigit, m)) or 0))


# --- (1) cross-task phenotype transition -----------------------------------
def build_transition() -> dict:
    """{mouse: (last_appetitive_metrics, first_generalization_metrics)} for mice
    that have both a tone and a light session."""
    app = LC.load_appetitive(None)
    gen = LC.load_generalization(None)
    out = {}
    for mouse in app:
        if mouse in gen and app[mouse] and gen[mouse]:
            out[mouse] = (app[mouse][-1], gen[mouse][0])  # last tone, first light
    return out


def classify_endpoints(trans: dict) -> dict:
    """Classify both endpoints in one shared frame (strong-engagement bar +
    impulsivity threshold from the pooled endpoints), like the within-task map."""
    engs = [m["engagement_rate"] for pair in trans.values() for m in pair]
    offs = [m["offcue_pokes_per_trial"] for pair in trans.values() for m in pair]
    strong = max(LC.ENGAGE_THRESH, float(np.median(engs)))
    impulsive = LC._robust_impulsive_threshold(offs)
    pheno = {}
    for mouse, (a, g) in trans.items():
        pa = LC.classify_session(a["engagement_rate"], a["accuracy_when_engaged"],
                                 a["offcue_pokes_per_trial"], strong, impulsive)
        pg = LC.classify_session(g["engagement_rate"], g["accuracy_when_engaged"],
                                 g["offcue_pokes_per_trial"], strong, impulsive)
        pheno[mouse] = (a, g, pa, pg)
    return pheno, strong


def fig_transition_map(pheno: dict, strong: float, out_path: str) -> None:
    fig, ax = plt.subplots(figsize=(8.6, 7.6))
    ax.axvline(strong, color="grey", ls="--", lw=1)
    ax.axhline(LC.ACC_STRONG, color="grey", ls="--", lw=1)
    ax.text(78, 102, "strong learners", fontsize=9, color="#2ca02c", ha="center")
    ax.text(20, 102, "knows rule,\nlow participation", fontsize=9, color="#1f77b4", ha="center")
    ax.text(22, 6, "non-learners", fontsize=9, color="#d62728", ha="center")
    for mouse in _sorted_mice(pheno):
        a, g, pa, pg = pheno[mouse]
        ya = 0.0 if np.isnan(a["accuracy_when_engaged"]) else a["accuracy_when_engaged"]
        yg = 0.0 if np.isnan(g["accuracy_when_engaged"]) else g["accuracy_when_engaged"]
        ax.annotate("", xy=(g["engagement_rate"], yg), xytext=(a["engagement_rate"], ya),
                    arrowprops=dict(arrowstyle="-|>", color="#666", lw=1.5, alpha=0.85,
                                    shrinkA=7, shrinkB=9), zorder=2)
        ax.scatter([a["engagement_rate"]], [ya], s=95, facecolors="white",
                   edgecolors=LC.CLASSES[pa][1], linewidths=2, zorder=3)
        ax.scatter([g["engagement_rate"]], [yg], s=135, color=LC.CLASSES[pg][1],
                   edgecolors="white", linewidths=0.9, zorder=4)
        ax.annotate(mouse, (g["engagement_rate"], yg), textcoords="offset points",
                    xytext=(7, 4), fontsize=8, zorder=5)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 105)
    ax.set_xlabel("engagement rate (%)  →  participation")
    ax.set_ylabel("accuracy when engaged (%)  →  competence")
    handles = [Line2D([], [], marker="o", ls="", mfc="white", mec="black", mew=1.5,
                      markersize=9, label="last appetitive (tone) session"),
               Line2D([], [], marker="o", ls="", color="black", markersize=9,
                      label="first generalization (light) session")]
    handles += [Line2D([], [], marker="o", ls="", color=c, markersize=9, label=lab)
                for lab, c in LC.CLASSES.values()]
    fig.legend(handles=handles, loc="upper center", ncol=3, fontsize=8,
               bbox_to_anchor=(0.5, 0.96))
    fig.suptitle("Phenotype shift when the cue changed: last tone → first light "
                 "(arrow = each mouse's move)", fontsize=12, y=1.0)
    fig.tight_layout(rect=(0, 0, 1, 0.86))
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


# --- (2) generalization first-session learning onset -----------------------
def step_onset(x: list[float], min_rise: float = 0.15) -> int | None:
    """1-based trial where an upward step in x begins (CUSUM changepoint), or None
    if there is no clear rise. min_rise is the required jump as a fraction of the
    signal's range, so it works for both 0/1 hit sequences and poke counts."""
    arr = np.asarray(x, dtype=float)
    n = arr.size
    if n < 6:
        return None
    dev = np.cumsum(arr - arr.mean())
    onset = int(np.argmin(dev)) + 1  # 0-based first trial of the higher regime
    if onset < 1 or onset >= n - 1:
        return None
    before, after = arr[:onset].mean(), arr[onset:].mean()
    rng = max(arr.max() - arr.min(), 1e-9)
    if (after - before) < min_rise * rng:
        return None
    return onset + 1  # 1-based


def first_gen_session() -> dict[str, dict]:
    """{mouse: {subject, session_num, trials}} for each mouse's first light session."""
    out = {}
    for mouse, subjects in G.discover_mice().items():
        rows = G.collect_mouse(subjects)
        if rows:
            out[mouse] = min(rows, key=lambda r: r["session_num"])
    return out


def onset_trials(trials: list[dict]) -> dict:
    """Rule / on-cue-poke / on-cue-poke+lick step-up onsets for one session."""
    hit = [1.0 if t["is_hit"] else 0.0 for t in trials]
    on_pokes, on_pokelick = [], []
    for t in trials:
        dur = t["led_dur"]
        p = sum(1 for x in t["nose_pokes"] if 0 <= x <= dur)
        lk = sum(1 for x in t["licks"] if 0 <= x <= dur)
        on_pokes.append(p)
        on_pokelick.append(p + lk)
    return {
        "rule": step_onset(hit),
        "poke": step_onset(on_pokes),
        "pokelick": step_onset(on_pokelick),
    }


def fig_first_session_raster(first: dict, onsets: dict, out_path: str) -> None:
    mice = _sorted_mice(first)
    ncol = 5
    nrow = (len(mice) + ncol - 1) // ncol
    fig, axes = plt.subplots(nrow, ncol, figsize=(3.7 * ncol, 3.1 * nrow), squeeze=False)
    axes = axes.reshape(-1)
    for ax, mouse in zip(axes, mice):
        trials = first[mouse]["trials"]
        n = len(trials)
        G._draw_trials(ax, trials, scale=0.5)
        for key, color, ls in [("rule", RULE_COLOR, "-"),
                               ("poke", POKE_COLOR, "--"),
                               ("pokelick", POKELICK_COLOR, ":")]:
            o = onsets[mouse][key]
            if o is not None:
                ax.axhline(n - o + 1.5, color=color, ls=ls, lw=1.8, zorder=6)
        ax.set_title(f"{mouse} · gen s{first[mouse]['session_num']} ({n} tr)", fontsize=9)
        ax.tick_params(labelsize=7)
    for ax in axes[len(mice):]:
        ax.axis("off")
    handles = [
        Line2D([], [], color="#2ca02c", marker="|", ls="None", label="nose poke"),
        Line2D([], [], color="black", marker="|", ls="None", label="lick"),
        Line2D([], [], color="#f5c518", marker="|", ls="None", label="rewarded lick (HIT)"),
        Line2D([], [], color=RULE_COLOR, ls="-", lw=2, label="rule onset (hit rate ↑)"),
        Line2D([], [], color=POKE_COLOR, ls="--", lw=2, label="on-cue poke onset"),
        Line2D([], [], color=POKELICK_COLOR, ls=":", lw=2, label="on-cue poke+lick onset"),
    ]
    fig.legend(handles=handles, loc="upper center", ncol=6, fontsize=8,
               bbox_to_anchor=(0.5, 0.945))
    fig.supxlabel("trial time (s)  —  0 = LED2 (cue) onset   ·   onset line = trial from which the behaviour steps up")
    fig.supylabel("trial  (top = first trial → bottom = last)")
    fig.suptitle("Generalization first session — when each mouse cracked the new (light) rule",
                 fontsize=12, y=0.995)
    fig.tight_layout(rect=(0, 0, 1, 0.90))
    fig.savefig(out_path, dpi=145)
    plt.close(fig)


# --- writers ---------------------------------------------------------------
def write_transition_csv(pheno: dict, path: str) -> None:
    cols = ["mouse", "tone_engagement", "tone_accuracy", "tone_phenotype",
            "light_engagement", "light_accuracy", "light_phenotype", "changed"]
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for m in _sorted_mice(pheno):
            a, g, pa, pg = pheno[m]
            w.writerow([m, f"{a['engagement_rate']:.1f}",
                        "" if np.isnan(a["accuracy_when_engaged"]) else f"{a['accuracy_when_engaged']:.1f}",
                        pa, f"{g['engagement_rate']:.1f}",
                        "" if np.isnan(g["accuracy_when_engaged"]) else f"{g['accuracy_when_engaged']:.1f}",
                        pg, "yes" if pa != pg else "no"])


def write_onset_csv(first: dict, onsets: dict, path: str) -> None:
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["mouse", "n_trials", "rule_onset_trial", "oncue_poke_onset_trial",
                    "oncue_pokelick_onset_trial"])
        for m in _sorted_mice(first):
            o = onsets[m]
            w.writerow([m, len(first[m]["trials"]),
                        o["rule"] if o["rule"] else "",
                        o["poke"] if o["poke"] else "",
                        o["pokelick"] if o["pokelick"] else ""])


def write_summary(pheno: dict, onsets: dict, first: dict, strong: float, path: str) -> None:
    lines = ["Cross-task transition — last appetitive (tone) -> first generalization (light)",
             f"strong-participation bar = {strong:.0f}% engagement", "",
             "## Phenotype shift (tone last -> light first)"]
    for m in _sorted_mice(pheno):
        a, g, pa, pg = pheno[m]
        moved = "  ==> CHANGED" if pa != pg else ""
        lines.append(f"  {m:>5}: {LC.CLASSES[pa][0]:28} -> {LC.CLASSES[pg][0]:28}"
                     f" (eng {a['engagement_rate']:.0f}->{g['engagement_rate']:.0f}%,"
                     f" acc {a['accuracy_when_engaged']:.0f}->{g['accuracy_when_engaged']:.0f}%){moved}")
    lines += ["", "## Learning onset in the first light session (trial #)"]
    for m in _sorted_mice(first):
        o = onsets[m]
        n = len(first[m]["trials"])
        fmt = lambda v: f"trial {v}/{n}" if v else "no clear step"
        lines.append(f"  {m:>5}: rule {fmt(o['rule'])} | on-cue poke {fmt(o['poke'])}"
                     f" | poke+lick {fmt(o['pokelick'])}")
    Path(path).write_text("\n".join(lines) + "\n")


def main() -> int:
    trans = build_transition()
    if not trans:
        print("No mice with both a tone and a light session — nothing to do.")
        return 1
    pheno, strong = classify_endpoints(trans)
    first = first_gen_session()
    onsets = {m: onset_trials(first[m]["trials"]) for m in first}

    os.makedirs(OUT_ROOT, exist_ok=True)
    fig_transition_map(pheno, strong, os.path.join(OUT_ROOT, "phenotype_transition_map.png"))
    fig_first_session_raster(first, onsets, os.path.join(OUT_ROOT, "gen_first_session_raster.png"))
    write_transition_csv(pheno, os.path.join(OUT_ROOT, "phenotype_transition.csv"))
    write_onset_csv(first, onsets, os.path.join(OUT_ROOT, "learning_onset.csv"))
    write_summary(pheno, onsets, first, strong,
                  os.path.join(OUT_ROOT, "cross_task_transition_summary.txt"))

    n_moved = sum(1 for _, _, pa, pg in pheno.values() if pa != pg)
    print(f"\nWrote 2 figures, 2 CSVs, and summary.txt under '{OUT_ROOT}/' "
          f"({len(pheno)} mice, {n_moved} changed phenotype tone→light).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
