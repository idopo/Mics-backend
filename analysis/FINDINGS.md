# What can we learn from this data? — synthesis across all analyses

Behavioral analysis of 10 mice (`m90, m92, m93, m97, m98, m100, m101, m102, m103,
m104`) on the `RecordingBox` pilot, across the appetitive tone task
(`AppetitveTaskReal`) and the generalization light task (`Generalization`).
Synthesizes the appetitive, generalization, behavior-pattern, action-sequence,
learner-criterion, and trial-history analyses.

---

## The one big finding: participation, not competence, is the story

Across every analysis the same theme holds — **a mouse's low hit rate almost
never means it failed to understand the task; it means it didn't engage often
enough.**

- **All 10 mice learned the rule.** Once a mouse pokes during the cue, it licks
  and collects reward ~85–95% of the time — and in the generalization task that
  accuracy is flat-high from *session 1*. The cue→poke→lick→reward chain almost
  never breaks downstream (the action-sequence funnel confirmed it). The only
  place behavior fails is the very first link: **engaging the cue at all.**
- **What develops across training is engagement, not accuracy.** Generalization
  group engagement climbs ~50% → 75% while accuracy-when-engaged sits flat at
  ~90%. So learning here = "deciding to participate," not "figuring out the rule."
- **Hit rate is a misleading summary** because `hit_rate = engagement ×
  competence`. The decomposition figure made this concrete: m93 has an 88%
  competence ceiling but a 13% hit rate purely because it engages 15% of the time
  (a participation problem), whereas m101's ceiling is itself low (~56% — a
  genuine competence problem). Same low hit rate, opposite causes.

## The cohort generalized immediately

Tone → light transfer was essentially instant: competence carried over fully (the
rule is modality-independent), and only *participation* had to ramp back up.
Cross-task, **engagement is a stable individual trait** (transfers, r ≈ 0.5) while
**competence does not transfer** (r ≈ 0.1 — and r ≈ 0.09 for hits-per-engaged),
because generalization competence is ceilinged for everyone.

## There are two stable phenotypes

- **Reward-gated / bursty — m92, m101:** they sit disengaged for long runs and
  re-engage mainly *after* a reward (Δengage +33pp / +21pp in generalization). The
  trial-history models showed reward gates *whether* they engage, not *whether
  they succeed once engaged*.
- **Steady — m97, m100, m102, m103:** engage regardless of the last outcome.
- **m102** is its own case: the best performer *and* the most impulsive (~8
  off-cue pokes/trial) — performance and impulsivity are independent axes.
- **m97 paradox:** the appetitive star whose participation didn't carry into
  generalization — high competence everywhere, but only moderate engagement on the
  light.

## What this is good for, methodologically

The real lesson for the lab: **score these mice on participation and competence
separately, not on hit rate.** A "non-learner" by hit rate is usually a
non-*participator* that knows the task fine — which has very different
implications for training, exclusion criteria, and any neural analysis (you'd be
contrasting "engaged vs not," not "learned vs not").

## Honest limitations — what we *cannot* conclude

- **n = 10.** The cross-task correlations (0.77 vs 0.54 vs 0.09) and per-mouse
  deltas have wide CIs; treat phenotype assignments as suggestive, not definitive.
- **Appetitive accuracy is noisy** for low-engagement mice (estimated from few
  engaged trials) — flagged in the data, not hidden.
- **These are descriptive behavioral patterns.** "Reward-gated" means "more likely
  to engage after reward," *not* a proven reinforcement-learning or neural
  mechanism. The data can't speak to *why* without the ephys/opto layer.
- We haven't tested **within-session satiation**, **circadian / time-of-day**
  effects, or **reaction-time learning** — all extractable from the same event
  stream and likely informative (RT speed-up may be where generalization learning
  actually shows, since accuracy is ceilinged).

---

## Open threads worth pursuing

- **Within-session satiation:** does engagement/accuracy decay late in a session
  as the mouse fills up on water? Front-loaders vs steady workers.
- **Reaction-time learning:** cue→poke latency across sessions — a learning signal
  independent of accuracy (useful since generalization accuracy is ceilinged).
- **Neural tie-in:** label trials engaged vs disengaged and ask what differs in
  the electrophysiology between participation states (rather than learned vs not).
