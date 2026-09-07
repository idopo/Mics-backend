# Pi Rig Hardware Knowledge Base — audio, analog I/O, GPIO budget, RFID, OptoBlueBerry, Pi 4B vs Pi 5

Status: research + code audit + live read-only probes of RecordingBox (132.77.73.213),
2026-09-07. No hardware changes made. Rig findings and two corrections are in §11.
Code audited: `/home/ido/mics_core` (`pilot/prefs.template.json`,
`autopilot/autopilot/hardware/`, `autopilot/autopilot/networking/Event_Dispatcher.py`).

Every claim below is tagged **[verified in code]**, **[datasheet/vendor]**, or **[reported]**.

---

## 1. The single hard constraint: the GPIO budget is already at 100%

**[verified in code]** `autopilot/hardware/__init__.py` `BOARD_TO_BCM` maps exactly the 26 general
GPIO lines BCM2–BCM27. `pilot/prefs.template.json` assigns 24 of them; the remaining two
(BCM2/BCM3, board 3/5) are I2C1 SDA/SCL, carrying both MPR121s and the motor-shield HAT.

**There is not one free pin on the header today.**

### 1.1 Current pin map (BOARD → BCM, from prefs.template.json)

| BOARD | BCM | Name | Group | Type | Alt function it consumes |
|---|---|---|---|---|---|
| 3 | 2 | *(I2C1 SDA)* | I2C | MPR121 ×2, motor HAT | **I2C1** |
| 5 | 3 | *(I2C1 SCL)* | I2C | " | **I2C1** |
| 7 | 4 | LED1 | LED | `gpio.Pulse20Hz` (soft PWM) | GPCLK0 |
| 8 | 14 | TOUCH_INT | touch_int | `Digital_In`, falling edge | **UART0 TXD** |
| 10 | 15 | AIR_PUF | AIR_PUFF | `Solenoid_mics` | **UART0 RXD** |
| 11 | 17 | LED2 | LED | `Digital_Out` | — |
| 12 | 18 | LED3 | LED | `Digital_Out` | **I2S BCK / PWM0** |
| 13 | 27 | IR5 | IR | `Digital_In`, both edges | — |
| 15 | 22 | IR1 | IR | `Digital_In` | — |
| 16 | 23 | IR2 | IR | `Digital_In` | — |
| 18 | 24 | IR3 | IR | `Digital_In` | — |
| 19 | 10 | ODOR3 | ODOR | `Solenoid_mics` | **SPI0 MOSI** |
| 21 | 9 | ODOR2 | ODOR | `Solenoid_mics` | **SPI0 MISO** |
| 22 | 25 | IR4 | IR | `Digital_In` | — |
| 23 | 11 | ODOR1 | ODOR | `Solenoid_mics` | **SPI0 SCLK** |
| 24 | 8 | ODOR4 | ODOR | `Solenoid_mics` | **SPI0 CE0** |
| 26 | 7 | ODOR5 | ODOR | `Solenoid_mics` | **SPI0 CE1** |
| 29 | 5 | IR6 | IR | `Digital_In` | — |
| 31 | 6 | IR7 | IR | `Digital_In` | — |
| 32 | 12 | TTL1 | TTL | `gpio.TTL` | **PWM0** |
| 33 | 13 | OG_TRIGGER | TRIGGERS | `Digital_Out` → BlueHub BNC | **PWM1** |
| 35 | 19 | VALVE1 | VALVE | `Solenoid_mics` | **I2S LRCK / PWM1** |
| 36 | 16 | AIR_PUF_S | AIR_PUFF | `Solenoid_mics` | — |
| 37 | 26 | VALVE4 | VALVE | `Solenoid_mics` | — |
| 38 | 20 | VALVE2 | VALVE | `Solenoid_mics` | **I2S DIN** |
| 40 | 21 | VALVE3 | VALVE | `Solenoid_mics` | **I2S DOUT** |

### 1.2 What this immediately rules out

- **SPI0 is gone.** BCM7/8/9/10/11 are all odor valves. No MCP3008 ADC, no SPI DAC, no RC522
  RFID, no SPI-attached anything — without moving valves first.
- **The header UART is gone.** BCM14 is TOUCH_INT (an *input*, on the UART TX pin — so the
  serial console must stay disabled) and BCM15 is AIR_PUF. A UART RFID reader cannot use the
  header; it must come in over USB.
- **I2S is gone**, and this is exactly what your electronics engineer meant: I2S on a Pi can
  only be routed to BCM18/19/20/21 (or 28–31, which are **not brought out on a Pi 4B**)
  ([forums.raspberrypi.com](https://forums.raspberrypi.com//viewtopic.php?p=854606&t=127150)).
  Those four are LED3, VALVE1, VALVE2, VALVE3.
- **The extra Pi 4 I2C buses are gone.** `i2c3` = BCM4/5, `i2c4` = BCM6/7 or 8/9, `i2c5` =
  BCM10/11 or 12/13, `i2c6` = BCM0/1 or 22/23 ([dotnet/iot](https://github.com/dotnet/iot/blob/main/Documentation/raspi-i2c.md)).
  Every one of those pairs except BCM0/1 is occupied.

### 1.3 The two pins nobody has counted

BOARD 27/28 = **BCM0/BCM1 (ID_SD / ID_SC)**. They are physically present on every Pi 4B and
are *not* in autopilot's `BOARD_TO_BCM` table. They are reserved for the HAT ID EEPROM.

> **You can have these two pins back, at the price of never fitting a real HAT with an ID
> EEPROM.** Since the recommendation below is a HAT-less DAC module, that price is zero.

**But there is a second price, found on the rig (§11.2): `PIGPIOMASK`.** pigpio's `-x` mask
governs which BCM lines the daemon may *update*, and both the value now shipped
(`0x0FFFFFFC`) and pigpiod's own default cover **BCM2–27 only**. BCM0/BCM1 sit outside both.
So any plan that relocates hardware onto them **must widen the mask to `0x0FFFFFFF` in the
same change**, or those two pins silently refuse every mode change with no error the pilot
surfaces. One line, not optional, easy to miss.

Adding those: **2 free pins**, rising to **3** if the OptoBlueBerry BNC path goes away
(see §6) which frees OG_TRIGGER / BCM13.

---

## 2. Why the audio is bad — three separate causes, only one of them is the sound card

### 2.1 Cause A — the PWM "sound card" is not a DAC

**[vendor]** The Pi 4B 3.5 mm jack is 11-bit PWM at 48 kHz driven into an RC filter; there is
no codec ([raspberrypi.com/documentation/accessories/audio](https://www.raspberrypi.com/documentation/accessories/audio.html),
[Hackaday](https://hackaday.com/2018/07/13/behind-the-pin-how-the-raspberry-pi-gets-its-audio/)).
Distortion comes from the driver's output voltage being quadratic in output current. Its
amplitude accuracy is unusable for calibrated acoustics, and it is *not* the source of the
onset jitter.

**Confirmed on the rig (§11.4):** `card 0: Headphones [bcm2835 Headphones]` is the only
playback device, `dtparam=audio=on`, and `snd_soc_bcm2835_i2s` is not loaded at all — the I2S
peripheral is not even instantiated. Adding a DAC is a config change, not a driver problem.

### 2.2 Cause B — the code decodes the file on every single trigger **[verified in code]**

`autopilot/hardware/mixer.py`:

```python
def __init__(self, **kwargs):
    mixer.init(buffer=1024)                     # no frequency= → SDL opens at 44100 Hz
    self.sound_list = [...]                     # only FILENAMES are cached

@log_action
def set(self, sound_file_index, volume=0.5):
    sound = mixer.Sound(os.path.join(...))      # ← open + decode + resample, PER TRIGGER
    sound.set_volume(volume)
    mixer.Channel(0).play(sound)
```

`mixer.Sound(path)` is constructed **inside the trigger call**. It opens the file, decodes it,
allocates, and — because pygame does "limited resampling to match the mixer init arguments"
([pygame docs](https://www.pygame.org/docs/ref/mixer.html)) — resamples it.

**This is why preloading the file into RAM did not help.** The cost was never disk I/O; the
page cache already had the file. The cost is decode + malloc + resample on the calling thread,
and it scales with file size — your `blip8.wav` is 689 KB, `alt_blip8.wav` 646 KB. Jitter
follows allocator and scheduler state, which is exactly the "random, won't go away" signature
you described.

### 2.3 Cause C — three resampling stages and a 23 ms buffer **[verified in code + docs]**

- `prefs.FS = 192000`, so the wav assets are presumably 192 kHz.
- `mixer.init(buffer=1024)` passes **no `frequency=`**, so SDL opens at its default 44100 Hz.
- pygame resamples 192k → 44.1k at `Sound()` construction time (per trigger, cause B).
- ALSA then goes through `plughw` to reach the device, resampling again.
- `buffer=1024` at 44100 Hz = **23.2 ms** of buffer, plus SDL's own queueing, plus
  `ALSA_NPERIODS=3`.

**[reported]** For comparison, a USB interface on Linux is usually run at 128 frames/period,
3 periods; ≤256 frames is considered acceptable and ≤64 good
([linuxaudio wiki](https://wiki.linuxaudio.org/wiki/raspberrypi), [McLaren Labs](https://mclarenlabs.com/blog/2019/01/05/punching-it-up-low-latency-notes/)).
You are running 8–16× larger than that.

### 2.4 Cause D — you have never actually measured the acoustic onset **[verified in code]**

`Event_Dispatcher.py` documents the clock model: **every** timestamp in the system comes off
the pigpio tick, mapped through `utils.clock.now_from_tick()`; `ts_source` is `"hardware"`
(the DMA-sampled tick at a GPIO edge) or `"software"` (a tick read at dispatch time), and both
come from the one counter.

`mixer.AUDIO.set()` is decorated `@log_action`, so the AUDIO event is `ts_source="software"`:
it records **when `play()` returned**, not when sound left the speaker. Everything downstream
of that call — SDL queue, ALSA buffer, the PWM/DAC pipeline, the amplifier — is invisible to
the event log.

> You cannot fix jitter you cannot see. Whatever card you buy, **the first deliverable is an
> acoustic-onset timestamp on the pigpio tick** (§3.3).

### 2.5 Software fixes worth doing regardless of hardware

1. Preload every `Sound` at `__init__` into a dict; `set()` should only call `.play()`.
2. `mixer.pre_init(frequency=<device rate>, size=-16, channels=2, buffer=256)` before init,
   and store the assets at the device's native rate so nothing resamples.
3. Better: drop pygame for `sounddevice`/PortAudio or raw ALSA with a **persistent open
   stream** and a pre-armed numpy buffer. Onset then quantizes deterministically to one period
   (1.3 ms at 64 frames / 48 kHz) instead of drifting with allocator state.
4. `SDL_AUDIODRIVER=alsa`, `AUDIODEV=hw:X,0` — bypass `plughw` and any dmix.
5. Pin the audio thread: `SCHED_FIFO` priority, `performance` CPU governor.

---

## 3. Sound card options, ranked by GPIO cost

| Option | GPIO cost | Clock relationship to the pigpio tick | Verdict |
|---|---|---|---|
| Onboard PWM jack | 0 | same crystal | Unusable quality (§2.1) |
| **HAT-style I2S DAC/codec** (HiFiBerry etc.) | **4 pins + I2C + EEPROM** | **Pi is I2S master → literally the same crystal** | Your engineer is right: as-is it does not fit |
| **HAT-less I2S DAC module (PCM5102A)** | **3 pins**, no I2C, no EEPROM | **same as above** | ★ Recommended primary |
| Generic USB audio dongle | **0** | independent crystal, free-running | Cheap, but you inherit USB scheduling jitter |
| **Class-compliant USB interface** (ES-8/ES-9, Scarlett, UMC) | **0** | independent crystal | ★ Recommended if you also want analog I/O (§4) |

### 3.1 The PCM5102A route — 3 pins, and the Pi *is* the clock

**[vendor/forum]** The PCM5102A has no control interface at all: BCK → BCM18, LRCK → BCM19,
DIN → BCM21, plus 3V3/GND. No I2C. `dtoverlay=hifiberry-dac` configures it correctly despite
the name ([raspberrypi forums](https://forums.raspberrypi.com/viewtopic.php?t=370450),
[himbeer.me](https://blog.himbeer.me/2018/12/27/how-to-connect-a-pcm5102-i2s-dac-to-your-raspberry-pi/)).
BCM20 (I2S DIN) is needed **only** for audio *input*.

So playback costs exactly **3 pins: BCM18 (LED3), BCM19 (VALVE1), BCM21 (VALVE3)**.

**And you have exactly 3 pins to give:** BCM0, BCM1 (§1.3) and BCM13 (OG_TRIGGER, freed by §6).

VALVE1/VALVE3 are timing-critical reward solenoids — they must move to *real* GPIO, and
BCM0/1/13 are real GPIO, so this works with **no I2C expander anywhere in the design**.

**Why this beats USB for your specific requirement:** as I2S master the Pi generates BCK and
LRCK from its own oscillator. The audio sample clock and the pigpio tick are then the same
crystal — there is no second clock to synchronise. That is precisely the property you asked
for, and it is only available over I2S, never over USB.

### 3.2 If you also want audio/analog **input**

Add BCM20 (I2S DIN) → 4 pins, and you are one short. Then one latency-tolerant output (LED3 or
an odor valve — **never** a reward valve) moves to an I2C expander (§4.3).

### 3.3 If you go USB: reconcile the clocks with a sync channel, not a wire

You cannot slave a USB interface's clock to a Pi — the Pi has no word-clock output, and no
class-compliant interface will accept one from a GPIO. **Invert the problem, which is standard
practice in electrophysiology** ([Springer, stimulus-latency methods](https://link.springer.com/article/10.3758/s13428-015-0608-x)):

- Dedicate **one output channel of the sound card as a sync/click track**.
- Every stimulus buffer carries a square onset marker on that channel, **sample-aligned** with
  the acoustic waveform on the other channels — so the marker inherits the card's own clock
  exactly, whatever it is doing.
- Feed that channel through a comparator into a spare Pi **GPIO input**, and let pigpio's
  DMA sampler timestamp its edge as `ts_source="hardware"`, on the one counter.

You then know the true acoustic onset per trial to microseconds, **and** you get a running
measurement of the card's drift against the pigpio tick for free. This also turns §2.4 from an
unknown into a logged number — do it even on the I2S route, as validation.

Cost: one GPIO input for the sync return (and note the comparator; a raw line-level audio
signal must not go to a 3.3 V GPIO directly).

---

## 4. Analog out (opto intensity) and analog in

### 4.1 Option A — hardware PWM + RC filter (cheapest, on the one clock)

**[vendor]** Pi 4B has **two** hardware PWM channels, routable to BCM12/BCM18 (PWM0) and
BCM13/BCM19 (PWM1) ([pi4j](https://www.pi4j.com/blog/2024/20240423_pwm_rpi5/)). pigpio's
`hardware_PWM()` drives them from DMA with no CPU involvement, so the carrier is jitter-free.

- BCM12 is TTL1, BCM13 is OG_TRIGGER (freed in §6), BCM18/19 are wanted for I2S.
- A 2nd-order RC at a ~100 kHz carrier gives a clean DC level with sub-ms settling.
- **Good for**: slow intensity setpoints and ramps for LED drivers. **Bad for**: modulation
  above ~1 kHz, and it is only ~8–10 effective bits.
- Conflict: you cannot have both PWM1 on BCM13 *and* I2S LRCK on BCM19 — they are the same
  PWM channel, but different pins, so this is fine (route PWM1 → BCM13, leave BCM19 to I2S).

### 4.2 Option B — a DC-coupled class-compliant USB interface (best signal, zero GPIO)

**[vendor]** Expert Sleepers **ES-8** (4-in/8-out) and **ES-9** (16-in/16-out) are USB 2.0
class-compliant interfaces with **DC-coupled inputs and outputs**, explicitly built to emit and
capture control voltages as well as audio ([expert-sleepers.co.uk/es8](https://www.expert-sleepers.co.uk/es8.html),
[es9](https://www.expert-sleepers.co.uk/es9.html)).

This is the single most capable answer to your combined ask: **one USB device gives you
speaker audio + waveform-accurate analog out for LED intensity + analog in, at 48–96 kHz,
consuming zero GPIO pins.** Class-compliant means the Linux `snd-usb-audio` driver handles it
with no vendor driver.

Caveats to check before buying:
- Eurorack module form factor; needs a Eurorack ±12 V PSU (fits your "everything in a box" plan
  but it is not a desktop unit).
- Output range is ±10 V modular-level — you need a scaler/attenuator into your LED driver's
  0–5 V analog input.
- Vendor does not publish Linux/Pi support; class compliance strongly implies it works, but
  **verify on the bench before committing.**
- Clock: independent. Use the §3.3 sync-channel method — which is nearly free here, since a
  DC-coupled output *is* already a perfect TTL source.

**[reported]** More generally, most audio interfaces are AC-coupled and cannot hold a DC level;
"DC-coupled" is a specific, advertised feature ([RME](https://rme-audio.de/dc-coupled.html),
[MOTU technote](https://motu.com/techsupport/technotes/testing-analog-outputs-for-control-voltage-compatibility)).
A PCM5102A module's output is AC-coupled — **an I2S audio DAC cannot drive a DC intensity
level.** If you take the I2S route for sound, you still need §4.1 or §4.3 for analog out.

### 4.3 Option C — dedicated I2C converters

| Part | Function | Bus | Speed | Note |
|---|---|---|---|---|
| MCP4728 | 4-ch 12-bit DAC | I2C | ~100–200 µs/update | Cheapest true analog out |
| ADS1115 | 4-ch 16-bit ADC | I2C | **860 SPS max** | Too slow for anything fast |
| MCP3008 | 8-ch 10-bit ADC | SPI | ~50 kSPS on a Pi | **SPI0 unavailable** (§1.2) |
| MCP23017 | 16 GPIO expander | I2C | **~80–120 µs/write** at 400 kHz | Only for LEDs / odor valves |

**[datasheet/reported]** The MCP23017 numbers above are the realistic per-write cost at 400 kHz
I2C. Use it **only** for latency-tolerant outputs. Never put a reward valve, TTL, or anything
that gets a `ts_source="hardware"` timestamp behind it — an I2C expander produces no edge for
pigpio to DMA-sample, so those events silently degrade to software timestamps.

### 4.4 On using the MPR121 as a GPIO expander — don't

**[datasheet]** ELE4–ELE11 (8 pins) on the MPR121 can be reconfigured as GPIO/LED drivers when
not used as electrodes ([NXP AN3894](https://www.nxp.com/docs/en/application-note/AN3894.pdf)).
Technically yes, you can gain 8 pins per chip.

Reasons not to:
- You would be sacrificing lick electrodes to get pins — you have 4 detectors configured
  (`num_detectors: 4`) on a 12-electrode part, so the spare capacity is future licker channels.
- Same I2C latency class as an MCP23017 but with a worse library story, and it shares the bus
  with the motor HAT and the second MPR121.
- **Critically**, `i2c.py` deliberately manipulates the ECR register to keep the level-held
  TOUCH_INT line honest **[verified in code]** (`_write_register_byte(0x5E, 0x00)` sequences,
  with comments explaining that a missed falling edge is unrecoverable without an external
  register read). Adding GPIO writes into that same register space is asking for exactly the
  latched-IRQ failure the code was hardened against.

If you need an expander, use a **dedicated MCP23017** — it has two configurable interrupt pins
and does not share state with your lick detection.

---

## 5. RFID for mouse position tracking

**[reported]** The lab standard is **ISO 11784/11785 FDX-B at 134.2 kHz** — the same glass
transponders used by IntelliCage, MoPSS and PyMouseTracks
([eNeuro/PyMouseTracks](https://www.eneuro.org/content/10/5/ENEURO.0127-22.2023),
[MoPSS](https://pubmed.ncbi.nlm.nih.gov/34346041/)). Readers are modules with UART / RS232 /
USB output; a per-antenna reader sits under each zone of the cage.

### GPIO cost: **zero, if you use USB**

PyMouseTracks' published architecture is exactly this: a Raspberry Pi with a **powered USB hub
relaying the RFID readers**. Given that BCM14/15 (the header UART) are already TOUCH_INT and
AIR_PUF, USB is not merely convenient — it is the only option without freeing pins.

### Two warnings that matter for *your* rig specifically

1. **LF RFID excitation vs. MPR121 lick electrodes.** A 134.2 kHz reader antenna is a
   deliberately strong oscillating field, and MPR121 capacitive electrodes are exactly the kind
   of high-impedance node that couples it in. Expect baseline drift or false touches.
   Mitigations, in order of preference: physical separation and grounded shielding between the
   antenna and the electrode leads; twisted/shielded electrode wiring; **duty-cycle the reader**
   so it never excites while a lick window is open; or move to HF 13.56 MHz (as
   [eeeHive](https://www.biorxiv.org/content/10.64898/2026.04.30.720993v1.full.pdf) did), whose
   near-field is far less troublesome for LF-band capacitive sensing.
   **Bench-test this before designing the box around it.**
2. **Timestamping.** A USB-serial reader gives you an arrival time in userspace, not a pigpio
   tick edge. For zone-entry events (100 ms-scale) that is fine; do not expect it to
   participate in the one-counter guarantee. Log it as software-timestamped and say so.

---

## 6. OptoBlueBerry: what the Pi can and cannot take over

**[vendor]** From the [BlueHub documentation](https://www.optoblueberry.org/docs/bluehub-documentation):
the BlueHub is an **Arduino UNO R4** control unit with BLE, **four BNC trigger inputs**, an OLED
+ rotary encoder GUI, and **three docking stations — two charge-only, one that charges and
uploads the base program to the BlueBerry**.

### 6.1 What Pi-native BLE replaces

The **control unit** only. Pi 4B's CYW43455 is BT 5.0 with BLE and works as a BLE central under
BlueZ; `bleak` talks to the BlueBerry's RN4871 fine. Replacing the hub frees **OG_TRIGGER
(BCM13, board 33)** — which is the third pin the I2S DAC needs (§3.1). That is a real,
countable win.

**Two things the rig settled (§11.3).** First, Bluetooth is **soft-blocked and DOWN** on
RecordingBox, so none of this works until someone unblocks it — and on a rig wired to
Ethernet, blocking both radios is often deliberate RF hygiene, so that is a decision to make,
not a command to run. Second, `pinctrl` confirms the controller sits on the **internal** UART
(GPIO30–33 = CTS0/RTS0/TXD0/RXD0 in alt3), which are not header pins: **enabling Bluetooth
costs zero GPIO.**

### 6.2 What it does **not** replace — answer to your open question

**Yes, the rig needs something extra.** Charging and the ATtiny85 base-program upload happen at
the BlueHub's docking stations. A Pi speaking BLE cannot charge a wearable or flash its MCU.
Plan for either:
- keeping one BlueHub on the bench purely as a charger/programmer (simplest), or
- a bare charging cradle in the rig box + a separate programming jig.

Either way, budget panel space and a power feed for a **charging dock**, and keep the
programming path (USB-serial to the RN4871 config, Arduino-as-ISP for the ATtiny85) accessible.

### 6.3 The timing cost nobody mentions

**[vendor/reported]** A BLE write lands on a connection event. The minimum connection interval
in the spec is **7.5 ms**, and BlueZ's initial values come from
`/sys/kernel/debug/bluetooth/hci0/conn_{min,max}_interval` — but the peripheral can request a
change ([Punch Through](https://punchthrough.com/ble-connection-parameters-guide/)).

So **stimulation onset over BLE carries ~7.5–30 ms of jitter**. The pulse *train* is fine — the
BlueBerry's own MCU generates it — but the onset is not millisecond-locked to behaviour. The
BlueHub's BNC inputs exist precisely to avoid this.

Decision rule:
- Onset tolerance ≳ 50 ms (e.g. reward-contingent stimulation blocks) → Pi-native BLE is fine.
- Onset must be ms-locked to a lick/poke → keep a wired trigger path, and use the Pi for
  *configuration* over BLE and the BNC/GPIO line for the *trigger*. In that case OG_TRIGGER is
  **not** free, and the I2S plan needs its third pin from an expander instead.

**This is the one architectural decision that changes the pin budget. Settle it first.**

### 6.4 Concurrency

**[reported]** Practical simultaneous BLE connections on a Pi 4 are in the 7–10 range, limited
by the CYW43455 and RAM. `bleak` on a Pi is **unreliable across multiple processes** — multi-
process competition causes immediate connection aborts
([bleak#1858](https://github.com/hbldh/bleak/issues/1858)). Run **one** connection-manager
process owning all devices, exactly as the `optoblueberry` skill's scaffold does.
Also: onboard BT shares the antenna with 2.4 GHz WiFi — put the rigs on Ethernet or 5 GHz.

---

## 7. Pi 4B vs Pi 5

### 7.1 What Pi 5 costs you

- **pigpio does not work on Pi 5, at all.** GPIO moved to the RP1 southbridge behind PCIe; the
  DMA controller is on the RP1 die and is not reachable through the legacy memory-mapped
  registers pigpio uses ([raspberry.tips](https://raspberry.tips/en/raspberrypi-tutorials/raspberry-pi-5-gpio-rpigpio-not-working-alternatives)).
  pigpio is also unmaintained (last release 2021) and gone from the Bookworm/Trixie apt repos.
- **[verified in code]** The entire MICS timing model is built on the pigpio tick —
  `Event_Dispatcher` documents `ts_source` `"hardware"`/`"software"` as *both* coming from the
  one counter, and `utils.clock.now_from_tick()` is the mapping. Commit `43f7b7b`
  ("ONE COUNTER — every logged timestamp comes off the pigpio tick") is the spine of the event
  log. Moving to Pi 5 means rebuilding that on `lgpio`/`libgpiod`.
- **[reported]** RP1 GPIO access traverses PCIe, adding latency variance to userspace toggles.
- Pi 5 has **no 3.5 mm jack at all** — irrelevant, since you are leaving it anyway.

### 7.2 What Pi 5 buys you

- **Four hardware PWM channels** instead of two (GPIO12/13/18/19) — directly relevant to §4.1.
- **[reported]** `libgpiod` edge events are timestamped **in the kernel IRQ handler at
  nanosecond resolution**. Arguably a *better* clock than pigpio's tick, which is a 32-bit
  microsecond counter that wraps roughly every 72 minutes. The trade: pigpio DMA-samples at
  1 MHz and therefore knows *when the edge happened* even if it tells you a millisecond later;
  an interrupt only tells you *when your handler was woken*. For lick/poke edges this is a real
  regression in worst-case accuracy.
- PCIe → NVMe boot. **SD-card I/O stalls are a genuine source of audio-thread jitter**; this is
  a concrete win for your actual problem.
- Faster CPU (less scheduling jitter), separate USB3 host bandwidth, better thermals, real RTC.
- I2S is still on GPIO18–21, so the §3.1 plan ports unchanged.

### 7.3 Verdict

**Do not move to Pi 5 for this project.** The audio and analog work is entirely independent of
the SoC, and the pigpio→lgpio migration is a separate, risky project touching every timestamp
in the system. Do the rig redesign on 4B.

But **design the carrier board so it does not foreclose Pi 5**: stay on the standard 40-pin
header, avoid anything that depends on BCM2711-specific peripherals, and keep the
`utils.clock` abstraction as the single place a future migration has to touch. The recent
one-counter refactor already put that seam in the right place.

---

## 8. Recommended configuration

Assuming §6.3 resolves as "BLE onset jitter is acceptable" (verify first):

| Function | Implementation | GPIO cost |
|---|---|---|
| Sound | PCM5102A I2S DAC module, `dtoverlay=hifiberry-dac` | 3 (BCM18/19/21) |
| Freed for it | LED3 → BCM0, VALVE1 → BCM1, VALVE3 → BCM13 | net 0 |
| Sound sync | one DAC channel → comparator → spare GPIO input | needs 1 more — see note |
| Analog out (opto intensity) | pigpio `hardware_PWM` on BCM12 or BCM13 + 2nd-order RC | shares a freed pin |
| Analog in | ADS1115 on I2C1 if slow (≤860 SPS) is enough | 0 |
| OptoBlueBerry | Pi-native BLE (`bleak`, one manager process) + separate charging/programming dock | 0 (frees BCM13) |
| RFID | FDX-B readers → powered USB hub | 0 |

**Note on the sync input:** the budget is exactly balanced, so the sync return needs a 4th pin.
Take it from an odor valve moved to an MCP23017 (odor onsets are ms-tolerant; reward valves are
not). Alternatively skip the permanent sync line and use it as a **bench validation fixture
only** — wire it during characterisation, measure the distribution, then remove it.

**If instead you want analog in/out done properly**, the ES-8/ES-9 route collapses sound +
analog out + analog in into one zero-GPIO USB device and leaves the whole header untouched.
It costs more money and gives up the shared-crystal property, which the §3.3 sync channel then
has to buy back. That is the cleaner engineering answer if the budget allows — and it is the
only option here that gives you a *fast, waveform-accurate* analog output.

---

## 9. Enclosure requirements

- **BNC panel for GPIO.** Pi GPIO is 3.3 V CMOS and not 50 Ω. Buffer every output, and put
  series resistance + ESD clamps on every input. BNC shells tie every connected instrument's
  shield to Pi ground — with Open Ephys or a stimulator in the loop this makes ground loops;
  **opto-isolate the TTL in/out** at the panel.
- **Separate the solenoid supply from the analog/audio supply.** Valve switching sags a shared
  5 V rail; that lands as an audible click on the DAC and as noise on any analog output, and it
  is a plausible contributor to the noise you already hear. Separate supplies, star ground,
  flyback diodes at each solenoid.
- **Keep the RFID antennas away from the MPR121 electrode leads** (§5).
- **SD card access.** The Pi 4B card sits on the underside board edge and is a **friction fit
  with no eject spring** — leave finger clearance and align a slot in the enclosure wall with
  the card edge. Do **not** use an SD extender ribbon: they are a known source of corruption at
  speed. Mount the Pi so nothing sits over that edge.
  Consider USB/NVMe boot instead, and leave the SD purely for OS installs.
- **Audio and analog panel access**: keep the DAC module's analog out and the LED-driver control
  line on separate panel connectors from the digital BNCs, with their own returns.

---

## 10. Open questions, in the order they should be answered

1. **§6.3 — is BLE onset jitter (7.5–30 ms) acceptable for your stimulation protocols?**
   This determines whether OG_TRIGGER is free, which determines whether the I2S plan needs an
   I2C expander. Everything else follows from it.
2. **Bench-test LF RFID against the MPR121 lick electrodes (§5).** If they interfere badly,
   the RFID choice changes to HF and the mechanical layout changes with it.
3. ~~Confirm the wav asset sample rate~~ — **settled 2026-09-07: no ultrasonic needed.** Set
   `AUDIO_FS = 48000`, convert the assets once, and any ordinary amplifier and speaker will do.
   `prefs.FS = 192000` was an aspiration, not a requirement.
4. **Build the sync-channel fixture (§3.3) on the current rig, before buying anything.**
   It converts "we couldn't get rid of the latency" into a measured distribution, and it will
   almost certainly show that §2.2 alone accounts for most of it.
5. **Verify ES-8/ES-9 enumerate and run on a Pi 4B** before committing to that route.
6. **Decide whether analog in is needed at all**, and at what bandwidth. ≤860 SPS is a €5
   ADS1115; kHz-rate analog in forces the USB-interface route.
7. **Decide whether Bluetooth may be on inside the recording box** (§11.3). It is soft-blocked
   today. This gates §6 entirely and is an RF-hygiene call, not a technical one.
8. **When you adopt any plan that uses BCM0/BCM1, widen `PIGPIOMASK` to `0x0FFFFFFF`
   in the same change** (§1.3, §11.2). Nothing warns you if you forget.

---

---

## 11. Verified on RecordingBox (132.77.73.213), 2026-09-07

Read-only probes against the live rig. Pi 4B Rev 1.5, Debian 13 trixie, kernel
6.18.39+rpt-rpi-v8, `/opt/mics` → `/home/pi/Apps/mics_core` @ `43f7b7b`, 52 °C,
`throttled=0x0`. Two of my earlier claims were wrong and are corrected here.

### 11.1 What the pin snapshots do and do not prove

Two `pinctrl get` captures — one with the pilot idle, one during a `clockSoak` run — are
**identical**: every GPIO 4–25 an input at its power-on pull, only BCM26 and BCM27 outputs.

That is not evidence about the pin map, because **the running task's hardware set contained
only the `Modules` entries** (`dlc_cam1`, `COMPUTE`), which come from the backend. `init_hardware()`
did run — the live `DlcCam1` ingress proves it — but the set has no GPIO, no I2C and no Mixer
members, so nothing ever asked pigpio for an output and nothing opened the audio device.

**Still outstanding:** one `pinctrl get` plus an `hw_params` capture during a task whose
toolkit includes GPIO hardware *and* `AUDIO1`. That is the only measurement that shows the
real pin state and the rate/format/period the device actually runs at.

BCM26/BCM27 as outputs is **soak residue, not a fault** — `clock_soak.py` takes `--out-pin`
and `--in-pin`, and nothing restores pin modes on exit (the known no-fail-safe,
[[project_pigpiod_no_failsafe]]). An earlier draft called BCM27 (IR5) an anomaly; that was
wrong. `pigs mg 26` and `pigs mg 27` both return `1` (OUTPUT), matching `pinctrl`.

One unexplained detail: **GPIO14 (TOUCH_INT) moved `pn` → `pu` between the two captures**,
though a Modules-only set should not touch it. Low priority, still open.

### 11.2 `PIGPIOMASK` has never taken effect — and "fixing the format" would break the rig

`pigpiod.c` parses the flag as a **number**:

```c
case 'x':
   mask = getNum(optarg, &err);
   if (!err) { updateMask = mask; updateMaskSet = 1; }
   else fatal("invalid -x option (%s)", optarg);
```

`getNum` is a strtol-family call with base 0. The shipped value
`1111110000111111111111110000` has no `0x` prefix, so it is read as **decimal** — ≈1.1×10²⁷,
which overflows a 64-bit integer. pigpiod is running, so it did not `fatal()`; it simply took
whatever the overflow produced. This confirms the SAFE-07 hypothesis in `REQUIREMENTS.md` and
matches the user's 2026-09-06 observation that changing the mask had no visible effect.

**Read as bits (MSB = GPIO27) that value means `0x0FC3FFF0`: exclude GPIO0–3 and GPIO18–21.**
In MICS, GPIO18/19/20/21 are **LED3, VALVE1, VALVE2 and VALVE3**. And it was never a MICS
decision — the string is Autopilot's stock default, verbatim from `prefs.py`'s `PIGPIOMASK`
entry and repeated as the example in `pilot.py`'s docstring. It has ridden along, inert, since
the fork.

So the danger is not the broken mask. It is that the mask **looks** like a deliberate bit
pattern: the day someone tidies it to `-x 0x0FC3FFF0`, LED3 and three reward valves stop
responding, silently, because pigpio just declines the mode changes.

**Fixed in `mics_core`:** `PIGPIOMASK` is now `"0x0FFFFFFC"` (BCM2–27) in
`pilot/prefs.template.json`, in `prefs.py`'s default so a freshly generated prefs cannot
regenerate the landmine, and in `pilot.py`'s docstring example. `tests/test_pigpio_mask.py`
pins the invariants: the mask parses as a number, and every BCM pin the `HARDWARE` dict
declares is permitted by it. All four assertions failed against the old value.

**Deploy note:** `prefs.json` is untracked on the rig, so a `git pull` does **not** update it.
The live `/opt/mics/pilot/prefs.json` has to be edited by hand, and the pilot restarted for
`external.start_pigpiod()` to pass the new flag.

### 11.3 Bluetooth is off, and it is not on the header

`rfkill` reports `hci0` **soft-blocked**, `hciconfig` reports **DOWN**; WiFi likewise. Pi-native
BLE to the BlueBerry cannot work until that changes — and unblocking puts a 2.4 GHz
transmitter inside the recording box, which is a decision worth taking deliberately.

`pinctrl` also confirms the controller is on the internal PL011 (GPIO30–33 in alt3), so
Bluetooth consumes **no header pin**. That closes an open question from §6.

### 11.4 Audio, confirmed

`card 0: Headphones [bcm2835 Headphones]` with 8 subdevices (the driver's own software
mixing — so even `hw:0,0` is not truly exclusive), plus two HDMI cards from `vc4-kms-v3d`.
`dtparam=audio=on`. **No I2S card, and `snd_soc_bcm2835_i2s` is not loaded** — the peripheral
is not instantiated at all. Every `hw_params` read `closed`, as expected with no Mixer object
in the running set.

**Already done, and worth knowing:** the pilot and `pigpiod` both run `SCHED_FIFO` at
`rtprio 10` — one of §2.5's four fixes is in place. They are at *equal* RT priority, so
pigpio's DMA work and the audio callback compete on the same footing; a plausible jitter
contributor once the decode is out of the trigger path.

### 11.5 Two config items to tidy

- **`dtoverlay=nospi10` is dead config here.** The overlay is real and stock
  (`/boot/firmware/overlays/nospi10.dtbo`), but its own help says *"Disable the spi10 device on
  Pi5."* There is no `spi10` on a BCM2711, so it does nothing. An earlier draft called it
  non-standard; that was wrong. Delete it so nobody else loses time on it.
- **`enable_uart=0`, but `cmdline.txt` still carries `console=serial0,115200`.** Inert today.
  But TOUCH_INT is on BCM14 = UART0 TXD, so if anyone ever sets `enable_uart=1` — raspi-config's
  "serial console" toggle does exactly that — the kernel claims BCM14 and the lick-detector IRQ
  line dies with no error. Strip the `console=serial0` token.

### 11.6 A live data-loss bug, unrelated to this plan but found on the way

Repeating roughly once a minute since at least 2026-09-02:

```
DlcCam1.dlc_cam1 → external_hardware_ingress.py:104  _trackers[name].set(value)
                 → logging_utils.py:42               coerce_for_event(_raw)
                 → log_value.py:77                   return int(raw), raw, None
ValueError: cannot convert float NaN to integer
```

DLC-Live emits NaN for every frame with no confident detection, and `coerce_for_event`'s float
branch does a bare `int(raw)`. **The severity is in the control flow:** line 104 sits inside a
`for kind, name, value, … in results:` loop that is itself inside the `try`, so one NaN aborts
the whole loop — every remaining signal *and event* from that frame is discarded, not just the
NaN one.

The function's own docstring names the fix: *"`value_str` carries anything that is not a number
at all."* NaN is exactly that. Two branches need the guard — the float branch, and the string
branch, where `float("nan")` parses fine and then `int()` raises identically. `log_value.py`
is **not** a DB hardware lib, so unlike `mixer.py` this cannot ship through the backend; it
needs a git deploy.

---

---

## 12. Audio and analog are different subsystems. They share nothing.

This keeps getting conflated, so, plainly: **audio is a fast AC waveform on three dedicated
pins. Analog is a slow DC level on the I2C bus you already have.** Different chips, different
buses, different wiring, different clocks. Adding one does not get you the other.

| | **AUDIO** | **ANALOG** |
|---|---|---|
| Job | make sound | make or read a voltage |
| Chip | PCM5102A | MCP4728 (out) · ADS1115 (in) |
| Bus | **I2S** — 3 dedicated GPIO | **I2C** — the two wires already there |
| Header cost | **3 pins** | **0 pins** |
| Coupling | **AC** — physically cannot hold a DC level | **DC** — that is the entire point |
| Rate | 48 000 samples/s | 860–5 000 samples/s |
| Clock | the Pi's own crystal (Pi is I2S master) | none; sampled when the CPU gets to it |
| Timestamp | µs, via the sync channel → GPIO edge → pigpio tick | software, ~1 ms jitter |
| Config | `dtoverlay=hifiberry-dac` | none — userspace I2C |

**The consequence people miss:** an I2S audio DAC is AC-coupled, so it *cannot* drive a light
intensity setpoint, no matter how fast it samples. Audio hardware only passes change. (It can
drive the *sync pulse*, because an edge is change — which is why that trick works.)

### 12.1 How each part physically attaches

None of these is a HAT, deliberately — see §12.3.

| Part | Attaches by | Wires | Notes |
|---|---|---|---|
| **PCM5102A** — audio DAC | **soldered to the carrier board**, or a header socket | 5: 3V3, GND, BCK→BCM18, LRCK→BCM19, DIN→BCM21 | No I2C, no address. Analog audio leaves on the module's own L/R pads or 3.5 mm jack. |
| **MCP4728** — analog voltage out | **taps the existing I2C bus** | 4: 3V3, GND, SDA→BCM2, SCL→BCM3 | 4 × 12-bit DC outputs. Needs a buffer op-amp to drive a real load. |
| **ADS1115** — analog voltage in | taps the same I2C bus | 4: 3V3, GND, SDA, SCL | 4 single-ended or 2 differential. Protect every input that leaves the box. |
| **MCP23017** — 16 slow on/off pins | taps the same I2C bus | 4 + 3 address pins | Only needed if you run short of header pins. Its outputs drive the *inputs* of the solenoid driver board, never a solenoid. |

**PCM5102A gotchas**, both of which cost people an afternoon:
- **XSMT (soft-mute) must be pulled high** or the module stays silent, with no error anywhere.
- **SCK must be tied to GND** so the module uses its internal PLL; the Pi supplies no master clock.

### 12.2 One I2C bus, one address space — and there is a collision

Everything above shares BCM2/BCM3 with what is already on the bus:

| Address | Device | Status |
|---|---|---|
| 0x5A, 0x5B | MPR121 × 2 (lick detection) | in use |
| 0x60 | Motor Shield HAT (PCA9685) | in use |
| 0x20 | MCP23017 | free |
| 0x48 | ADS1115 | free |
| **0x60** | **MCP4728 — default address** | **COLLIDES with the motor HAT** |

**Resolve it before ordering.** The motor HAT has solder jumpers A0–A4 covering 0x60–0x7F, so
moving it one address is a single blob of solder. Reprogramming an MCP4728 is harder — it needs
a timed sequence on the LDAC pin. Move the HAT.

### 12.3 Why nothing here is a HAT

A HAT covers the whole 40-pin header, stacks mechanically, and carries an ID EEPROM on
**BCM0/BCM1** — the two spare pins the DAC plan depends on (§1.3). A HAT would claim them and
block the rest of the header. Every part above is a small breakout wired to a carrier board.

**Check before counting on BCM0/BCM1:** run `ls /proc/device-tree/hat/`. If that directory is
absent or empty, no HAT ID EEPROM was detected at boot and the two pins are genuinely free.

### 12.4 The treadmill is a voltage source — settled 2026-09-07

It lands on a **two-pin socket** and **transfers voltage**. Two conclusions follow:

1. **It needs an ADC** — an ADS1115 on the existing I2C bus, **zero header pins.**
2. **It cannot report direction.** A quadrature encoder needs four to six conductors; two
   carries speed only. If forward/backward ever matters scientifically, that is a different
   sensor, not a different chip.

Rate is not a concern: 860 SPS on a single channel is one sample every **1.16 ms**, against
locomotion that moves on a 10–100 ms timescale. Across all four channels it divides to roughly
200 SPS each, still ample. `ADS1015` trades to 12-bit for 3300 SPS if you ever need it.

**What does need care is the input, and it is mandatory, not optional.** A tachogenerator's
open-circuit voltage rises with speed and can swing **negative** if the belt reverses, while the
ADS1115 tolerates at most ±6.144 V and never more than VDD+0.3 V absolute.

> **Measure it first.** Spin the treadmill by hand at the fastest speed an animal will produce
> and read the open-circuit voltage across the two pins. Size a divider from *that* number, add
> a clamp, and feed it as a **differential** pair so a reversal reads as a negative value rather
> than damaging the part.

### 12.5 What this build actually costs

Audio out, light-intensity analog out, treadmill analog in. No ultrasonic, so `AUDIO_FS = 48000`
and any ordinary amplifier and speaker will do.

| Item | Header pins | ~Cost |
|---|---|---|
| PCM5102A — audio out, Pi-clocked, 48 kHz | **3** | €5 |
| MCP4728 — light intensity out | 0 | €5 |
| ADS1115 — treadmill in | 0 | €5 |
| Divider + clamp on the treadmill input | 0 | €1 |
| **Total** | **3** | **under €20** |

**It fits exactly.** The three spare pins — BCM0, BCM1, and BCM13 once OptoBlueBerry moves to
BLE — cover the DAC and nothing else is needed. **No expander, no SPI bus, no valve migration.**
Plan B's five-valve move stays worthwhile for kHz-rate analog in and for headroom, but this
build does not require it.

Two things this build still does not buy, both of which cost one more pin each: the **audio sync
return** (§3.3), without which acoustic onset stays unmeasured, and any **hard-timed** treadmill
timestamp — an ADC reading is software-stamped with ~1 ms of jitter, unlike a GPIO edge.

---

---

## 13. I2C bus design for the new rig

I2C is the one subsystem where a decision made casually now is expensive later, because the
address space and the pull-up network are global properties of the bus — you cannot fix them
one board at a time.

**Verified on RecordingBox 2026-09-07:** `i2cdetect -y 1` returns exactly one device, `0x5a`.
One MPR121, nothing else. `i2cdetect -l` confirms only `i2c-1` is usable (`i2c-20`/`i2c-21`
are the HDMI DDC buses). What look like "two I2C buses" on the rig are **two sockets
daisy-chained on the one bus** — same SDA/SCL pair, same address space, same bandwidth.

Note also that `prefs.json` declares `MOTOR_SHIELD_HAT`, `DOOR1`, `DOOR2` and
`MOTORIZED_REWARD` at `0x60`, and **nothing answers there**. Per
[[project_door_test_new_stack]] a missing motor HAT fails *silently*, so a task definition
pulling in those modules on this box would produce no error and no motion. Decide whether the
shield belongs here or whether those entries are stale copy from the door-test rig.

### 13.1 Reserve the whole address space on paper, once

| Range | Device | Max on one bus |
|---|---|---|
| `0x20–0x27` | **MCP23017** — 16 extra on/off pins over I2C, for slow switches and LEDs | 8 |
| `0x48–0x4B` | **ADS1115** — analog voltage reader (treadmill, sensors) | 4 |
| `0x5A–0x5D` | **MPR121** — 12-channel capacitive touch sensor (the lick detector) | 4 |
| `0x60–0x67` | **MCP4728** — analog voltage output (light intensity) | 8 |
| `0x60–0x7F` | **PCA9685** — 16-channel PWM generator, as fitted on the motor shield | overlaps ↑ |

**`0x60` is the only contested address.** Settle it once and write it down: **the DAC keeps
`0x60`; any PCA9685 starts at `0x61`** (one solder jumper on the shield). A PCA9685 also
answers on its all-call address `0x70` — that is the same chip appearing twice in a scan, not
a second device.

### 13.2 The pin cost scales with IRQ lines, not with chips

An MPR121 costs nothing on the bus — it is address-selected — but **each one needs its own
GPIO for its IRQ**:

| Lick chips | Electrodes | Header pins |
|---|---|---|
| 1 | 12 | 1 |
| 2 | 24 | **2** |

**Do not wire-OR two IRQs onto one pin to save it.** `i2c.py` already fights a level-held
latch on a single chip (§ the ECR hygiene invariant in `tests/test_mpr121_irq_hygiene.py`);
two chips sharing a line makes a missed deassertion much harder to reason about and to
recover from.

**Budget impact:** the generic hard-timed pin count drops from 20 to 19 if the new rig carries
two lick chips. Twelve electrodes is already a lot of lickers — decide before laying out the
board, not after.

### 13.3 Pull-ups stack, and that is what breaks long buses

The Pi has **fixed 1.8 kΩ pull-ups** on BCM2/BCM3. Nearly every breakout board adds its own
10 kΩ. Five boards in parallel with the Pi's gives roughly 1.5 kΩ, and at 3.3 V that exceeds
the 3 mA sink limit: the bus stops reaching a valid logic low and you get intermittent errors
that look like anything but a resistor problem.

> **Rule: de-populate or cut the pull-ups on every board except one.** On a daisy-chain, keep
> them on the board at the far end.

### 13.4 Socket design

Make every I2C socket **identical and interchangeable**: SDA, SCL, 3V3, GND, plus a dedicated
IRQ line back to its own GPIO. Any socket then takes an MPR121 or an analog board with no
rework. Reserve IRQ pins for two sockets; the rest can be IRQ-less, since DACs, ADCs and
expanders do not need one.

Keep the whole chain under about 1 m at 400 kHz — the spec limit is 400 pF of bus capacitance
and ribbon cable consumes it quickly. Twisted pair with ground return. Beyond that, add an I2C
buffer such as a TCA9517.

### 13.5 One bus, at 400 kHz

**One.** Enabling `i2c3`–`i2c6` costs 2 GPIO each (§1.2) and the budget has none to give. The
argument for a second bus is isolating lick reads from bulk ADC traffic — but MPR121 reads are
IRQ-driven and rare, and an ADS1115 running flat out at 400 kHz uses only about 9% of the bus.
Not worth two pins.

Set the speed explicitly; the default is 100 kHz:

```
dtparam=i2c_arm_baudrate=400000
```

At 100 kHz an ADS1115 read costs ~400 µs, so continuous sampling at 860 SPS burns **~34% of
the bus**. At 400 kHz it is ~9%. Both the MPR121 and the ADS1115 are rated for 400 kHz and the
PCA9685 reaches 1 MHz, so the electrical limit is the wiring, not the parts — test once after
changing it, because a daisy-chain of sockets is exactly the geometry that makes 400 kHz
marginal.

**What this does not fix:** lick *timing* is unaffected by bus speed. The TOUCH_INT edge is
DMA-timestamped by pigpio before any I2C happens; the bus read only reports *which* electrode.
Faster I2C buys quicker closed-loop response and room for the ADC, not better lick timestamps.

---

---

## 14. Parts list, and what actually has to be built

### 14.1 What to buy — one of each per rig, not one per channel

These are ~2 × 3 cm breakout boards, not "cards" in the sound-card sense.

| Board | One gives you | Enough for | ~Cost |
|---|---|---|---|
| **PCM5102A** — *audio DAC: turns digital sound into a real analog audio signal* | 1 stereo audio out | the whole rig | €5 |
| **MCP4728** — *4-channel analog voltage output: holds a steady DC level, e.g. LED brightness* | **4** independent analog outs | 4 light channels | €5 |
| **ADS1115** — *4-channel analog voltage reader: measures a DC voltage, e.g. the treadmill* | 4 single-ended *or* 2 differential ins | 4 sensors, or 2 like the treadmill | €5 |
| Passives — divider, clamp, op-amp | input and output conditioning | — | €3 |
| Connectors, cable, panel BNCs | — | — | €10 |

Buy a second of anything only when you exceed those channel counts. The bus holds up to 8
MCP4728s and 4 ADS1115s (§13.1).

### 14.2 What plugs in, what gets soldered, what gets built

**Plugs in — near-zero work.** The MCP4728 and ADS1115 go into the free I2C socket. If the
socket and the breakout share a 4-pin JST/Qwiic connector it is a cable and nothing else;
otherwise a 4-wire pigtail. The one fiddly part is **de-populating the onboard pull-ups on all
but one board** (§13.3) — cutting a jumper trace or lifting two resistors.

**Gets soldered — the PCM5102A only.** Five wires to the header (3V3, GND, BCK→pin 12,
LRCK→pin 35, DIN→pin 40), plus the two config connections that fail silently if skipped:
**XSMT pulled high** and **SCK tied to GND** (§12.1). Output pads go to the amplifier.

**Gets built — the analog conditioning.** This is the real work:

| Path | What is needed |
|---|---|
| Analog out → LED driver | Possibly nothing — see §14.3 |
| Treadmill → ADS1115 | Divider + clamp (Schottky pair or TVS) + series resistor, into a differential input |
| Light onset gate | GPIO → buffer / opto-isolator → the driver's TTL input |

Roughly half a day of veroboard, or one small custom PCB.

### 14.3 Two checks that can each remove a build step

**Check the LED driver's analog input spec before designing anything.** The MCP4728 has a
rail-to-rail output buffer and drives about 1 kΩ directly. If the driver accepts **0–3.3 V into
a high-impedance input, no output conditioning is needed at all** — wire it straight. If it
wants 0–5 V you are using two-thirds of the range, losing resolution and peak power; a ×1.5
op-amp stage recovers it.

**Do not solve that by powering the DAC from 5 V.** The MCP4728's I2C logic-high threshold is
0.7 × VDD = 3.5 V at a 5 V supply, and the Pi only drives 3.3 V. It would work intermittently
and be miserable to diagnose. Run the DAC at 3.3 V and add the gain stage.

### 14.4 Build or buy

| | Build | Buy |
|---|---|---|
| Parts | 3 breakouts + passives | Expert Sleepers ES-8 |
| Cost | **~€20** | **~€500** |
| Header pins | 3 (audio only) | **0** |
| Bench time | ~half a day of conditioning circuitry | one USB cable |
| Audio clock | **the Pi's own crystal** | independent — needs the sync channel (§3.3) |
| Conditioning | you build it | already inside, DC-coupled, 24-bit / 96 kHz |
| Risk | known parts, proven patterns in `i2c.py` | Linux support implied by class compliance, **unverified on a Pi** |

The ES-8 costs 25× more and gives up the shared-crystal audio clock, which is the one property
USB can never provide. But it is genuinely one cable, and everything that would otherwise be
breadboarded is inside it. **If bench time is scarcer than budget, that is the trade.**

### 14.5 Software integration, end to end

`i2c.py` already contains both integration patterns, so nothing here is new ground:

```python
# ~line 600 -- MPR121, via Adafruit Blinka
self.i2c = busio.I2C(board.SCL, board.SDA)
self.mpr121 = adafruit_mpr121.MPR121(self.i2c)

# ~line 208 -- I2C_9DOF, via pigpio's own I2C
self.accel = self.pig.i2c_open(1, self._ADDRESS_ACCELGYRO)
```

**Follow the MPR121 pattern** — Adafruit ships drivers for both the MCP4728 and the ADS1115,
Blinka is already a dependency, and it is the path proven on this rig. Share one `busio.I2C`
object across devices rather than constructing one per Hardware class; Blinka's `try_lock`
semantics get unpleasant otherwise.

```python
import adafruit_mcp4728

class Analog_Out(Hardware):
    """4-channel 12-bit DAC on I2C. Light intensity."""

    def __init__(self, channel=0, **kwargs):
        super(Analog_Out, self).__init__(**kwargs)
        self.i2c = busio.I2C(board.SCL, board.SDA)
        dac = adafruit_mcp4728.MCP4728(self.i2c)
        self.channel = [dac.channel_a, dac.channel_b,
                        dac.channel_c, dac.channel_d][channel]

    @log_action
    def set(self, percent):
        """0-100 -> 0 V to VDD on this channel."""
        self.channel.raw_value = int(4095 * max(0, min(100, percent)) / 100)
        self.hardware_state = HardwareState.OPENED
```

Registered in `HARDWARE.I2C` exactly like the MPR121, and called from an FDA entry action as
`LIGHT1.set(40)`:

```json
"LIGHT1": {
  "group": "ANALOG_OUT", "name": "LIGHT1", "channel": 0, "type": "i2c.Analog_Out"
}
```

**The design pattern that matters.** A DAC write is `ts_source="software"` — stamped when the
I2C write returns, ~150 µs later at 400 kHz. Fine for a level; it is **not** a hardware edge on
the pigpio tick.

> **The DAC sets *how bright*. A GPIO sets *when*.**

Set the intensity during the ITI, then gate the light with a TTL from a real GPIO at stimulus
onset. The GPIO edge is DMA-timestamped on the one counter and the intensity rides along as a
separate logged event. That is exactly why commercial optogenetic drivers have separate
analog-level and TTL-gate inputs.

---

---

## 15. Doors, and other motors

### 15.1 No, they do not need another bus

The Adafruit DC/Stepper Motor HAT is a **PCA9685** (a 16-channel PWM generator) driving
**TB6612FNG** H-bridges (the power stage that actually moves a DC motor). It talks I2C at
`0x60`, on the bus you already have. `prefs.json` drives three motors through it —
`DOOR1` (id 2), `DOOR2` (id 3) and `MOTORIZED_REWARD` (id 1).

**Header cost: zero.** Doors are an address, not a pin.

### 15.2 But the HAT form factor conflicts with the audio plan

Two problems, and the second is decisive:

1. **It covers the 40-pin header.** The audio DAC needs five soldered wires to pins 12, 35 and
   40 plus power; a stacked HAT makes that a pass-through header exercise.
2. **If its ID EEPROM is populated, it claims BCM0/BCM1** — which are exactly the two spare pins
   the audio DAC depends on (§1.3). That would break Plan A outright.

**Check before designing anything around it:** `ls /proc/device-tree/hat/`. Absent or empty
means no EEPROM was detected at boot and the pins are free. This check is still outstanding.

### 15.3 For the new rig: use the chips, not the shield

A motor HAT is not a special device — it is two ordinary chips in a shield-shaped package.
Buy them as breakouts and put them on the carrier board instead:

| Part | What it does | Bus | Address |
|---|---|---|---|
| **PCA9685** | 16-channel PWM generator — makes the speed and direction signals | I2C | **`0x40`** by default on a plain breakout |
| **TB6612FNG** or **DRV8833** | dual H-bridge — the power stage that actually turns a motor | wired from the PCA9685 | none |

Three things this buys you:

- **No HAT.** The header stays accessible and BCM0/BCM1 stay free.
- **`0x40` instead of `0x60`**, so the address clash with the analog-voltage output (§13.1)
  disappears entirely — nothing has to move.
- One PCA9685 drives up to 8 motors through 4 H-bridges, well beyond the 3 in use.

If the doors are **servos** rather than DC motors, the PCA9685 alone is enough — servos take a
PWM pulse directly and need no H-bridge.

### 15.4 Fix the stalling while you are here

[[project_door_test_new_stack]] records two live defects: a missing HAT fails **silently**, and
**motors are left stalled**. Stalling a DC motor against an end stop draws locked-rotor current
indefinitely — it cooks the motor and the driver, and it is the kind of thing that fails months
later.

**Add limit switches.** Two per door, so the motor stops when the door arrives instead of
pushing against the frame. They are not timing-critical, so they belong on an **MCP23017**,
whose interrupt-on-change gives you all 16 inputs for **one** GPIO pin. That is the cheapest
possible fix for a real hardware-damage risk.

The silent-missing-HAT defect is separate and lives in software: instantiating a motor module
should fail loudly when nothing answers at its address.

### 15.5 Scaling: everything fits on one bus, and motors scale by board

**Addresses are nowhere near the limit.** A realistic rig is five devices against a 112-address
space:

| Device | Address range | Max on one bus |
|---|---|---|
| MPR121 — lick detection | `0x5A–0x5D` | 4 |
| PCA9685 — motor PWM | `0x40–0x47` | 8 |
| ADS1115 — analog voltage in | `0x48–0x4B` | 4 |
| MCP4728 — analog voltage out | `0x60–0x67` | 8 |
| MCP23017 — slow on/off pins | `0x20–0x27` | 8 |

**Bandwidth is not the limit either.** At 400 kHz an ADS1115 running flat out at 860 SPS is
~8.6% of the bus; lick reads are IRQ-driven and rare; DAC and motor writes happen only on
change. Total under 15%.

**The real ceiling is physical:** the 400 pF bus-capacitance limit and the stacking pull-ups
(§13.3). Five devices on short leads is nothing; fifteen daisy-chained down a metre of ribbon
is trouble, and the fix is a TCA9517 bus buffer, not a second bus.

**Motors scale by adding boards, not buses or pins.** One PCA9685 has 16 PWM channels and a DC
motor consumes 3 of them (speed plus two direction lines):

| Doors | PCA9685 | TB6612FNG (dual H-bridge) | Header pins |
|---|---|---|---|
| 2 | 1 | 1 | 0 |
| 4 | 1 | 2 | 0 |
| 8 | 2 | 4 | 0 |
| 16 | 4 | 8 | 0 |

**If the doors can be servos the maths changes completely** — a servo takes *one* channel and
no H-bridge, so a single PCA9685 drives **16 doors** for €10. Worth establishing whether the
mechanism genuinely needs a DC motor: it is a 4× difference in board count and 8× in cost.

**The one thing that consumes header pins as you scale is the limit switches.** An MCP23017
gives 16 inputs, so **8 doors per chip**, each chip wanting one GPIO for its interrupt line.
Past 8 doors you may wire-OR two MCP23017 interrupt outputs onto one pin — safe here, unlike
the MPR121 case (§13.2), because the MCP23017's interrupt clears on an ordinary register read
and has none of the ECR latching fragility, and a missed limit-switch edge is recoverable by a
poll.

**Size the motor supply for stall current, not running current.** A DC motor at its end stop
draws several times its running draw, and a sequence that commands several doors at once stalls
them together. TB6612FNG is rated 1.2 A continuous / 3.2 A peak per channel; four doors is
roughly 2 A of headroom on a rail that must stay separate from the logic supply (§9).

### 15.5 Full door subsystem cost

| Item | Header pins | ~Cost |
|---|---|---|
| PCA9685 — PWM generator | 0 | €10 |
| 2 × TB6612FNG — H-bridges | 0 | €8 |
| Limit switches, 2 per door | 0 (via MCP23017) | €5 |
| MCP23017 — if not already fitted | 0 | €3 |
| Motor supply, shared with the solenoid rail | — | — |

**Zero header pins**, or one if the MCP23017 interrupt line is wired — which is worth doing, so
a limit switch reports the instant it closes rather than at the next poll.

---

---

## 16. Timestamping I2C events on the one counter

An I2C transaction cannot be timestamped on the pigpio tick — it is a userspace bus operation
and `@log_action` stamps it `ts_source="software"` when the call returns. But **almost every
I2C chip has a spare pin that can witness the event on a real GPIO**, where pigpio DMA-samples
the edge to microseconds.

> **Inputs are timestamped by their interrupt or ready line. Outputs are timestamped by a GPIO
> that gates them.**

The rig already does this without naming it: the MPR121's IRQ on BCM14 says *when* a lick
happened; the I2C read afterwards says *which* electrode. **Edge = when, bus = what.**

### 16.1 The four witness lines

| Witness pin | Chip pin | What it timestamps |
|---|---|---|
| Lick IRQ *(exists)* | MPR121 `IRQ` | the instant an electrode is touched |
| Door arrival | MCP23017 `INTA` | a limit switch closing — the door physically arriving |
| Treadmill anchor | ADS1115 `ALERT/RDY` | end of an ADC conversion |
| Light change | MCP4728 `LDAC` | the instant all four DAC outputs update |

**Four pins buy hardware timestamps for the entire I2C subsystem.**

### 16.2 Doors: the limit switch *is* the timestamp

The I2C "start motor" command was never the door's arrival time — mechanical travel sits in
between. The limit switch closing is the physical event worth recording.

- I2C command → software timestamp: *when we asked*
- Limit switch edge → **hardware** timestamp: *when it arrived*
- The difference is measured travel time, per trial, for free

It scales to **one pin for any number of doors**: wire-OR every limit switch to a single GPIO
for the edge, then read the MCP23017 to learn which one closed. Exactly the MPR121 pattern.

### 16.3 Treadmill: anchor and interpolate

The ADS1115's `ALERT/RDY` pin can be configured to pulse at the end of each conversion (set the
`Hi_thresh` MSB to 1 and the `Lo_thresh` MSB to 0). Wired to a GPIO, every conversion carries a
hardware timestamp.

At 860 SPS that is 860 callbacks a second — heavy, and unnecessary. **Anchor instead:** run the
ADC continuously at a known rate, take a hardware timestamp every Nth conversion, and
interpolate the samples between anchors. The anchors simultaneously measure the ADC's internal
oscillator drifting against the pigpio tick, so the correction comes free. Identical in spirit
to the audio sync channel (§3.3).

### 16.4 Light intensity: use LDAC

The MCP4728 has an **`LDAC`** input. Write values over I2C whenever convenient, then pulse
`LDAC` from a GPIO — **all four channels update simultaneously, at that instant.** One pin both
*causes* and *timestamps* the voltage change, which is better than gating the light separately.

> This is a reason to specify the **MCP4728 over the MCP4725** even for a single channel: the
> 4725 has no `LDAC`, so its output changes whenever the I2C write lands and can never be
> hardware-timestamped.

The PCA9685 has no equivalent output, so a motor command cannot self-witness — which is exactly
why §16.2 matters.

### 16.5 What this costs, and why it settles the Plan A / Plan B question

Four witness pins on a budget that balances at exactly zero. So:

| Purpose | Pins |
|---|---|
| Shared I2C bus | 2 |
| Audio chip (I2S) | 3 |
| **Timing witness lines** — lick, doors, treadmill, light | **4** |
| Audio sync return | 1 |
| TTL sync out to recording equipment | 1 |
| **Remaining generic** | **17** |
| **Total signal pins** | **28** |

The rig needs 21 generic lines once the OptoBlueBerry trigger retires to BLE. Against 17
available it is **four short** — resolved by moving the five odour valves to the MCP23017, which
leaves **16 needed against 17 available, one spare**, and returns the SPI bus as a bonus.

**So Plan B is no longer the optional upgrade.** If you want hardware timestamps on the doors,
the treadmill and the light, the odour-bank migration is the plan, not a nice-to-have. That
changes what is being asked for approval, and it should be stated plainly in the planning
document.

---

## Sources

- [Raspberry Pi audio documentation](https://www.raspberrypi.com/documentation/accessories/audio.html)
- [Behind The Pin: How The Raspberry Pi Gets Its Audio — Hackaday](https://hackaday.com/2018/07/13/behind-the-pin-how-the-raspberry-pi-gets-its-audio/)
- [I2S/PCM pin restrictions — Raspberry Pi Forums](https://forums.raspberrypi.com//viewtopic.php?p=854606&t=127150)
- [PCM5102A needs no I2C — Raspberry Pi Forums](https://forums.raspberrypi.com/viewtopic.php?t=370450)
- [How to connect a PCM5102 I2S DAC — Himbeer's Blog](https://blog.himbeer.me/2018/12/27/how-to-connect-a-pcm5102-i2s-dac-to-your-raspberry-pi/)
- [Raspberry Pi extra I2C buses — dotnet/iot](https://github.com/dotnet/iot/blob/main/Documentation/raspi-i2c.md)
- [pygame.mixer documentation](https://www.pygame.org/docs/ref/mixer.html)
- [Raspberry Pi and realtime, low-latency audio — linuxaudio wiki](https://wiki.linuxaudio.org/wiki/raspberrypi)
- [Punching it Up: Low-latency notes — McLaren Labs](https://mclarenlabs.com/blog/2019/01/05/punching-it-up-low-latency-notes/)
- [Reducing audio stimulus presentation latencies — Behavior Research Methods](https://link.springer.com/article/10.3758/s13428-015-0608-x)
- [MPR121 GPIO and LED Driver Function — NXP AN3894](https://www.nxp.com/docs/en/application-note/AN3894.pdf)
- [Expert Sleepers ES-8](https://www.expert-sleepers.co.uk/es8.html) · [ES-9](https://www.expert-sleepers.co.uk/es9.html)
- [RME: DC-coupled outputs](https://rme-audio.de/dc-coupled.html) · [MOTU: testing analog outputs for CV](https://motu.com/techsupport/technotes/testing-analog-outputs-for-control-voltage-compatibility)
- [PyMouseTracks — eNeuro](https://www.eneuro.org/content/10/5/ENEURO.0127-22.2023) · [MoPSS — PubMed](https://pubmed.ncbi.nlm.nih.gov/34346041/) · [eeeHive HF RFID — bioRxiv](https://www.biorxiv.org/content/10.64898/2026.04.30.720993v1.full.pdf)
- [OptoBlueBerry BlueHub documentation](https://www.optoblueberry.org/docs/bluehub-documentation)
- [BLE connection parameters guide — Punch Through](https://punchthrough.com/ble-connection-parameters-guide/)
- [bleak #1858: multi-process BLE failures on Raspberry Pi](https://github.com/hbldh/bleak/issues/1858)
- [Pi 5 GPIO alternatives to RPi.GPIO/pigpio — raspberry.tips](https://raspberry.tips/en/raspberrypi-tutorials/raspberry-pi-5-gpio-rpigpio-not-working-alternatives)
- [PWM hardware support on RPi5 — Pi4J](https://www.pi4j.com/blog/2024/20240423_pwm_rpi5/)
- [libgpiod vs pigpio timing precision — Raspberry Pi Forums](https://forums.raspberrypi.com/viewtopic.php?t=383773)
