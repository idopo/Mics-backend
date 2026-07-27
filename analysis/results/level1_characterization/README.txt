LEVEL-1 CHARACTERIZATION — output guide
==================================================

Task: appetitive tone-detection (AppetitveTaskReal). Every trial is a
go-tone; the mouse pokes during the tone, licks, and earns water (HIT).
An ITI nose-poke is a FALSE ALARM and triggers PUNISHMENT (ITI reset).
There are no explicit no-go trials, so 'correct rejection' is implicit
(an ITI with no poke) and correct_rejection_rate == 100 - false_alarm_rate.

Sessions are segmented by LAB-DAY (one per calendar day), not the ES
session counter (which merged two days for m100). session_date = the day;
session = the 1..N training ordinal.

KEY DEFINITIONS
  performance_score = 100 * hits / participated_trials  (the LEARNING metric)
  hit_rate          = 100 * hits / total_trials         (raw, engagement-limited)
  participation_rate= 100 * engaged_trials / total_trials
  reward_rate       == hit_rate      (1 reward per hit)
  punishment_rate   == false_alarm_rate
  Criterion: performance_score >= 70% on 2 consecutive sessions
            (a session needs >= 8 engaged trials to count).
  activity level is a PROXY (pokes+licks/trial); no locomotion is logged.

FILES
  mouse_session_summary.csv          one row per mouse x session, all metrics
  mouse_learning_criterion_summary.csv  one row per mouse + preliminary_type
  figure_01_mouse_session_performance_heatmap.{png,svg}
  figure_02_learning_curve_per_mouse.{png,svg}
  figure_03_false_alarm_curve_per_mouse.{png,svg}
  figure_04a_participation_curve_per_mouse.{png,svg}
  figure_04b_participation_heatmap.{png,svg}
  figure_05_reward_punishment_per_session.{png,svg}
  figure_06_trial_by_trial_raster.{png,svg}   (+ trial_rasters_by_mouse/)
  figure_07_mouse_summary_metrics.{png,svg}

RESULT: 7/10 mice reached the learning criterion.

PRELIMINARY PHENOTYPES (Level-1 only — do not over-interpret):
  m100   high-punishment mouse                  [part=36% perf=74% FA=65% lat=3.5s cross@=2.0]
  m101   low-participation mouse                [part=18% perf=46% FA=45% lat=3.5s cross@=nan]
  m102   high-punishment mouse                  [part=39% perf=89% FA=69% lat=2.8s cross@=1.0]
  m103   strong learner                         [part=25% perf=74% FA=58% lat=3.4s cross@=2.0]
  m104   slow but accurate mouse                [part=22% perf=63% FA=58% lat=4.1s cross@=4.0]
  m90    high-punishment mouse                  [part=31% perf=80% FA=65% lat=3.7s cross@=2.0]
  m92    low-participation mouse                [part=17% perf=56% FA=44% lat=3.3s cross@=nan]
  m93    slow but accurate mouse                [part=21% perf=93% FA=59% lat=3.9s cross@=1.0]
  m97    high-punishment mouse                  [part=45% perf=92% FA=79% lat=3.0s cross@=1.0]
  m98    low-participation mouse                [part=11% perf=59% FA=36% lat=4.1s cross@=nan]
