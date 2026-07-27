#!/usr/bin/env python3
"""Level-1 characterization of the appetitive tone-detection task.

A deliberately small, interpretable pipeline that answers four questions per mouse:

    1. Did the mouse participate?      -> participation_rate
    2. Did the mouse learn?            -> performance_score crossing criterion
    3. When did it start learning?     -> first_session_crossing_criterion
    4. Who has high FA / misses /       -> the per-session rates + a preliminary
       rewards / punishments / low         phenotype label
       engagement?

One master trial-level table (`build_master_table`) feeds every metric and every
figure -- no analysis recomputes trials on its own.

Task structure (verified against the event stream; see appetitive_analysis.py):
    - Every trial plays a go-tone. There are NO explicit no-go trials.
    - The mouse nose-pokes during the tone (= participates / engages), licks, and
      earns water == HIT.
    - A nose-poke during the inter-trial interval (ITI) is a FALSE ALARM; it
      resets the ITI timer == PUNISHMENT.
    - Because rewards are tied to hits and punishments to ITI false alarms:
          reward_rate     == hit_rate
          punishment_rate == false_alarm_rate
          correct_rejection_rate == 100 - false_alarm_rate   (an ITI with no poke)
      These identities are a property of the task, not a bug -- reported honestly.

Why performance_score is NOT raw hit rate
-----------------------------------------
Raw hit rate (hits / all trials) tops out around 30-40% here because it is
gated by how often the mouse bothers to engage, not by whether it knows the
rule. Applying a 70% criterion to it would label every mouse a non-learner.
The rule-learning signal is ACCURACY GIVEN ENGAGEMENT (hits / participated
trials), which sits ~85-95%. So:

    performance_score = 100 * hits / participated_trials      (the learning metric)
    hit_rate          = 100 * hits / total_trials             (raw throughput)

Both are kept in the summary; the 70% criterion is applied to performance_score.

Sessions are segmented by LAB-DAY (one session per calendar day) via the shared
`trial_history_analysis.load_appetitive` loader -- not the unreliable ES `session`
counter, which sometimes merged two days into one ~120-trial session (e.g. m100).
This is the corrected definition adopted across the current analyses.

Usage:
    python3 level1_characterization.py                 # all 10 mice
    python3 level1_characterization.py --mouse m100
    ES_URL=http://132.77.73.125:9200 python3 level1_characterization.py
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
import numpy as np
import pandas as pd

try:
    import seaborn as sns  # optional: only used to prettify default style
    sns.set_theme(style="white", context="notebook")
    _HAVE_SNS = True
except ImportError:  # pipeline runs fine on the minimal numpy+matplotlib env
    _HAVE_SNS = False

# Reuse the canonical loader: it segments sessions by LAB-DAY (group_by_day +
# keep_main_run), NOT the unreliable ES `session` counter that merged two days'
# runs into one ~120-trial session (e.g. m100). This is the same trial source
# every other current analysis imports, so the session counts match (m100 = 12
# sessions, appetitive total = 116 mouse-sessions).
import trial_history_analysis as thist

OUT_ROOT = Path(__file__).resolve().parent / "results" / "level1_characterization"
RASTER_DIR = OUT_ROOT / "trial_rasters_by_mouse"

# --- analysis parameters (documented; override via env if needed) ------------
CRITERION_PCT = 70.0          # learning criterion on performance_score
MIN_ENGAGED_FOR_CRITERION = 8  # a session needs >= this many engaged trials to
#                                count toward a criterion crossing (noise guard)
CONSECUTIVE_FOR_CRITERION = 2  # sessions in a row above criterion == "learned"
DPI = 200

# Consistent outcome colors across every figure.
C_HIT = "#2ca02c"          # hit / reward (green)
C_MISS = "#ff7f0e"         # engaged but no reward (orange)
C_NORESP = "#c7c7c7"       # did not engage (grey)
C_FA = "#d62728"           # false alarm / punishment (red)
C_CR = "#4c78a8"           # correct rejection (blue)
C_MISSING = "#eeeeee"      # missing mouse x session cell
OUTCOME_CODE = {"no_response": 0, "miss": 1, "hit": 2}
OUTCOME_CMAP = ListedColormap([C_NORESP, C_MISS, C_HIT])


# ============================================================================
# 1-3. LOAD + STANDARDIZE + DERIVE  ->  one master trial-level table
# ============================================================================
def build_master_table(only_mouse: str | None) -> pd.DataFrame:
    """One row per trial for every mouse, with all Level-1 variables derived.

    Trials come from `trial_history_analysis.load_appetitive`, which segments
    sessions by LAB-DAY: a subject's events are binned per calendar day, any
    same-day aborted false-start is trimmed (keep_main_run), and a day is kept
    only when its trial count is in the valid band [MIN_TRIALS, MAX_TRIALS].
    `session_date` holds the calendar day; `session` is the 1..N training ordinal.
    """
    rows: list[dict] = []
    for rec in thist.load_appetitive(only_mouse):
        mouse, subject = rec["mouse"], rec["subject"]
        session_date, ordinal = rec["session"], rec["training_day"]
        for tr in rec["trials"]:
            engaged, is_hit = tr["engaged"], tr["rewarded"]
            if is_hit:
                outcome = "hit"
            elif tr["missed"]:            # engaged on-cue but earned no reward
                outcome = "miss"
            else:
                outcome = "no_response"   # never engaged the cue
            rows.append({
                "subject": subject,
                "mouse": mouse,
                "session_date": session_date,
                "session": ordinal,
                "trial": tr["trial_index"],
                "engaged": engaged,
                "is_hit": is_hit,
                "outcome": outcome,
                "n_false_alarms": tr["n_false_alarms"],
                "punished": tr["n_false_alarms"] > 0,
                "rewarded": is_hit,
                "latency": tr["cue_to_poke_latency"] if engaged else np.nan,
                "activity": len(tr["nose_pokes"]) + len(tr["licks"]),  # motor proxy
            })
    df = pd.DataFrame(rows)
    # global (cumulative) trial index per mouse, for the raster x-axis
    df["global_trial"] = df.groupby("mouse").cumcount() + 1
    return df


def print_column_mapping(df: pd.DataFrame) -> None:
    """Required Level-1 variable -> where it lives / how it was derived."""
    rows = [
        ("mouse ID", "mouse (from subject)", "e.g. m100; parsed from ES subject name"),
        ("session number/date", "session (ordinal) / session_date", "segmented by LAB-DAY; valid ~60-trial days renumbered 1..N"),
        ("trial number", "trial (within session), global_trial", "derived by trial segmentation"),
        ("cue type / trial type", "(none)", "every trial is a go-tone; no no-go trials in this task"),
        ("correct action", "engage cue then lick", "implicit: poke during tone -> lick -> reward"),
        ("actual choice/action", "engaged, outcome", "engaged = nose-poke while tone plays"),
        ("outcome", "outcome", "hit / miss / no_response (one per trial)"),
        ("reward", "rewarded (== is_hit)", "solenoid fire; 1 reward per hit"),
        ("punishment", "punished", "true if any ITI false-alarm poke (resets ITI)"),
        ("hit", "is_hit", "rewarded trial"),
        ("false alarm", "n_false_alarms", "ITI nose-poke count (state_ITI_nose_poke)"),
        ("miss", "outcome == 'miss'", "engaged on-cue but earned no reward"),
        ("correct rejection", "derived (no ITI poke)", "IMPLICIT: an ITI with no false alarm; no explicit no-go trials"),
        ("response latency", "latency", "time of first on-cue poke rel. tone onset (s)"),
        ("activity / movement", "activity (PROXY)", "pokes+licks per trial; no locomotion/accel is logged"),
        ("participation / engagement", "engaged", "on-cue nose-poke == participated"),
    ]
    width = max(len(r[0]) for r in rows)
    print("\n" + "=" * 92)
    print("COLUMN MAPPING  (required variable  ->  found in data  |  notes)")
    print("=" * 92)
    print(f"{'REQUIRED VARIABLE'.ljust(width)} | {'FOUND / DERIVED'.ljust(26)} | NOTES")
    print("-" * 92)
    for req, found, note in rows:
        print(f"{req.ljust(width)} | {found.ljust(26)} | {note}")
    print("=" * 92)
    print(f"Master table: {len(df):,} trials  |  {df['mouse'].nunique()} mice  |  "
          f"{df.groupby('mouse')['session'].nunique().sum()} mouse-sessions\n")


# ============================================================================
# 4. MOUSE x SESSION SUMMARY
# ============================================================================
def summarize_sessions(df: pd.DataFrame) -> pd.DataFrame:
    """One row per (mouse, session) with every Level-1 metric."""
    out: list[dict] = []
    for (mouse, session), g in df.groupby(["mouse", "session"], sort=True):
        n = len(g)
        participated = int((g["engaged"] | g["is_hit"]).sum())
        hits = int(g["is_hit"].sum())
        misses = int((g["outcome"] == "miss").sum())
        trials_with_fa = int((g["n_false_alarms"] > 0).sum())
        lat = g["latency"].dropna()
        out.append({
            "mouse": mouse,
            "session": session,
            "session_date": g["session_date"].iloc[0],
            "total_trials": n,
            "participated_trials": participated,
            "participation_rate": 100.0 * participated / n,
            "hits": hits,
            "misses": misses,
            "no_responses": int((g["outcome"] == "no_response").sum()),
            # rates on all trials (every trial is a go-tone == relevant)
            "hit_rate": 100.0 * hits / n,
            "miss_rate": 100.0 * misses / n,
            "false_alarm_rate": 100.0 * trials_with_fa / n,
            "correct_rejection_rate": 100.0 * (n - trials_with_fa) / n,
            "reward_rate": 100.0 * hits / n,                       # == hit_rate
            "punishment_rate": 100.0 * trials_with_fa / n,         # == false_alarm_rate
            "n_false_alarms_total": int(g["n_false_alarms"].sum()),
            "mean_latency": float(lat.mean()) if len(lat) else np.nan,
            "median_latency": float(lat.median()) if len(lat) else np.nan,
            "mean_activity_level": float(g["activity"].mean()),
            # THE learning metric: accuracy given the mouse engaged
            "performance_score": 100.0 * hits / participated if participated else np.nan,
        })
    summary = pd.DataFrame(out).sort_values(["mouse", "session"]).reset_index(drop=True)
    eligible = summary["participated_trials"] >= MIN_ENGAGED_FOR_CRITERION
    summary["crossed_criterion"] = eligible & (summary["performance_score"] >= CRITERION_PCT)
    return summary


# ============================================================================
# 5. LEARNING CRITERION (per mouse)
# ============================================================================
def compute_criterion(summary: pd.DataFrame) -> pd.DataFrame:
    """Per-mouse learning summary. A mouse has 'learned' when it clears the
    criterion on CONSECUTIVE_FOR_CRITERION sessions in a row (stability guard).
    first_session_crossing_criterion = ordinal session that starts that run."""
    out: list[dict] = []
    for mouse, g in summary.groupby("mouse", sort=True):
        g = g.sort_values("session")
        flags = g["crossed_criterion"].to_numpy()
        sessions = g["session"].to_numpy()
        first_cross = None
        run = 0
        for flag, sess in zip(flags, sessions):
            run = run + 1 if flag else 0
            if run >= CONSECUTIVE_FOR_CRITERION and first_cross is None:
                first_cross = int(sessions[list(sessions).index(sess)
                                           - (CONSECUTIVE_FOR_CRITERION - 1)])
                break
        ever_70 = bool((g["performance_score"] >= CRITERION_PCT).any())
        out.append({
            "mouse": mouse,
            "n_sessions": len(g),
            "total_trials": int(g["total_trials"].sum()),
            "mean_participation_rate": float(g["participation_rate"].mean()),
            "mean_performance_score": float(g["performance_score"].mean(skipna=True)),
            "best_performance_score": float(g["performance_score"].max(skipna=True)),
            "final_performance_score": float(g["performance_score"].iloc[-1]),
            "mean_false_alarm_rate": float(g["false_alarm_rate"].mean()),
            "mean_reward_rate": float(g["reward_rate"].mean()),
            "mean_punishment_rate": float(g["punishment_rate"].mean()),
            "mean_latency": float(g["mean_latency"].mean(skipna=True)),
            "mean_activity_level": float(g["mean_activity_level"].mean()),
            "crossed_criterion": "yes" if first_cross is not None else "no",
            "first_session_crossing_criterion": first_cross if first_cross is not None else np.nan,
            "sessions_to_criterion": first_cross if first_cross is not None else np.nan,
            "ever_reached_criterion_once": "yes" if ever_70 else "no",
        })
    return pd.DataFrame(out)


# ============================================================================
# 6. FIGURES
# ============================================================================
def _pivot(summary: pd.DataFrame, value: str) -> pd.DataFrame:
    """mouse (rows) x session (cols) matrix, missing sessions == NaN."""
    return summary.pivot(index="mouse", columns="session", values=value).sort_index()


def _save(fig, name: str) -> None:
    for ext in ("png", "svg"):
        fig.savefig(OUT_ROOT / f"{name}.{ext}", dpi=DPI, bbox_inches="tight")
    plt.close(fig)


def _lines_per_mouse(summary: pd.DataFrame, value: str, ylabel: str, title: str,
                     name: str, refline: float | None = None, ylim=(0, 105)) -> None:
    fig, ax = plt.subplots(figsize=(10, 6))
    cmap = plt.get_cmap("tab10")
    for i, (mouse, g) in enumerate(summary.groupby("mouse")):
        g = g.sort_values("session")
        ax.plot(g["session"], g[value], "-o", color=cmap(i % 10), lw=1.5,
                ms=4, alpha=0.85, label=mouse)
    if refline is not None:
        ax.axhline(refline, color="black", ls="--", lw=1.2, alpha=0.7,
                   label=f"{refline:.0f}% criterion")
    ax.set_xlabel("Session (ordinal)")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.set_ylim(*ylim)
    ax.margins(x=0.02)
    ax.legend(loc="center left", bbox_to_anchor=(1.01, 0.5), fontsize=8, frameon=False)
    _save(fig, name)


def _heatmap(matrix: pd.DataFrame, title: str, cbar_label: str, name: str,
             cmap: str = "viridis", vmin=0, vmax=100) -> None:
    fig, ax = plt.subplots(figsize=(1.1 * matrix.shape[1] + 3, 0.5 * matrix.shape[0] + 2))
    masked = np.ma.masked_invalid(matrix.to_numpy(dtype=float))
    cm = plt.get_cmap(cmap).copy()
    cm.set_bad(C_MISSING)
    im = ax.imshow(masked, aspect="auto", cmap=cm, vmin=vmin, vmax=vmax)
    ax.set_xticks(range(matrix.shape[1]))
    ax.set_xticklabels(matrix.columns)
    ax.set_yticks(range(matrix.shape[0]))
    ax.set_yticklabels(matrix.index)
    ax.set_xlabel("Session (ordinal)")
    ax.set_ylabel("Mouse")
    ax.set_title(title)
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            v = matrix.to_numpy(dtype=float)[i, j]
            if not np.isnan(v):
                ax.text(j, i, f"{v:.0f}", ha="center", va="center", fontsize=7,
                        color="white" if v < (vmin + vmax) / 2 else "black")
    cbar = fig.colorbar(im, ax=ax, shrink=0.8)
    cbar.set_label(cbar_label)
    ax.text(0.0, -0.14, "grey = missing session", transform=ax.transAxes, fontsize=8,
            color="#555555")
    _save(fig, name)


def figure_01_performance_heatmap(summary: pd.DataFrame) -> None:
    _heatmap(_pivot(summary, "performance_score"),
             "Figure 1 — Performance (accuracy given engagement) by mouse x session",
             "performance_score (%)", "figure_01_mouse_session_performance_heatmap")


def figure_02_learning_curve(summary: pd.DataFrame) -> None:
    _lines_per_mouse(summary, "performance_score",
                     "performance_score  (hits / engaged trials, %)",
                     "Figure 2 — Learning curve per mouse",
                     "figure_02_learning_curve_per_mouse", refline=CRITERION_PCT)


def figure_03_false_alarm_curve(summary: pd.DataFrame) -> None:
    _lines_per_mouse(summary, "false_alarm_rate",
                     "false_alarm_rate  (% of trials with an ITI poke)",
                     "Figure 3 — False-alarm curve per mouse (impulsivity)",
                     "figure_03_false_alarm_curve_per_mouse",
                     ylim=(0, max(105, summary["false_alarm_rate"].max() * 1.1)))


def figure_04_participation(summary: pd.DataFrame) -> None:
    _lines_per_mouse(summary, "participation_rate",
                     "participation_rate  (% engaged trials)",
                     "Figure 4a — Participation per mouse",
                     "figure_04a_participation_curve_per_mouse")
    _heatmap(_pivot(summary, "participation_rate"),
             "Figure 4b — Participation by mouse x session",
             "participation_rate (%)", "figure_04b_participation_heatmap", cmap="magma")


def figure_05_reward_punishment(summary: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(15, 6), sharex=True)
    cmap = plt.get_cmap("tab10")
    for (value, ax, title, color_label) in [
        ("reward_rate", axes[0], "Reward rate (== hit rate)", "reward_rate (%)"),
        ("punishment_rate", axes[1], "Punishment rate (== false-alarm rate)", "punishment_rate (%)"),
    ]:
        for i, (mouse, g) in enumerate(summary.groupby("mouse")):
            g = g.sort_values("session")
            ax.plot(g["session"], g[value], "-o", color=cmap(i % 10), lw=1.5,
                    ms=4, alpha=0.85, label=mouse)
        ax.set_title(title)
        ax.set_xlabel("Session (ordinal)")
        ax.set_ylabel(color_label)
        ax.set_ylim(0, max(105, summary["punishment_rate"].max() * 1.1))
    axes[1].legend(loc="center left", bbox_to_anchor=(1.01, 0.5), fontsize=8, frameon=False)
    fig.suptitle("Figure 5 — Reward and punishment per session", fontsize=13)
    fig.tight_layout()
    _save(fig, "figure_05_reward_punishment_per_session")


def _outcome_matrix(df_mouse: pd.DataFrame):
    """sessions (rows) x trial (cols) integer outcome codes + a punished mask."""
    sessions = sorted(df_mouse["session"].unique())
    max_trials = int(df_mouse["trial"].max())
    codes = np.full((len(sessions), max_trials), np.nan)
    punished = np.zeros((len(sessions), max_trials), dtype=bool)
    for r, sess in enumerate(sessions):
        g = df_mouse[df_mouse["session"] == sess]
        for _, row in g.iterrows():
            c = int(row["trial"]) - 1
            codes[r, c] = OUTCOME_CODE[row["outcome"]]
            punished[r, c] = row["n_false_alarms"] > 0
    return sessions, codes, punished


def _draw_raster(ax, sessions, codes, punished, title) -> None:
    cm = OUTCOME_CMAP.copy()
    cm.set_bad("white")
    ax.imshow(np.ma.masked_invalid(codes), aspect="auto", cmap=cm, vmin=0, vmax=2,
              interpolation="none")
    pr, pc = np.where(punished)
    ax.scatter(pc, pr, marker="x", s=14, color=C_FA, linewidths=0.8, zorder=3)
    ax.set_yticks(range(len(sessions)))
    ax.set_yticklabels(sessions)
    ax.set_title(title, fontsize=10)
    ax.set_xlabel("Trial within session")
    ax.set_ylabel("Session")


def _raster_legend():
    return [
        Patch(color=C_HIT, label="hit / reward"),
        Patch(color=C_MISS, label="miss (engaged, no reward)"),
        Patch(color=C_NORESP, label="no response"),
        Line2D([], [], marker="x", color=C_FA, linestyle="None",
               label="false alarm / punishment"),
        Patch(facecolor="white", edgecolor="#bbbbbb", label="no trial / correct rejection*"),
    ]


def figure_06_rasters(df: pd.DataFrame) -> None:
    RASTER_DIR.mkdir(parents=True, exist_ok=True)
    mice = sorted(df["mouse"].unique())
    # combined small-multiples grid
    ncol = 2
    nrow = (len(mice) + ncol - 1) // ncol
    fig, axes = plt.subplots(nrow, ncol, figsize=(7 * ncol, 2.4 * nrow), squeeze=False)
    axes = axes.reshape(-1)
    for ax, mouse in zip(axes, mice):
        sessions, codes, punished = _outcome_matrix(df[df["mouse"] == mouse])
        _draw_raster(ax, sessions, codes, punished, mouse)
    for ax in axes[len(mice):]:
        ax.axis("off")
    fig.legend(handles=_raster_legend(), loc="lower center", ncol=5, fontsize=8,
               frameon=False, bbox_to_anchor=(0.5, -0.01))
    fig.suptitle("Figure 6 — Trial-by-trial outcome raster (per mouse)", fontsize=13)
    fig.tight_layout(rect=(0, 0.03, 1, 0.98))
    _save(fig, "figure_06_trial_by_trial_raster")

    # one clean raster per mouse
    for mouse in mice:
        sessions, codes, punished = _outcome_matrix(df[df["mouse"] == mouse])
        fig, ax = plt.subplots(figsize=(11, 0.4 * len(sessions) + 2))
        _draw_raster(ax, sessions, codes, punished, f"{mouse} — trial outcomes")
        ax.legend(handles=_raster_legend(), loc="center left",
                  bbox_to_anchor=(1.01, 0.5), fontsize=8, frameon=False)
        for ext in ("png", "svg"):
            fig.savefig(RASTER_DIR / f"raster_{mouse}.{ext}", dpi=DPI, bbox_inches="tight")
        plt.close(fig)


def figure_07_summary_bars(criterion: pd.DataFrame) -> None:
    metrics = [
        ("total_trials", "Total trials", "#555555"),
        ("mean_participation_rate", "Mean participation rate (%)", C_CR),
        ("mean_performance_score", "Mean performance (%)", C_HIT),
        ("mean_false_alarm_rate", "Mean false-alarm rate (%)", C_FA),
        ("mean_reward_rate", "Mean reward rate (%)", C_HIT),
        ("mean_punishment_rate", "Mean punishment rate (%)", C_FA),
        ("mean_latency", "Mean latency (s)", C_MISS),
        ("mean_activity_level", "Mean activity (pokes+licks/trial)*", "#8c564b"),
    ]
    fig, axes = plt.subplots(2, 4, figsize=(18, 8))
    axes = axes.reshape(-1)
    order = criterion.sort_values("mouse")
    for ax, (col, label, color) in zip(axes, metrics):
        ax.bar(order["mouse"], order[col], color=color, alpha=0.85)
        ax.set_title(label, fontsize=10)
        ax.tick_params(axis="x", rotation=90, labelsize=8)
    fig.suptitle("Figure 7 — Per-mouse summary metrics  (*proxy / see README)", fontsize=13)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    _save(fig, "figure_07_mouse_summary_metrics")


# ============================================================================
# 8. INTERPRETATION  (preliminary phenotype per mouse — Level-1 only)
# ============================================================================
def classify(criterion: pd.DataFrame) -> pd.DataFrame:
    """Assign ONE preliminary phenotype per mouse using group-relative thresholds.
    Deliberately coarse: Level-1 metrics only, not to be over-interpreted."""
    c = criterion.copy()
    part_lo = c["mean_participation_rate"].quantile(0.33)
    fa_hi = c["mean_false_alarm_rate"].quantile(0.66)
    lat_hi = c["mean_latency"].quantile(0.66)
    act_hi = c["mean_activity_level"].quantile(0.66)

    labels, notes = [], []
    for _, r in c.iterrows():
        learned = r["crossed_criterion"] == "yes"
        ever = r["ever_reached_criterion_once"] == "yes"
        low_part = r["mean_participation_rate"] <= part_lo
        high_fa = r["mean_false_alarm_rate"] >= fa_hi
        slow = r["mean_latency"] >= lat_hi
        active = r["mean_activity_level"] >= act_hi

        # priority: crossing the criterion is the primary signal; modifiers
        # (impulsivity / speed) refine WHICH kind of learner, then the
        # non-learner branch is split by participation vs impulsivity.
        if learned and high_fa:
            label = "high-punishment mouse"
        elif learned and slow:
            label = "slow but accurate mouse"
        elif learned:
            label = "strong learner"
        elif low_part:
            label = "low-participation mouse"
        elif high_fa and active:
            label = "active but poorly selective mouse"
        elif high_fa:
            label = "high false-alarm / impulsive mouse"
        elif ever:
            label = "partial learner"
        else:
            label = "non-learner"
        labels.append(label)
        notes.append(
            f"part={r['mean_participation_rate']:.0f}% perf={r['mean_performance_score']:.0f}% "
            f"FA={r['mean_false_alarm_rate']:.0f}% lat={r['mean_latency']:.1f}s "
            f"cross@={r['first_session_crossing_criterion']}")
    c["preliminary_type"] = labels
    c["notes"] = notes
    return c


def write_readme(summary: pd.DataFrame, criterion: pd.DataFrame) -> None:
    n_learned = (criterion["crossed_criterion"] == "yes").sum()
    lines = [
        "LEVEL-1 CHARACTERIZATION — output guide",
        "=" * 50,
        "",
        "Task: appetitive tone-detection (AppetitveTaskReal). Every trial is a",
        "go-tone; the mouse pokes during the tone, licks, and earns water (HIT).",
        "An ITI nose-poke is a FALSE ALARM and triggers PUNISHMENT (ITI reset).",
        "There are no explicit no-go trials, so 'correct rejection' is implicit",
        "(an ITI with no poke) and correct_rejection_rate == 100 - false_alarm_rate.",
        "",
        "Sessions are segmented by LAB-DAY (one per calendar day), not the ES",
        "session counter (which merged two days for m100). session_date = the day;",
        "session = the 1..N training ordinal.",
        "",
        "KEY DEFINITIONS",
        f"  performance_score = 100 * hits / participated_trials  (the LEARNING metric)",
        f"  hit_rate          = 100 * hits / total_trials         (raw, engagement-limited)",
        "  participation_rate= 100 * engaged_trials / total_trials",
        "  reward_rate       == hit_rate      (1 reward per hit)",
        "  punishment_rate   == false_alarm_rate",
        f"  Criterion: performance_score >= {CRITERION_PCT:.0f}% on "
        f"{CONSECUTIVE_FOR_CRITERION} consecutive sessions",
        f"            (a session needs >= {MIN_ENGAGED_FOR_CRITERION} engaged trials to count).",
        "  activity level is a PROXY (pokes+licks/trial); no locomotion is logged.",
        "",
        "FILES",
        "  mouse_session_summary.csv          one row per mouse x session, all metrics",
        "  mouse_learning_criterion_summary.csv  one row per mouse + preliminary_type",
        "  figure_01_mouse_session_performance_heatmap.{png,svg}",
        "  figure_02_learning_curve_per_mouse.{png,svg}",
        "  figure_03_false_alarm_curve_per_mouse.{png,svg}",
        "  figure_04a_participation_curve_per_mouse.{png,svg}",
        "  figure_04b_participation_heatmap.{png,svg}",
        "  figure_05_reward_punishment_per_session.{png,svg}",
        "  figure_06_trial_by_trial_raster.{png,svg}   (+ trial_rasters_by_mouse/)",
        "  figure_07_mouse_summary_metrics.{png,svg}",
        "",
        f"RESULT: {n_learned}/{len(criterion)} mice reached the learning criterion.",
        "",
        "PRELIMINARY PHENOTYPES (Level-1 only — do not over-interpret):",
    ]
    for _, r in criterion.sort_values("mouse").iterrows():
        lines.append(f"  {r['mouse']:<6} {r['preliminary_type']:<38} [{r['notes']}]")
    (OUT_ROOT / "README.txt").write_text("\n".join(lines) + "\n")


# ============================================================================
# DRIVER
# ============================================================================
def run(only_mouse: str | None) -> int:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    print("Loading (sessions segmented by lab-day) ...", flush=True)
    df = build_master_table(only_mouse)
    if df.empty:
        print("No matching data found.", file=sys.stderr)
        return 1
    mice = sorted(df["mouse"].unique())
    print(f"Subjects ({len(mice)}): {', '.join(mice)}")
    print_column_mapping(df)

    summary = summarize_sessions(df)
    criterion = classify(compute_criterion(summary))

    summary.to_csv(OUT_ROOT / "mouse_session_summary.csv", index=False)
    criterion.to_csv(OUT_ROOT / "mouse_learning_criterion_summary.csv", index=False)

    figure_01_performance_heatmap(summary)
    figure_02_learning_curve(summary)
    figure_03_false_alarm_curve(summary)
    figure_04_participation(summary)
    figure_05_reward_punishment(summary)
    figure_06_rasters(df)
    figure_07_summary_bars(criterion)
    write_readme(summary, criterion)

    print("\n" + "=" * 70)
    print("INTERPRETATION SUMMARY  (preliminary — Level-1 metrics only)")
    print("=" * 70)
    for _, r in criterion.sort_values("mouse").iterrows():
        cross = r["first_session_crossing_criterion"]
        cross = f"session {int(cross)}" if pd.notna(cross) else "never"
        print(f"  {r['mouse']:<6} {r['preliminary_type']:<38} learned={r['crossed_criterion']:<3} "
              f"first-cross={cross}")
    n_learned = (criterion["crossed_criterion"] == "yes").sum()
    print(f"\n{n_learned}/{len(criterion)} mice reached criterion "
          f"(>= {CRITERION_PCT:.0f}% for {CONSECUTIVE_FOR_CRITERION} sessions).")
    print(f"Outputs written under: {OUT_ROOT}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mouse", help="single mouse short name, e.g. m100 (default: all 10 mice)")
    return run(ap.parse_args().mouse)


if __name__ == "__main__":
    raise SystemExit(main())
