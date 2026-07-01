#!/usr/bin/env python3
"""Cross-cutting behavioral patterns for the generalization-task mice.

Four exploratory analyses requested after the core participation work:

  (A) phenotypes      — two engagement phenotypes: reward-gated/bursty vs steady,
                        from trial-to-trial structure (win-stay + disengagement bouts)
  (B) impulsivity     — off-cue (no-cue) poking per mouse: who responds when they
                        shouldn't
  (C) licking         — anticipatory licking (≈absent: poke-gated task) alongside
                        poke→lick latency, the licking signal that does exist
  (D) cross-task      — does participation/competence transfer appetitive↔generalization

Reuses data loaders from generalization_analysis (light cue) and
appetitive_analysis (tone). Output under MICS_BEH_OUT (default 'behavior_figs/').

`--task generalization` (default) reproduces the original generalization
within-task figures plus the cross-task transfer figures; `--task appetitive`
emits the within-task figures (phenotypes / impulsivity / licking / scorecard)
for the appetitive tone task; `--task both` emits everything.
"""
from __future__ import annotations

import os
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

import generalization_analysis as G
import appetitive_analysis as A

# Within-task figures route to results/<task>/behavior_patterns/; the cross-task
# transfer figures route to results/cross_task/transfer/. MICS_BEH_OUT (if set)
# overrides both to a single directory (back-compat).
_RESULTS_ROOT = Path(__file__).resolve().parent / "results"
_ENV_OUT = os.environ.get("MICS_BEH_OUT")
BURSTY_RUN = 10  # ≥ this many consecutive disengaged trials → "bursty/reward-gated"
C_BURSTY, C_STEADY = "#d62728", "#1f77b4"


def _longest_false_run(seq: list[bool]) -> int:
    best = cur = 0
    for b in seq:
        cur = 0 if b else cur + 1
        best = max(best, cur)
    return best


# --- data gathering -------------------------------------------------------
def gather_generalization() -> dict[str, dict]:
    data: dict[str, dict] = {}
    for mouse, subjects in G.discover_mice().items():
        rows = G.collect_mouse(subjects)
        after_hit, after_miss, off_cue, antic, latency = [], [], [], [], []
        cue_pokes_engaged = []
        eng_rates, accs, max_run, total_hits, total_engaged = [], [], 0, 0, 0
        n_sessions = len(rows)
        for r in rows:
            eng_rates.append(r["engaged_rate"])
            if r["n_engaged"] > 0:
                accs.append(r["acc_given_engaged"])
            trials = r["trials"]
            total_hits += sum(t["is_hit"] for t in trials)
            total_engaged += sum(1 for t in trials if t["engaged"])
            max_run = max(max_run, _longest_false_run([t["engaged"] for t in trials]))
            for i, t in enumerate(trials):
                ld = t["led_dur"]
                off_cue.append(sum(1 for p in t["nose_pokes"] if not 0 <= p <= ld))
                cutoff = min(t["rewarded_licks"]) if t["rewarded_licks"] else ld
                antic.append(sum(1 for lk in t["licks"] if 0 <= lk < cutoff))
                on_cue = [p for p in t["nose_pokes"] if 0 <= p <= ld]
                if on_cue:
                    cue_pokes_engaged.append(len(on_cue))
                if t["is_hit"] and t["rewarded_licks"] and on_cue:
                    latency.append(min(t["rewarded_licks"]) - min(on_cue))
                if i + 1 < len(trials):
                    nxt = trials[i + 1]["engaged"]
                    (after_hit if t["is_hit"] else after_miss).append(nxt)
        data[mouse] = {
            "win_stay": 100 * np.mean(after_hit) - 100 * np.mean(after_miss),
            "max_run": max_run,
            "off_cue": float(np.mean(off_cue)),
            "antic_rate": 100 * float(np.mean([a > 0 for a in antic])),
            "latency": float(np.median(latency)) if latency else np.nan,
            "engagement": float(np.mean(eng_rates)),
            "accuracy": float(np.mean(accs)) if accs else np.nan,
            "hits": int(total_hits),
            "hits_per_session": total_hits / n_sessions if n_sessions else np.nan,
            "hits_per_engaged": 100.0 * total_hits / total_engaged if total_engaged else np.nan,
            "cue_effort": float(np.mean(cue_pokes_engaged)) if cue_pokes_engaged else np.nan,
        }
    return data


def gather_appetitive() -> dict[str, dict]:
    """Per-mouse appetitive (tone) metrics, computed with the same trial-structure
    measures as gather_generalization so the within-task figures (phenotypes,
    impulsivity, licking, scorecard) work identically across the two tasks."""
    data: dict[str, dict] = {}
    for subject in A.discover_subjects():
        by_session = A.group_by_session(A.fetch_events(subject))
        eng_rates, accs, total_hits, cue_pokes_engaged = [], [], 0, []
        after_hit, after_miss, off_cue, antic, latency = [], [], [], [], []
        total_engaged, max_run, n_sessions = 0, 0, 0
        for evs in by_session.values():
            trials = A.segment_trials(evs)
            if not A.session_len_ok(len(trials)):
                continue
            n_sessions += 1
            total_hits += sum(t["is_hit"] for t in trials)
            engaged_seq = [
                any(0 <= p <= t["tone_dur"] for p in t["nose_pokes"]) for t in trials
            ]
            max_run = max(max_run, _longest_false_run(engaged_seq))
            for i, t in enumerate(trials):
                td = t["tone_dur"]
                on_cue = [p for p in t["nose_pokes"] if 0 <= p <= td]
                off_cue.append(sum(1 for p in t["nose_pokes"] if not 0 <= p <= td))
                cutoff = min(t["rewarded_licks"]) if t["rewarded_licks"] else td
                antic.append(sum(1 for lk in t["licks"] if 0 <= lk < cutoff))
                if on_cue:
                    cue_pokes_engaged.append(len(on_cue))
                if t["is_hit"] and t["rewarded_licks"] and on_cue:
                    latency.append(min(t["rewarded_licks"]) - min(on_cue))
                if i + 1 < len(trials):
                    (after_hit if t["is_hit"] else after_miss).append(engaged_seq[i + 1])
            em = A.engagement_metrics(trials)
            total_engaged += em["n_engaged"]
            eng_rates.append(em["engaged_rate"])
            if em["n_engaged"] > 0:
                accs.append(em["acc_given_engaged"])
        if eng_rates:
            data[A.short_name(subject)] = {
                "win_stay": (100 * np.mean(after_hit) - 100 * np.mean(after_miss))
                if after_hit and after_miss else np.nan,
                "max_run": max_run,
                "off_cue": float(np.mean(off_cue)) if off_cue else np.nan,
                "antic_rate": 100 * float(np.mean([a > 0 for a in antic])) if antic else np.nan,
                "latency": float(np.median(latency)) if latency else np.nan,
                "engagement": float(np.mean(eng_rates)),
                "accuracy": float(np.mean(accs)) if accs else np.nan,
                "hits": int(total_hits),
                "hits_per_session": total_hits / n_sessions if n_sessions else np.nan,
                "hits_per_engaged": 100.0 * total_hits / total_engaged if total_engaged else np.nan,
                "cue_effort": float(np.mean(cue_pokes_engaged)) if cue_pokes_engaged else np.nan,
            }
    return data


def _sorted_mice(d: dict) -> list[str]:
    return sorted(d, key=lambda m: int(m[1:]))


def _is_bursty(d: dict) -> bool:
    return d["max_run"] >= BURSTY_RUN


# --- figures --------------------------------------------------------------
def plot_phenotypes(gen: dict, out_path: str, task_label: str = "generalization") -> None:
    fig, ax = plt.subplots(figsize=(8.5, 6.5))
    for mouse in _sorted_mice(gen):
        d = gen[mouse]
        bursty = _is_bursty(d)
        ax.scatter(d["win_stay"], d["max_run"], s=120, zorder=3,
                   color=C_BURSTY if bursty else C_STEADY, edgecolor="white", linewidths=0.6)
        ax.annotate(mouse, (d["win_stay"], d["max_run"]), textcoords="offset points",
                    xytext=(7, 3), fontsize=9)
    ax.axhline(BURSTY_RUN - 0.5, color="grey", ls="--", lw=0.8, alpha=0.7)
    ax.set_xlabel("reward dependence of engagement\nP(engage | prev hit) − P(engage | prev miss)  [pp]")
    ax.set_ylabel("longest run of consecutive disengaged trials")
    ax.set_title(f"Two engagement phenotypes — {task_label} task\n"
                 "(top-right = reward-gated / bursty; bottom-left = steady)")
    handles = [plt.Line2D([], [], marker="o", linestyle="None", color=C_BURSTY,
                          label="reward-gated / bursty"),
               plt.Line2D([], [], marker="o", linestyle="None", color=C_STEADY,
                          label="steady participator")]
    ax.legend(handles=handles, loc="lower right", fontsize=9)
    fig.tight_layout()
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


def plot_impulsivity(gen: dict, out_path: str) -> None:
    mice = sorted(gen, key=lambda m: gen[m]["off_cue"], reverse=True)
    vals = [gen[m]["off_cue"] for m in mice]
    colors = [C_BURSTY if i == 0 else "#7f7f7f" for i in range(len(mice))]
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar(range(len(mice)), vals, color=colors, width=0.7)
    ax.axhline(float(np.median(vals)), color="black", ls="--", lw=0.9,
               label=f"median = {np.median(vals):.1f}")
    ax.set_xticks(range(len(mice)))
    ax.set_xticklabels(mice, rotation=45, ha="right")
    ax.set_ylabel("off-cue nose pokes per trial (no cue, no reward available)")
    ax.set_title("Impulsivity — poking when there is no cue (higher = more impulsive)")
    ax.legend(fontsize=9)
    fig.tight_layout()
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


def plot_licking(gen: dict, out_path: str) -> None:
    mice = _sorted_mice(gen)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))
    ax1.bar(range(len(mice)), [gen[m]["antic_rate"] for m in mice], color="#9467bd", width=0.7)
    ax1.set_ylim(0, 100)
    ax1.set_ylabel("% of trials with an anticipatory lick (cue, pre-reward)")
    ax1.set_title("Anticipatory licking is essentially absent\n(poke-gated task: licking follows the poke)")
    ax2.bar(range(len(mice)), [gen[m]["latency"] for m in mice], color="#2ca02c", width=0.7)
    ax2.set_ylabel("median poke → reward-lick latency (s)")
    ax2.set_title("Reward-collection speed — the licking signal that exists")
    for ax in (ax1, ax2):
        ax.set_xticks(range(len(mice)))
        ax.set_xticklabels(mice, rotation=45, ha="right")
    fig.suptitle("Licking dynamics", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


def _scatter_corr(ax, gen: dict, app: dict, key: str, label: str) -> None:
    xs, ys, names = [], [], []
    for mouse in _sorted_mice(gen):
        if mouse in app and not np.isnan(gen[mouse][key]) and not np.isnan(app[mouse][key]):
            xs.append(app[mouse][key])
            ys.append(gen[mouse][key])
            names.append(mouse)
    xs, ys = np.array(xs), np.array(ys)
    for x, y, n in zip(xs, ys, names):
        ax.scatter(x, y, s=90, color="#1f77b4", edgecolor="white", linewidths=0.5, zorder=3)
        ax.annotate(n, (x, y), textcoords="offset points", xytext=(6, 3), fontsize=8)
    if len(xs) > 2:
        r = float(np.corrcoef(xs, ys)[0, 1])
        m, b = np.polyfit(xs, ys, 1)
        xr = np.array([xs.min(), xs.max()])
        ax.plot(xr, m * xr + b, color="grey", ls="--", lw=1, label=f"r = {r:.2f}")
        ax.legend(fontsize=9, loc="upper left")
    ax.set_xlabel(f"appetitive (tone) — {label}")
    ax.set_ylabel(f"generalization (light) — {label}")
    ax.set_title(label)


def plot_cross_task(gen: dict, app: dict, out_path: str) -> None:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5.6))
    _scatter_corr(ax1, gen, app, "engagement", "participation (engagement %)")
    _scatter_corr(ax2, gen, app, "accuracy", "competence (accuracy when engaged %)")
    fig.suptitle("Does behavior transfer across tasks?  (each point = one mouse)", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


def plot_hits_correlation(gen: dict, app: dict, out_path: str, key: str,
                          unit: str, title: str) -> None:
    """Dot plot: do mice that earn the most hits on the first association
    (appetitive, tone) task also earn the most on the generalization (light)
    task?  One dot = one mouse; `key` selects raw total hits or hits/session."""
    xs, ys, names = [], [], []
    for mouse in _sorted_mice(gen):
        if mouse in app and not np.isnan(gen[mouse][key]) and not np.isnan(app[mouse][key]):
            xs.append(app[mouse][key])
            ys.append(gen[mouse][key])
            names.append(mouse)
    xs, ys = np.array(xs, dtype=float), np.array(ys, dtype=float)

    fig, ax = plt.subplots(figsize=(7.5, 6.5))
    for x, y, n in zip(xs, ys, names):
        ax.scatter(x, y, s=110, color="#1f77b4", edgecolor="white",
                   linewidths=0.6, zorder=3)
        ax.annotate(n, (x, y), textcoords="offset points", xytext=(7, 3), fontsize=9)
    if len(xs) > 2:
        r = float(np.corrcoef(xs, ys)[0, 1])
        m, b = np.polyfit(xs, ys, 1)
        xr = np.array([xs.min(), xs.max()])
        ax.plot(xr, m * xr + b, color="grey", ls="--", lw=1.2,
                label=f"r = {r:.2f}  (n = {len(xs)} mice)")
        ax.legend(fontsize=10, loc="upper left")
    ax.set_xlabel(f"first association task (appetitive, tone) — {unit}")
    ax.set_ylabel(f"generalization task (light) — {unit}")
    ax.set_title(title)
    fig.tight_layout()
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


SCORECARD_METRICS = [
    ("engagement", "engagement\n(% trials engaged)", "{:.0f}"),
    ("accuracy", "accuracy\n(% when engaged)", "{:.0f}"),
    ("hits_per_session", "hits\nper session", "{:.0f}"),
    ("off_cue", "impulsivity\n(off-cue pokes/trial)", "{:.1f}"),
    ("latency", "reward-collection\nlatency (s)", "{:.1f}"),
]


def plot_scorecard(gen: dict, out_path: str, task_label: str = "generalization") -> None:
    """Integrated per-mouse scorecard for one task: each column a
    metric, color = z-score within that column (blue low / red high), cell text =
    the raw value. One glance answers who engaged most, tried hardest during the
    cue, was most accurate, earned most, and was most impulsive."""
    mice = _sorted_mice(gen)
    keys = [k for k, _, _ in SCORECARD_METRICS]
    raw = np.array([[gen[m][k] for k in keys] for m in mice], dtype=float)
    z = (raw - np.nanmean(raw, axis=0)) / np.nanstd(raw, axis=0)

    fig, ax = plt.subplots(figsize=(9, 6.5))
    im = ax.imshow(z, cmap="RdBu_r", aspect="auto", vmin=-2, vmax=2)
    ax.set_xticks(range(len(keys)))
    ax.set_xticklabels([lab for _, lab, _ in SCORECARD_METRICS], fontsize=9)
    ax.set_yticks(range(len(mice)))
    ax.set_yticklabels(mice, fontsize=10)
    for i in range(len(mice)):
        for j, (_, _, fmt) in enumerate(SCORECARD_METRICS):
            val = raw[i, j]
            ax.text(j, i, "—" if np.isnan(val) else fmt.format(val),
                    ha="center", va="center", fontsize=8.5, color="black")
    ax.set_title(f"Per-mouse scorecard — {task_label} task\n"
                 "(color = z-score within column; red = high, blue = low)")
    fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02, label="z-score")
    fig.tight_layout()
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


def _rank(data: dict, key: str, label: str, fmt: str) -> None:
    ranked = sorted((m for m in data if not np.isnan(data[m][key])),
                    key=lambda m: data[m][key], reverse=True)
    print(f"\n{label} (high -> low):")
    for m in ranked:
        print(f"  {m:6} {fmt.format(data[m][key])}")


def _print_phenotype_table(data: dict) -> None:
    print(f"\n{'mouse':6} {'phenotype':18} {'win-stay':9} {'maxRun':7} {'off-cue/trial':13}")
    for m in _sorted_mice(data):
        d = data[m]
        phenotype = "bursty" if _is_bursty(d) else "steady"
        win_stay = "    n/a" if np.isnan(d["win_stay"]) else f"{d['win_stay']:+7.0f}"
        print(f"{m:6} {phenotype:18} {win_stay}  {d['max_run']:6d} {d['off_cue']:12.2f}")


def run_within_task(data: dict, label: str, suffix: str, task_slug: str, out_root: str) -> int:
    """Emit the four within-task behavior figures (phenotypes, impulsivity,
    licking, scorecard) for one task's per-mouse metric dict."""
    os.makedirs(out_root, exist_ok=True)
    _print_phenotype_table(data)
    plot_phenotypes(data, os.path.join(out_root, f"phenotypes{suffix}.png"), label)
    plot_impulsivity(data, os.path.join(out_root, f"impulsivity{suffix}.png"))
    plot_licking(data, os.path.join(out_root, f"licking_dynamics{suffix}.png"))
    plot_scorecard(data, os.path.join(out_root, f"scorecard_{task_slug}.png"), label)
    _rank(data, "engagement", f"Engaged most / tried most during the cue ({label})", "{:.0f}%")
    return 4


def run_cross_task(gen: dict, app: dict, out_root: str) -> int:
    """Emit the three appetitive↔generalization transfer figures (need both tasks)."""
    os.makedirs(out_root, exist_ok=True)
    plot_cross_task(gen, app, os.path.join(out_root, "cross_task_transfer.png"))
    plot_hits_correlation(
        gen, app, os.path.join(out_root, "hits_first_vs_generalization.png"),
        key="hits", unit="total hits",
        title="Do the best learners on the first task earn the most hits when\n"
              "the cue generalizes to a light?  (each point = one mouse)")
    plot_hits_correlation(
        gen, app, os.path.join(out_root, "hits_per_session_first_vs_generalization.png"),
        key="hits_per_session", unit="hits per session",
        title="Hits per session — first association vs generalization\n"
              "(normalized for session count; each point = one mouse)")
    plot_hits_correlation(
        gen, app, os.path.join(out_root, "hits_per_engaged_first_vs_generalization.png"),
        key="hits_per_engaged", unit="hits per engaged trial (%)",
        title="Success decoupled from engagement — hits per engaged trial\n"
              "(= accuracy when engaged; competence, not participation)")
    print(f"\n{'mouse':6} {'app hits':>9} {'app/sess':>9} {'app/eng':>9} "
          f"{'gen hits':>9} {'gen/sess':>9} {'gen/eng':>9}")
    for m in _sorted_mice(gen):
        if m in app:
            print(f"{m:6} {app[m]['hits']:>9d} {app[m]['hits_per_session']:>9.1f} "
                  f"{app[m]['hits_per_engaged']:>8.0f}% {gen[m]['hits']:>9d} "
                  f"{gen[m]['hits_per_session']:>9.1f} {gen[m]['hits_per_engaged']:>8.0f}%")
    return 4


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--task", choices=["appetitive", "generalization", "both"],
                        default="generalization",
                        help="within-task figures for which task; cross-task transfer "
                             "figures are added whenever both tasks are loaded")
    args = parser.parse_args()

    # env override sends everything to one dir; else route by area under results/.
    def within(task_area: str) -> str:
        return _ENV_OUT or str(_RESULTS_ROOT / task_area / "behavior_patterns")
    transfer_root = _ENV_OUT or str(_RESULTS_ROOT / "cross_task" / "transfer")
    n_fig = 0

    if args.task == "appetitive":
        print("Loading appetitive patterns ...")
        app = gather_appetitive()
        n_fig += run_within_task(app, "appetitive (tone)", "_appetitive", "appetitive",
                                 within("appetitive"))
    else:
        # generalization or both: within-task generalization figures keep their
        # original (un-suffixed) names, plus the cross-task transfer figures.
        print("Loading generalization patterns ...")
        gen = gather_generalization()
        print("Loading appetitive patterns (cross-task) ...")
        app = gather_appetitive()
        n_fig += run_within_task(gen, "generalization (light)", "", "generalization",
                                 within("generalization"))
        n_fig += run_cross_task(gen, app, transfer_root)
        if args.task == "both":
            n_fig += run_within_task(app, "appetitive (tone)", "_appetitive", "appetitive",
                                     within("appetitive"))

    print(f"\nWrote {n_fig} figures under '{_RESULTS_ROOT}/'.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
