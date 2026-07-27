# Hit / false-alarm dashboard — metric definitions

Exact mathematical definition of every metric selectable on the X/Y axes of
`hit_fa_trajectory_dashboard.html`. Source of truth: `analysis/hit_fa_dashboard.py`
(`session_row`) and `learning_trajectories_analysis._lick_bout_onsets`.

All metrics are computed **per session** (one point per mouse per session).

---

## 1. Per-trial primitives (the raw data every metric is built from)

Time reference: **t = 0 is cue onset** (tone for the appetitive task, light for
generalization). Every timestamp below is in seconds relative to that onset, so a
negative time = *before* the cue.

For a trial `t`:

| Symbol | Field | Meaning |
|---|---|---|
| `dur` | `tone_dur` / `led_dur` | Cue duration. On an appetitive **hit** the tone mutes at reward, so `dur` = time from onset to mute (can be < 8 s); otherwise the full cue length. |
| `iti_start` | `iti_start` | Time the inter-trial interval (ITI) begins. |
| `iti_end` | `iti_end` | Time the ITI ends. |
| `pokes` | `nose_pokes` | List of times the nose-poke beam was broken (nose entered the port), anywhere in the recorded trial. |
| `licks` | `licks` | List of lick times. |
| `is_hit` | `is_hit` | Boolean: **a water reward was delivered** on this trial. |

Two named time windows used below:

- **Cue window** = `[0, dur]` — while the cue is on.
- **Response window** = `[0, iti_start)` — cue period **plus** post-cue reward
  consumption, up to (but not including) the ITI. Used instead of `[0, dur]`
  because on a hit the tone mutes early, so the reward-drinking licks land *after*
  `dur` but *before* the ITI — they are still a legitimate cue response.
- **ITI window** = `[iti_start, iti_end]` — the dead time between trials.

### Lick bout
A **lick bout** is a maximal run of licks with no internal gap longer than
`LICK_BOUT_GAP = 1.0 s`. Formally, sorting the licks ascending, a bout *onset* is:
the first lick, plus every lick whose gap from the previous lick is `> 1.0 s`.
`O(t)` = the set of bout-onset times for trial `t`. (One long drink = one bout.)

### Two different senses of "hit" — important
- **Lick-bout hit** (used by accuracy / success rate / FA rate): a *lick bout* whose
  onset falls in the response window. Behavioural, based on licking.
- **Reward hit** `is_hit` (used by hit rate / competence): the hardware actually
  delivered water. These are **not** the same number.

---

## 2. Session-level counts

Let `N` = number of trials in the session. Summed over all trials `t` in the session:

```
H  = Σ_t  |{ o ∈ O(t) : 0 ≤ o < iti_start }|      # lick-bout hits  (bouts in response window)
F  = Σ_t  |{ o ∈ O(t) : iti_start ≤ o ≤ iti_end }| # lick-bout false alarms (bouts in ITI)
A  = Σ_t  1[ pokes(t) ≠ ∅ ]                        # trials with ≥1 nose poke anywhere
E  = Σ_t  1[ ∃ p ∈ pokes(t) : 0 ≤ p ≤ dur ]        # trials with ≥1 poke in the cue window
R  = Σ_t  1[ is_hit(t) ]                           # rewarded trials
RE = Σ_t  1[ is_hit(t) AND (∃ p ∈ pokes(t): 0 ≤ p ≤ dur) ]  # rewarded AND on-cue-engaged
P_off = Σ_t |{ p ∈ pokes(t) : p < 0 OR p > dur }|  # poke events outside the cue window
L  = { min{ p ∈ pokes(t) : 0 ≤ p ≤ dur }  for each trial that has such a poke }  # first on-cue poke times
```

Note: bout onsets with `o < 0` (a bout starting before the cue) are **ignored** —
counted as neither hit nor false alarm.

---

## 3. The metrics (as they appear in the axis menus)

| Menu label | Key | Formula | Units | Range | Undefined (blank) when |
|---|---|---|---|---|---|
| accuracy = hits / (hits + false alarms) | `accuracy` | `100 · H / (H + F)` | % | 0–100 | `H + F = 0` (no licking at all) |
| success rate = hits / trials | `success_rate` | `100 · H / N` | % | 0 – >100 | `N = 0` |
| engagement (any poke) | `engagement_any` | `100 · A / N` | % | 0–100 | `N = 0` |
| on-cue engagement | `engagement_oncue` | `100 · E / N` | % | 0–100 | `N = 0` |
| hit rate | `hit_rate` | `100 · R / N` | % | 0–100 | `N = 0` |
| competence (accuracy \| engaged) | `competence` | `100 · RE / E` | % | 0–100 | `E = 0` (never engaged on-cue) |
| false-alarm rate = FA / trials | `fa_rate` | `100 · F / N` | % | 0 – >100 | `N = 0` |
| off-cue pokes / trial | `offcue` | `P_off / N` | pokes per trial | ≥ 0 | `N = 0` |
| latency to engage | `latency` | `median(L)` | seconds | ≥ 0 | `L = ∅` (no on-cue poke all session) |
| session length | `n_trials` | `N` | trials | ≥ 0 | — |

### Why some rates exceed 100%
`success_rate` and `fa_rate` divide a **bout count** by trials. A single trial can
contain several lick bouts (especially a long ITI with repeated dry licking), so
`H` or `F` can exceed `N` → the rate can exceed 100%. This is intentional; the axes
auto-scale so nothing is clipped.

---

## 4. Plain-English gloss (and the one you asked about)

- **accuracy** — of all the licking bouts the mouse produced (in the response window
  or the ITI), what fraction landed in the *right* window (the response window).
  High = temporally precise licking; low = lots of impulsive ITI licking.
- **success rate** — how many cue-response lick bouts per trial (as a %). How often
  it "scored".
- **engagement (any poke)** — the fraction of trials in which the mouse poked its
  nose into the port **at least once, at any time in the trial** — during the cue,
  during the ITI, or just before onset. It's a coarse "did the animal interact with
  the port at all this trial" measure. Because it ignores *when* the poke happened,
  it is usually high and not very selective.
- **on-cue engagement** — the stricter version: fraction of trials with a poke
  **inside the cue window `[0, dur]`**. This is the one that tracks cue-driven
  behaviour; prefer it over "any poke" when you want a learning signal.
- **hit rate** — fraction of trials that actually delivered water (`is_hit`).
- **competence** — among the trials where the mouse engaged on-cue, the fraction
  that were rewarded = `P(reward | engaged on-cue)`. "When it tries, does it succeed."
- **false-alarm rate** — cue-inappropriate lick bouts (during the ITI) per trial.
- **off-cue pokes / trial** — mean number of poke *events* outside the cue window;
  an impulsivity measure.
- **latency to engage** — median time from cue onset to the first in-cue poke, over
  the trials where it engaged. Lower = faster to respond.
- **session length** — number of trials that session.
