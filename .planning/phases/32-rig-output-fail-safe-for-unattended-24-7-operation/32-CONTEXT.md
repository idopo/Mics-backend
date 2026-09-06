# Phase 32 Context — Rig output fail-safe for unattended 24/7 operation

Written 2026-09-06 from a discussion with the user, verified against **`/home/ido/mics_core`**
(branch `phase-31-modern-pi-platform`), the live stack. Everything with a file:line reference was
read in this session; everything marked UNVERIFIED is a discovery item and **must not be designed
around until answered**.

> **Read `mics_core`, not `pi-mirror`.** `~/pi-mirror/` is the OLD stack (.72.28) and the rig has
> migrated. `prefs.py` and `external/__init__.py` differ between the two trees. Every claim below
> was re-verified against `mics_core` after an earlier draft was built on the mirror.

---

## 1. Why this phase exists

Phase 31 proved the clock and logging path survives unattended operation (soak run 580). This is the
remaining blocker between that result and running 24/7 experiments with animals.

When the pilot process dies, **GPIO outputs keep their state**. A valve, air puff, odor line or LED
can stay energised indefinitely with nobody watching.

The system already says so in two places, in writing:

- `PI_TRIXIE_INSTALL.txt` STILL OPEN: *"The rig has no working output fail-safe … Pre-existing,
  unfixed, and worth knowing before a solenoid is wired."*
- `deploy/mics-pilot.service` (~line 99), in the unit's own comment: *"THIS RIG CURRENTLY HAS NO
  OUTPUT FAIL-SAFE, clean stop or not. Fail-safe behaviour under systemd specifically is
  UNVERIFIED."*

---

## 2. The characterised defect

`autopilot/autopilot/external/__init__.py`, verified **identical in `mics_core`** to the mirror:

```python
proc = subprocess.Popen('sudo ' + launch_pigpiod, shell=True)
...
def kill_proc(*args):
    proc.kill()
    sys.exit(1)
atexit.register(kill_proc)
signal.signal(signal.SIGTERM, kill_proc)
```

Three independent reasons it never reaches the daemon: `shell=True` makes `proc` the **shell
wrapper**; `pigpiod` **daemonises** (no `-g`) and reparents to init; and it runs under `sudo`, so an
unprivileged `proc.kill()` could not signal it anyway.

PLAT-33 was withdrawn on the belief that this hook closes the solenoids at session end. It does not.
The withdrawal stands by user instruction; this phase supersedes its intent rather than reopening it.

### 2a. The correction that removes an option

The roadmap offers *"repairing the `pigpiod` lifecycle so the kill hook actually works"* as a
candidate. **On its own it does not meet the goal.** `pigpiod` does not restore GPIO state on exit —
killing it correctly leaves every pin exactly as energised as it was. A fail-safe needs an explicit
**de-energise write**, not a correct kill.

### 2b. A de-energise path exists; nothing guarantees it runs

`gpio.py` `Digital_Out.release()` calls `self.set(self.off)`, and the `Hardware` metaclass calls
`release()` on object deletion. A **clean** exit already de-energises. What cannot run is `__del__`
under `SIGKILL`, OOM-kill, kernel panic or power loss.

**The gap is a missing guarantee, not missing code.** Plans should not re-implement `release()`;
they should make something outside the process responsible.

---

## 3. Scope — what is actually instantiated (CORRECTED)

**Only the toolkit the task definition runs under is instantiated. Nothing more, nothing less.**
(User, 2026-09-06; verified.)

`mics_task.py:110-112`:

```python
self.HARDWARE = self._resolve_hardware_classes(kwargs["HARDWARE"])
self._merge_prefs_hardware(kwargs["PREFS_HARDWARE"])
```

Both come from the backend dispatch spec. `task.py init_hardware()` then iterates
`for type, values in self.HARDWARE.items()` and uses `prefs.get('HARDWARE')` **only** as a pin-
argument lookup (`pin_numbers[type][pin]`). So the dispatch decides what exists; prefs only says how
it is wired.

### 3a. `Modules` is the only live group

The other groups in the HARDWARE dict — `GPIO` (24 entries), `I2C` (5), `Mixer` (1), `Timers` (3) —
are **legacy** (user, 2026-09-06). `mics_task.py:1129` agrees: *"Only Modules = toolkit hardware;
other groups (GPIO, I2C, etc.) should not be reachable by name alone."*

`prefs.template.json` still *carries* all of them, and `_merge_prefs_hardware` replaces only the
groups the backend **sent**, leaving absent groups as-is. So the file contains a full legacy `GPIO`
group that nothing instantiates. **Reading "every GPIO entry" over-collects; reading the `Modules`
group is correct.**

### 3b. Two corrections to an earlier draft of this document

- **The "all 16 outputs" scope was wrong.** It was built from the prefs *template* — the rig's
  wiring superset — not from anything a run drives.
- **`SEMANTIC_HARDWARE` does not widen the set.** An earlier draft claimed it routes into the
  GPIO/I2C groups, citing `("GPIO", "VALVE1")`. That mapping is inside a **docstring** — an example
  of what a toolkit developer could write, not live config. And a real one could not widen anything:
  `mics_task.py:1120` does `self._semantic_hw[name] = self.hardware[group][hw_id]`, a lookup into
  already-instantiated hardware that **raises KeyError** otherwise. It aliases; it never instantiates.

Consequence: the bus-conflict hazard that draft raised (driving idle I2S/SPI lines) **dissolves**.
A hook that writes only instantiated entries touches only pins already configured as outputs.

### 3c. The shape of a `Modules` entry, and the rule that falls out

From `pilot/prefs.template.json`:

```json
"Left_LED": {"pin": 11, "polarity": 1, "pulse_width": 100, "trigger": "U",
             "record": true, "max_events": 256, "name": "Left_LED", "type": "Modules"}
"Mid_LED":  {"type": "gpio.Digital_Out", "pin": 12, "polarity": 1, ...}
"TIMER":    {"type": "timer.TIMER", "name": "TIMER", "group": ""}
```

- Each entry carries its own **`pin` and `polarity`** — everything a de-energise needs, with no
  cross-reference into the legacy groups.
- **`type` is not reliable.** `_merge_prefs_hardware` sets `config["type"] = group` when the backend
  sends none, which is why three entries read `"type": "Modules"`. The real class comes from the
  dispatch spec's `class_name`/`source_code`, **not** from prefs.
- **`TIMER` has no `pin` key at all.**

→ **Rule: de-energise every `Modules` entry that carries a numeric `pin`.** That is exactly the
GPIO-backed set. Pin-less entries (timers) are inert. I2C actuators have no pin either and need the
separate mechanism in §6.

### 3d. Pin numbering is still load-bearing

`Modules` pins are **BOARD** numbers — they feed the same `gpio.Digital_Out` that does
`BOARD_TO_BCM[self._pin]` (`gpio.py:234`). Any `pigs`/shell/systemd-level write takes **BCM**.

This is a silent-failure class: several BOARD numbers used on this rig are *also* valid BCM, so a
numbering error drives the wrong line and reports success. Every plan, command and unit file must
state which numbering it uses.

Note also that duplicate pins across entries are normal (`Left_LED` and `Right_LED` both `pin: 11`;
`Solenoid` and `Mid_LED` both `pin: 12`). Writing LOW twice is harmless; deduplicate for tidiness,
not correctness.

---

## 4. `prefs.json` as the fail-safe's input — verified, with caveats

The user's proposal: `prefs.json` persists on disk and records the last dispatch, so a post-mortem
hook can read it. **Verified.**

`mics_task.py:233` `_merge_prefs_hardware()` ends in `autopilot_prefs.set("HARDWARE", existing)`, and
`prefs.py:504` `set()` calls `save_prefs()` whenever initialised. The docstring says it: *"prefs are
system-durable"*. `deploy/mics-pilot.service` confirms it happens for real — `Pilot.l_start` calls
`prefs.set('SUBJECT', ...)` on **every task start**, at `/opt/mics/pilot/prefs.json`.

Three caveats:

1. **It records dispatch, not instantiation.** `_merge_prefs_hardware` runs *before*
   `init_hardware()`. `OPEN-ITEMS-2026-08-30.md:66` records `Left_LED` and `Mid_LED` failing to
   instantiate on **every** run on pilot 3 while prefs still listed them. Errs safe — writing LOW to
   a pin nothing drove is a no-op — but it is not proof.
2. **It is reset from the template on every boot.** `mics-prefs.service` runs `render-prefs.sh`
   `Before=mics-pilot.service`, and `render-prefs.sh:110` states: *"The template is authoritative:
   any runtime-written key an existing prefs.json carries and the template does not … is dropped
   here because the output is built from the template, never merged with a prior render."* So the
   dispatched `Modules` group **survives a crash but not a reboot**. This is harmless in practice:
   the only route to a reboot is a power cut, which de-energises the pins anyway and is the
   pull-downs' case.
3. **It may name hardware this rig no longer has**, since the group persists until the next dispatch
   overwrites it. Also harmless in the same direction.

### 4a. BLOCKER — `save_prefs()` is not crash-safe

`prefs.py:543`, identical in `mics_core`:

```python
with globals()['_LOCK']:
    with open(prefs_fn, 'w') as prefs_f:
        json.dump(save_prefs, prefs_f, indent=4, separators=(',', ': '))
```

`open(...,'w')` **truncates first**, then writes in place. No temp file, no `os.replace()`. Dying
mid-write leaves `prefs.json` truncated. Two failures stack:

1. The fail-safe hook cannot parse its own input — no fail-safe, precisely in the scenario it exists
   for.
2. The next boot cannot read prefs, so the pilot does not start.

The window is every task start, not once per boot.

**This is a pre-existing bug independent of this phase** — a power cut during any `set()` can brick
the pilot's config today. The fix is `.tmp` + `os.replace()` (atomic on POSIX).

The same tree already knows how: `render-prefs.sh` writes via `mktemp` + `mv` with a comment saying
an interrupted render must never leave a half-written file. The shell script got it right; the
Python that writes the same file far more often did not.

**Design rule that follows:** the hook keeps a **static fallback list** and uses it whenever
`prefs.json` is missing, truncated or unparseable. Fail toward de-energising *more* lines, never
fewer.

---

## 5. The systemd platform — read from `mics_core/deploy/`

`deploy/` holds `install.sh`, `render-prefs.sh`, `uninstall.sh`, `mics-pilot.service`,
`mics-prefs.service`, `mics-firstboot-once.service`, plus chrony/journald configs.

`mics-pilot.service`, the unit this phase modifies:

| Directive | Value | Why it matters here |
|---|---|---|
| `ExecStopPost` | **absent** | this is the gap |
| `ExecStart` | `/home/pi/.venv/mics/bin/python -m autopilot.core.pilot -f /opt/mics/pilot/prefs.json` | names the prefs path the hook must read |
| `User=` | `pi` | an `ExecStopPost` runs unprivileged unless prefixed `+`; interacts with the `sudo pigpiod` question |
| `Restart=` / `RestartSec=` | `always` / `5` | the pilot returns 5 s later and `_set_initial_state()` runs — the hook must not fight the restart, and this is Phase 33 surface |
| `KillSignal=` | `SIGINT` | reaches `atexit` on a clean exit, so `release()` runs — within the timeout |
| `TimeoutStopSec=` | `20` | past this, systemd escalates to `SIGKILL` and no handler runs |
| `Type=` | `simple` | — |

The unit's own comment states the clean-stop guarantee *"holds only if the pilot exits cleanly WITHIN
TimeoutStopSec"*, and then that the hook does not reach the daemon at all. Both are consistent with
§2.

---

## 6. Actuator classes — GPIO is not the whole story

Scope must be stated by actuator class, not by pin list.

| Class | Reached by `ExecStopPost` + pull-downs? | Status |
|---|---|---|
| GPIO-backed `Modules` entries (numeric `pin`) | yes | **in scope** |
| I2C motor shield — doors, motorised reward | **no** — needs a third mechanism | **IN SCOPE** (SAFE-10, user 2026-09-06) — see §6a |
| I2C sensors (MPR121 / `Touch_Detector`) | n/a — cannot actuate | out of scope; see §6b |
| `ExternalHardware` (network/BLE devices) | **no** | **DEFERRED** (SAFE-11, user 2026-09-06) — gap recorded, not silently left |

### 6a. The motor shield is the highest-energy hazard and neither mechanism reaches it

`i2c.py` `Motor_Shield_Hat_extend.set()`:

```python
if bool==True:  self.throttle(self.id, -1)
if bool==False: self.throttle(self.id, 1)
```

Full throttle, ±1, and **nothing ever stops it** — there is no timed stop in `set()`. The motor runs
at 100% until something calls `throttle(None)`. `Motor_Shield_Hat.release()` does exactly that, and
`release()` only runs on a polite shutdown — the identical gap as GPIO.

So a pilot dying mid-door-move leaves a DC motor at full throttle stalled against the door frame:
stall current and heat, indefinitely, unattended. This matches the already-recorded "motors left
stalled" issue.

A GPIO write does nothing to an I2C device, and a pull-down on a Pi pin does nothing to a motor
driven by a HAT with its own supply. This needs a **third mechanism in the same hook** — putting the
PCA9685 to sleep (MODE1 `SLEEP` bit drops all 16 PWM channels at once) or zeroing the channel
registers, with cutting the HAT's motor rail as the SAFE-06 analogue.

**The exact register write and the address are DISCOVERY ITEMS, not assumptions.**
`Motor_Shield_Hat.__init__` uses `MotorKit(address=0x60)` and carries a comment recording that
`i2cdetect` reports both `0x60` and `0x70` (`0x70` is the PCA9685 all-call address).

**IN SCOPE for Slice 1** — user decision 2026-09-06.

### 6b. MPR121 is a sensor — out of scope for de-energising, but note the latch

`Touch_Detector` only reads and cannot harm an animal. Recorded explicitly so it is not re-opened.
Its `release()` carries a different problem, in its own comment: a device left sensing latches IRQ
and no falling edge can ever occur again, recoverable only by an external reset. That is a
**recovery** failure, not a safety one — it belongs to Phase 33.

---

## 7. Chosen approach (user, 2026-09-06): systemd `ExecStopPost` **plus** hardware pull-downs

The split is by failure mode, not preference:

| Failure mode | `ExecStopPost` | Pull-downs |
|---|---|---|
| clean stop / `systemctl stop` | ✅ | ✅ |
| crash, non-zero exit | ✅ | ✅ |
| `SIGKILL` / OOM-kill | ✅ | ✅ |
| pilot **hangs** without exiting | ❌ | ❌ (needs a watchdog — **Phase 33**) |
| kernel panic | ❌ | ✅ |
| power loss | ❌ | ✅ |
| SD card / rootfs death | ❌ | ✅ |

The **hang** case is deliberately Phase 33's. This phase must not silently claim it, and must not
build anything a later `WatchdogSec` would have to undo.

### 7a. Pull-down design notes

Two things a plan must establish rather than assume:

- **The Pi's power-on state.** GPIOs come up as inputs with indeterminate internal pulls; an
  external pull-down makes the line deterministic from the instant of power-on — the window no
  software fix can cover.
- **Whether the solenoid driver latches.** A pull-down on the Pi's pin does nothing if the driver
  board holds its own state. Must be checked against the actual driver before a resistor is
  specified, and it is a question for whoever wired the rig.

---

## 8. Discovery items — UNVERIFIED

### 8a. Confirm a write lands — the mask is one hypothesis, and a weak one

The fail-safe's whole job is "drive pin LOW". A write that returns success without changing the line
makes the mechanism a silent no-op, so **the check that matters is `pigs w 17 0` then `pigs r 17`**.

If it fails, candidate causes are: the daemon is not running; the pin is claimed elsewhere;
permissions; or `PIGPIOMASK`.

**`PIGPIOMASK` is the weakest of these.** `prefs.template.json` carries
`1111110000111111111111110000`, passed as `-x`, which is binary where pigpio expects hex — and
neither bit ordering decodes self-consistently with the rig working. **The user reports changing the
mask on the old OS with no observable effect (2026-09-06)**, which is direct evidence the argument is
being ignored, and is exactly what a malformed `-x` would look like.

**An earlier draft of this document ranked the mask as a load-bearing unknown that everything else
was downstream of. That was wrong** — it over-weighted a textual reading against the user's direct
experiment. Keep the write-and-read-back check, because it validates the *mechanism* cheaply and
closes every hypothesis at once. Do not build a mask investigation.

### 8b. `-l` may make `pigs` unusable

`PIGPIOARGS = -t 0 -l`. If `-l` is pigpiod's "disable remote socket interface", `pigs` will not work
and the hook must use the `/dev/pigpio` pipe. This decides the **mechanism**.

### 8c. sudoers path may not match the built binary

`PI_TRIXIE_INSTALL.txt:234` grants `NOPASSWD: /usr/bin/pigpiod`; on trixie there is no apt candidate
and `install.sh` builds to **`/usr/local/bin/pigpiod`**. A mismatch means `sudo pigpiod` prompts —
fatal unattended, presenting as "the pilot comes up without a GPIO daemon" (the symptom the install
doc already describes at line 68).

### 8d. `install.sh` has never been executed anywhere

`PI_TRIXIE_INSTALL.txt` STILL OPEN — plan 31-09, which would have proven it, was deferred. Whatever
this phase changes in `deploy/` is unproven until someone runs it.

---

## 9. Process constraints (standing, non-negotiable)

- **Never run git, Python, or process control on any Pi.** The user has confirmed for this phase
  that **they run every rig command** and the agent runs none.
- No `rsync --delete` to a Pi. The Pi's git repo is the user's alone.
- Read **`~/mics_core`**, not `~/pi-mirror`, for anything about the live stack.
- Hardware libs (`gpio.py`, `i2c.py`, `timer.py`, `compute_ops.py`) execute from
  `hardware_lib_versions.source_code`, pinned per task definition — **a Pi `git pull` does not deploy
  them**. Any plan touching `gpio.py` must say which lib version it publishes and what pins to it,
  and must not mass-repoint existing definitions.
- `Message` and `hardware_state` are excluded from every sweep and refactor.
- State the **write footprint** of every command handed to the user, or say it writes nothing.
- Keep `PI_TRIXIE_INSTALL.txt` current as part of the fix, not as a follow-up.

---

## 10. Validation posture

Exercised on **RecordingBox (132.77.73.213)** with a **killed pilot**. Acceptance is not "the unit
file contains `ExecStopPost`" — it is: dispatch a task definition, energise a line, `SIGKILL` the
pilot, and measure the pin low, for every GPIO-backed `Modules` entry that run instantiated. Read
**BCM** (§3d). The pull-down half is proven by cutting power.

---

## 11. Open questions

**Resolved 2026-09-06 (user):**

1. ~~Does the motor shield come into this phase?~~ **Yes — SAFE-10, Slice 1.** (§6a)
2. ~~`ExternalHardware` in scope?~~ **Deferred — SAFE-11.** Gap recorded; no plan may assume the
   actuator set is closed at the Pi's own pins. (§6)
3. ~~Is `save_prefs()` atomicity fixed here?~~ **Yes — SAFE-04**, because SAFE-03 depends on the file
   it corrupts. (§4a)

**Still open, all discovery items for plan 01:**

4. **Does a write actually land?** (§8a.) `pigs w 17 0` then `pigs r 17`. Closes the mask question
   and every other silent-write cause in one check. The mask itself is a weak hypothesis — the user
   reports changing it with no effect.
5. **Socket or pipe interface?** (§8b.) Decides how the `ExecStopPost` writes.
6. **Which PCA9685 register, at which address?** (§6a.) `0x60` vs `0x70`, MODE1 `SLEEP` vs zeroing
   channel registers.
7. **Does the solenoid driver latch?** (§7a.) Decides whether pull-downs work at all. May be
   answerable only by whoever wired the rig.
8. **Does the motor HAT have a separately cuttable motor rail?** (§6a.) The hardware analogue of
   SAFE-06 for the I2C side.

---

## 12. Phase shape (merged 2026-09-06)

This document is Slice 1's analysis. The phase now also absorbs the former Phase 33:

| Slice | Content | Requirements |
|---|---|---|
| 1 | Fail-safe outputs — `ExecStopPost`, pull-downs, `save_prefs()` atomicity, motor shield | SAFE-01…11 |
| 2 | Crash classification — task error vs service crash vs user stop; 5 s/30 s reconciliation | RECOV-01, 02 |
| 3 | Resume policy and trigger — per `error_type`, dispatched on reconnect | RECOV-03, 04, 05 |
| 4 | UI surface — why a run ended, whether it resumed, how many times | RECOV-06 |
| 5 | Pi fault reporting — A1-A4 + B1, run-scoped→ES, pilot-scoped→backend/UI | FAULT-01…09 |

**Slice 1 is a hard precondition for Slice 3** (RECOV-05): never resume onto unknown output state.

**Phase 19 is superseded** — Slice 5 builds its transport generalised rather than waiting on it.
