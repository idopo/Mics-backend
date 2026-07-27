# Session list — canonical reference (this dataset)

**This is the authoritative session list for this dataset. Use these
sessions for all analyses going forward (Gili & Noa).**

## How a session is defined

A **session = one mouse + one lab-local calendar day** (Asia/Jerusalem).

- Sessions are derived from the subject/mouse name, then split by the day
  each trial ran — not by the Elasticsearch `session` counter, which is
  unreliable (it sometimes fails to advance and merges two different days
  under one number — e.g. m100 appetitive had four 122-trial "double days").
- Any files or subject-strings from the **same calendar day merge into one
  session** (e.g. a morning + afternoon run, or `_2` continuation strings).
- A same-day aborted false-start is trimmed; sessions are numbered 1..N in
  chronological order per mouse per task.
- A session is **valid** when its trial count is within the 50-72 band
  (nominal 60). Out-of-band days are listed but excluded from analyses.

Source of truth: `session_inventory.csv`  ·  181 sessions total.

## Counts per mouse x task (valid / total)

| mouse | appetitive | generalization | extinction |
|---|---|---|---|
| m90 | 13 / 13 | 4 / 4 | 2 / 2 |
| m92 | 12 / 13 | 4 / 4 | 2 / 2 |
| m93 | 12 / 12 | 4 / 4 | 2 / 2 |
| m97 | 8 / 8 | 4 / 4 | 2 / 2 |
| m98 | 12 / 12 | 4 / 5 | 1 / 2 |
| m100 | 12 / 13 | 4 / 4 | 2 / 2 |
| m101 | 12 / 12 | 4 / 4 | 2 / 2 |
| m102 | 11 / 13 | 4 / 4 | 2 / 2 |
| m103 | 12 / 12 | 4 / 4 | 2 / 2 |
| m104 | 12 / 12 | 4 / 4 | 2 / 2 |

## Out-of-band sessions (excluded from analyses)

| task | mouse | session | date | trials |
|---|---|---|---|---|
| appetitive | m92 | 9 | 2025-11-26 | 46 |
| appetitive | m100 | 12 | 2025-12-10 | 4 |
| appetitive | m102 | 2 | 2025-11-11 | 42 |
| appetitive | m102 | 12 | 2025-12-16 | 35 |
| generalization | m98 | 2 | 2025-12-31 | 30 |
| extinction | m98 | 2 | 2026-01-14 | 0 |

## Appetitive — full session list

**m90** (13 sessions): s1=2025-11-09(60t), s2=2025-11-11(60t), s3=2025-11-12(60t), s4=2025-11-13(60t), s5=2025-11-16(60t), s6=2025-11-18(60t), s7=2025-11-19(60t), s8=2025-11-23(60t), s9=2025-11-26(61t), s10=2025-12-02(60t), s11=2025-12-07(60t), s12=2025-12-09(60t), s13=2025-12-16(60t)
**m92** (13 sessions): s1=2025-11-09(60t), s2=2025-11-11(60t), s3=2025-11-12(60t), s4=2025-11-13(60t), s5=2025-11-16(60t), s6=2025-11-18(60t), s7=2025-11-19(62t), s8=2025-11-24(60t), s9=2025-11-26(46t,oob), s10=2025-12-02(60t), s11=2025-12-07(60t), s12=2025-12-09(60t), s13=2025-12-17(60t)
**m93** (12 sessions): s1=2025-11-10(59t), s2=2025-11-11(60t), s3=2025-11-12(60t), s4=2025-11-13(60t), s5=2025-11-17(60t), s6=2025-11-18(60t), s7=2025-11-19(65t), s8=2025-11-24(60t), s9=2025-12-01(63t), s10=2025-12-03(60t), s11=2025-12-07(60t), s12=2025-12-10(60t)
**m97** (8 sessions): s1=2025-11-10(60t), s2=2025-11-11(60t), s3=2025-11-12(60t), s4=2025-11-13(60t), s5=2025-11-17(60t), s6=2025-11-18(60t), s7=2025-11-20(60t), s8=2025-11-24(60t)
**m98** (12 sessions): s1=2025-11-10(61t), s2=2025-11-11(61t), s3=2025-11-12(61t), s4=2025-11-13(61t), s5=2025-11-17(61t), s6=2025-11-18(61t), s7=2025-11-20(61t), s8=2025-11-24(61t), s9=2025-12-01(61t), s10=2025-12-03(61t), s11=2025-12-08(61t), s12=2025-12-15(61t)
**m100** (13 sessions): s1=2025-11-10(61t), s2=2025-11-11(61t), s3=2025-11-12(61t), s4=2025-11-13(61t), s5=2025-11-17(61t), s6=2025-11-19(61t), s7=2025-11-23(62t), s8=2025-11-25(61t), s9=2025-12-01(61t), s10=2025-12-03(61t), s11=2025-12-08(61t), s12=2025-12-10(4t,oob), s13=2025-12-15(61t)
**m101** (12 sessions): s1=2025-11-10(60t), s2=2025-11-12(61t), s3=2025-11-13(61t), s4=2025-11-16(61t), s5=2025-11-18(61t), s6=2025-11-19(61t), s7=2025-11-23(62t), s8=2025-11-25(61t), s9=2025-12-02(61t), s10=2025-12-03(61t), s11=2025-12-08(60t), s12=2025-12-15(61t)
**m102** (13 sessions): s1=2025-11-10(61t), s2=2025-11-11(42t,oob), s3=2025-11-12(61t), s4=2025-11-13(61t), s5=2025-11-17(61t), s6=2025-11-19(61t), s7=2025-11-23(61t), s8=2025-11-25(61t), s9=2025-12-02(61t), s10=2025-12-03(61t), s11=2025-12-08(61t), s12=2025-12-16(35t,oob), s13=2025-12-17(61t)
**m103** (12 sessions): s1=2025-11-10(61t), s2=2025-11-12(61t), s3=2025-11-13(61t), s4=2025-11-16(61t), s5=2025-11-18(61t), s6=2025-11-19(61t), s7=2025-11-23(61t), s8=2025-11-25(61t), s9=2025-12-02(61t), s10=2025-12-07(61t), s11=2025-12-09(61t), s12=2025-12-16(61t)
**m104** (12 sessions): s1=2025-11-09(60t), s2=2025-11-10(60t), s3=2025-11-16(60t), s4=2025-11-18(60t), s5=2025-11-19(60t), s6=2025-11-23(60t), s7=2025-11-25(60t), s8=2025-12-02(60t), s9=2025-12-07(60t), s10=2025-12-09(60t), s11=2025-12-16(60t), s12=2025-12-17(60t)

## Generalization — full session list

**m90** (4 sessions): s1=2025-12-28(61t), s2=2025-12-29(60t), s3=2026-01-01(61t), s4=2026-01-04(61t)
**m92** (4 sessions): s1=2025-12-28(61t), s2=2025-12-29(60t), s3=2026-01-01(61t), s4=2026-01-04(61t)
**m93** (4 sessions): s1=2025-12-28(61t), s2=2025-12-30(60t), s3=2026-01-01(61t), s4=2026-01-04(61t)
**m97** (4 sessions): s1=2025-12-29(61t), s2=2025-12-31(60t), s3=2026-01-04(61t), s4=2026-01-05(61t)
**m98** (5 sessions): s1=2025-12-29(61t), s2=2025-12-31(30t,oob), s3=2026-01-04(61t), s4=2026-01-05(61t), s5=2026-01-06(60t)
**m100** (4 sessions): s1=2025-12-28(61t), s2=2025-12-30(60t), s3=2026-01-01(61t), s4=2026-01-05(61t)
**m101** (4 sessions): s1=2025-12-28(61t), s2=2025-12-30(60t), s3=2026-01-01(61t), s4=2026-01-05(61t)
**m102** (4 sessions): s1=2025-12-28(61t), s2=2025-12-30(60t), s3=2026-01-01(61t), s4=2026-01-05(61t)
**m103** (4 sessions): s1=2025-12-29(61t), s2=2025-12-31(61t), s3=2026-01-04(61t), s4=2026-01-05(62t)
**m104** (4 sessions): s1=2025-12-29(61t), s2=2025-12-31(61t), s3=2026-01-04(61t), s4=2026-01-05(61t)

## Extinction — full session list

**m90** (2 sessions): s1=2026-01-11(61t), s2=2026-01-12(61t)
**m92** (2 sessions): s1=2026-01-11(61t), s2=2026-01-12(61t)
**m93** (2 sessions): s1=2026-01-11(61t), s2=2026-01-12(61t)
**m97** (2 sessions): s1=2026-01-11(61t), s2=2026-01-12(61t)
**m98** (2 sessions): s1=2026-01-13(65t), s2=2026-01-14(0t,oob)
**m100** (2 sessions): s1=2026-01-11(61t), s2=2026-01-12(61t)
**m101** (2 sessions): s1=2026-01-12(61t), s2=2026-01-13(61t)
**m102** (2 sessions): s1=2026-01-11(61t), s2=2026-01-13(61t)
**m103** (2 sessions): s1=2026-01-12(61t), s2=2026-01-13(68t)
**m104** (2 sessions): s1=2026-01-12(61t), s2=2026-01-13(61t)
