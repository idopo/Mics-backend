"""Participation-vs-competence analyses, shared by the appetitive and
generalization scripts.

The recurring question in both tasks is whether a slow learner is slow to
*participate* (engage at all) or slow to *succeed once engaged*. These five
plots isolate participation dynamics. Each works off a common per-mouse
structure:

    per_mouse[mouse] = [session_row, ...]   # one row per session, ordered

where each session_row has:
    session_num        : int   (1..N, chronological)
    n_trials           : int
    n_engaged          : int   (trials with an on-cue nose poke)
    engaged_rate       : float (% of trials engaged)
    acc_given_engaged  : float (% of engaged trials that were hits)
    engaged_seq        : list[bool]   (engaged flag per trial, in order)
    rt_list            : list[float]  (cue->first on-cue poke latency, engaged trials)

Mouse keys may be short ("m97") or full subject strings ("m90_AppetitiveTone_150");
labels/sorting use the leading m<number>.
"""
from __future__ import annotations

import os
import re

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.cm import ScalarMappable
from matplotlib.colors import Normalize
from matplotlib.ticker import MaxNLocator
import numpy as np

ENGAGE_CRITERION = 50.0  # % engagement that counts as "participating"
ROLL_WINDOW = 10  # trials, trailing window for the within-session ramp


def _mouse_num(key: str) -> int:
    m = re.search(r"m(\d+)", key)
    return int(m.group(1)) if m else 0


def _short(key: str) -> str:
    m = re.match(r"(m\d+)", key)
    return m.group(1) if m else key


def _sorted_mice(per_mouse: dict) -> list[str]:
    return sorted(per_mouse, key=_mouse_num)


def _max_session(per_mouse: dict) -> int:
    return max((r["session_num"] for rows in per_mouse.values() for r in rows), default=1)


def _mean_sem_by_session(per_mouse: dict, key: str, max_s: int):
    xs, means, sems = [], [], []
    for s in range(1, max_s + 1):
        vals = [r[key] for rows in per_mouse.values() for r in rows
                if r["session_num"] == s and r[key] is not None]
        if not vals:
            continue
        xs.append(s)
        means.append(float(np.mean(vals)))
        sems.append(float(np.std(vals, ddof=1) / np.sqrt(len(vals))) if len(vals) > 1 else 0.0)
    return np.array(xs), np.array(means), np.array(sems)


def _grid(n: int, ncol: int = 5):
    nrow = (n + ncol - 1) // ncol
    fig, axes = plt.subplots(nrow, ncol, figsize=(3 * ncol, 2.6 * nrow),
                             sharex=True, sharey=True)
    return fig, np.array(axes).reshape(-1)


# --- 1. engagement (participation) learning curve -------------------------
def plot_engagement_curve(per_mouse: dict, out_path: str, cue_label: str, num: int) -> None:
    fig, ax = plt.subplots(figsize=(9, 6))
    cmap = plt.get_cmap("tab10")
    mice = _sorted_mice(per_mouse)
    max_s = _max_session(per_mouse)
    for i, mouse in enumerate(mice):
        rows = per_mouse[mouse]
        ax.plot([r["session_num"] for r in rows], [r["engaged_rate"] for r in rows],
                "-o", color=cmap(i % 10), lw=1.5, ms=4, alpha=0.7, label=_short(mouse))
    xs, means, sems = _mean_sem_by_session(per_mouse, "engaged_rate", max_s)
    ax.plot(xs, means, "-", color="black", lw=2.8, zorder=5, label="group mean")
    ax.fill_between(xs, means - sems, means + sems, color="black", alpha=0.15, zorder=4)
    ax.axhline(ENGAGE_CRITERION, color="grey", ls=":", lw=0.8, alpha=0.7)
    ax.set_xlabel("session #")
    ax.set_ylabel("engagement rate (% of trials with on-cue poke)")
    ax.set_title(f"[{num}] {cue_label} — participation across sessions")
    ax.set_ylim(0, 100)
    ax.set_xlim(0.5, max_s + 0.5)
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.legend(fontsize=8, ncol=2, framealpha=0.9)
    fig.tight_layout()
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


# --- 2. participation vs competence dissociation --------------------------
def plot_dissociation(per_mouse: dict, out_path: str, cue_label: str, num: int) -> None:
    fig, ax = plt.subplots(figsize=(7.5, 6.5))
    max_s = _max_session(per_mouse)
    norm = Normalize(vmin=1, vmax=max_s)
    cmap = plt.get_cmap("viridis")
    accs = []
    for rows in per_mouse.values():
        for r in rows:
            if r["n_engaged"] == 0:
                continue
            ax.scatter(r["engaged_rate"], r["acc_given_engaged"], s=45,
                       color=cmap(norm(r["session_num"])), edgecolor="white", linewidths=0.4)
            accs.append(r["acc_given_engaged"])
    if accs:
        ax.axhline(float(np.mean(accs)), color="grey", ls="--", lw=1.0,
                   label=f"mean accuracy = {np.mean(accs):.0f}%")
        ax.legend(fontsize=9, loc="lower left")
    ax.set_xlabel("engagement rate (% of trials with on-cue poke)  →  participation")
    ax.set_ylabel("accuracy when engaged (% of engaged trials)  →  competence")
    ax.set_title(f"[{num}] {cue_label} — participation vs competence\n(each point = one mouse-session)")
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 105)
    fig.colorbar(ScalarMappable(norm=norm, cmap=cmap), ax=ax, label="session #")
    fig.tight_layout()
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


# --- 3. within-session engagement ramp ------------------------------------
def _rolling(seq: list[bool], window: int) -> list[float]:
    out = []
    for i in range(len(seq)):
        chunk = seq[max(0, i - window + 1):i + 1]
        out.append(100.0 * sum(chunk) / len(chunk))
    return out


def plot_within_session_ramp(per_mouse: dict, out_path: str, cue_label: str, num: int) -> None:
    mice = _sorted_mice(per_mouse)
    fig, axes = _grid(len(mice))
    max_s = _max_session(per_mouse)
    norm = Normalize(vmin=1, vmax=max_s)
    cmap = plt.get_cmap("viridis")
    for ax, mouse in zip(axes, mice):
        for r in per_mouse[mouse]:
            seq = r["engaged_seq"]
            if not seq:
                continue
            ax.plot(range(1, len(seq) + 1), _rolling(seq, ROLL_WINDOW),
                    color=cmap(norm(r["session_num"])), lw=1.2, alpha=0.85)
        ax.set_title(_short(mouse), fontsize=10)
        ax.set_ylim(0, 100)
    for ax in axes[len(mice):]:
        ax.axis("off")
    fig.supxlabel("trial # within session")
    fig.supylabel(f"engagement (rolling %, window={ROLL_WINDOW})")
    fig.suptitle(f"[{num}] {cue_label} — within-session engagement ramp", fontsize=12)
    fig.colorbar(ScalarMappable(norm=norm, cmap=cmap), ax=axes.tolist(),
                 label="session #", fraction=0.02, pad=0.01)
    fig.savefig(out_path, dpi=140, bbox_inches="tight")
    plt.close(fig)


# --- 4. latency to engage (trials-to-first + reaction time) ---------------
def plot_latency(per_mouse: dict, out_path: str, cue_label: str, num: int) -> None:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5.2))
    cmap = plt.get_cmap("tab10")
    mice = _sorted_mice(per_mouse)
    max_s = _max_session(per_mouse)

    for i, mouse in enumerate(mice):
        rows = per_mouse[mouse]
        col = cmap(i % 10)
        first_eng, rt_med = [], []
        for r in rows:
            seq = r["engaged_seq"]
            idx = next((k + 1 for k, v in enumerate(seq) if v), None)
            r["_first_eng"] = idx
            r["_rt_med"] = float(np.median(r["rt_list"])) if r["rt_list"] else None
        xs1 = [r["session_num"] for r in rows if r["_first_eng"] is not None]
        ys1 = [r["_first_eng"] for r in rows if r["_first_eng"] is not None]
        ax1.plot(xs1, ys1, "-o", color=col, lw=1.4, ms=4, alpha=0.7, label=_short(mouse))
        xs2 = [r["session_num"] for r in rows if r["_rt_med"] is not None]
        ys2 = [r["_rt_med"] for r in rows if r["_rt_med"] is not None]
        ax2.plot(xs2, ys2, "-o", color=col, lw=1.4, ms=4, alpha=0.7, label=_short(mouse))

    mx, mm, _ = _mean_sem_by_session(per_mouse, "_first_eng", max_s)
    ax1.plot(mx, mm, "-", color="black", lw=2.6, label="group mean")
    rx, rm, _ = _mean_sem_by_session(per_mouse, "_rt_med", max_s)
    ax2.plot(rx, rm, "-", color="black", lw=2.6, label="group mean")

    for ax in (ax1, ax2):
        ax.set_xlabel("session #")
        ax.set_xlim(0.5, max_s + 0.5)
        ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax1.set_ylabel("trials until first engaged trial")
    ax1.set_title("How long before the mouse switches on")
    ax2.set_ylabel("median reaction time (s): cue → first on-cue poke")
    ax2.set_title("How fast it pokes once engaged")
    ax1.legend(fontsize=7, ncol=2, framealpha=0.9)
    fig.suptitle(f"[{num}] {cue_label} — latency to engage", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


# --- 5. sessions to engagement criterion ----------------------------------
def plot_sessions_to_criterion(per_mouse: dict, out_path: str, cue_label: str, num: int) -> None:
    mice = _sorted_mice(per_mouse)
    max_s = _max_session(per_mouse)
    labels, values, colors = [], [], []
    for mouse in mice:
        rows = sorted(per_mouse[mouse], key=lambda r: r["session_num"])
        hit = next((r["session_num"] for r in rows if r["engaged_rate"] >= ENGAGE_CRITERION), None)
        labels.append(_short(mouse))
        if hit is None:
            values.append(max_s + 1)  # "never reached" sentinel bar
            colors.append("#d62728")
        else:
            values.append(hit)
            colors.append("#1f77b4")
    fig, ax = plt.subplots(figsize=(9, 5))
    x = np.arange(len(mice))
    ax.bar(x, values, color=colors, width=0.7)
    for xi, v, c in zip(x, values, colors):
        ax.text(xi, v + 0.1, "n/a" if c == "#d62728" else str(int(v)),
                ha="center", va="bottom", fontsize=8)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right")
    ax.set_ylabel(f"sessions to reach {ENGAGE_CRITERION:.0f}% engagement")
    ax.set_title(f"[{num}] {cue_label} — speed of participation (lower = faster; red = never reached)")
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    ax.set_ylim(0, max_s + 1.5)
    fig.tight_layout()
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


def plot_all(per_mouse: dict, out_dir: str, prefix: str, cue_label: str) -> list[str]:
    """Render all five participation figures; return the written paths."""
    jobs = [
        (1, "engagement_curve", plot_engagement_curve),
        (2, "participation_vs_competence", plot_dissociation),
        (3, "within_session_ramp", plot_within_session_ramp),
        (4, "latency_to_engage", plot_latency),
        (5, "sessions_to_criterion", plot_sessions_to_criterion),
    ]
    paths = []
    for num, name, fn in jobs:
        path = os.path.join(out_dir, f"{prefix}{num}_{name}.png")
        fn(per_mouse, path, cue_label, num)
        paths.append(path)
    return paths
