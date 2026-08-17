# Superseded — the lgpio rewrite (archived 2026-08-17)

These seven plans implemented the pigpio→lgpio migration. They were **withdrawn** when a hardware
audit found that under lgpio a GPIO line cannot be output-claimed and alert-claimed at the same
time (`lgGpio.c:1104-1108` frees the line and re-requests it as `INPUT`; `:1437-1443` re-claims it
as output on the next write), so every `Digital_Out` on the rig would have silently lost its
hardware-timestamped edge events.

**Do not execute these.** They are kept for two reasons:

1. If a Pi 5 / RP1 PIO phase is ever opened, plans 11-13 hold the verified port inventory
   (pigpio call sites, per-class reference counts, I²C surface) that would still be needed.
2. Plans **14** (dual-timebase dispatcher) and **15** (clock-freeze removal, `--final` F3
   retirement) contain the clock work whose substance moved into the new `C2`/`C3` plans. Their
   analysis is sound; only the timestamp source changed.

Authoritative current scope: `../31-REVISED-SCOPE.md`.
