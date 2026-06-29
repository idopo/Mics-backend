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
"""
from __future__ import annotations

import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

import generalization_analysis as G
import appetitive_analysis as A

OUT_ROOT = os.environ.get("MICS_BEH_OUT", "behavior_figs")
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
        eng_rates, accs, max_run = [], [], 0
        for r in rows:
            eng_rates.append(r["engaged_rate"])
            if r["n_engaged"] > 0:
                accs.append(r["acc_given_engaged"])
            trials = r["trials"]
            max_run = max(max_run, _longest_false_run([t["engaged"] for t in trials]))
            for i, t in enumerate(trials):
                ld = t["led_dur"]
                off_cue.append(sum(1 for p in t["nose_pokes"] if not 0 <= p <= ld))
                cutoff = min(t["rewarded_licks"]) if t["rewarded_licks"] else ld
                antic.append(sum(1 for lk in t["licks"] if 0 <= lk < cutoff))
                on_cue = [p for p in t["nose_pokes"] if 0 <= p <= ld]
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
        }
    return data


def gather_appetitive() -> dict[str, dict]:
    data: dict[str, dict] = {}
    for subject in A.discover_subjects():
        by_session = A.group_by_session(A.fetch_events(subject))
        eng_rates, accs = [], []
        for evs in by_session.values():
            trials = A.segment_trials(evs)
            if len(trials) < 10:
                continue
            em = A.engagement_metrics(trials)
            eng_rates.append(em["engaged_rate"])
            if em["n_engaged"] > 0:
                accs.append(em["acc_given_engaged"])
        if eng_rates:
            data[A.short_name(subject)] = {
                "engagement": float(np.mean(eng_rates)),
                "accuracy": float(np.mean(accs)) if accs else np.nan,
            }
    return data


def _sorted_mice(d: dict) -> list[str]:
    return sorted(d, key=lambda m: int(m[1:]))


def _is_bursty(d: dict) -> bool:
    return d["max_run"] >= BURSTY_RUN


# --- figures --------------------------------------------------------------
def plot_phenotypes(gen: dict, out_path: str) -> None:
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
    ax.set_title("Two engagement phenotypes\n(top-right = reward-gated / bursty; bottom-left = steady)")
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


def main() -> int:
    print("Loading generalization patterns ...")
    gen = gather_generalization()
    print("Loading appetitive patterns (cross-task) ...")
    app = gather_appetitive()

    os.makedirs(OUT_ROOT, exist_ok=True)
    print(f"\n{'mouse':6} {'phenotype':18} {'win-stay':9} {'maxRun':7} {'off-cue/trial':13}")
    for m in _sorted_mice(gen):
        d = gen[m]
        print(f"{m:6} {'bursty' if _is_bursty(d) else 'steady':18} "
              f"{d['win_stay']:+7.0f}  {d['max_run']:6d} {d['off_cue']:12.2f}")

    plot_phenotypes(gen, os.path.join(OUT_ROOT, "phenotypes.png"))
    plot_impulsivity(gen, os.path.join(OUT_ROOT, "impulsivity.png"))
    plot_licking(gen, os.path.join(OUT_ROOT, "licking_dynamics.png"))
    plot_cross_task(gen, app, os.path.join(OUT_ROOT, "cross_task_transfer.png"))
    print(f"\nWrote 4 figures under '{OUT_ROOT}/'.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
