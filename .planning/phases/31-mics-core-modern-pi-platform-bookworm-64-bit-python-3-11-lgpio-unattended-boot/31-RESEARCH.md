# Phase 31: mics_core Modern Pi Platform — Research

**Researched:** 2026-08-16
**Domain:** Raspberry Pi OS Bookworm 64-bit provisioning · Python 3.11 packaging · Linux GPIO character device (uAPI v2) via lgpio · systemd unattended boot · clock discipline for 24/7 behavioural timestamping
**Confidence:** HIGH on the lgpio API and clock semantics (read from the shipped C and Python source plus the kernel uAPI header); HIGH on Bookworm packaging (read from the live Raspberry Pi archive index and raspi-config's `bookworm` branch); MEDIUM on absolute jitter numbers (must be measured on hardware — see `## Validation Architecture`)

---

## Summary

The single most consequential finding of this research is **not** the one the phase brief expected. The kernel/clock half of the argument is even stronger than CONTEXT.md assumed: lgpio's edge timestamps are taken by the kernel **in hardirq context** via `ktime_get_ns()`, on `CLOCK_MONOTONIC`, as 64-bit nanoseconds, and lgpio never asks for anything else (the `EVENT_CLOCK_REALTIME` flag is present but *commented out* in lgpio's own source). There is no daemon, no tick estimation, no 32-bit wrap. That claim is now verified at source level, not inferred.

The transmit half goes the other way, and the plan must be built around it. **lgpio's `tx_pulse`/`tx_pwm`/`tx_wave`/`tx_servo` are software-timed in a single ordinary `pthread`** created inside `gpiochip_open()`, sleeping on `clock_nanosleep(CLOCK_MONOTONIC, TIMER_ABSTIME)` and writing lines by ioctl at each wake. lgpio contains **zero** calls to `sched_setscheduler`, `pthread_setschedparam` or `mlockall`. pigpio, by contrast, puts its *whole process* at `SCHED_FIFO` maximum priority (`pigpio.c:8340-8343`), and every thread it later creates inherits that. So a naive port moves the valve-open, TTL and 20 Hz LED timing from a real-time-scheduled thread to a best-effort one. The mitigation is cheap and verified-by-construction: `lgPthTxStart()` and `lgPthAlertStart()` are both called from inside `lgGpiochipOpen()` (`lgGpio.c:772-774`), and POSIX threads inherit scheduling policy by default, so setting `SCHED_FIFO` on the process **before the first `gpiochip_open()` call** — via `CPUSchedulingPolicy=fifo` in the systemd unit — gives the lgpio tx thread pigpio-equivalent priority. This must be measured, not assumed; it is the reason the phase's acceptance gate is a before/after pulse-timing measurement.

Everything else is comparatively routine and now pinned to specifics: `python3-lgpio 0.2.2-1~rpt1` is real and in `archive.raspberrypi.com/debian bookworm main` for arm64, but PyPI also ships a prebuilt `cp311 manylinux_2_34_aarch64` wheel that needs neither SWIG nor a compiler on Bookworm (glibc 2.36 ≥ 2.34) — so a plain venv without `--system-site-packages` is the cleaner route. `raspi-config nonint do_i2c 0` on the `bookworm` branch does the whole I²C job (config.txt dtparam + un-blacklist + `/etc/modules` i2c-dev + live `dtparam`/`modprobe`) in one line and auto-detects `/boot/firmware/`. Debian's stock `chrony.conf` already ships `makestep 1 3`, i.e. step only during the first three updates and slew forever after — which is precisely the discipline the phase needs, and precisely what `systemd-timesyncd` (the Bookworm default) cannot do, because it steps unconditionally whenever the offset exceeds a hardcoded 0.4 s with no configuration knob.

**Primary recommendation:** Port to **in-process lgpio** (never `rgpiod`); resolve the gpiochip **by label with a line-count assertion**, never by index; map `Digital_Out.series()` to `tx_wave` for one-shots and `tx_pulse` for repeating trains; run the pilot under systemd with `CPUSchedulingPolicy=fifo` at a *modest* priority, `LG_WD` pointed at a `RuntimeDirectory`, and `StartLimitIntervalSec=0`; replace `systemd-timesyncd` with `chrony` and order the pilot `After=chrony-wait.service`; and thread the **kernel edge timestamp** from the alert callback through `Event_Dispatcher.dispatch_event()` instead of re-reading a clock at dispatch time — that last change is what makes the kernel-timestamp claim visible in the data.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

| Decision | Value | Rationale |
|---|---|---|
| Target OS | **Raspberry Pi OS Lite, 64-bit, Bookworm** (Debian 12, Python 3.11) | Ships `python3-lgpio` in apt; Lite avoids desktop services competing with pulse timing; 64-bit gets prebuilt arm64 wheels instead of on-Pi compilation. Trixie rejected — Python 3.13 has thinner wheel coverage for the adafruit/zmq stack for no benefit a rig needs. Ubuntu Server rejected — diverges from every Pi guide on `config.txt`/dtoverlay handling. |
| GPIO library | **lgpio** | pigpio cannot run on Pi 5 (RP1) and is unmaintained. lgpio covers Pi 1–5 from one codebase. |
| Repo + branch | `~/mics_core`, **dedicated feature branch** | Planning docs stay in `mics-backend`; no code changes land here. |
| Target hardware | **Pi 4B now, Pi 5 designed for** | Pi 5 adds a battery-backed RTC (sane clock after an offline reboot) and NVMe boot (SD wear is the top failure mode under 24/7). |
| Stage order | shed → OS/Python+installer → lgpio | Risky stage last, after the other two have shrunk it. |
| Acceptance | **before/after pulse-timing measurement** on spare hardware | Not "it imports", not "it runs". |

Additional locked decisions carried in CONTEXT.md prose:

- HDF5 writing, `TrialData`, and port calibration are **obsolete** — Elasticsearch is the sole data path. Delete, do not port. (`tools/tree_integrity/final_checks.py:108` asserts on `PORT_CALIBRATION` and must be updated in the same change.)
- `PySide2`/`shiboken2`/`pyqtgraph`/`npyscreen` are setup-wizard-only and are **dropped** — PySide2 5.15 is what makes Python 3.11 impossible otherwise.
- Final runtime dependency set is **7 direct packages**: `numpy`, `pyzmq`, `tornado`, `msgpack`, `adafruit-circuitpython-mpr121`, `adafruit-circuitpython-motorkit`, `lgpio`. The `pyzmq==23.0.0b2` beta pin must not survive into a rig requirements file.
- No HiFiBerry overlay exists and `AUDIOSERVER` is `false` — `JACKDSTRING`, `sndrpihifiberry` and the 192 kHz audio config are **deleted, not ported**.
- The commented clock-freeze block at `pilot.py:1137-1148` is to be **deleted, not restored**; the Phase 30 `--final` F3 assertion that requires those calls to exist *in commented form* must be retired deliberately in the same change.
- `pilot/prefs.json` becomes `prefs.template.json` + gitignore, because `prefs.set()` rewrites the whole file at runtime.
- Hostname is always `mics-<serial8>` from the **LOW** bytes of the CPU serial, independent of `PILOT_NAME`; `/etc/hosts`'s `127.0.1.1` line must be rewritten too.
- `mics-firstboot` is **split in two** — a once-only unit and an every-boot unit that re-renders prefs from `mics.conf`.
- `python3 tools/check_tree_integrity.py --strict` must be run after ANY change. **Never `--rebaseline`.**
- The repo was published via fresh `git init` because of a leaked credential in the old history. **Do not re-import old history.**

### Claude's Discretion

CONTEXT.md §9 explicitly hands the following to research/planning:

1. lgpio API shapes and timing guarantees (answered below; hardware confirmation still required).
2. Which clock the gpiochip reports (answered below — `CLOCK_MONOTONIC`, verified).
3. Pulse-timing benchmark definition and acceptance thresholds (proposed below in `## Validation Architecture`).
4. Whether the installer owns the whole box or coexists (recommendation below; **still needs a user decision** — flagged in Open Questions).
5. Backend-side follow-ups — reject `CHANGE_ME_*` handshakes; take the Pi IP from the ZMQ peer instead of `get_ip()` (recommend deferring to a separate phase).

### Deferred Ideas (OUT OF SCOPE)

- Pi-hosted config web page.
- `_mics-pilot._tcp` avahi service records and any discovery protocol.
- Backend "unclaimed device" claim UI.
- The asyncssh browser terminal from `pi_code_editor_plan.md`.
- Making the `mics_core` GitHub repo public (private/404 today — flag, don't solve).
- mDNS as anything other than SSH break-glass.
- Cross-device clock synchronisation to the backend or to ephys — the TTL hardware pulse remains ground truth and that is Phase 28's territory.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

No pre-existing REQUIREMENTS.md IDs cover this phase. A scan of `.planning/REQUIREMENTS.md` for `pigpio|lgpio|bookworm|buster|python 3.11|gpiochip|systemd|autostart|unattended` returned **zero** matches, and the existing prefix set is `BUG CANVAS CMP COND DB DVK EDIT EPHYS EXTLINK FDA HEALTH HOT HW HYG PROTO TRIG TRIGA UI VAR` — none of which is a platform prefix. Phase 30 introduced `HYG-` for its own scope in exactly this way, so this phase should introduce **`PLAT-`** and follow the same convention (one row per requirement, a `Phase` column, added to the phase-mapping table at `REQUIREMENTS.md:267`-ish).

Proposed IDs, grouped by the locked three-stage order. Each row names the research finding that makes it plannable.

| ID | Description | Research Support |
|----|-------------|-----------------|
| **PLAT-01** | The shed lands as one change: HDF5/`TrialData`, port calibration (`dur_from_vol`, `calibrate_port`, `compute_calibration`), the setup-wizard GUI deps, and the dead audio config are removed, and `tools/tree_integrity/final_checks.py:108`'s `PORT_CALIBRATION` assertion is updated in the same commit. | CONTEXT §3 (given). No new research needed. |
| **PLAT-02** | The numpy-alias breakages are fixed **together with** the numpy bump, not before it: `gpio.py:367,506,1039,1042,1077`, `pilot.py:794`, and the four non-pilot modules. | CONTEXT §4 (given) + § *Standard Stack* below: pin `numpy==1.26.4`, which keeps the migration surface to exactly the 1.24 alias removals CONTEXT already enumerated. numpy ≥ 2.5 **requires Python ≥ 3.12** and would not install at all. |
| **PLAT-03** | `requirements.txt` is rewritten to the 7 direct runtime deps with real pins and no betas; every pin is proven to resolve to a **prebuilt aarch64 cp311 wheel** on Bookworm. | Wheel availability verified against PyPI for every C-extension dep — see *Standard Stack*. |
| **PLAT-04** | A single idempotent installer script provisions a stock Raspberry Pi OS Lite 64-bit Bookworm card: apt packages, I²C enable, venv creation, dependency install, group membership, unit installation. Re-running it is a no-op. | `raspi-config nonint do_i2c 0` (bookworm branch) does the whole I²C job; `set_config_var` is idempotent by construction. |
| **PLAT-05** | The installer writes **`/boot/firmware/config.txt`**, never `/boot/config.txt`, and `mics.conf` lives at **`/boot/firmware/mics.conf`**. | Verified: current Bookworm replaced the `/boot/config.txt` symlink with a placeholder file that says "DO NOT EDIT THIS FILE". Writing it silently does nothing. **This changes the CONTEXT §7 design.** |
| **PLAT-06** | The pilot runs from a venv with **no** `--system-site-packages` and with `PYTHONNOUSERSITE=1` set in the unit. | Verified empirically: `--system-site-packages` also injects `~/.local/lib/pythonX.Y/site-packages` onto `sys.path`, which lets a stray `pip install --user` shadow a pinned rig dependency. |
| **PLAT-07** | `mics-firstboot-once.service` runs exactly once (hostname, `/etc/hosts` `127.0.1.1`, SSH host keys, machine-id, filesystem expand, `/boot/firmware/mics-device.txt`), guarded by an explicit stamp file, **not** by `ConditionFirstBoot`. | See *Architecture Patterns → Pattern 4*. |
| **PLAT-08** | `mics-prefs.service` runs on **every** boot and re-renders `pilot/prefs.json` from `prefs.template.json` + `/boot/firmware/mics.conf`, ordered `Before=mics-pilot.service`. | CONTEXT §7 requires the split; the failure mode it guards against (later `mics.conf` edits silently doing nothing) is real. |
| **PLAT-09** | `mics-pilot.service` starts the pilot unattended with `Restart=always`, `RestartSec`, and **`StartLimitIntervalSec=0`**. | systemd's default start-rate limit (5 starts / 10 s) puts a crash-looping unit into `failed` permanently — fatal for an unattended 24/7 rig. |
| **PLAT-10** | The pilot unit sets `WorkingDirectory=` and `Environment=LG_WD=` to a writable directory backed by `RuntimeDirectory=`. | **Verified in lgpio source:** `import lgpio` opens a FIFO at `<workdir>/.lgd-nfy<N>` where workdir is `$LG_WD` or `getcwd()`, at *module import time*. systemd's default CWD is `/`, which is read-only in practice. Without this, **all** edge callbacks fail. |
| **PLAT-11** | The pilot user is a member of `gpio` and `i2c`; `DynamicUser=` is not used. | Verified from `raspberrypi-sys-mods` `99-com.rules`: `SUBSYSTEM=="gpio", GROUP="gpio", MODE="0660"` and `SUBSYSTEM=="i2c-dev", GROUP="i2c", MODE="0660"`. |
| **PLAT-12** | The gpiochip is resolved **by label with a line-count assertion**, with a `prefs` override, never by index. | Verified: on Pi 5 Bookworm the header chip has been `gpiochip4`, then `gpiochip0` (kernel 6.6.45), then `gpiochip15` (kernel 6.12.96). Any hardcoded index is guaranteed to break. |
| **PLAT-13** | The I²C surface (2× `i2c_open`, 14× `i2c_write_byte_data`, 7× `i2c_read_i2c_block_data`, 6× `i2c_read_byte_data`) moves to `lgpio.i2c_*`. | 1:1 mapping verified against the shipped Python API; only the block-read return shape changes (`(count, bytearray)` tuple). |
| **PLAT-14** | Edge detection moves to `gpio_claim_alert` + `callback`; `set_glitch_filter` → `gpio_set_debounce_micros`. `set_pad_strength`/`get_pad_strength` are **deleted** (no lgpio equivalent, confirmed: zero occurrences of "pad" in `lgpio.h`). | Verified. Note the debounce timestamp shift documented under *Common Pitfalls*. |
| **PLAT-15** | `Digital_Out.store_series()`/`series()` and the whole pigpio-script machinery (`store_script`/`run_script`/`script_status`/`stop_script`/`delete_script`, `PI_SCRIPT_INITING` polling) are replaced by `tx_wave` for one-shots and `tx_pulse` for repeating trains. **No Python `time.sleep` anywhere in the pulse path.** | Verified: every `repeat`-using consumer in the tree (`TTL` at `gpio.py:1146`, `Pulse20Hz` at `gpio.py:1671`) is a **uniform two-level cycle**, which `tx_pulse` expresses natively including infinite repeat. Non-uniform sequences map exactly onto `tx_wave` with per-pulse `(bits, mask, delay_us)`. |
| **PLAT-16** | `pilot.py`'s pigpio lifecycle is deleted: `:16 import pigpio`, `:205-206 self.init_pigpio()`, `:949 external.start_pigpiod()`, `:1069-1080 init_pigpio()`. `self.pi` becomes a gpiochip handle. The patched `pigpio.py` fork (with its non-upstream `synchronize()`/`ticks_to_timestamp()`) is deleted. | CONTEXT §5, §6 (given). |
| **PLAT-17** | The pilot process runs at `SCHED_FIFO` at a modest priority so the lgpio tx and alert threads inherit it, and the choice is **justified by measurement**, not assertion. | **Verified in source:** lgpio has zero RT-scheduling calls; pigpio sets `SCHED_FIFO` at max priority process-wide (`pigpio.c:8340-8343`); `lgPthTxStart()`/`lgPthAlertStart()` are called from inside `lgGpiochipOpen()` (`lgGpio.c:772-774`), and POSIX threads inherit policy by default. |
| **PLAT-18** | `Event_Dispatcher.dispatch_event()` accepts the **kernel edge timestamp** from the alert callback and only falls back to reading a clock when no edge timestamp exists. | Verified in `mics_core`: today `dispatch_event` (`Event_Dispatcher.py:77`) calls `self.pi.get_current_tick()` in the calling thread, i.e. it stamps when *Python* runs, discarding the edge time the callback already carries. Fixing this is what makes the kernel-timestamp claim show up in ES. |
| **PLAT-19** | Every dispatched event carries **both** a raw `CLOCK_MONOTONIC` nanosecond field and a derived UTC field, with the monotonic field designated as the interval-analysis source. | Verified: kernel gpio v2 events default to `CLOCK_MONOTONIC` (`include/uapi/linux/gpio.h`), lgpio never sets `EVENT_CLOCK_REALTIME` (the flag is commented out at `lgGpio.c:243-246`), so an epoch offset is mandatory to produce UTC. |
| **PLAT-20** | `chrony` replaces `systemd-timesyncd`, keeping Debian's stock `makestep 1 3`, with lab NTP sources added via a drop-in in `/etc/chrony/conf.d/`. | Verified: `systemd-timesyncd` **steps** whenever `|offset| ≥ NTP_MAX_ADJUST = 0.4 s` (`timesyncd-manager.c:52,247`) with no config option to prevent it. Debian's stock `chrony.conf` already ships `makestep 1 3` + `rtcsync` + `driftfile`. |
| **PLAT-21** | `mics-pilot.service` is ordered `After=chrony-wait.service` so no session can start before the clock has converged. | Verified: `chrony-wait.service` ships in Debian bookworm's `chrony` package (`/lib/systemd/system/chrony-wait.service`), runs `chronyc waitsync 0 0.1 0.0 1`, is `Before=time-sync.target`, `TimeoutStartSec=180`. |
| **PLAT-22** | The Phase 30 clock-freeze block at `pilot.py:1137-1148` is deleted and the `--final` F3 assertion in `30-HARDWARE-VALIDATION.md` §6.7 that requires it to exist in commented form is retired in the same change. | CONTEXT §6 + STATE.md:1686 (given). Flagged here so it does not get missed — the gate is *inverted* and will fail loudly if the block is simply deleted without touching the guard. |
| **PLAT-23** | A GPIO loopback timing harness exists in-repo and produces a machine-readable capture of commanded-vs-measured pulse widths and periods. | See `## Validation Architecture`. |
| **PLAT-24** | Acceptance is a **paired** before/after capture on the same spare hardware, under both idle and loaded conditions, with lgpio required to be no worse than the pigpio baseline on the stated statistics. | The locked acceptance criterion; thresholds proposed in `## Validation Architecture`. |
| **PLAT-25** | The 24/7 claim is validated by a **forced clock step** (forwards and backwards) mid-capture, not by waiting 24 hours: monotonic timestamps must stay continuous and monotonic, intervals unaffected, derived UTC stepping by exactly the applied amount, and the pilot must survive. | See `## Validation Architecture`. |
</phase_requirements>

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `lgpio` | `0.2.2.0` (PyPI) / `0.2.2-1~rpt1` (apt `python3-lgpio`) | GPIO, edge alerts, timed pulses, I²C, via the kernel gpiochip chardev | The only library the author (joan, also pigpio's author) maintains; covers Pi 1–5 from one codebase; in-process, no daemon. Present in `archive.raspberrypi.com/debian bookworm main` for arm64 — **verified against the live `Packages.gz`**. |
| `numpy` | **`==1.26.4`** | array ops in `gpio.py`, `pilot.py` | Last 1.x line; supports cp311; keeps the migration surface to exactly the 1.24 alias removals CONTEXT.md already enumerated. numpy `2.5.x` **requires Python ≥3.12** and cannot install; numpy `2.3.x` is the last cp311-capable 2.x if a 2.x bump is later wanted. |
| `pyzmq` | `>=26,<28` (current `27.1.0`) | ZMQ transport to the orchestrator | cp311 `manylinux_2_28_aarch64` wheel exists. **The existing `23.0.0b2` pin is a beta and must go.** |
| `tornado` | `>=6.4` (current `6.5.8`) | IOLoop under the networking layer | ships `cp39-abi3-manylinux2014_aarch64` — one wheel covers 3.9+. |
| `msgpack` | `>=1.0.8` (current `1.2.1`) | wire serialisation | cp311 aarch64 wheel exists. The `==1.0.5` pin existed only for the Python-3.9 floor and is obsolete on 3.11. |
| `chrony` | `4.3-2+deb12u*` (Debian bookworm) | clock discipline: slew-not-step after boot | Stock `chrony.conf` already encodes the wanted policy. |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `adafruit-circuitpython-mpr121` | `2.1.27` | MPR121 touch sensor | Only where the existing `hardware/i2c.py:799 MPR121` class is not used. Pulls `Adafruit-Blinka`. |
| `adafruit-circuitpython-motorkit` | `1.6.21` | PCA9685 motor HAT | Pulls `Adafruit-Blinka` + `adafruit-circuitpython-pca9685`. |
| `Adafruit-Blinka` | `9.2.0` | CircuitPython compat shim | Transitive. **Note:** 9.2.0 no longer hard-depends on `RPi.GPIO` (verified from PyPI metadata), so it will not drag a Pi-5-incompatible package in. It does depend on `sysv_ipc>=1.1.0`, which **does** have a cp311 aarch64 wheel — no compiler needed. |
| `Adafruit-PureIO` | `1.1.11` | Blinka's I²C backend | **sdist only, no wheels.** It is pure Python, so it still installs without a compiler, but this is the one dep that will build from source — verify on first install. |
| `smbus2` | `0.4.x` | pure-Python I²C alternative | Fallback if `lgpio.i2c_*` proves awkward for the MPR121/MotorKit path. Not recommended as the primary — one library for both GPIO and I²C is simpler. |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| **in-process `lgpio`** | `rgpiod` + `python3-rgpio` (both packaged: `rgpiod 0.2.2-1~rpt1`, `python3-rgpio 0.2.2-1~rpt1`) | **Reject.** Same API surface, but over a socket to a separate daemon. That reintroduces exactly the IPC boundary and process-lifecycle management the phase exists to remove, adds latency to every call, and gains nothing — the timestamps still originate in the same kernel. The *only* reason to pick `rgpio` is remote/multi-host GPIO, which the rig does not need. |
| `lgpio` from PyPI | `apt install python3-lgpio` + `venv --system-site-packages` | Both work. Prefer **PyPI in a clean venv**: it pins in `requirements.txt`, needs no `--system-site-packages` (which also exposes `~/.local`), and the `cp311 manylinux_2_34_aarch64` wheel is statically linked against liblgpio so there is no apt/pip version skew. Keep apt as the documented fallback if PyPI is unreachable from the rig network. |
| `lgpio` | `libgpiod` v2 + `python3-libgpiod` | libgpiod is the canonical kernel-blessed binding and gives finer control (including `EVENT_CLOCK_REALTIME` and `event_buffer_size`, neither of which lgpio exposes). But it has **no transmit primitives at all** — no `tx_pulse`, no `tx_wave` — so every timed pulse would have to be hand-built. Given the phase's whole risk sits in timed pulses, that is the wrong trade. Revisit only if lgpio's tx jitter fails the acceptance gate. |
| `lgpio` | `rpi-lgpio` (`python3-rpi-lgpio 0.6-0~rpt1`) | A drop-in `RPi.GPIO` API implemented on lgpio. Useful only for porting code already written against `RPi.GPIO`. `mics_core` is written against pigpio, so this buys nothing. |
| `chrony` | keep `systemd-timesyncd` | **Reject.** Verified in systemd source: it steps the clock whenever the offset reaches 0.4 s, at any point in uptime, and `timesyncd.conf` has no directive to change that. |
| `chrony` | `ntpsec` / classic `ntpd` | chrony converges faster on intermittently-connected machines and is the Debian default recommendation. No reason to diverge. |

**Installation (installer script sketch — the shapes, not the final script):**

```bash
sudo apt update
sudo apt install -y python3-venv python3-dev i2c-tools chrony
# lgpio via apt is the documented fallback:
#   sudo apt install -y python3-lgpio
sudo raspi-config nonint do_i2c 0        # config.txt + blacklist + /etc/modules + live modprobe
sudo usermod -aG gpio,i2c,spi,dialout "$PILOT_USER"

python3 -m venv /home/pi/.venv/mics       # NO --system-site-packages
/home/pi/.venv/mics/bin/pip install -r requirements.txt
```

---

## Architecture Patterns

### Recommended Repository Structure (additions only)

```
mics_core/
├── deploy/                      # NEW — does not exist today
│   ├── install.sh               # idempotent one-shot provisioner
│   ├── mics-firstboot-once.service
│   ├── mics-prefs.service       # every boot, re-renders prefs
│   ├── mics-pilot.service
│   ├── chrony-mics.conf         # drop-in for /etc/chrony/conf.d/
│   └── mics.conf.example        # → /boot/firmware/mics.conf
├── pilot/
│   ├── prefs.template.json      # replaces the tracked prefs.json
│   └── prefs.json               # gitignored, runtime-written
├── autopilot/autopilot/hardware/
│   ├── gpio.py                  # pigpio → lgpio rewrite
│   └── lgchip.py                # NEW — chip resolution + handle ownership
└── tools/
    └── pulse_timing/            # NEW — the loopback acceptance harness
```

### Pattern 1: Resolve the gpiochip by label, assert the line count

**What:** Never `gpiochip_open(0)`. Enumerate chips, match on label, and assert the line count so a same-named-but-wrong chip cannot slip through.

**When to use:** Once, at pilot start; store the handle.

**Why:** Verified — on Pi 5 under Bookworm the header chip has moved index three times: `gpiochip4` (original), `gpiochip0` (kernel 6.6.45), `gpiochip15` (kernel 6.12.96+rpt-rpi-2712). The `/lib/udev/rules.d/60-gpiochip4.rules` symlink workaround Raspberry Pi shipped for the first move is already defunct after the second. There is no stable index.

```python
# Verified against lgpio 0.2.2.0 source:
#   gpiochip_open(n)          -> handle, and encodes n in the high 16 bits (lgpio_extra.py:411-414)
#   gpio_get_chip_info(h)     -> [status, lines, name, label]  (lgpio_extra.py:432-443)
#   both raise lgpio.error on failure because module-global `exceptions` is True (lgpio_extra.py:219-228)
import lgpio

# Ordered preference. Pi 5 = pinctrl-rp1 (54 lines); Pi 4 = pinctrl-bcm2711 (58 lines);
# Pi 2/3/Zero = pinctrl-bcm2835. Verified from gpiodetect output reported on Pi 4 and Pi 5 Bookworm.
_HEADER_LABELS = ("pinctrl-rp1", "pinctrl-bcm2711", "pinctrl-bcm2835")

def open_header_chip(preferred_label=None, max_chip=32):
    """Return an lgpio handle for the 40-pin header controller."""
    candidates = []
    for n in range(max_chip):
        try:
            h = lgpio.gpiochip_open(n)
        except lgpio.error:
            continue
        try:
            _status, lines, name, label = lgpio.gpio_get_chip_info(h)
        except lgpio.error:
            lgpio.gpiochip_close(h)
            continue
        # The header controller always exposes at least the 28 BCM header GPIOs.
        if lines >= 54 and (label == preferred_label or label in _HEADER_LABELS
                            or label.startswith("pinctrl-")):
            candidates.append((label, n, h, lines))
        else:
            lgpio.gpiochip_close(h)

    if not candidates:
        raise RuntimeError("no header gpiochip found; run `gpiodetect` and set GPIOCHIP_LABEL in prefs")

    def rank(c):
        label = c[0]
        if preferred_label and label == preferred_label:
            return -1
        return _HEADER_LABELS.index(label) if label in _HEADER_LABELS else len(_HEADER_LABELS)

    candidates.sort(key=rank)
    chosen = candidates[0]
    for _l, _n, h, _lines in candidates[1:]:
        lgpio.gpiochip_close(h)
    return chosen[2]        # handle
```

`prefs` should carry an optional `GPIOCHIP_LABEL` so a future board can be pinned without a code change.

### Pattern 2: One-shot pulse (valve, TTL single) → `tx_wave`

**What:** Replace `store_series(values=on, durations=[ms], finish_off=True)` with an explicit two-entry wave.

**When to use:** Any non-repeating, possibly non-uniform level sequence — this covers `Solenoid.open()` (`gpio.py:1555`, `:1608`), which is the reward-volume path.

```python
# lgpio.pulse(group_bits, group_mask, pulse_delay)  -- pulse_delay is MICROSECONDS
#   (lgpio_extra.py:169-185; the delay is added verbatim to the tx thread's next-edge
#    deadline in lgPthTx.c:136, so it is a true microsecond field)
# For a singleton output claimed with gpio_claim_output, the group is one line:
#   bit 0 == that line, so mask == 1.
import lgpio

def pulse_once(h, gpio, level_on, duration_ms, level_off):
    pulses = [
        lgpio.pulse(level_on,  0b1, int(round(duration_ms * 1000))),
        lgpio.pulse(level_off, 0b1, 0),
    ]
    try:
        lgpio.tx_wave(h, gpio, pulses)      # returns free queue slots; raises on TX_QUEUE_FULL
    except lgpio.error:
        # Verified: the wave queue is LG_TX_BUF == 10 entries per GPIO (lgPthTx.h:36).
        # Must be caught: this is called from a hardware callback and an escaping
        # exception unwinds the caller before its remaining writes run
        # (see the comment at Event_Dispatcher.py:70-75).
        ...
```

Two properties worth stating in the plan: `tx_wave` copies the pulse list into a malloc'd buffer (`lgGpio.c:625-632`), so the Python list may be discarded immediately; and there is **no maximum pulse count** — the only limit is 10 *queued waves* per GPIO. An arbitrary `values[]`/`durations[]` sequence of any length is expressible in one call.

### Pattern 3: Repeating train (TTL, 20 Hz LED, blink/flash) → `tx_pulse`

**What:** `tx_pulse(handle, gpio, on_us, off_us, offset_us, cycles)` — `cycles=0` means infinite.

**Why this is the right map:** Both repeat-using consumers in the tree are *uniform two-level cycles*:
- `TTL.__init__` (`gpio.py:1146`): `values=[on, off]`, `durations=[pulse_width, interval - pulse_width]`, `repeat=<n>`
- `Pulse20Hz._build_script` (`gpio.py:1671-1678`): `values=[on, off]`, `durations=[on_time, off_time]`, `repeat=-1`

so `cycles = repeat` and `cycles = 0` for `repeat == -1` covers both exactly. Stopping is `tx_pulse(h, gpio, 0, 0, 0, 0)` — verified: "If both pulse_on and pulse_off are zero pulses will be switched off for that GPIO. The active pulse, if any, will be stopped and any queued pulses will be deleted."

```python
def start_train(h, gpio, on_us, off_us, repeat):
    cycles = 0 if repeat == -1 else int(repeat)
    lgpio.tx_pulse(h, gpio, int(on_us), int(off_us), 0, cycles)

def stop_train(h, gpio):
    lgpio.tx_pulse(h, gpio, 0, 0, 0, 0)
```

**Two real gaps to state in the plan, not discover during implementation:**
1. `tx_pulse` requires `on_us + off_us > lgMinTxDelay` (default **10 µs**, `lgPthTx.c:34`); otherwise `LG_BAD_PWM_MICROS`. It is adjustable up to 1000 via `lgpio.set_internal(1, value)` (`LG_CFG_ID_MIN_DELAY == 1`, `lgpio.h`). No Python constant is exported for it — pass the literal `1`.
2. There is **no lgpio primitive for infinitely repeating a *non-uniform* wave.** `tx_wave` transmits a finite pulse list; only 10 waves can be queued. This is not a problem today (nothing in the tree needs it), but if a future FDA state wants a looping arbitrary pattern it needs a Python refill thread driven by `tx_room(h, gpio, lgpio.TX_WAVE)`, which reintroduces Python at the wave seams. Record the constraint.

### Pattern 4: The first-boot / every-boot unit split

**What:** Two units, not one, with an explicit stamp file for the once-only half.

**Why not `ConditionFirstBoot=yes`:** systemd's own first-boot condition keys off `/etc/machine-id` being unpopulated. The once-only unit *itself* regenerates machine-id (per CONTEXT §7), which makes the condition's semantics circular and version-dependent. An explicit stamp is auditable and reversible (`rm` the stamp to re-provision).

```ini
# /etc/systemd/system/mics-firstboot-once.service
[Unit]
Description=MICS one-time device provisioning
ConditionPathExists=!/var/lib/mics/.firstboot-done
DefaultDependencies=no
After=local-fs.target
Before=sysinit.target
[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/opt/mics/deploy/firstboot-once.sh
ExecStartPost=/usr/bin/mkdir -p /var/lib/mics
ExecStartPost=/usr/bin/touch /var/lib/mics/.firstboot-done
[Install]
WantedBy=sysinit.target
```

```ini
# /etc/systemd/system/mics-prefs.service   -- EVERY boot
[Unit]
Description=Render MICS pilot prefs from /boot/firmware/mics.conf
After=local-fs.target
Before=mics-pilot.service
[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/opt/mics/deploy/render-prefs.sh
[Install]
WantedBy=multi-user.target
```

An alternative worth naming so the plan can reject it deliberately: Raspberry Pi's own first-boot hook is `systemd.run=/boot/firmware/firstrun.sh systemd.run_success_action=reboot` appended to `cmdline.txt` (that is how `rpi-imager`'s advanced options are applied), with `custom.toml` as the declarative front end. It is a legitimate mechanism, but it is *consumed and removed* by the image's own first boot and it runs before the network exists. Use plain systemd units instead — they are inspectable, re-runnable, and survive an OS reinstall of the units directory.

### Pattern 5: The pilot unit

```ini
# /etc/systemd/system/mics-pilot.service
[Unit]
Description=MICS pilot
Wants=network-online.target
After=network-online.target chrony-wait.service mics-prefs.service
Requires=mics-prefs.service
StartLimitIntervalSec=0                # 24/7: never latch into `failed`

[Service]
Type=simple
User=pi
WorkingDirectory=/run/mics
RuntimeDirectory=mics
RuntimeDirectoryMode=0755
Environment=LG_WD=/run/mics
Environment=PYTHONNOUSERSITE=1
Environment=PYTHONUNBUFFERED=1
ExecStart=/home/pi/.venv/mics/bin/python -m autopilot.core.pilot
Restart=always
RestartSec=5
CPUSchedulingPolicy=fifo
CPUSchedulingPriority=10               # NOT 99 -- see Pitfall 2
TimeoutStopSec=20
KillSignal=SIGINT                      # let the pilot close handles and stop tx cleanly

[Install]
WantedBy=multi-user.target
```

Notes, each load-bearing:

- `network-online.target` is meaningful here because Raspberry Pi OS Bookworm enables `NetworkManager-wait-online.service` by default. On a network-free boot it times out after a couple of minutes rather than hanging forever.
- `After=chrony-wait.service` (**not `Requires=`**) delays the pilot until the clock has converged to within 0.1 s or 180 s have elapsed. `After=` without `Requires=` means a network-free rig still boots the pilot, just late.
- `RuntimeDirectory=mics` creates `/run/mics` owned by `User=`, on tmpfs, and removes it on stop. Combined with `LG_WD`, this is where lgpio's `.lgd-nfy*` FIFO lands. **Without it, edge callbacks silently do not work.**
- `CPUSchedulingPolicy=fifo` is applied at `exec`, so the process's main thread is already `SCHED_FIFO` before `gpiochip_open()` creates the tx and alert threads, which inherit it. This is the whole mechanism for restoring pigpio-class pulse timing.
- Do **not** add `ProtectSystem=strict` / `PrivateDevices=yes` reflexively: `PrivateDevices=yes` hides `/dev/gpiochip*` and `/dev/i2c-*` and would break the rig outright.

### Pattern 6: Dual timebase, offset computed per event

```python
import time

CLOCK_MONO = time.CLOCK_MONOTONIC

def edge_callback(chip, gpio, level, ts_ns):
    """lgpio alert callback. ts_ns is the KERNEL edge timestamp on CLOCK_MONOTONIC,
    taken in hardirq context (verified: gpiolib-cdev.c edge_irq_handler -> ktime_get_ns)."""
    # Recomputing the offset per event is two vDSO reads (~tens of ns) and is the only
    # form that stays correct across a wall-clock step: each event's UTC is derived from
    # the REALTIME<->MONOTONIC relation that held when it was recorded.
    offset_ns = time.clock_gettime_ns(time.CLOCK_REALTIME) - time.clock_gettime_ns(CLOCK_MONO)
    dispatcher.dispatch_event(event, ts_mono_ns=ts_ns, ts_utc_ns=ts_ns + offset_ns)
```

The contract to write into the plan and into the ES mapping:

| Field | Clock | Use for | Never use for |
|---|---|---|---|
| `t_mono_ns` | `CLOCK_MONOTONIC`, kernel, at interrupt | **all** interval / latency / rate analysis within a session | joining across machines |
| `t_utc` | derived (`t_mono_ns + offset`) | display, joining to backend/session records | interval analysis across a clock step |

**A subtlety that must be written down, because it looks like a contradiction otherwise:** `CLOCK_MONOTONIC` on Linux *is* affected by NTP/adjtime frequency adjustments — it is slewed, but never stepped and never runs backwards (`clock_gettime(2)`; `CLOCK_MONOTONIC_RAW` is the un-disciplined variant). For this rig that is the desirable property: chrony's frequency discipline improves the long-run rate accuracy of inter-event intervals, while the absence of steps is what makes 24/7 safe. Do **not** "fix" this by switching to `CLOCK_MONOTONIC_RAW` — lgpio cannot ask the kernel for it anyway.

### Anti-Patterns to Avoid

- **`gpiochip_open(0)`.** Guaranteed to break on Pi 5, and has already broken twice on Bookworm kernels.
- **Any `time.sleep()` in a pulse path.** CONTEXT.md already says this; it is worth repeating because `tx_wave`/`tx_pulse` make it unnecessary and the GIL makes it actively harmful.
- **Re-reading a clock at dispatch time when the callback already carries the edge timestamp.** This is what the code does today (`Event_Dispatcher.py:77`) and it discards the phase's main benefit.
- **`rgpiod`.** Re-adds a daemon to a phase whose purpose is deleting one.
- **`--rebaseline` on `check_tree_integrity.py`.** Explicitly forbidden; the manifest needs a deliberate edit for the `prefs.json` rename and `PORT_CALIBRATION` removal.
- **Wholesale systemd hardening directives.** `PrivateDevices=`, `ProtectSystem=strict`, `DevicePolicy=closed` all break GPIO/I²C access. Copying `chrony-wait.service`'s hardening block into `mics-pilot.service` would produce a unit that starts and does nothing.
- **`sudo pip install`.** Bookworm ships `/usr/lib/python3.11/EXTERNALLY-MANAGED` (PEP 668); this errors out. Do not defeat it with `--break-system-packages`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Timed output pulses | A Python thread with `time.sleep` between `gpio_write` calls | `lgpio.tx_wave` / `lgpio.tx_pulse` | Both run in lgpio's C thread on absolute `clock_nanosleep` deadlines (`lgPthTx.c:171-183`), so lateness on one edge does **not** shift subsequent edges — there is no cumulative drift. A Python loop has the GIL, the scheduler, *and* drift. |
| Edge timestamps | `time.time()` inside the callback | the `timestamp` argument the callback already receives | The callback argument is the kernel's hardirq timestamp; anything you read inside the callback includes the full ppoll + FIFO + Python-dispatch latency (lgpio's alert thread polls with a 0.5 ms `ppoll` timeout, `lgPthAlerts.c:438`). |
| Wall-clock ↔ monotonic mapping | Cristian's-algorithm round-trip estimation (i.e. the patched `pigpio.synchronize()`) | `clock_gettime_ns(CLOCK_REALTIME) - clock_gettime_ns(CLOCK_MONOTONIC)` | Two vDSO reads of the *same* kernel timekeeper. Exact by construction; no round trip to estimate, no staleness, nothing to re-sync. |
| Switch/contact debounce | A Python timer that ignores events for N ms | `lgpio.gpio_set_debounce_micros` | Implemented in lgpio's alert thread against kernel timestamps (`lgPthAlerts.c:309-343`), so the debounce window is measured on the edge clock, not on when Python happened to run. |
| Enabling I²C in the installer | Hand-editing `config.txt`, `raspi-blacklist.conf` and `/etc/modules` | `raspi-config nonint do_i2c 0` | Verified from the `bookworm` branch: one call does the `dtparam` in the right file (auto-detecting `/boot/firmware/`), un-blacklists `i2c-bcm2708`, un-comments/appends `i2c-dev` in `/etc/modules`, and applies both live via `dtparam` + `modprobe`. Its `set_config_var` is a lua-based idempotent upsert — safe to re-run. |
| Slew-not-step clock policy | A cron job calling `ntpdate`/`adjtimex`, or freezing the clock during a task | `chrony` with Debian's stock `makestep 1 3` | Debian's shipped `/etc/chrony/chrony.conf` **already** contains `makestep 1 3` + `driftfile` + `rtcsync` + `maxupdateskew 100.0`. Writing a custom policy would be reimplementing the default. |
| "Wait until the clock is good" | Polling `timedatectl` in the pilot's startup path | `After=chrony-wait.service` | Ships in the `chrony` package; runs `chronyc waitsync 0 0.1 0.0 1` with a 180 s cap. |
| First-boot idempotence | A hand-rolled lockfile in `/tmp` | `ConditionPathExists=!` + a stamp under `/var/lib/` | Survives reboot, is inspectable, and `rm`-able to force re-provisioning. `/tmp` is cleared on boot. |
| The alert notification pipe | Reading `/dev/gpiochipN` directly, or `notify_open()` plumbing | plain `lgpio.callback()` | `import lgpio` already opens a notification FIFO and starts a daemon thread at module import (`lgpio_extra.py:331`). `gpio_claim_alert(..., notify_handle=None)` wires into it automatically. Just make sure the CWD/`LG_WD` is writable. |

**Key insight:** every one of the pigpio-era workarounds in this codebase — the tick synchroniser, the script store/run/status/delete dance, the `PI_SCRIPT_INITING` polling loop, the daemon-lifecycle code in `pilot.py` — exists to work around the fact that pigpio is a *separate process*. Removing the daemon deletes the workarounds rather than porting them. The port should be a net **reduction** in code, and if it is not, something is being ported that should be deleted.

---

## Common Pitfalls

### Pitfall 1: The lgpio notification FIFO is created in the current working directory
**What goes wrong:** Edge callbacks never fire. No exception, no log line — the FIFO open fails at `import lgpio` and alerts silently go nowhere.
**Why it happens:** Verified in source. `lgpio_extra.py:273` does `open('.lgd-nfy{}'.format(self._notify), 'rb')` — a **relative** path — and the C side builds `<workdir>/.lgd-nfy<handle>` where workdir is `$LG_WD` if set, otherwise `getcwd()` (`lgNotify.c:130`, `lgUtil.c` `lguGetWorkDir`). Under systemd the default CWD is `/`. Today the pilot is started by `run_pilot.sh` from the repo directory, so this has never bitten.
**How to avoid:** `WorkingDirectory=/run/mics` + `RuntimeDirectory=mics` + `Environment=LG_WD=/run/mics`.
**Warning signs:** `ls /run/mics/.lgd-nfy*` returns nothing after the pilot starts. Also note `lguGetWorkDir()` calls `chdir()` on the whole process when `LG_WD` is set — set it deliberately, and do not assume relative paths elsewhere in the pilot still resolve.

### Pitfall 2: lgpio's transmit thread runs at ordinary priority; pigpio's ran at real-time
**What goes wrong:** Valve-open duration — i.e. **reward volume** — becomes load-dependent. This is a data-quality defect that will not show up in any functional test.
**Why it happens:** Verified: `grep -E 'sched_setscheduler|SCHED_FIFO|pthread_setschedparam|mlockall'` across all of lgpio's C sources returns **nothing**. `lgPthTx.c:194` is a bare `pthread_create(..., NULL, ...)`. pigpio does `sched_setscheduler(0, SCHED_FIFO, sched_get_priority_max(SCHED_FIFO))` on the whole process (`pigpio.c:8340-8343`), and threads created afterwards inherit it because `PTHREAD_INHERIT_SCHED` is the POSIX default.
**How to avoid:** `CPUSchedulingPolicy=fifo` on the unit, at a **modest** priority (10, not 99). The kernel's RT throttle (`kernel.sched_rt_runtime_us` = 950000 of 1000000 µs) is the safety net if a Python thread spins; a max-priority CPython process can otherwise make the box unreachable. Then **measure** — this is the point of the acceptance gate.
**Warning signs:** In the loopback capture, the distribution of measured-vs-commanded pulse width has a long right tail that grows under `stress-ng` load. Cross-check with `chrt -p $(pidof python3)` on the pilot's threads (`/proc/<pid>/task/*/`) — but note lgpio does **not** name its threads (no `pthread_setname_np` anywhere), so you cannot identify them by `comm`; check that *all* threads report `SCHED_FIFO`.

### Pitfall 3: `gpio_set_debounce_micros` deliberately shifts the reported timestamp
**What goes wrong:** Every debounced event is timestamped later than the physical edge, by exactly the debounce window — and the shift is invisible unless you know to look for it.
**Why it happens:** Verified in both the docstring and the code. `lgpio_extra.py:1000-1001`: "Note that level changes will be timestamped debounce microseconds after the actual level change." `lgPthAlerts.c:322`: `aBuf[*cp].report.timestamp = p->last_evt_ts + p->debounce_nanos;`.
**How to avoid:** Either subtract the configured debounce from the timestamp at ingest, or record the debounce value alongside the event so post-hoc correction is possible. Whichever is chosen, **write it down** — the current `set_glitch_filter` has a different (pigpio-side) semantics and the two are not interchangeable at the millisecond level. Note also the debounce is enforced in **userspace** by lgpio's alert thread; lgpio never sets the kernel's `GPIO_V2_LINE_ATTR_ID_DEBOUNCE` (zero hits for `DEBOUNCE` attribute usage in `lgGpio.c`).

### Pitfall 4: Chardev lines are released when the process dies
**What goes wrong:** If the pilot crashes with a solenoid energised, the kernel releases the line and the pin reverts to its default state. With pigpio, the daemon outlived the client and kept driving the pin.
**Why it happens:** This is fundamental to the gpiochip chardev model — line ownership is tied to the open file descriptor.
**How to avoid:** This is arguably an **improvement** (crash → valve closes, if the external circuit pulls to the safe level), but it is a *behaviour change on the reward path* and must be verified per device on the rig, not assumed. Document the fail-safe level for each output in prefs and check it physically. Also add `KillSignal=SIGINT` + a handler that explicitly stops transmissions and writes outputs to their safe level before exit.

### Pitfall 5: `/boot/config.txt` is a decoy on current Bookworm
**What goes wrong:** The installer writes `/boot/config.txt`, reports success, and nothing takes effect.
**Why it happens:** Bookworm moved the firmware partition to `/boot/firmware`. Initially `/boot/config.txt` was a symlink; a later `raspberrypi-sys-mods` update **replaced the symlinks with placeholder files** containing "DO NOT EDIT THIS FILE — The file you are looking for has moved to /boot/firmware/config.txt", because scripts kept breaking the symlink and then editing the wrong file.
**How to avoid:** Detect like `raspi-config` does — `if [ -e /boot/firmware/config.txt ]; then FIRMWARE=/firmware; fi` — or just call `raspi-config nonint` and let it do the detection. **`/boot/mics.conf` in the CONTEXT §7 design becomes `/boot/firmware/mics.conf`.** The user-facing property is unchanged: it is still the FAT partition's root as seen from a laptop.

### Pitfall 6: PEP 668 blocks system-wide pip on Bookworm
**What goes wrong:** `pip install` outside a venv exits with `error: externally-managed-environment`.
**Why it happens:** Debian 12 ships `/usr/lib/python3.11/EXTERNALLY-MANAGED`.
**How to avoid:** Always install into the venv. Do **not** pass `--break-system-packages`. If apt-installed `python3-lgpio` is used instead of the PyPI wheel, the venv needs `--system-site-packages` — verified empirically that this does put `/usr/lib/python3/dist-packages` on `sys.path`, but it *also* adds `~/.local/lib/python3.11/site-packages`, so pair it with `PYTHONNOUSERSITE=1`.

### Pitfall 7: systemd's start-rate limit turns a restart loop into a permanent outage
**What goes wrong:** The pilot crashes five times in ten seconds (e.g. the backend is briefly unreachable at boot), systemd marks the unit `failed`, and `Restart=always` stops meaning always. The rig is then down until a human intervenes — the exact failure the phase exists to eliminate.
**Why it happens:** Defaults are `StartLimitIntervalSec=10s`, `StartLimitBurst=5`.
**How to avoid:** `StartLimitIntervalSec=0` in `[Unit]`, plus `RestartSec=5` so a genuinely broken build does not spin the CPU.

### Pitfall 8: lgpio raises where pigpio returned negative numbers
**What goes wrong:** A `TX_QUEUE_FULL` (-96) or `GPIO_BUSY` (-79) becomes an exception thrown out of a hardware callback, unwinding the caller before its remaining writes (including the view update an FDA transition depends on) can run — the precise hazard `Event_Dispatcher.py:70-75` already documents.
**Why it happens:** `lgpio_extra.py` has a module global `exceptions = True`, and `_u2i()` raises `lgpio.error` on any negative status.
**How to avoid:** Wrap every lgpio call reachable from a hardware/tracker callback in `try/except lgpio.error`, count the failures (following the existing `_dropped_on_send` pattern), and never let it propagate. Do **not** set `lgpio.exceptions = False` globally — silent negative returns are worse.

### Pitfall 9: `Pulse20Hz` is not 20 Hz, and the port changes its actual frequency
**What goes wrong:** A silent change to an optogenetic stimulation frequency, introduced by an "obvious" unit conversion.
**Why it happens:** `gpio.py:1655-1659` sets `self.frequency = 60.0` and `period_ms = 16.667`, so at `duty_cycle=0.5` the durations are `8.333 ms` each. `_series_script` then does `round(dur)` (`gpio.py:572`) → `8 ms` / `8 ms` → **62.5 Hz**. Porting to `tx_pulse` in microseconds (`8333`/`8334`) yields ~60 Hz. Both are wrong relative to the class name, and they are wrong by *different* amounts.
**How to avoid:** Surface this to the user as a decision before the port, not after. Do not silently "improve" the rounding. Record whichever value is chosen in the phase's evidence log.

### Pitfall 10: A stray `pigpiod` will make lgpio's claims fail
**What goes wrong:** `gpio_claim_output` returns `LG_GPIO_BUSY` (-79) → raises.
**Why it happens:** The chardev refuses to hand out a line another consumer holds. pigpio's mmap-based access had no such interlock and would happily fight for a pin.
**How to avoid:** The installer must `apt purge pigpio pigpiod python3-pigpio` (or at minimum `systemctl disable --now pigpiod`), and `pilot.py:949`'s `external.start_pigpiod()` must be deleted, not merely bypassed. Note this is *also* a benefit: a busy-line error is a loud, immediate signal that something else owns the pin, which pigpio never gave you.

---

## Code Examples

### Claiming an input with alerts + a callback

```python
# Verified signatures (lgpio 0.2.2.0):
#   gpio_claim_alert(handle, gpio, eFlags, lFlags=0, notify_handle=None) -> 0
#   callback(handle, gpio, edge=RISING_EDGE, func=None) -> callback instance
#   callback func receives (chip, gpio, level, timestamp)
#     level: 0 falling, 1 rising, 2 watchdog timeout
import lgpio

h = open_header_chip()                      # Pattern 1

lgpio.gpio_claim_alert(h, PIN, lgpio.BOTH_EDGES, lgpio.SET_PULL_UP)
lgpio.gpio_set_debounce_micros(h, PIN, 2000)          # 2 ms; shifts ts by +2 ms (Pitfall 3)

def on_edge(chip, gpio, level, ts_ns):
    ...

cb = lgpio.callback(h, PIN, lgpio.BOTH_EDGES, on_edge)
# ...
cb.cancel()
```

**Two things that are easy to get wrong:** `callback()` does **not** claim the line — `gpio_claim_alert()` must be called first, and `callback()` alone will simply never fire. And `callback()` takes `handle >> 16` internally (`lgpio_extra.py:1127`) because `gpiochip_open` packs the chip number into the handle's high bits; pass the handle from `gpiochip_open` unmodified and it works, but do not construct handles by hand.

### Migration map: pigpio → lgpio

| pigpio (in `mics_core` today) | lgpio | Replacement quality |
|---|---|---|
| `pigpio.pi(sync_ticks=True)` + connect check | `gpiochip_open(n)` (by label) | **Full** — and deletes the daemon-lifecycle code at `pilot.py:205-206,949,1069-1080` |
| `pi.set_mode(p, INPUT/OUTPUT)` | `gpio_claim_input` / `gpio_claim_output` | **Full** |
| `pi.set_pull_up_down(p, PUD_*)` | `lFlags=SET_PULL_UP / SET_PULL_DOWN / SET_PULL_NONE` on the claim | **Full** |
| `pi.write` / `pi.read` | `gpio_write` / `gpio_read` | **Full** |
| `pi.callback(p, EITHER_EDGE, f)` | `gpio_claim_alert(..., BOTH_EDGES)` + `callback(...)` | **Full, and better** — the timestamp is now kernel-at-interrupt rather than a daemon tick |
| `pi.set_glitch_filter(p, us)` | `gpio_set_debounce_micros(h, p, us)` | **Full, with a caveat** — reported timestamp is shifted by the debounce window (Pitfall 3) |
| `pi.set_servo_pulsewidth(p, w)` | `tx_servo(h, p, w, 50, 0, 0)` | **Partial** — lgpio's own docs say "I would only use software timed servo pulses for testing purposes. The timing jitter will cause the servo to fidget." pigpio's was DMA-timed. If a servo is on a behavioural path, this needs measuring; if it is only a feeder gate, it is fine. |
| `pi.gpio_trigger(p, us, level)` | `tx_wave` two-pulse, or `gpio_write` ×2 | **Full** |
| `pi.set_pad_strength` / `get_pad_strength` | — | **None.** Confirmed: zero occurrences of `pad` in `lgpio.h`. Delete, or poke `/sys/kernel/debug/...` (root-only, not recommended). |
| `store_script` / `run_script` / `script_status` / `stop_script` / `delete_script` | `tx_wave` (arbitrary) or `tx_pulse` (uniform, repeating) + `tx_busy`/`tx_room` | **Full for every consumer in this tree.** The `PI_SCRIPT_INITING` polling loop at `gpio.py:673-681` disappears entirely — `tx_wave`/`tx_pulse` enqueue synchronously. |
| `pi.get_current_tick()` (32-bit µs) | the callback's `ts_ns`, or `time.clock_gettime_ns(CLOCK_MONOTONIC)` | **Full, and better** — 64-bit ns, no ~71.6 min wrap |
| patched `pi.synchronize()` / `ticks_to_timestamp()` | `clock_gettime_ns(CLOCK_REALTIME) - clock_gettime_ns(CLOCK_MONOTONIC)` | **Full** — replaces an estimator with an exact read |
| `i2c_open` / `i2c_write_byte_data` / `i2c_read_byte_data` | `lgpio.i2c_open(bus, addr, flags=0)` / `i2c_write_byte_data(h, reg, v)` / `i2c_read_byte_data(h, reg)` | **Full, identical signatures** |
| `i2c_read_i2c_block_data(h, reg, n)` | `lgpio.i2c_read_i2c_block_data(h, reg, count)` → `(count, bytearray)` | **Full, different return shape** — pigpio returned `(count, data)` too, but verify the callers at each of the 7 sites |
| `pi.stop()` | `gpiochip_close(h)`, `i2c_close(h)` | **Full** |

### The clock story, side by side

```python
# BEFORE (patched pigpio 1.78, pigpio.py:5306/5320 -- NOT upstream):
#   offset = mean over N round trips of (host_wallclock - daemon_tick/1e6)
#   ts     = tick/1e6 + offset,  re-synced only when tick < last_tick (i.e. on wrap)
#   -> 32-bit us counter wraps every 71.582788 minutes  (2**32 / 1e6 / 60)
#   -> ~20 wraps/day under 24/7 operation
#   -> a wall-clock STEP between wraps silently corrupts every timestamp until the next wrap

# AFTER (lgpio + kernel gpiochip v2):
#   ts_ns comes from the callback. Kernel-side provenance, verified:
#     drivers/gpio/gpiolib-cdev.c edge_irq_handler():
#         /* Just store the timestamp in hardirq context so we get it as
#            close in time as possible to the actual event. */
#         line->timestamp_ns = line_event_timestamp(line);
#     line_event_timestamp() -> ktime_get_ns()   [CLOCK_MONOTONIC], because
#     lgpio never sets GPIO_V2_LINE_FLAG_EVENT_CLOCK_REALTIME -- the flag is
#     present but COMMENTED OUT at lgGpio.c:243-246 and lgGpio.c:268-271.
#   include/uapi/linux/gpio.h, struct gpio_v2_line_event:
#     "By default the @timestamp_ns is read from CLOCK_MONOTONIC and is
#      intended to allow the accurate measurement of the time between events.
#      It does not provide the wall-clock time."
#   -> 64-bit ns, wraps in ~584 years
#   -> unaffected by wall-clock steps by construction
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `/sys/class/gpio` sysfs | gpiochip character device, uAPI **v2** | v2 in Linux 5.10 (2020); sysfs long deprecated | Everything below follows from this. Line ownership is fd-scoped; edge events carry kernel timestamps. |
| pigpio daemon + `pigs` scripts | in-process `lgpio` | lgpio released 2020; **pigpio's last release 1.79 (2021), unmaintained, cannot run on Pi 5/RP1** | Removes an IPC clock domain and a service to manage. |
| gpio v1 chardev event timestamps on `CLOCK_REALTIME` | v2 default `CLOCK_MONOTONIC`; `EVENT_CLOCK_REALTIME` opt-in (5.11); `EVENT_CLOCK_HTE` (5.19) | 5.10–5.19 | This is why lgpio's own docs hedge ("Early kernels used to provide a timestamp as the number of nanoseconds since the Epoch… Later kernels use the number of nanoseconds since boot. It's probably best not to make any assumption as to the timestamp origin"). On Bookworm's kernel the answer is unambiguous: **monotonic**. Do not carry the hedge into the code as a runtime heuristic; carry it as a startup assertion instead. |
| Pi 5 header GPIOs on `gpiochip4` | `gpiochip0` (kernel 6.6.45), then `gpiochip15` (kernel 6.12.96+rpt-rpi-2712) | Jul 2024, then 2025/26 | Index-based access is not merely fragile, it has *already* broken twice on the target OS. The `60-gpiochip4.rules` udev symlink Raspberry Pi shipped as a fix is itself now defunct. |
| firmware config at `/boot/config.txt` | `/boot/firmware/config.txt`; `/boot/config.txt` was a symlink, now a **placeholder file** | Bookworm (2023), symlink removal later | Silently breaks any installer written against the old path. |
| `dhcpcd` + `wpa_supplicant` | NetworkManager (`NetworkManager-wait-online` enabled by default) | Bookworm | `network-online.target` is meaningful and usable in the unit ordering. |
| system-wide `pip install` | PEP 668 `EXTERNALLY-MANAGED`; venvs mandatory | Bookworm / pip 23.0 | The installer must create a venv; there is no supported alternative. |
| `ntpd` / manual `ntpdate` | `systemd-timesyncd` default, `chrony` when policy matters | Bookworm | timesyncd is fine for a desktop and wrong for a rig — it steps at ≥0.4 s offset with no way to stop it. |

**Deprecated / outdated:**
- **pigpio** — last release 1.79 (2021); no RP1/Pi 5 support; the `mics_core` copy is additionally a *patched fork* with non-upstream `synchronize()`/`ticks_to_timestamp()`. Delete it, do not vendor it forward.
- **`np.int` / `np.bool` / `np.float`** — removed in numpy 1.24. Already enumerated in CONTEXT §4.
- **`Thread.setDaemon()`** — deprecated since 3.10, removed in 3.13. Cosmetic on 3.11 but fix it now rather than at the next OS bump.
- **`/boot/config.txt`**, **`gpiochip` by index**, **sysfs GPIO** — all covered above.

---

## Open Questions

1. **Does the installer own the whole box, or coexist?** (CONTEXT §9.4, unresolved.)
   - *What we know:* The operations it needs — `apt install`, `raspi-config nonint do_i2c 0`, writing `/boot/firmware/config.txt`, `usermod -aG`, enabling units, replacing `systemd-timesyncd` with `chrony`, purging `pigpiod` — are all system-wide and not scoped to a user.
   - *What's unclear:* whether a researcher might run the installer on a Pi already doing something else.
   - *Recommendation:* Declare **"the installer owns the box"** and put that sentence at the top of the README. Then make it defensible rather than dangerous: back up every file it edits to `<file>.mics.bak`, make it idempotent, and add a `--dry-run` that prints the diff. Ask the user to confirm this framing before Stage 2 is planned — it changes the script's shape substantially.

2. **What real jitter does lgpio's tx thread deliver on a Pi 4B under Bookworm, at `SCHED_OTHER` vs `SCHED_FIFO`, idle vs loaded?**
   - *What we know:* The mechanism exactly (absolute-deadline `clock_nanosleep` in an ordinary pthread, drift-free schedule, per-edge lateness = scheduler wakeup latency + ioctl time).
   - *What's unclear:* the numbers. Anything I state here would be a guess.
   - *Recommendation:* **Must be confirmed on hardware during the spike.** It is the first measurement of Stage 3 and it gates the design. Do not plan the `Digital_Out` rewrite in detail until it is in hand.

3. **Does `CPUSchedulingPolicy=fifo` actually reach the lgpio tx thread?**
   - *What we know:* systemd applies the policy at `exec`; `lgPthTxStart()`/`lgPthAlertStart()` are called from inside `lgGpiochipOpen()` (`lgGpio.c:772-774`); `pthread_attr_setinheritsched(3)`'s default is `PTHREAD_INHERIT_SCHED`. Every link in the chain is documented.
   - *What's unclear:* whether CPython does anything between `exec` and the pilot's `gpiochip_open()` that resets scheduling (it should not).
   - *Recommendation:* Verify with one command on the box — `for t in /proc/$(pgrep -f mics)/task/*; do chrt -p ${t##*/}; done` — and assert it in the harness. Cheap; do it before relying on it.

4. **How many event-FIFO slots does the kernel give each claimed line, and can the rig overflow it?**
   - *What we know:* The kernel drops events when the per-request FIFO is full (`pr_debug_ratelimited("event FIFO is full - event dropped")`), and the request's `event_buffer_size` defaults to 16 × lines. **lgpio never sets `event_buffer_size`** — zero occurrences in `lgGpio.c`.
   - *What's unclear:* whether a lick-sensor burst can exceed 16 events between lgpio's 0.5 ms poll cycles. 16 events in 0.5 ms is 32 kHz, so it is unlikely — but "unlikely" is not "measured", and a dropped edge is silent.
   - *Recommendation:* Count commanded-vs-observed edges in the soak test (see `## Validation Architecture`). If drops ever appear, the fix is a small lgpio patch or a move to libgpiod for that line — record the escape hatch, do not pre-build it.

5. **Does anything on the rig still need `tx_servo`?**
   - *What we know:* lgpio's author explicitly warns against software-timed servo pulses for real use.
   - *What's unclear:* whether the `set_servo_pulsewidth` call sites are on a behavioural path or a mechanical convenience.
   - *Recommendation:* Enumerate the call sites in Stage 1 and, if any are behavioural, measure them in the same harness as the valve.

6. **Backend-side follow-ups** (CONTEXT §9.5) — rejecting `CHANGE_ME_*` handshakes and taking the Pi IP from the ZMQ peer instead of `get_ip()`.
   - *Recommendation:* **Separate phase.** Both are `mics-backend` changes, neither blocks the Pi work, and mixing repos in one phase makes the exit gate ambiguous.

7. **journald persistence vs SD wear.**
   - *What we know:* Pi log *files* are 0 bytes by design, so under systemd the journal becomes the only real log. Bookworm's `Storage=auto` means the journal is volatile unless `/var/log/journal` exists — i.e. a crash-and-reboot loses exactly the evidence you wanted. But SD wear is named as the top 24/7 failure mode.
   - *Recommendation:* Enable persistence with a hard cap — `mkdir -p /var/log/journal` plus `SystemMaxUse=200M`, `SystemMaxFileSize=20M`, `Compress=yes`, `RateLimitBurst=` tuned — and make it a documented, reversible installer choice rather than a silent default. Needs a user decision.

---

## Validation Architecture

The acceptance gate for this phase is a **paired before/after pulse-timing measurement**, not a functional smoke test. This section defines the instrument, the statistics, the thresholds, and how the 24/7 claim is tested without waiting 24 hours.

### Constraint that shapes everything here

The standing hard rules forbid running any Python on the Pi and forbid starting or stopping the pilot process. **Every hardware measurement in this section is therefore USER-RUN**: the plan supplies the exact command, the user runs it and pastes back the output or the artifact path, and the agent analyses the artifact locally. This follows the precedent already set by Phase 30, where HYG-01 and HYG-02 are marked USER-RUN. Analysis of a captured artifact is fully automatable and runs on the dev machine; capture is not.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | `pytest` (the tree's only test config today is `autopilot/pytest.ini`, which HYG-09 replaces; `mics_core/pytest.ini` exists at the root) |
| Config file | `mics_core/pytest.ini` |
| Quick run command (dev machine) | `cd ~/mics_core && python -m pytest -q tests/ -x` |
| Full suite command (dev machine) | `cd ~/mics_core && python -m pytest -q && python3 tools/check_tree_integrity.py --strict` |
| Hardware capture (Pi) | **USER-RUN.** `sudo systemctl stop mics-pilot && /home/pi/.venv/mics/bin/python -m tools.pulse_timing.capture --config <profile> --out /tmp/pulse_<label>.jsonl` — supplied to the user as a copy-paste block, never executed by the agent |
| Artifact analysis (dev machine) | `python -m tools.pulse_timing.analyse /path/to/pulse_before.jsonl /path/to/pulse_after.jsonl` |

The 23 root test modules have **never been run anywhere** (HYG-13). Wave 0 must therefore include getting `pytest` green on the dev machine before any of this is trusted as a gate.

### The instrument: GPIO loopback self-measurement

**Method.** Jumper a spare output pin to a spare input pin. Claim the output normally; claim the input with `gpio_claim_alert(BOTH_EDGES)` and **no debounce** (Pitfall 3 would otherwise shift every timestamp). Command a pulse via exactly the production code path (`tx_wave` / `tx_pulse`), and read the resulting edge timestamps out of the alert callback. Measured width = `t_falling − t_rising`.

**Why this is the right instrument, not a compromise:**
- The measurement clock is the kernel's hardirq timestamp on `CLOCK_MONOTONIC` — nanosecond resolution, taken as close to the physical edge as the hardware allows. It is strictly better than anything a userspace timer could give.
- Both edges of a pulse are measured on the same clock with the same latency path, so the **IRQ latency largely cancels in the width difference** even though it does not cancel in the absolute timestamp. Width accuracy is therefore much better than absolute-timestamp accuracy.
- It exercises the exact code under test, on the exact hardware, with no additional equipment — which means the "before" (pigpio) capture is equally easy to obtain, and the comparison is genuinely paired.

**Its honest limits, stated so the plan does not overclaim:** the input-side IRQ latency is not zero, and under heavy load its jitter contaminates the measurement. A loopback capture cannot distinguish "the output edge was late" from "the input interrupt was serviced late". For that reason:

**Independent cross-check (do this once, not per-run):** a USB logic analyser — any 24 MHz 8-channel clone driven by `sigrok-cli`/PulseView, 41.7 ns resolution, ~£10 — sampling the output pin directly, on the same commanded pulse train. Run it once at the start of Stage 3 to establish that the loopback method agrees with an external observer to within the loopback's claimed resolution. After that, the loopback is the routine instrument. An oscilloscope works equally well for this one calibration step if one is available; a scope is *worse* for the routine measurement because it cannot easily produce n≥1000 automatically.

### Measurement profiles

| Profile | Stimulus | Why |
|---|---|---|
| `valve` | 1000 × one-shot 200 ms pulse, 300 ms apart | The reward-volume path (`Solenoid.open`, `gpio.py:1555/1608`). 200 ms and 40 ms are the durations actually in prefs. |
| `valve_short` | 1000 × one-shot 40 ms pulse | The odour/air-puff duration. |
| `ttl` | 1000 × TTL pulse at the configured `pulse_width`/`interval` | Sync-pulse width (`gpio.py:1146`). |
| `train` | 60 s continuous `Pulse20Hz` train | Period jitter **and cumulative drift** — the property `tx_pulse`'s absolute-deadline scheduling should protect. |
| `mixed` | `valve` + `train` running concurrently | The tx thread services all GPIOs from one loop; contention between them is the realistic case and is not visible in single-profile runs. |

Each profile is captured under **two load conditions**:
- **idle** — nothing else running
- **loaded** — `stress-ng --cpu 4 --io 2 --vm 1 --vm-bytes 128M --timeout 120s` **plus** a live ZMQ session generating CONTINUOUS traffic

and under **two scheduling settings** for the `after` arm: `SCHED_OTHER` and `SCHED_FIFO:10`. The `before` (pigpio) arm is captured as-is, since pigpio self-elevates to `SCHED_FIFO` max.

That is 5 profiles × 2 loads × (1 before + 2 after) = 30 captures. At ~5 minutes each this is a single afternoon of user-run work, and it is the phase's most valuable artifact.

### Statistics to report

Per profile × load × arm, over n ≥ 1000 pulses (60 s × 60 Hz ≈ 3600 for `train`):

| Statistic | Definition |
|---|---|
| `n`, `n_missing` | commanded pulses vs observed edge pairs — **`n_missing > 0` is an automatic fail** (it means a dropped edge, cf. Open Question 4) |
| `err_median` | median(measured_width − commanded_width) — systematic bias |
| `err_sd` | SD of the error — the jitter figure |
| `err_p99`, `err_max` | tail behaviour; this is what a mouse experiences on a bad trial |
| `err_iqr` | robust spread, reported alongside SD because the distribution is expected to be right-skewed |
| `period_sd` (trains only) | SD of successive rising-edge intervals |
| `rate_ppm` (trains only) | slope of a least-squares fit of edge index vs edge time, expressed as ppm deviation from commanded — **this is the cumulative-drift test** |

Report as a table plus an ECDF plot of `|err|` per arm. Do not report only the mean.

### Proposed pass thresholds

The **primary** gate is comparative and needs no arbitrary numbers:

> **G1 (primary).** For every profile × load, the lgpio arm's `err_p99` and `err_sd` must be **≤ 1.25 ×** the pigpio baseline captured on the same hardware in the same session. `n_missing` must be 0 in every capture.

The absolute thresholds below are secondary, and exist so that a *jointly bad* baseline cannot pass by comparison alone. They are derived from the science, not from what the hardware happens to do:

| Profile | Statistic | Threshold | Derivation |
|---|---|---|---|
| `valve` (200 ms) | `err_p99` | ≤ 1.0 ms (0.5 %) | Reward-volume reproducibility. Valve flow is roughly linear in open time; 0.5 % is well inside the volumetric variance of the solenoid itself. |
| `valve_short` (40 ms) | `err_p99` | ≤ 0.5 ms (1.25 %) | Same argument at the shorter duration where relative error is larger. |
| `ttl` | `err_p99` | ≤ 200 µs | The TTL is the cross-device alignment ground truth (Phase 28); its *width* only needs to be unambiguously detectable, but its *edge* is the alignment point, so tighten this if Phase 28 states a stricter figure. |
| `train` | `period_sd` | ≤ 200 µs | ~1.2 % of a 16.7 ms period; below the temporal resolution of any downstream behavioural analysis. |
| `train` | `rate_ppm` | \|rate error\| ≤ 100 ppm | Guards the drift-free property of absolute-deadline scheduling. A failure here means something is re-basing the schedule, which would be a genuine bug. |

**If the thresholds are missed at `SCHED_OTHER` but met at `SCHED_FIFO:10`,** that is the expected outcome and it *justifies* the unit's scheduling directive with evidence. **If they are missed at `SCHED_FIFO` too,** stop and escalate: the options are a `PREEMPT_RT`/`PREEMPT` kernel, CPU isolation (`isolcpus=3` + affinity for the tx thread), or moving the timing-critical outputs to hardware PWM — all of which are much larger changes and none of which should be planned speculatively.

### Validating the 24/7 claim without waiting 24 hours

Four bounded experiments replace the calendar.

**V1 — Forced clock step (the core claim).** While a capture is running, apply a step forwards and, separately, backwards:
```bash
sudo timedatectl set-ntp false
sudo date -s '+1 hour'      # then, in a second run: sudo date -s '-1 hour'
sudo timedatectl set-ntp true
```
Assertions, all machine-checkable from the artifact:
- `t_mono_ns` is strictly increasing across the step, with **no discontinuity** — the interval between the pulses straddling the step equals the commanded interval within the profile's jitter budget.
- The derived `t_utc` steps by **exactly** the applied amount and by nothing else. (This is *correct* behaviour, not corruption — and stating it that way in the plan is what keeps the claim honest.)
- The pilot does not crash; the session continues; `_dropped_no_clock` and `_dropped_on_send` remain 0.
- Run the identical experiment on the pigpio baseline and record the contrast: there, `ticks_to_timestamp()` is corrupted from the step until the next 32-bit wrap, because `synchronize()` is only re-run when `ticks < _last_synced_tick`.

**V2 — Counter wraparound.** pigpio's counter wraps every **71.58 minutes** (`2**32 / 1e6 / 60`). Demonstrate the old failure with a single 75-minute baseline capture (once, not per-run) showing the re-sync discontinuity. For lgpio no experiment is needed — 64-bit nanoseconds is ~584 years — but the harness should assert the field's width and monotonicity so the claim is machine-checked rather than asserted in prose.

**V3 — Overnight soak (8–12 h, unattended, one time).** `train` profile plus periodic `valve` pulses, running under the real systemd unit. Assertions: `n_missing == 0`; `err_p99` in the last hour is within 1.25× of the first hour (no thermal or drift degradation); pilot RSS flat within 5 %; journal size within its configured cap; `systemctl show mics-pilot -p NRestarts` returns 0. This is the one experiment that genuinely needs wall-clock time, and it runs while nobody is watching — which is the point.

**V4 — Restart and reboot resilience.** `sudo systemctl kill -s SIGKILL mics-pilot` → assert the unit restarts within `RestartSec`, the pilot re-handshakes with the backend, and `/run/mics/.lgd-nfy*` is recreated. Then `sudo reboot` → assert the pilot is up and connected with no human action. Repeat the kill 10× in 30 s to prove `StartLimitIntervalSec=0` prevents the `failed` latch (Pitfall 7). Also verify the fail-safe output level after SIGKILL with a solenoid energised (Pitfall 4) — physically, with a meter.

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PLAT-01 | shed leaves the tree importable; `PORT_CALIBRATION` gate updated | unit | `python -m pytest -q tests/ -x && python3 tools/check_tree_integrity.py --strict` | ❌ Wave 0 |
| PLAT-02 | no numpy-removed aliases remain | static | `python -m pytest -q tests/test_numpy_compat.py` (greps the tree for `np.int\b`, `np.bool\b`, `np.float\b`, `np.object\b`, `setDaemon`) | ❌ Wave 0 |
| PLAT-03 | every pin resolves to a prebuilt aarch64 cp311 wheel | integration | `python -m pytest -q tests/test_requirements_wheels.py` (queries the PyPI JSON API per pin; skipped when offline) | ❌ Wave 0 |
| PLAT-04, 05 | installer is idempotent and targets `/boot/firmware` | integration | `bash -n deploy/install.sh && shellcheck deploy/install.sh && python -m pytest -q tests/test_installer_paths.py` | ❌ Wave 0 |
| PLAT-06 | venv has no system-site-packages and sets `PYTHONNOUSERSITE` | unit | `python -m pytest -q tests/test_unit_files.py::test_pilot_unit_env` | ❌ Wave 0 |
| PLAT-07, 08, 09, 10, 11 | unit files are well-formed and carry the required directives | unit | `python -m pytest -q tests/test_unit_files.py` (parses the `.service` files; asserts `StartLimitIntervalSec=0`, `RuntimeDirectory`, `LG_WD`, `After=chrony-wait.service`, absence of `PrivateDevices`) | ❌ Wave 0 |
| PLAT-07..11 | units actually load on the target | smoke | **USER-RUN:** `systemd-analyze verify /etc/systemd/system/mics-*.service` | n/a |
| PLAT-12 | chip resolution picks the header chip by label | unit | `python -m pytest -q tests/test_lgchip.py` (fakes `gpio_get_chip_info` for Pi 4, Pi 5-6.6.45, Pi 5-6.12.96 layouts) | ❌ Wave 0 |
| PLAT-13 | I²C call sites converted; return shapes handled | unit | `python -m pytest -q tests/test_i2c_port.py` (fake lgpio module) | ❌ Wave 0 |
| PLAT-14, 15 | `series`/`store_series` emit the right `tx_wave`/`tx_pulse` calls | unit | `python -m pytest -q tests/test_digital_out_tx.py` (asserts pulse lists, µs conversion, `cycles=0` for `repeat=-1`) | ❌ Wave 0 |
| PLAT-16 | zero `pigpio` references remain in the pilot import path | static | `python -m pytest -q tests/test_no_pigpio.py` | ❌ Wave 0 |
| PLAT-17 | all pilot threads report `SCHED_FIFO` | smoke | **USER-RUN:** `for t in /proc/$(pgrep -f mics_core)/task/*; do chrt -p ${t##*/}; done` | n/a |
| PLAT-18, 19 | dispatched events carry both timebases; edge ts is threaded through | unit | `python -m pytest -q tests/test_event_dispatcher_clock.py` | ❌ Wave 0 |
| PLAT-20, 21 | chrony installed, `makestep 1 3` intact, timesyncd gone | smoke | **USER-RUN:** `chronyc tracking; grep -R makestep /etc/chrony/; systemctl is-enabled systemd-timesyncd \|\| echo absent` | n/a |
| PLAT-22 | the clock-freeze block and its `--final` F3 guard are both gone | static | `python -m pytest -q tests/test_clock_block_removed.py` + `python3 tools/check_tree_integrity.py --strict --final` | ❌ Wave 0 |
| PLAT-23 | harness produces a well-formed capture | unit | `python -m pytest -q tests/test_pulse_timing_analyse.py` (analyses a checked-in synthetic capture) | ❌ Wave 0 |
| PLAT-24 | paired before/after meets G1 + absolute thresholds | manual-only (capture) → automated (analysis) | capture **USER-RUN**; then `python -m tools.pulse_timing.analyse before.jsonl after.jsonl --gate` exits non-zero on failure | ❌ Wave 0 |
| PLAT-25 | forced clock step leaves monotonic timestamps coherent | manual-only (capture) → automated (analysis) | capture **USER-RUN**; then `python -m tools.pulse_timing.analyse step_capture.jsonl --check-step +3600` | ❌ Wave 0 |

**Manual-only justification:** every row marked USER-RUN requires either physical hardware the dev machine does not have, or an action the hard rules forbid the agent from taking (running Python on the Pi, starting/stopping the pilot). In each case the *capture* is manual and the *analysis* is fully automated against a committed artifact — so the evidence is reproducible and reviewable even though its production is not.

### Sampling Rate

- **Per task commit:** `cd ~/mics_core && python -m pytest -q tests/ -x`
- **Per wave merge:** `cd ~/mics_core && python -m pytest -q && python3 tools/check_tree_integrity.py --strict`
- **Per stage exit:** the above, plus `shellcheck deploy/*.sh`, plus the USER-RUN smoke commands for that stage
- **Phase gate:** full suite green, `check_tree_integrity.py --strict --final` green with the F3 guard deliberately retired, and the paired timing capture passing G1 + absolute thresholds, before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `pytest` green at all on the dev machine — the 23 existing root test modules have never been executed anywhere (HYG-13); this is a prerequisite for every gate above
- [ ] `tests/conftest.py` — a fake `lgpio` module fixture, so every port test runs on the dev machine without hardware
- [ ] `tests/test_lgchip.py` — covers PLAT-12
- [ ] `tests/test_digital_out_tx.py` — covers PLAT-14, PLAT-15
- [ ] `tests/test_i2c_port.py` — covers PLAT-13
- [ ] `tests/test_event_dispatcher_clock.py` — covers PLAT-18, PLAT-19
- [ ] `tests/test_unit_files.py` — covers PLAT-06 through PLAT-11
- [ ] `tests/test_installer_paths.py` — covers PLAT-04, PLAT-05
- [ ] `tests/test_no_pigpio.py`, `tests/test_numpy_compat.py`, `tests/test_clock_block_removed.py` — static gates for PLAT-16, PLAT-02, PLAT-22
- [ ] `tests/test_requirements_wheels.py` — covers PLAT-03
- [ ] `tools/pulse_timing/{capture,analyse}.py` + a committed synthetic capture fixture — covers PLAT-23, PLAT-24, PLAT-25
- [ ] `shellcheck` available on the dev machine (`sudo apt install shellcheck`)
- [ ] A logic analyser (or scope) borrowed **once** for the loopback calibration cross-check
- [ ] Spare Pi 4B + spare SD card + two jumpered GPIO pins, confirmed available before Stage 3 is scheduled

---

## Sources

### Primary (HIGH confidence)

- **lgpio 0.2.2.0 source**, downloaded from PyPI and read directly (`pip download lgpio --no-binary :all:`):
  - `lgpio_extra.py` — the shipped Python API: signatures, docstrings, the `pulse` class, `_callback_thread` (line 262-331, incl. the relative `.lgd-nfy` open at :273 and module-import-time thread start at :331), `_u2i` exception behaviour (:219-228), `gpiochip_open` handle packing (:411-414), `gpio_get_chip_info` (:432-443), `tx_pulse` (:752-808), `tx_wave` (:900-940), `gpio_set_debounce_micros` timestamp-shift note (:1000-1001), `gpio_claim_alert` (:1035-1064), `callback` (:1066-1127)
  - `src/lgPthTx.c` — the transmit thread: `lgMinTxDelay = 10` (:34), the `clock_nanosleep(CLOCK_MONOTONIC, TIMER_ABSTIME)` loop (:171-183), `lgGroupCreateWaveRec` (:283-318)
  - `src/lgPthAlerts.c` — the alert thread: `xMonotonicTimestamp()` (:76-83), debounce timestamp shift (:322), watchdog synthesis (:369), `ppoll` 0.5 ms timeout (:438), kernel `timestamp_ns` propagation (:504-519)
  - `src/lgGpio.c` — `EVENT_CLOCK_REALTIME` commented out (:243-246, :268-271), `xSetAsPwm` (:505-596), `xWave` (:598-655), `lgTxPulse`/`lgTxWave`/`lgTxBusy`/`lgTxRoom` (:1168-1285), `lgPthTxStart()`/`lgPthAlertStart()` inside chip open (:772-774)
  - `src/lgPthTx.h` — `LG_TX_BUF 10` (:36)
  - `src/lgNotify.c` — FIFO path construction (:130); `src/lgUtil.c` — `lguGetWorkDir()` / `$LG_WD`
  - `src/lgpio.h` — `LG_MAX_MICS_DEBOUNCE 5000000`, `LG_MAX_MICS_WATCHDOG 300000000`, `LG_CFG_ID_MIN_DELAY 1`; **zero** occurrences of pad-strength APIs
  - Verified absence of `sched_setscheduler` / `SCHED_FIFO` / `pthread_setschedparam` / `mlockall` across all `src/*.c`
- **Linux kernel uAPI**, `include/uapi/linux/gpio.h` (torvalds/linux master) — `struct gpio_v2_line_event` doc comment: *"By default the @timestamp_ns is read from %CLOCK_MONOTONIC … If the %GPIO_V2_LINE_FLAG_EVENT_CLOCK_REALTIME flag is set then the @timestamp_ns is read from %CLOCK_REALTIME."*
- **Linux kernel**, `drivers/gpio/gpiolib-cdev.c` (torvalds/linux master) — `line_event_timestamp()` (:576-585) → `ktime_get_ns()`; `edge_irq_handler()` (:779-791) *"Just store the timestamp in hardirq context so we get it as close in time as possible to the actual event."*; `edge_irq_thread()` (:733-777); event-FIFO-full drop path
- **pigpio**, `pigpio.c` (joan2937/pigpio master) — `sched_setscheduler(0, SCHED_FIFO, sched_get_priority_max(SCHED_FIFO))` at :8340-8343
- **systemd**, `src/timesync/timesyncd-manager.c` (systemd main) — `#define NTP_MAX_ADJUST 0.4` (:52) and the step branch at :245-247
- **raspi-config**, `bookworm` branch (RPi-Distro/raspi-config) — `/boot/firmware` auto-detection (:10-15), `do_i2c()` full body, `set_config_var()` lua upsert, `do_hostname()`, `do_expand_rootfs()`
- **raspberrypi-sys-mods**, `etc.armhf/udev/rules.d/99-com.rules` — `SUBSYSTEM=="gpio", GROUP="gpio", MODE="0660"`, `SUBSYSTEM=="i2c-dev", GROUP="i2c", MODE="0660"`
- **Raspberry Pi apt archive**, `archive.raspberrypi.com/debian dists/bookworm/main/binary-arm64/Packages.gz` (read directly) — `python3-lgpio 0.2.2-1~rpt1`, `liblgpio1 0.2.2-1~rpt1`, `rgpiod 0.2.2-1~rpt1`, `python3-rgpio 0.2.2-1~rpt1`, `python3-rpi-lgpio 0.6-0~rpt1`, `pigpio 1.79-1+rpt1`
- **Debian chrony packaging** (salsa.debian.org/debian/chrony, `debian/bookworm`) — stock `chrony.conf` with `makestep 1 3`, `rtcsync`, `driftfile`, `maxupdateskew 100.0`; package file list confirming `/lib/systemd/system/chrony-wait.service`
- **chrony upstream**, `examples/chrony-wait.service` — `After=chronyd.service`, `Before=time-sync.target`, `chronyc waitsync 0 0.1 0.0 1`, `TimeoutStartSec=180`
- **PyPI JSON API** — wheel/tag inventory for `lgpio` (cp311 `manylinux_2_34_aarch64`), `numpy` (2.5 requires ≥3.12; 2.3.5 last cp311), `pyzmq`, `msgpack`, `tornado` (abi3), `sysv_ipc`, `Adafruit-PureIO` (sdist only), `adafruit-blinka` 9.2.0 dependency list
- **Empirical, this machine** (Debian-family, Python 3.12) — confirmed `EXTERNALLY-MANAGED` present, and that `python3 -m venv --system-site-packages` puts both `/usr/lib/python3/dist-packages` **and** `~/.local/lib/pythonX.Y/site-packages` on `sys.path`
- **`~/mics_core` source, read directly** — `gpio.py:519-693` (`_series_script`/`store_series`/`series`), `gpio.py:1130-1174` (`TTL`), `gpio.py:1628-1690` (`Pulse20Hz`, incl. the 60 Hz/`round()` defect), `Event_Dispatcher.py:1-95` (dispatch-time clock read at :77)
- `chrony.conf(5)` (chrony-project.org, 4.3) — `makestep`, `maxslewrate` (default 83333.333 ppm), `corrtimeratio`, `maxchange`, `rtcsync`, `leapsecmode`

### Secondary (MEDIUM confidence)

- Raspberry Pi Forums, *"pinctrl-rp1 no longer gpiochip0 with 6.12.96+rpt-rpi on bookworm"* — `gpiochip0 [pinctrl-rp1]` on 6.12.93 → `gpiochip15 [pinctrl-rp1]` on 6.12.96; `/lib/udev/rules.d/60-gpiochip4.rules` now defunct. Corroborated by the gpiozero issue below and consistent with the kernel-6.6.45 renumbering.
- gpiozero issue #1166, *"lgpio pin factory is broken on RPi5 since kernel 6.6.45"* — the `gpiochip4` → `gpiochip0` move
- Raspberry Pi Forums / raspberrypi-sys-mods issue #88 — `/boot/config.txt` and `/boot/cmdline.txt` symlinks replaced with placeholder files; corroborated by raspi-config's own `-e /boot/firmware/config.txt` detection, which only makes sense if `/boot/config.txt` is not a reliable alias
- Pi 4 `gpiodetect` output `gpiochip0 [pinctrl-bcm2711] (58 lines)`; Pi 5 `gpiochip? [pinctrl-rp1] (54 lines)`. **This refines CONTEXT.md §5**, which names `pinctrl-bcm2835` as the Pi 4 label — `bcm2835` is the label on Pi 2/3/Zero. The recommended resolver in Pattern 1 accepts all three plus any `pinctrl-*` fallback, so the refinement does not change the design, only the allowlist ordering.
- Raspberry Pi OS Bookworm uses NetworkManager with `NetworkManager-wait-online` enabled by default, making `network-online.target` usable
- `rpi-imager` first-boot mechanism (`systemd.run=/boot/firmware/firstrun.sh`, `custom.toml`) — named as a considered-and-rejected alternative, not as a dependency

### Tertiary (LOW confidence — flagged for validation on hardware)

- **All absolute jitter numbers.** No figure for lgpio's tx-thread jitter on a Pi 4B under Bookworm appears anywhere I could verify. The mechanism is fully known; the magnitude is not. **Must be measured during the spike.**
- **Whether `CPUSchedulingPolicy=fifo` reaches the lgpio tx thread in practice.** Every link (systemd applies at exec; threads created in `gpiochip_open`; POSIX default is `PTHREAD_INHERIT_SCHED`) is documented, but the composition is not verified end-to-end. One `chrt -p` check settles it.
- **Whether the kernel's 16-events-per-line default FIFO can overflow on this rig.** Arithmetic says no by a wide margin; no measurement exists.
- **`Adafruit-PureIO` building cleanly from sdist on Bookworm arm64.** Pure Python, so it should — unverified.
- **Whether the `tx_servo` call sites matter behaviourally.** Not yet enumerated.

---

## Metadata

**Confidence breakdown:**

| Area | Level | Reason |
|------|-------|--------|
| lgpio API signatures & semantics | **HIGH** | Read from the shipped Python wrapper *and* the C implementation, not from prose docs. Where the docs and the code could disagree (e.g. the debounce timestamp shift), both were checked and they agree. |
| Callback timestamp clock & provenance | **HIGH** | Triangulated across three independent primary sources: lgpio's commented-out `EVENT_CLOCK_REALTIME` flag, the kernel uAPI header's normative doc comment, and `gpiolib-cdev.c`'s hardirq handler. |
| Timed-pulse *mechanism* | **HIGH** | The tx thread's full source was read. Fire-and-forget in C: yes. Hardware/DMA-timed: **no** — and that distinction is the phase's principal risk. |
| Timed-pulse *jitter magnitude* | **LOW** | No verifiable published figure. Deliberately left as a measurement, not a guess. |
| Bookworm packaging & installer surface | **HIGH** | Live archive index, the actual `bookworm` branch of raspi-config, the actual udev rules, and a local empirical venv check. |
| systemd unit design | **MEDIUM-HIGH** | Directive semantics are from systemd's documented behaviour and its own source for the timesyncd threshold; the specific composition (FIFO inheritance reaching lgpio's threads, `LG_WD` + `RuntimeDirectory`) is sound but unverified end-to-end on hardware. |
| Clock discipline (chrony vs timesyncd) | **HIGH** | timesyncd's 0.4 s step threshold read from systemd source; Debian's `makestep 1 3` read from the packaging; `chrony-wait.service` confirmed present in the bookworm package file list. |
| Pi 5 / RP1 forward-compat | **MEDIUM-HIGH** | The *instability* of chip indices is well evidenced (three different indices across three kernels). Exact label strings for each board rest on reported `gpiodetect` output rather than a primary source, which is why the recommended resolver uses a prefix fallback and a line-count assertion rather than exact-match alone. |
| Validation architecture | **MEDIUM** | The instrument and its cancellation argument are sound and cheap. The absolute thresholds are *proposed from the science*, not measured, and should be reviewed with the user before Stage 3 — the comparative gate G1 is the one that carries the weight. |

**Research date:** 2026-08-16
**Valid until:** 2026-09-15 (30 days). Two things move faster than that and should be re-checked at planning time: Raspberry Pi kernel gpiochip numbering (it has changed twice in ~18 months) and PyPI wheel availability for the pinned versions.
