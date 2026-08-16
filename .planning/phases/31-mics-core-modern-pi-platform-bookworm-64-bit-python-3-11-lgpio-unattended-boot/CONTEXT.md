# Phase 31 Context — mics_core Modern Pi Platform

Gathered 2026-08-16 by direct audit of `~/mics_core`, `~/pi-mirror`, and the live Pi at
`132.77.72.28`. **Everything below is verified, not assumed.** Do not re-derive it during
planning — spend the research budget on the open questions in §9 instead.

---

## 1. Decisions already taken (do not re-open)

| Decision | Value | Rationale |
|---|---|---|
| Target OS | **Raspberry Pi OS Lite, 64-bit, Bookworm** (Debian 12, Python 3.11) | Ships `python3-lgpio` in apt; Lite avoids desktop services competing with pulse timing; 64-bit gets prebuilt arm64 wheels instead of on-Pi compilation. Trixie rejected — Python 3.13 has thinner wheel coverage for the adafruit/zmq stack for no benefit a rig needs. Ubuntu Server rejected — diverges from every Pi guide on `config.txt`/dtoverlay handling. |
| GPIO library | **lgpio** | pigpio cannot run on Pi 5 (RP1) and is unmaintained. lgpio covers Pi 1–5 from one codebase. |
| Repo + branch | `~/mics_core`, **dedicated feature branch** | Planning docs stay in `mics-backend`; no code changes land here. |
| Target hardware | **Pi 4B now, Pi 5 designed for** | Pi 5 adds a battery-backed RTC (sane clock after an offline reboot) and NVMe boot (SD wear is the top failure mode under 24/7). |
| Stage order | shed → OS/Python+installer → lgpio | Risky stage last, after the other two have shrunk it. |
| Acceptance | **before/after pulse-timing measurement** on spare hardware | Not "it imports", not "it runs". |

**Correction to earlier notes:** `SUBJECT='bp_s114_r560'` in the live prefs is a **stale DB row
left unclosed**, not an active experiment (user-confirmed 2026-08-16). Nothing is running on the
Pi. The "don't touch the live rig mid-experiment" framing does not apply; the standing hard rules
(never run git on the Pi, never start/stop the pilot, never run Python on the Pi) still do.

---

## 2. Live rig baseline

- **Raspberry Pi 4 Model B rev 1.5**, Raspbian Buster 10, Python 3.7.3, `armv7l`/`armhf` (32-bit)
- Live prefs: `NAME='pilot_raspberry_lior'`, `TERMINALIP='132.77.73.125'`
- glibc **2.28**; libstdc++ max **GLIBCXX_3.4.25**. VS Code 1.86+ requires **3.4.26** — that, not
  glibc, is why Remote-SSH broke. Bookworm (GCC 12 → 3.4.30) fixes it as a side effect.
- **No autostart of any kind** — no systemd unit, no crontab, no rc.local. Pilot is started by
  hand via `run_pilot.sh`. This is the gap Stage 2 closes.
- `pilot.py:949` calls `external.start_pigpiod()` — the pilot starts its own daemon today, so the
  future systemd unit needs no ordering beyond network. With lgpio this code is **deleted**.
- Dual-homed: `eth0 132.77.72.28/23` and `wlan0 10.7.152.33/19`. Backend `ido-server` is
  `132.77.73.125/23` — same /23 as `eth0`.
- `pilot.py:277` `get_ip()` uses `socket.gethostbyname_ex()` — unreliable when dual-homed, can
  return `127.0.1.1`. Better fixed backend-side by taking the peer address from the ZMQ socket.

### Hardware configuration surface is 4 lines (the whole reason an installer is viable)

```
dtparam=i2c_arm=on        # /boot/config.txt — listed TWICE in the current file
dtparam=audio=on
dtoverlay=disable-bt
enable_uart=0
i2c-dev                   # /etc/modules
```
Plus group membership: `pi ∈ {i2c, gpio, spi, dialout}`.

**No HiFiBerry overlay exists**, and prefs has `"AUDIOSERVER": false` — so `JACKDSTRING`,
`sndrpihifiberry` and the 192 kHz audio config are dead weight. Delete rather than port.

---

## 3. Dead subsystems — confirmed dead, verified safe to delete

User-confirmed (2026-08-16): HDF5 writing, `TrialData`, and port calibration are all obsolete —
Elasticsearch is the sole data path.

**HDF5 / `TrialData`**
- `mics_task.py` (76 KB, the real MICS task base) references `tables`/`pandas`/`scipy` **zero** times
- `pilot/plugins/` is empty in both the repo and `~/pi-mirror`
- Only survivors: `task.py:7` `import tables`; `task.py:75,103` `class TrialData(tables.IsDescription)`;
  `pilot.py:34` `tables.NaturalNameWarning` filter
- **Only consumer** is `pilot.py:1105` `if hasattr(self.task, 'TrialData')` — a guarded branch, so
  deleting the class means it is simply never taken

**Port calibration**
- Lookup lives in `Solenoid.dur_from_vol()` (`gpio.py:1582`), reached only when `vol` is passed
- `Solenoid_mics.__init__` (`gpio.py:1618`) defaults `vol=None`, and every `VALVE*`/`ODOR*`/`AIR_PUF*`
  prefs entry sets an explicit `duration` (200 ms / 40 ms) and never `vol`
- Already falls back to a default LUT on exception, so the path is doubly dead
- Delete: `dur_from_vol`; `pilot.py:699-760` (`calibrate_port`); `prefs.py:610-628` and
  `prefs.py:700-743` (`compute_calibration`)

**⚠ Gotcha:** `tools/tree_integrity/final_checks.py:108` asserts on the `PORT_CALIBRATION` key and
must be updated as part of the same change.

**Setup-wizard GUI deps** — `PySide2`, `shiboken2`, `pyqtgraph`, `npyscreen` appear **only** in
`autopilot/setup/` (`setup.py`, `setup_autopilot.py`, `forms.py`), never in the pilot import path.
PySide2 5.15 is the one dependency that genuinely cannot run on Python 3.11, so dropping it is
what makes the bump possible at all.

### Resulting dependency floor

Removing the above drops `tables`, `blosc`, `numexpr`, `pandas`, and `scipy` (scipy's only use was
`linregress` inside the deleted calibration function — **no numpy-polyfit rewrite is needed**).

Final runtime set — **7 direct dependencies**, all with current arm64 wheels:
`numpy`, `pyzmq`, `tornado`, `msgpack`, `adafruit-circuitpython-mpr121`,
`adafruit-circuitpython-motorkit`, `lgpio`.

Audit-for-need (probably also droppable): `scikit-video`, `inputs`, `python-osc`, `validators`.
Version floors if kept: numpy ≥1.23.2, tornado ≥6.2, pyzmq current (**the `23.0.0b2` pin is a
beta and should not be in a rig requirements file**). The `msgpack==1.0.5` pin exists solely
because ">=1.1 requires Python ≥3.9" — that constraint evaporates on 3.11.

---

## 4. Python 3.11 blockers — whole tree scanned, result is small

**Must fix** (numpy removed these aliases in 1.24, so they break the moment numpy is bumped —
the two changes are coupled):
- `gpio.py:367, 506, 1039, 1042, 1077` — `.astype(np.int)` → `.astype(int)`
- `pilot.py:794` — `dtype=np.bool` → `dtype=bool`
- Outside the pilot path: `stim/managers.py`, `transform/geometry.py`, `transform/transforms.py`,
  `stim/sound/base.py` (fix, or delete with those modules)

**Cosmetic:** `setDaemon()` in `networking/station.py` and `networking/node.py` → `.daemon = True`.

**Confirmed clean:** no `getargspec`, no `imp`, no `distutils`, no `asyncio.coroutine`, no
`isAlive`, no `time.clock`, no `binhex`. Every `from collections import` is
`OrderedDict`/`deque`/`namedtuple` — **zero ABC breakage**, which is the usual killer in code
this old.

---

## 5. pigpio → lgpio: the actual porting surface (~30 calls)

**Easy — I²C** (14× `i2c_write_byte_data`, 7× `i2c_read_i2c_block_data`, 6× `i2c_read_byte_data`,
2× `i2c_open`): maps ~1:1 to lgpio `i2c_*`, or drop to `smbus2`.

**Easy — pins and edges:** `callback` + `RISING_EDGE`/`FALLING_EDGE`/`EITHER_EDGE`/`PUD_*` →
`gpio_claim_alerts`; `set_glitch_filter` → `gpio_set_debounce_micros`; `set_servo_pulsewidth` →
`tx_servo`; `gpio_trigger` → `gpio_write`/`tx_pulse`.
`set_pad_strength`/`get_pad_strength` have **no lgpio equivalent** — poke `/sys` or drop.

**HARD — pigpio daemon scripts.** `store_script` / `run_script` / `script_status` / `stop_script` /
`delete_script` (+ `PI_SCRIPT_RUNNING`, `PI_SCRIPT_INITING`) back
`Digital_Out.store_series()`/`series()` (`gpio.py:519-680`). **This is the timing-critical path:**

| Consumer | Sites | Why it matters |
|---|---|---|
| `Solenoid.open()` | `gpio.py:1555` (store), `:1608` (run) | valve open duration → **reward volume** |
| `TTL` | `gpio.py:1146`, `:1157` | sync pulse width |
| `Pulse20Hz` | `gpio.py:1671`, `:1682` | 20 Hz LED train |
| `Digital_Out.blink` / `flash` | `gpio.py:1243`, `:1422` | cue lights |

These execute **inside the C daemon**, not in Python. They must map to lgpio `tx_pulse`
(uniform on/off/repeat — covers valve, TTL, 20 Hz LED) and `tx_wave` + `lgpio.pulse()` (arbitrary
`values[]`/`durations[]` sequences from `_series_script`). **Never Python `time.sleep`** — that
makes valve-open duration jitter under load and reward volume variable, which is a data-quality
defect, not an engineering one.

Confirmed: the tree uses **no** `wave_*` calls today, only scripts. `pilot/test.py:27` also calls
`.series()`.

**`pilot.py` pigpio surface is small (~20 lines, mostly deleted):**
`:16` `import pigpio` · `:205-206` `self.init_pigpio()` · `:949` `external.start_pigpiod()` ·
`:1069-1080` `init_pigpio()` = `pigpio.pi(sync_ticks=True)` + connect check + tick alignment.
With lgpio the daemon-lifecycle code is deleted and `self.pi` becomes a `gpiochip` handle.

**Pi 5 forward-compat:** resolve the chip **by label** (`pinctrl-rp1` on Pi 5 vs `pinctrl-bcm2835`
on Pi 4), not `gpiochip_open(0)` — the header moves chip index on RP1.

---

## 6. The clock story — why this phase is what makes 24/7 safe

The installed `pigpio.py` is **1.78 patched by Autopilot**; `synchronize()` (`:5306`) and
`ticks_to_timestamp()` (`:5320`) are **not upstream**. Verified implementation:

```python
def synchronize(self, n_iters=5):          # Cristian's algorithm — a mini-NTP
    offset_forward  = syncts_forward  - synctick_forward/1e6
    offset_backward = syncts_backward - synctick_backward/1e6
    self._sync_offset = mean of the pairs  # averages out round-trip latency

def ticks_to_timestamp(self, ticks):
    if ticks < self._last_synced_tick: self.synchronize()   # crude wrap detection
    return ticks/1e6 + self._sync_offset
```

Consumers: `Event_Dispatcher.py:44` and `:77`. `self.pi` is assigned at `Event_Dispatcher.py:16`;
`self.pig` at `gpio.py:183`.

**Why this exists:** pigpio is a *daemon*, so the tick lives in another process's clock domain and
must be mapped across an IPC boundary by estimation.

**Three failure modes, all worse under 24/7:**
1. The counter is **32-bit microseconds → wraps every ~71.6 min**, i.e. **~20 times a day** in
   continuous operation. Each wrap triggers a re-sync.
2. The offset is re-estimated **only** when `ticks < _last_synced_tick`. A system-clock **step**
   between wraps silently corrupts timestamps until the next wrap.
3. The whole mapping is an estimate of a round trip, not a measurement.

**What lgpio changes:** in-process, kernel gpiochip chardev timestamps taken **at interrupt**,
64-bit nanoseconds. No daemon, no clock domains, no wraparound, no estimation step to go stale.
The patched pigpio fork is deleted.

**Direct link to deferred Phase 30 work:** the commented clock-freeze block at
`pilot.py:1137-1148` (`enable_ntp_and_wait()` / `disable_ntp()`, anchored by
`# ---- CLOCK SETUP ----` and `# Freeze wall clock so it never jumps during the task`) exists
*because* a wall-clock jump corrupts the estimated tick→timestamp mapping. Once timestamps come
from the kernel, freezing the wall clock is no longer necessary. **Plan for deleting that block,
not restoring it** — and note `30-HARDWARE-VALIDATION.md` §6.7 plus the `--final` F3 assertion
that currently requires those calls to exist *in commented form*; that guard must be retired
deliberately in the same change.

**Honest boundary — state it in the plan so the claim doesn't inflate:** this makes each rig's
*own* timing robust (inter-event intervals become immune to clock steps). It does **not**
synchronise a rig's clock to the backend's or to an ephys system. That needs (a) `chrony` per Pi
configured to **slew rather than step** after boot, (b) **monotonic + realtime dual logging** so
post-hoc correction stays possible, and (c) the TTL hardware pulse remaining ground truth for
cross-device alignment. (a) and (b) are in scope for this phase; (c) is Phase 28's territory.

---

## 7. Provisioning design (carried forward, still valid)

Core reframe: **don't reach the Pi — let the Pi dial out.** Outbound TCP survives VLAN
segmentation, client isolation and filtered multicast, so the only question is how the Pi learns
the backend address. The answer that never depends on the network is a file on the FAT boot
partition.

**`/boot/mics.conf` — two lines**, editable by putting the card in any laptop:
```ini
BACKEND_HOST=132.77.73.125
PILOT_NAME=cage-07
```
Optionally accept a comma-separated fallback list so a backend move self-heals.

**Three units to add:**
1. `mics-firstboot.service`, **split in two** — *once-only*: hostname, regenerate SSH host keys +
   machine-id, expand filesystem, write `/boot/mics-device.txt` (MAC + serial, for university
   MAC-registration/NAC); *every-boot*: re-render `pilot/prefs.json` from `prefs.template.json` +
   `mics.conf`. **The split matters** — marking the whole thing done after first run means later
   edits to `mics.conf` silently do nothing.
2. `mics-pilot.service` — `Restart=always`, after network. (Replaces `run_pilot.sh`.)
3. `prefs.template.json` — replaces the tracked `prefs.json`.

**Hostname is always `mics-<serial8>`**, independent of `PILOT_NAME`: unique by construction, and
a researcher's cage-naming choice can't break the network layer. Take the **LOW** bytes of the CPU
serial (the high half `10000000` is not per-board). Must also rewrite the `127.0.1.1` line in
`/etc/hosts` (else `sudo` warns on every command) and restart avahi.

**Name collision is real and already happening:** `/etc/hostname` is `raspberrypi`; avahi logs
"Host name conflict, retrying with raspberrypi-6"; `raspberrypi.local` resolves to a *different*
machine (`132.77.72.13`). ≥5 other devices squat the default name on that LAN. Avahi renames
silently, leaves `/etc/hostname` untouched, and the suffix is not sticky across reboots.

**Explicitly out of scope** (each solved a real problem but assumed network behaviour that can't
be guaranteed at another site): Pi-hosted config web page; `_mics-pilot._tcp` avahi service
records; backend "unclaimed device" claim UI; any discovery protocol; the asyncssh browser
terminal from `pi_code_editor_plan.md`. mDNS still works where it works, as SSH break-glass only.

---

## 8. `mics_core` repo state

- Single commit `1651434`; remote `git@github.com:idopo/mics_core.git` — **private (404)**, so
  "outside users clone it" stays blocked until that is resolved (out of scope, but it caps the
  adoption benefit — flag it, don't solve it here).
- **`pilot/prefs.json` IS tracked in git.** It must become `prefs.template.json` + gitignore,
  because **`prefs.set()` rewrites the whole file at runtime**: `prefs.py:505-525` saves on every
  set once `_INITIALIZED`, and `pilot.py:595` calls `prefs.set('SUBJECT', ...)` on every run start.
  So the tracked file is dirtied by every experiment and `git pull` on a field unit always
  conflicts. Note `tools/tree_protect_list.json:57` already carries a `PLUGIN_DB` exemption
  referencing `pilot/prefs.json`.
- Placeholders `CHANGE_ME_pilot_name` / `CHANGE_ME_terminal_ip` already in place.
- Paths hardcoded to `/home/pi/Apps/mice_interactive_home_cage` and `/home/pi/.venv/autopilot`
  (`REPODIR`/`BASEDIR`/`VENV`) — the installer must either honour or parameterise these.
- `requirements.txt` has two deliberately **unpinned** `adafruit-circuitpython-*` lines, to be
  resolved and pinned during the first fresh install.
- ZMQ identity set at `networking/station.py:175` and `:182` via `setsockopt_string(zmq.IDENTITY, …)`.
- No `deploy/` directory yet. `tools/` holds `check_tree_integrity.py`, `tree_protect_list.json`,
  `deploy_pi.sh`, `sync_pi.sh`, `validate_fda.py`.
- **`python3 tools/check_tree_integrity.py --strict` must be run after ANY change. Never
  `--rebaseline`.** The protected-file manifest needs a deliberate update when `prefs.json` is
  renamed and when `PORT_CALIBRATION` is removed.

**Security note carried from Phase 30:** the repo was published via fresh `git init` (not a clone)
because a live Gmail app password existed in the old history. Do not re-import old history.

---

## 9. Open questions for planning (spend research budget here)

1. **lgpio API shapes are unverified on hardware.** `tx_pulse`/`tx_wave`/`gpio_claim_alerts`
   signatures and the exact timing guarantees need confirming on a real Pi before the hardware-lib
   rewrite is planned in detail.
2. **Which clock does the gpiochip report** — `CLOCK_MONOTONIC` or `CLOCK_REALTIME`? Determines
   whether an epoch-mapping offset is needed and how dual logging is structured.
3. **Pulse-timing benchmark definition.** The existing LED2 E2→E3 gap analysis is the natural
   basis (see `memory/project_pi_timing_analysis.md`), but the acceptance thresholds need stating
   before Stage 3 starts, not after.
4. **Does the installer own the whole box or coexist?** i.e. is it allowed to write
   `/boot/config.txt`, install apt packages, and enable services on a Pi the user already uses.
5. **Backend-side follow-ups** — reject `CHANGE_ME_*` handshakes; take the Pi IP from the ZMQ peer
   instead of `get_ip()`. Small, and possibly a separate phase.

---

## 10. Hard rules (non-negotiable, from user memory)

- **Never run git on the Pi.** No commit/merge/push/pull/checkout/reset, no `rsync --delete`.
  SSH for reading and grepping is fine.
- **Never start/stop the pilot process, and never run any Python file on the Pi.** Give the user
  the command and wait.
- Pi log files are 0 bytes **by design** — do not "fix" them.
- `Message` and `hardware_state` classes are off-limits to every sweep, refactor and lint pass;
  two known defects in them are deliberately unfixed.
- RTK-proxied grep can render a matching line blank or compress output — never claim a symbol is
  unused from it alone. It misbehaved during this audit; every claim above was re-verified with a
  direct `grep -n`.

---

## 11. Decisions taken 2026-08-16 after research (LOCKED — do not re-open)

These three were surfaced as open questions by `31-RESEARCH.md` and answered by the user.

### 11.1 `Pulse20Hz` frequency — preserve 62.5 Hz exactly

**Verified defect:** `gpio.py:1655` sets `frequency = 60.0` → 8.333 ms half-periods; `_series_script`
at `gpio.py:572` emits `str(round(dur))` against the `mils` (integer-millisecond) pigpio wait
function → **8 ms** each → period 16 ms → **62.5 Hz actual**. The class name says 20 Hz, the code
says 60 Hz, the hardware emits 62.5 Hz. This drives `LED1` (`type: gpio.Pulse20Hz`) in prefs.

**Decision:** the lgpio port must reproduce **62.5 Hz bit-exactly**. lgpio's microsecond resolution
would otherwise "fix" the rounding and silently shift a stimulation parameter relative to every
dataset collected so far. Alongside: **rename the class to reflect reality** and **expose the
frequency in prefs** so the value is explicit rather than buried in a constant. Any future
correction then becomes a deliberate, dated change that can be cited in a methods section.

**Plan implication:** a regression test asserting the emitted waveform is 8000 µs on / 8000 µs off
is mandatory, not optional. Do not "clean up" the rounding.

### 11.2 Installer scope — own the box

`install.sh` may assume a **dedicated rig Pi**: write `/boot/firmware/config.txt`, apt-install,
enable services, disable Bluetooth. No coexistence mode, no interactive prompting, no `--dry-run`
requirement. This matches how these Pis are actually deployed (one per cage, doing nothing else)
and keeps the script small enough to be reviewable.

### 11.3 journald — volatile RAM journal, capped

Elasticsearch is the system of record, so the journal only needs to cover the current boot for
debugging. Set `Storage=volatile` with a size cap so 24/7 operation writes nothing to the SD card
(SD wear being the top failure mode in continuous operation).

**Do not confuse this with the pilot's own log files**, which are 0 bytes by design and must be
left alone (hard rule, §10).

---

## 12. Corrections to this document from research (apply these)

- **§5 gpiochip label allowlist:** this document named `pinctrl-bcm2835` as the Pi 4 label.
  Evidence says Pi 4 is **`pinctrl-bcm2711`**; `bcm2835` is Pi 2/3/Zero. The resolver should accept
  `pinctrl-rp1`, `pinctrl-bcm2711`, `pinctrl-bcm2835` plus a `pinctrl-*` fallback. The design is
  unaffected — only the allowlist ordering.
- **§7 boot-partition path:** `/boot/mics.conf` must become **`/boot/firmware/mics.conf`**. On
  current Bookworm the FAT partition mounts at `/boot/firmware/`, and `/boot/config.txt` is a
  placeholder file, not a symlink.
- **New landmine (not in this document):** `import lgpio` opens its notification FIFO at
  `<cwd>/.lgd-nfy<N>`. Under systemd the working directory is `/`, so **all callbacks die silently**
  unless `LG_WD` + `RuntimeDirectory=` are set on the unit. See `31-RESEARCH.md`.
- **New landmine:** systemd's default start-rate limit latches a crash-looping unit into `failed`
  permanently — fatal for a 24/7 rig. `StartLimitIntervalSec`/`StartLimitBurst` must be set
  explicitly.
- **Transmit-path risk inverts the earlier assumption:** lgpio's `tx_pulse`/`tx_wave` are
  software-timed in an ordinary `pthread` with **no** `SCHED_FIFO`/`mlockall`, whereas pigpio runs
  its whole process at `SCHED_FIFO` max. Mitigation is `CPUSchedulingPolicy=fifo` on the systemd
  unit (both lgpio threads spawn inside `gpiochip_open()`, so they inherit it) — but this **must be
  measured, not assumed**, and confirmed with `chrt -p`.
