# Phase 31 — REVISED SCOPE (2026-08-17)

> **This document supersedes the lgpio portion of the phase.** `CONTEXT.md`, `31-RESEARCH.md`,
> `31-VALIDATION.md` and plans `31-10` through `31-16` were written against a premise that a
> hardware audit has now disproved. Stages 1 and 2 of the phase are unaffected and proceed as
> planned. Read this before `31-RESEARCH.md`; where they disagree, this document wins.

---

## 1. The finding that forced the revision

**Under lgpio, a GPIO line cannot be output-claimed and alert-claimed at the same time.** Every
`Digital_Out` on the rig (`LED1-3`, `OG_TRIGGER`, `TTL1`, `VALVE1-4`, `ODOR1-5`, `AIR_PUF`,
`AIR_PUF_S`) registers an edge callback in `Digital_Out.__init__` (`gpio.py:359` → `:414`) and is
*then* set to output (`gpio.py:374`). That is how output events are logged today.

Verified in three independent places:

| Evidence | What it shows |
|---|---|
| `lgGpio.c:1104-1108` (`lgGpioClaimAlert`) | calls `xSetAsFree(chip, gpio)` then re-requests the line with `GPIO_V2_LINE_FLAG_INPUT` — alert-claiming an output **converts it to an input** |
| `lgGpio.c:1437-1443` (`lgGpioWrite`) | a write to a non-output line silently calls `xSetAsOutput` — **tearing the alert claim down**. The two states ping-pong; they never coexist |
| `/usr/include/linux/gpio.h` + `gpiolib` | edge detection is a line-request flag requiring `INPUT`; `gpiochip_lock_as_irq()` refuses an IRQ on a line flagged as output. **This is the kernel's rule, not lgpio's choice** |

**Forking lgpio cannot fix it.** `lg` contains no `mmap`, no `/dev/mem`, no `gpiomem`, no DMA —
grepped across every `.c`/`.h` in `lgpio-0.2.2.0/src/`. It is a pure ioctl wrapper over the kernel
chardev, with no hardware access of its own to extend. A forked `lg` would issue the same ioctl and
receive the same `-EINVAL`/`-EIO`.

### Two options were considered and rejected by the user

- **Loopback jumpers** (output → spare input, kernel IRQ-timestamps the real edge). Rejected: MICS
  is a deployed platform, not a bespoke rig. Per-rig soldering makes every future pilot a hardware
  project. Also infeasible as-is — **24 of the 26 usable header pins are assigned**; the only two
  free are BOARD 3/5 = BCM 2/3 = the I²C pair.
- **Hybrid** (lgpio drives, `pigpiod` DMA-samples for timestamps). Rejected on the user's own
  single-clock requirement: pigpio's tick comes from the BCM system timer while kernel edge events
  come from `CLOCK_MONOTONIC` — two counters, related by a drifting calibrated offset. That is
  precisely the time bias PLAT-27 exists to forbid.

### A second regression lgpio would have introduced

`lgPthTx.c:182` generates pulses with **`clock_nanosleep` in a userspace thread** — software-timed.
So porting `Pulse20Hz` (the 62.5 Hz optogenetic train) to lgpio would make the *stimulus itself*
scheduler-dependent, while simultaneously removing the DMA sampler that is the only thing able to
measure that jitter. Today pigpio's 5 µs sampling reports when the light pulses **actually** fired.

**Conclusion: the capability the rig depends on — hardware-timestamped output edges, out of the box,
no rewiring — exists today only via userspace DMA sampling of the GPIO block. That is pigpio, or a
reimplementation of pigpio. lgpio is architecturally the wrong layer to ask.**

---

## 2. The finding that redefined the goal

**The single-clock invariant is already broken in production, roughly 20 times a day.** This is the
real 24/7 defect, and it has nothing to do with pigpio vs lgpio.

Read from the deployed client, `~/.venv/autopilot/lib/python3.7/site-packages/pigpio.py`:

- The callback thread has its **own** converter (`:1206-1207`):
  `timestamp = (tick/1000000.) + self.synchronize` — **no wrap detection at all**.
- `pi.ticks_to_timestamp` (`:5320-5322`) **does** detect wrap: `if ticks < self._last_synced_tick:
  self.synchronize()`.
- The thread received its offset **by value** (`:5264` → `:1157`), so re-syncs never reach it.

The tick is a 32-bit microsecond counter (`MSG_SIZ = 12`, `struct.unpack('HHII', msgbuf)` — the tick
is an `I`), so it wraps every **71.6 minutes**. On each wrap the callback path computes
`tick/1e6 + offset` from a tick that just restarted at zero, so **every GPIO event timestamp jumps
backwards by 4294.97 seconds** and stays wrong until the next wrap. `datetime.fromtimestamp` does
not raise — `1.7e9 + 4295` is a perfectly valid timestamp. It is simply the wrong one.

Meanwhile `Event_Dispatcher` goes through the `pi` object, which *does* re-sync. **After the first
wrap the two event paths are on different clocks** — the exact violation PLAT-27 forbids, occurring
every ~72 minutes under the continuous operation this phase is meant to enable.

### Provenance: this is not upstream pigpio's design

`sync_ticks` (`:5207`), `synchronize()`, and both `ticks_to_timestamp` implementations are
**Autopilot patches**, not upstream. Stock pigpio hands out raw 32-bit ticks and documents that the
caller must handle wrap. **Every defect above lives in those ~50 patched lines.** The `pigpiod` C
daemon — the DMA sampler, the genuinely hard part — is stock and is not implicated.

---

## 3. Revised approach

**Keep the DMA sampler. Replace the clock layer. Drop the lgpio rewrite.**

| Layer | Decision | Rationale |
|---|---|---|
| `pigpiod` DMA sampler | **Keep, stock upstream** (rig runs a v78 source build) | Produces the hardware tick before any of our code runs. Has no 24/7 defect. Reimplementing it is weeks-to-months and Pi 4-only anyway |
| Vendored patched `pigpio.py` | **Delete entirely**; pin the stock **client** from PyPI | Source of every clock defect; untracked in git; invisible to review |
| Clock / timestamping | **Clean-room MICS-owned module** | Where 100% of the defects are. Small, well understood, and **library-independent — it survives any future GPIO backend** |
| lgpio rewrite (plans 11-16) | **Dropped from this phase** | Costs hardware output timestamps and adds software-timed pulse generation, for a Pi 5 capability not currently required |
| Pi 5 | **Deferred**, pending an RP1 PIO investigation | RP1's PIO block can drive *and* timestamp with cycle-exact hardware timing, no wires — potentially better than today. New development; see §7 |

### The clock design

Canonical clock: **one monotonic timeline**, with hardware edges never passing through a
load-dependent step.

- **GPIO edges** keep their DMA-sampled hardware tick, extended to 64 bits and mapped through a
  single calibrated tick ↔ `CLOCK_MONOTONIC` relation. Both are free-running hardware counters off
  the same crystal, so the relation is near-fixed and re-fit periodically.
- **Software events** (state transitions, dispatcher-originated) read `clock_gettime_ns(CLOCK_MONOTONIC)`
  directly — no socket round trip.
- The mapping is **common-mode**: it shifts every event identically, so **intervals between hardware
  events are exact and load-independent**, which is the property the science depends on.

Why 64 bits is available without touching the wire protocol: the BCM System Timer is a **64-bit**
free-running 1 MHz counter (`CLO`/`CHI`); pigpio only ever exposes the low half. The notify thread
dispatches **all** callbacks for **all** GPIOs sequentially (`run()` → `for cb in self.callbacks`),
so it sees every tick in arrival order, and the tick can be extended to a 64-bit monotonic
microsecond counter — at 1 MHz, 64 bits is ~584,000 years. A **64-bit OS does not fix this**; the
wrap is a protocol field width, not a word size.

> ⚠ **CORRECTION 2026-08-17 — do not implement `if tick < last_tick: wraps += 1`.** That naive rule
> is correct only for a single strictly-ordered stream. PLAT-29 also requires a **heartbeat on a
> different thread** feeding the same counter, and one heartbeat sample arriving microseconds out of
> order is then read as a wrap. Measured: the naive rule turns a 20 µs advance into **4294967316 µs**
> — a **+4294.967 s** injection, the same magnitude as the defect being deleted, from our own code.
>
> Use modular extension instead: `d = (tick - last) % 2**32`, then advance by `d` if `d <= 2**31`,
> else treat it as a small backward step of `-(2**32 - d)`. This handles genuine wraps and
> out-of-order samples correctly. Its price is a structural ambiguity limit of **2**31 µs = 35.79
> min**, which is precisely *why* the heartbeat bound is half the wrap period — the bound is not a
> safety margin, it is what makes the algorithm well-defined.
>
> A second hazard in the same area: a periodic re-fit of the tick ↔ `CLOCK_MONOTONIC` mapping must
> be **continuity-preserving** — re-anchored so the new fit agrees with the old at the changeover
> instant. A naive coefficient swap steps the output and puts a backward jump into the very series
> C4 asserts has none. **A re-fit changes the rate, never the value.**

### The seam is one the phase already specified

PLAT-27 already placed the adapter **inside `assign_cb`**, preserving its signature so `task.py:199`
never changes. That design was written for the lgpio port; it is the same seam here, with a different
timestamp source. `localize_tz`'s contract still changes from ISO-string to integer — already scoped.

### What is honestly *not* preserved

- **Software-originated events remain software-timed.** They become *comparable* on one timeline;
  they do not acquire hardware precision. Events must therefore be **marked** with their precision
  class so analysis can tell them apart (new requirement, PLAT-31).
- **Delivery latency and capacity remain load-sensitive.** Timestamps stay correct, but under
  starvation events arrive late, and beyond `pigpiod`'s sample buffer (`PIGPIOARGS` has no `-b`, so
  the 120 ms default applies) samples are **dropped**. Dropped events must be detected and reported,
  not silently lost (new requirement, PLAT-32).

---

### Two artifacts, two version numbers — do not conflate them

*(Correction 2026-08-17, found during replan.)* The **C daemon** (`pigpiod`, v78 on the rig, v79
upstream) and the **Python client** (`import pigpio`, versioned separately on PyPI, pure Python
`py3-none-any`) are different artifacts. `requirements.txt` pins the **client**; `install.sh`
installs the **daemon** via apt. An executor told to "pin v79" will not find it. Resolve the client
pin at execution time against the PyPI JSON API, and give the wheel-check an explicit
pure-Python allow-list entry alongside `Adafruit-PureIO`.

### Installing stock pigpio breaks the run path until C2/C3 land

*(Correction 2026-08-17.)* `pilot.py:1073` calls `pigpio.pi(sync_ticks=True)` and `:1079` calls
`self.pi.synchronize()`. Both are **patch-only** — stock pigpio has neither, so `pi(sync_ticks=True)`
raises `TypeError`. This is bounded: it fires only on the run path when a task starts, which plan 09
never exercises. But §6's claim that plan 09 is "no longer an awkward intermediate state" was too
clean — it *is* an intermediate state, just a differently-shaped one, and plan 09 names it.

A knock-on: PLAT-09 (restart-without-latching) used to get its evidence for free, because the pilot
crash-looped on a missing pigpio import. It no longer crashes, so plan 09 must **force** a
10-kills-in-30-seconds storm to prove `StartLimitIntervalSec=0`.

## 4. What the rig actually runs (verified 2026-08-17)

| Fact | Value |
|---|---|
| Hardware / OS | Pi 4B rev 1.5, Raspbian Buster 10, kernel `5.10.103-v7l+`, `armv7l` |
| `pigpiod` | source build in `/usr/local/bin` (Apr 2022), **v78**; not a dpkg package |
| Client | patched `pigpio.py` in `~/.venv/autopilot/lib/python3.7/site-packages/` |
| `PIGPIOARGS` | `-t 0 -l` → PWM clock peripheral (PCM left free for audio), remote socket disabled, **no `-s`, so the default 5 µs sample rate**, no `-b`, so the default 120 ms buffer |
| `PIGPIOMASK` | `1111110000111111111111110000` |
| Time sync | `NTP service: inactive`; `ntp 4.2.8p12` installed; clock synchronised |
| chardev | `/dev/gpiochip0` and `gpiochip1` **already present on Buster** |
| Pin budget | 24 of 26 usable header pins assigned; free = BOARD 3/5 (BCM 2/3, the I²C pair) |

---

## 5. Requirement disposition

**Unchanged (stages 1-2):** PLAT-01, 02, 03, 04, 05, 06, 07, 08, 09, 23, 26.

**Revised:**

| ID | Change |
|---|---|
| PLAT-03 | must additionally pin **stock upstream pigpio** |
| PLAT-10 | drop the `LG_WD` clause; keep `WorkingDirectory=` + `RuntimeDirectory=` |
| PLAT-11 | `gpio`/`i2c` group membership still required; add `pigpiod`'s access requirements |
| PLAT-17 | `SCHED_FIFO` justification changes from *lgpio tx jitter* to **notification-drain headroom** (preventing dropped samples), still measurement-backed |
| PLAT-18 | retargeted: the dispatcher accepts the **extended hardware tick** rather than a kernel edge timestamp |
| PLAT-21 | relaxed — with monotonic-primary timestamps, blocking on clock convergence is no longer required for correctness |
| PLAT-22 | line range corrected to `pilot.py:1071-1082`; the deletion now happens **because NTP is safe**, not as part of an lgpio port |
| PLAT-24 | paired capture is now **before/after the clock refactor** (no regression), not pigpio-vs-lgpio |

**Deferred to a future phase** (the lgpio rewrite): **PLAT-12, PLAT-13, PLAT-14, PLAT-15, PLAT-16.**
Not cancelled — they become the requirement set of the Pi 5 / RP1 PIO phase if that path is taken.

**Unchanged and now central:** PLAT-19, PLAT-20, PLAT-25, PLAT-27.

**New:**

| ID | Requirement |
|---|---|
| **PLAT-28** | **Stock pigpio, no vendored patch.** The patched `pigpio.py` is deleted; `requirements.txt` pins upstream pigpio; nothing monkey-patches the library; all clock logic lives in a MICS-owned, git-tracked, tested module. No untracked venv file may carry behaviour |
| **PLAT-29** | **64-bit tick extension.** A wrap counter maintained where every tick is seen in order reconstructs a monotonic 64-bit microsecond counter, plus a heartbeat polling `get_current_tick()` at no more than half the wrap period so quiet stretches cannot lose a wrap. Proven across ≥3 wraps with zero backward jumps |
| **PLAT-30** | **One shared clock object.** A single calibrated tick ↔ `CLOCK_MONOTONIC` relation is read by **both** event paths — no scalar snapshot copies (the existing defect), re-fit periodically, and **failures are loud**: the silent revert to raw ticks at `:1214` is removed |
| **PLAT-31** | **Timestamp provenance is explicit.** Every event records whether its timestamp is hardware-captured (DMA edge) or software-read, so analysis never assumes uniform precision |
| **PLAT-32** | **Sample and notification loss is detected and reported.** `pigpiod` buffer overflow or dropped notifications surface as an error with a count, never as silence |
| ~~**PLAT-33**~~ | ⛔ **WITHDRAWN 2026-08-17 — see below.** *(Was: `pigpiod` runs as its own systemd unit ordered before `mics-pilot.service`; the pilot no longer spawns it.)* |

### PLAT-33 withdrawn — the `pigpiod` spawn stays in the pilot (user decision, 2026-08-17)

**This was my scope addition, not a user requirement.** It appeared in this document's §5 "New" table
during the replan, was never asked for, and it traded a real safety property for a supervision
property. The user was asked and chose to leave the spawn where it is.

**The reasoning, which is decisive and belongs in the record:**

The decision was taken on the belief that `external.start_pigpiod()`'s `kill_proc` hook
(`external/__init__.py:55-60`) kills the daemon at session end and thereby drops every output.

**⚠ VERIFIED FALSE 2026-08-17 — the fail-safe does not work as described.** Read
`external/__init__.py:52`: `proc = subprocess.Popen('sudo ' + launch_pigpiod, shell=True)`. With
`shell=True`, `proc` is the `/bin/sh -c` process, **not** `pigpiod`. `PIGPIOARGS` is `"-t 0 -l"` with
**no `-g`**, so `pigpiod` daemonises — it forks, the parent exits, `sudo` exits, the shell exits — and
by the time `kill_proc` runs at `:56-57` `proc` is already gone, so `proc.kill()` kills nothing.
`sudo` also means the daemon runs as root, so a `User=pi` pilot could not signal it even with the
right pid. **The daemon already outlives the pilot today, and outputs are NOT dropped at session
end.** PLAT-33 was withdrawn on the belief that this hook was a fail-safe; the withdrawal **stands by
user instruction**, but its premise is void. **Neither the current design nor a supervised unit is
fail-safe** — a real one (something that de-energises solenoids when the pilot is absent, regardless
of how `pigpiod` is managed) is separate, unscheduled work. Plan 09 Step 12 and C4 Step 4 **measure**
this; nothing may assert it. Canonical wording: `31-C4-PLAN.md`'s NOT PROVEN entry. Making `pigpiod` an independently supervised unit inverts that: the daemon would
**outlive** the pilot, so a pilot crash mid-trial with a solenoid energised would leave
**`VALVE1-4` / `AIR_PUF` / `ODOR1-5` open**, with no process left to close them. That is an
animal-welfare hazard, and §3's own fail-safe note already flagged that the pigpio design has no
process-death line release.

So the current design **fails safe** and the systemd version would not, absent additional fail-safe
work (a daemon-side safe-state on client disconnect, or a watchdog) that is not in this phase and
that the user does not want in this phase. Supervision is worth less than a closed valve.

**What still happens, and what does not:**

| Item | Disposition |
|---|---|
| `apt install pigpio` in `install.sh` | **Stays.** `external/__init__.py:15` gates on `shutil.which('pigpiod')` and `start_pigpiod()` raises `ImportError` without the binary. The daemon package is still required |
| `deploy/pigpiod-mics.conf` drop-in | **Dropped** from plan 05 |
| `systemctl enable pigpiod` in `install.sh` | **Dropped** from plan 07 |
| `After=` / `Requires=pigpiod.service` on `mics-pilot.service` | **Dropped** from plan 05 |
| `pilot.py:949 external.start_pigpiod()` and its `:206` call | **KEPT.** C3 no longer deletes them, so `init_pigpio()` is **not** emptied and `:947-953` survives intact |
| `PIGPIOARGS` / `PIGPIOMASK` | **Single-sourced in `prefs.json`.** The two-sources-of-truth problem plan 05 handed to C3 never arises and that handoff is deleted |
| Plan 09's mandatory 10-kills-in-30-seconds restart storm | **KEPT.** It is still the only proof of `StartLimitIntervalSec=0` |

Everything else in plan 05 is unchanged: the `LG_WD` removal, `WorkingDirectory=`/`RuntimeDirectory=`,
chrony, the PLAT-21 relaxation and the `SCHED_FIFO` rejustification all stand on their own reasons.

---

## 6. Plan disposition

| Plan | Disposition |
|---|---|
| 31-01 branch + dev-host harness + fakes | **Keep** — `fake_lgpio` becomes a fake pigpio **notification stream** (the seam the clock module is tested against), with edge injection and wrap simulation |
| 31-02 the shed | **Keep unchanged** |
| 31-03 Python 3.11 + numpy aliases + requirements | **Keep** — add the stock pigpio pin. Note `gpio.py:1039/1042/1077` live in `PWM`, which is **no longer deleted**, so all five sites stay in scope |
| 31-04 prefs render | **Keep unchanged** |
| 31-05 systemd units | **Keep** — drop `LG_WD`. *(2026-08-17: the `pigpiod` unit and the `After=`/`Requires=pigpiod.service` ordering are **removed** with PLAT-33's withdrawal.)* |
| 31-06 pulse-timing harness | **Keep, repurposed** — proves the clock fix rather than comparing GPIO libraries |
| 31-07 installer | **Keep** — installs stock pigpio instead of purging it |
| 31-08 Buster baseline capture | **Keep, de-risked** — the "one-way door" largely dissolves: nothing irreplaceable is being rescued now that the patch is not carried forward. A timing **baseline** is still wanted, but it is measurement data, not code |
| 31-09 flash + provision + first boot | **Keep** — and it is no longer an awkward intermediate state, since pigpio is the destination |
| 31-10 lgpio spike / decision gate | **Dropped** |
| 31-11 lgchip + I²C port | **Dropped** (PLAT-12/13 deferred) |
| 31-12 `Digital_In` + edge port | **Dropped as written**; its `assign_cb` adapter and `localize_tz` contract work **carries into** the new clock plans |
| 31-13 `Digital_Out` tx port | **Dropped** (PLAT-15 deferred). `PWM` and `LED_RGB` are **no longer deleted** — that decision was a consequence of the lgpio port |
| 31-14 dispatcher timebase | **Substance carries forward** into the clock plans (PLAT-18/19) with the timestamp source changed |
| 31-15 pigpio removal + clock-freeze | **Split** — pigpio removal dropped; the clock-freeze deletion and F3 retirement (PLAT-22) carry forward |
| 31-16 hardware acceptance campaign | **Keep, retargeted** — acceptance is now the clock soak, not an lgpio comparison |

**New plans (clean-room clock layer):**

| New | Content |
|---|---|
| **C1** | The clock module: 64-bit wrap extension, heartbeat, calibrated mapping, shared object, loud failures (PLAT-29, PLAT-30). TDD against the fake notification stream from 31-01 |
| **C2** | The `assign_cb` adapter: keeps its signature, converts raw tick → `t_mono_ns`, updates `localize_tz`'s contract, puts **both** event paths on the one clock, marks provenance (PLAT-18, PLAT-19, PLAT-27, PLAT-31) |
| **C3** | Cut over to stock pigpio: delete the vendored patch, pin upstream, chrony enabled, clock-freeze block deleted and the F3 guard retired (PLAT-20, PLAT-22, PLAT-28). *(2026-08-17: the `pigpiod`-as-a-unit item is gone with PLAT-33; `pilot.py:949 external.start_pigpiod()` **stays**.)* |
| **C4** | Acceptance soak (PLAT-24, PLAT-25, PLAT-32) — see §8 |

Approximate shape: **13 plans** rather than 16, with the six highest-risk ones replaced by four
smaller, well-understood ones.

---

## 7. Deferred: Pi 5 / RP1 PIO

Pi 5 support is **deferred, not abandoned**. The path is **not** lgpio — it is the RP1's **PIO**
block, which can drive *and* timestamp pins with cycle-exact hardware timing, no wires and no kernel
patch. If it delivers, it would be **better than today**: hardware-timed optogenetic trains *and*
hardware-captured edges.

Recommended as **its own phase**, scoped as a research spike before any implementation. *(The user
did not state a preference on placement; this is an assumption and is easy to change — the
alternative is a scoping task inside this phase.)*

Standing risk to accept explicitly: **pigpio is unmaintained.** A future kernel could break it. The
mitigation is that the clock layer is library-independent, so a later backend swap does not repeat
this work.

---

## 8. Acceptance

The phase's acceptance gate becomes the **clock soak**, which must *prove* the invariant rather than
assume it:

1. Run **≥3 tick wraps** (>3.6 hours) under deliberate CPU load.
2. Force a **wall-clock step**, forwards and backwards, mid-run (PLAT-25).
3. Assert: monotonic timestamps strictly non-decreasing; **zero** backward jumps; both event paths
   agree on the same physical edge; provenance flags present and correct; **zero** undetected
   dropped samples.
4. Paired before/after pulse-timing capture on the same spare hardware showing **no regression**
   versus the Buster baseline (PLAT-24).

---

## 9. What this phase now delivers

Bookworm 64-bit, Python 3.11, an audited dependency set, a one-command installer, unattended boot
with supervised restart, `/boot`-partition provisioning, journald on volatile storage, working
VS Code Remote — **and a correct clock**: one timeline for every event, hardware precision preserved
where the hardware provides it, NTP running normally, and the 71.6-minute backward-jump defect gone.

What it no longer claims: Pi 5 capability, and removal of pigpio.
