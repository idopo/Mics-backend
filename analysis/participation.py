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
from matplotlib.ticker import MaxNLocator
import numpy as np

ENGAGE_CRITERION = 50.0  # % engagement that counts as "participating"
BLOCK_TRIALS = 10  # within-session block size for the engagement ramp


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


def _mean_sem_by_session(per_mouse: dict, key: str, max_s: int, predicate=None):
    xs, means, sems = [], [], []
    for s in range(1, max_s + 1):
        vals = [r[key] for rows in per_mouse.values() for r in rows
                if r["session_num"] == s and r[key] is not None
                and (predicate is None or predicate(r))]
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


# --- 2. participation vs competence (the dissociation, one axes) ----------
def plot_dissociation(per_mouse: dict, out_path: str, cue_label: str, num: int) -> None:
    """Group-level dissociation: competence (accuracy when engaged) is high and
    flat from session 1, while participation (engagement rate) climbs toward it.
    The across-session gain is participation, not competence. Faint per-mouse
    lines show spread; bold lines are group mean ± SEM."""
    c_part, c_comp = "#ff7f0e", "#2ca02c"
    fig, ax = plt.subplots(figsize=(9, 6))
    max_s = _max_session(per_mouse)

    for rows in per_mouse.values():
        rows = sorted(rows, key=lambda r: r["session_num"])
        xs = [r["session_num"] for r in rows]
        ax.plot(xs, [r["engaged_rate"] for r in rows], color=c_part, lw=0.8, alpha=0.2)
        ax.plot(xs, [r["acc_given_engaged"] if r["n_engaged"] else np.nan for r in rows],
                color=c_comp, lw=0.8, alpha=0.2)

    xp, mp, sp = _mean_sem_by_session(per_mouse, "engaged_rate", max_s)
    xc, mc, sc = _mean_sem_by_session(per_mouse, "acc_given_engaged", max_s,
                                      predicate=lambda r: r["n_engaged"] > 0)
    ax.plot(xc, mc, "-s", color=c_comp, lw=3, ms=7, zorder=5,
            label="competence — accuracy when engaged")
    ax.fill_between(xc, mc - sc, mc + sc, color=c_comp, alpha=0.15, zorder=4)
    ax.plot(xp, mp, "-o", color=c_part, lw=3, ms=7, zorder=5,
            label="participation — engagement rate")
    ax.fill_between(xp, mp - sp, mp + sp, color=c_part, alpha=0.15, zorder=4)

    if len(mp):
        ax.annotate("participation rises", (xp[-1], mp[-1]), textcoords="offset points",
                    xytext=(-6, -16), color=c_part, fontsize=9, ha="right")
    if len(mc):
        ax.annotate("competence stays high", (xc[0], mc[0]), textcoords="offset points",
                    xytext=(8, 6), color=c_comp, fontsize=9)

    ax.set_xlabel("session #")
    ax.set_ylabel("% of trials  (group mean ± SEM)")
    ax.set_title(f"[{num}] {cue_label} — participation rises while competence stays high")
    ax.set_ylim(0, 100)
    ax.set_xlim(0.5, max_s + 0.5)
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.legend(fontsize=9, loc="lower right", framealpha=0.9)
    fig.tight_layout()
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


def plot_dissociation_by_mouse(per_mouse: dict, out_path: str, cue_label: str, num: int) -> None:
    """Same dissociation, but each mouse in its own color across two panels:
    participation (engagement rate) and competence (accuracy when engaged).
    Participation lines fan upward and vary; competence lines cluster flat-high."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.6), sharey=True)
    cmap = plt.get_cmap("tab10")
    mice = _sorted_mice(per_mouse)
    max_s = _max_session(per_mouse)
    for i, mouse in enumerate(mice):
        rows = sorted(per_mouse[mouse], key=lambda r: r["session_num"])
        xs = [r["session_num"] for r in rows]
        col = cmap(i % 10)
        ax1.plot(xs, [r["engaged_rate"] for r in rows], "-o", color=col, lw=1.6, ms=4,
                 label=_short(mouse))
        ax2.plot(xs, [r["acc_given_engaged"] if r["n_engaged"] else np.nan for r in rows],
                 "-o", color=col, lw=1.6, ms=4, label=_short(mouse))
    for ax in (ax1, ax2):
        ax.set_xlabel("session #")
        ax.set_ylim(0, 100)
        ax.set_xlim(0.5, max_s + 0.5)
        ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax1.set_ylabel("% of trials")
    ax1.set_title("participation — engagement rate")
    ax2.set_title("competence — accuracy when engaged")
    ax1.legend(fontsize=8, ncol=2, framealpha=0.9)
    fig.suptitle(f"[{num}] {cue_label} — participation vs competence, per mouse", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


# --- 3. within-session engagement ramp (binned) ---------------------------
def _session_color(s: int, max_s: int):
    """Distinct categorical color per session number (1-based)."""
    cmap = plt.get_cmap("tab10" if max_s <= 10 else "tab20")
    return cmap((s - 1) % cmap.N)


def _block_engagement(seq: list[bool], size: int) -> list[float]:
    """Mean engagement (%) per consecutive full block of `size` trials. A trailing
    partial block (e.g. a stray 61st trial) is dropped to avoid a misleading dip."""
    last = max(size, len(seq) - len(seq) % size)  # keep >=1 block even if seq<size
    return [100.0 * sum(seq[i:i + size]) / len(seq[i:i + size])
            for i in range(0, last, size)]


def _block_x(n_blocks: int, size: int) -> list[float]:
    return [b * size + size / 2 + 0.5 for b in range(n_blocks)]


def plot_within_session_ramp(per_mouse: dict, out_path: str, cue_label: str, num: int) -> None:
    """Group-level warm-up: mean engagement in successive trial-blocks within a
    session, one line per session. Rising left→right = within-session warm-up;
    later-session lines sitting higher = the ramp strengthens across sessions."""
    fig, ax = plt.subplots(figsize=(9, 6))
    max_s = _max_session(per_mouse)
    for s in range(1, max_s + 1):
        per_mouse_blocks = [_block_engagement(r["engaged_seq"], BLOCK_TRIALS)
                            for rows in per_mouse.values() for r in rows
                            if r["session_num"] == s and r["engaged_seq"]]
        if not per_mouse_blocks:
            continue
        nb = max(len(b) for b in per_mouse_blocks)
        xs, ys = [], []
        for b in range(nb):
            vals = [bm[b] for bm in per_mouse_blocks if b < len(bm)]
            xs.append(_block_x(nb, BLOCK_TRIALS)[b])
            ys.append(float(np.mean(vals)))
        ax.plot(xs, ys, "-o", color=_session_color(s, max_s), lw=2.2, ms=5,
                label=f"session {s}")
    ax.set_xlabel(f"trial # within session (mean per {BLOCK_TRIALS}-trial block)")
    ax.set_ylabel("engagement (% of trials in block)")
    ax.set_ylim(0, 100)
    ax.set_title(f"[{num}] {cue_label} — within-session engagement ramp")
    ax.legend(fontsize=9, framealpha=0.9)
    fig.tight_layout()
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


def plot_within_session_ramp_by_mouse(per_mouse: dict, out_path: str, cue_label: str,
                                       num: int) -> None:
    """Same warm-up, per-mouse grid (binned), one distinct color per session."""
    mice = _sorted_mice(per_mouse)
    fig, axes = _grid(len(mice))
    max_s = _max_session(per_mouse)
    for ax, mouse in zip(axes, mice):
        for r in per_mouse[mouse]:
            seq = r["engaged_seq"]
            if not seq:
                continue
            ys = _block_engagement(seq, BLOCK_TRIALS)
            ax.plot(_block_x(len(ys), BLOCK_TRIALS), ys, "-o",
                    color=_session_color(r["session_num"], max_s), lw=1.4, ms=3)
        ax.set_title(_short(mouse), fontsize=10)
        ax.set_ylim(0, 100)
    for ax in axes[len(mice):]:
        ax.axis("off")
    handles = [plt.Line2D([], [], color=_session_color(s, max_s), label=f"session {s}")
               for s in range(1, max_s + 1)]
    fig.legend(handles=handles, loc="upper right", fontsize=8, framealpha=0.9,
               ncol=1 if max_s <= 6 else 2)
    fig.supxlabel(f"trial # within session (per {BLOCK_TRIALS}-trial block)")
    fig.supylabel("engagement (% of trials in block)")
    fig.suptitle(f"[{num}] {cue_label} — within-session engagement ramp, per mouse", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


# --- 4. latency to engage (trials-to-first + reaction time), grouped bars --
def _first_engaged_idx(seq: list[bool]):
    return next((k + 1 for k, v in enumerate(seq) if v), None)


def plot_latency(per_mouse: dict, out_path: str, cue_label: str, num: int) -> None:
    """x-axis = mice; bars grouped by session (color = session number)."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.4))
    mice = _sorted_mice(per_mouse)
    max_s = _max_session(per_mouse)
    base = np.arange(len(mice))
    width = 0.8 / max_s

    for s in range(1, max_s + 1):
        color = _session_color(s, max_s)
        offset = (s - 1 - (max_s - 1) / 2) * width
        x1, y1, x2, y2 = [], [], [], []
        for i, mouse in enumerate(mice):
            row = next((r for r in per_mouse[mouse] if r["session_num"] == s), None)
            if row is None:
                continue
            idx = _first_engaged_idx(row["engaged_seq"])
            if idx is not None:
                x1.append(i + offset)
                y1.append(idx)
            if row["rt_list"]:
                x2.append(i + offset)
                y2.append(float(np.median(row["rt_list"])))
        ax1.bar(x1, y1, width=width, color=color, label=f"session {s}")
        ax2.bar(x2, y2, width=width, color=color)

    for ax in (ax1, ax2):
        ax.set_xlabel("mouse")
        ax.set_xticks(base)
        ax.set_xticklabels([_short(m) for m in mice], rotation=45, ha="right", fontsize=8)
    ax1.set_ylabel("trials until first engaged trial")
    ax1.set_title("How long before the mouse switches on")
    ax2.set_ylabel("median reaction time (s): cue → first on-cue poke")
    ax2.set_title("How fast it pokes once engaged")
    ax1.legend(fontsize=8, ncol=1 if max_s <= 6 else 2, framealpha=0.9)
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
        (1, "1_engagement_curve", plot_engagement_curve),
        (2, "2_participation_vs_competence", plot_dissociation),
        (2, "2b_participation_vs_competence_by_mouse", plot_dissociation_by_mouse),
        (3, "3_within_session_ramp", plot_within_session_ramp),
        (3, "3b_within_session_ramp_by_mouse", plot_within_session_ramp_by_mouse),
        (4, "4_latency_to_engage", plot_latency),
        (5, "5_sessions_to_criterion", plot_sessions_to_criterion),
    ]
    paths = []
    for num, name, fn in jobs:
        path = os.path.join(out_dir, f"{prefix}{name}.png")
        fn(per_mouse, path, cue_label, num)
        paths.append(path)
    return paths
