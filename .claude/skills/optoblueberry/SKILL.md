---
name: optoblueberry
description: >
  OptoBlueBerry wireless optogenetics integration for the MICS/Pi system.
  Use this skill whenever the user mentions BlueBerry, BlueHub, optogenetics, wireless LED stimulation,
  BLE stimulation devices, replacing the Arduino hub with Pi code, or wiring optogenetics into MICS tasks/FDA.
  Also triggers for: "configure stimulation parameters", "BLE not connecting to BLUEBERRY",
  "pulse width / frequency / LED channel setup", "LED current resistor", "bleak BLE scan".
  This skill should fire proactively whenever optogenetics hardware or BlueBerry devices come up in
  the context of the MICS Pi system — even if the user doesn't say "optoblueberry" explicitly.
---

# OptoBlueBerry Skill

## System Architecture

```
MICS Orchestrator (ZMQ events)
        │
        ▼
  pi_blueberry.py  ← THIS IS WHAT WE'RE BUILDING
  (asyncio service on Pi)
        │  BLE (bleak)
        ▼
  BLUEBERRY1…9  (ATtiny85 + RN4871 wearables)
        │  2×2 Mill-Max connector
        ▼
  Implant (cortical PCB or fiber-LED probe)
```

The BlueHub (Arduino UNO R4) is being replaced by a Python asyncio service running directly on the Pi, using the [bleak](https://github.com/hbldh/bleak) library for BLE. The Pi receives stimulation commands from MICS task events instead of BNC GPIO pulses.

---

## BLE Protocol

| Item | Value |
|---|---|
| Device names | `BLUEBERRY1` … `BLUEBERRY9` |
| Service UUID | `4D6963726F636869702D524E34383730` |
| Characteristic UUID | `BF3FBD80-063F-11E5-9E69-0002A5D5C501` |
| Command format | `"PPWW,IILL"` (8-char hex string) |
| Stop command | `"0000,0009"` |

### Command Encoding

```python
def encode_command(pulse_count: int, pulse_width_ms: int, freq_hz: int, channel: int) -> str:
    """
    PP = pulse count (hex, 0 = continuous)
    WW = pulse width (ms, hex)
    II = interval = (1000 / freq_hz) - pulse_width_ms  (ms, hex)
    LL = LED channel: 01=right, 02=left, 03=both
         Add 05 for continuous mode (06=right-cont, 07=left-cont, 08=both-cont)
         Add 09 for single long pulse mode
    """
    interval = int(1000 / freq_hz) - pulse_width_ms
    if interval < 0:
        raise ValueError(f"pulse_width ({pulse_width_ms}ms) exceeds period ({1000//freq_hz}ms) at {freq_hz}Hz")
    pp = format(pulse_count, '02X')
    ww = format(pulse_width_ms, '02X')
    ii = format(interval, '02X')
    ll = format(channel, '02X')
    return f"{pp}{ww},{ii}{ll}"

STOP_COMMAND = "0000,0009"

# Examples:
# 10 pulses, 10ms width, 20Hz, both LEDs:  encode_command(10, 10, 20, 3) → "0A0A,2803"
# Continuous, 5ms, 40Hz, right LED:        encode_command(0, 5, 40, 6)  → "00050A06" (cont mode)
```

### Channel Codes (LL byte)
| Code | Mode | LEDs |
|---|---|---|
| `01` | burst | Right |
| `02` | burst | Left |
| `03` | burst | Both |
| `06` | continuous | Right |
| `07` | continuous | Left |
| `08` | continuous | Both |
| `09` | stop / single long | — |

---

## Pi-Native BlueHub: `pi_blueberry.py`

Build this as an asyncio service. Key responsibilities:
1. **Scan & connect** to named BLUEBERRY devices
2. **Expose a simple async API** (`stimulate()`, `stop()`) called by MICS tasks
3. **Reconnect** automatically on disconnect
4. **Config** loaded from a dict (device_id → params)

### Scaffold

```python
"""
pi_blueberry.py — Pi-native BlueHub replacement using bleak
Install: pip install bleak
"""
import asyncio
from bleak import BleakScanner, BleakClient

SERVICE_UUID = "4D6963726F636869702D524E34383730"
CHAR_UUID    = "BF3FBD80-063F-11E5-9E69-0002A5D5C501"
STOP_CMD     = "0000,0009"

class BlueBerryDevice:
    def __init__(self, device_id: int):
        self.name = f"BLUEBERRY{device_id}"
        self._client: BleakClient | None = None
        self._address: str | None = None

    async def connect(self, timeout=10.0):
        device = await BleakScanner.find_device_by_name(self.name, timeout=timeout)
        if device is None:
            raise ConnectionError(f"{self.name} not found")
        self._client = BleakClient(device, disconnected_callback=self._on_disconnect)
        await self._client.connect()
        print(f"[BlueBerry] Connected to {self.name}")

    async def stimulate(self, pulse_count, pulse_width_ms, freq_hz, channel):
        cmd = encode_command(pulse_count, pulse_width_ms, freq_hz, channel)
        await self._write(cmd)

    async def stop(self):
        await self._write(STOP_CMD)

    async def _write(self, cmd: str):
        if self._client is None or not self._client.is_connected:
            raise ConnectionError(f"{self.name} not connected")
        await self._client.write_gatt_char(CHAR_UUID, cmd.encode())

    def _on_disconnect(self, client):
        print(f"[BlueBerry] {self.name} disconnected — will reconnect on next command")
        self._client = None

    async def disconnect(self):
        if self._client:
            await self._client.disconnect()
```

### MICS Task Integration Pattern

In a MICS ToolKit task (Pi side), call BlueBerry from state entry actions:

```python
# In your task's __init__, create a shared device handle:
self.berry = BlueBerryDevice(device_id=1)

# In your task's start/setup state:
await self.berry.connect()

# In your reward/stim state entry action:
await self.berry.stimulate(
    pulse_count=10,
    pulse_width_ms=10,
    freq_hz=20,
    channel=3  # both LEDs
)

# In your ITI/cleanup state:
await self.berry.stop()
```

For synchronous MICS tasks (non-async), run BLE in a background thread:
```python
import threading, asyncio

def run_ble_in_thread(coro):
    loop = asyncio.new_event_loop()
    t = threading.Thread(target=loop.run_forever, daemon=True)
    t.start()
    return asyncio.run_coroutine_threadsafe(coro, loop)
```

---

## LED Current-Limiting Resistors (R5/R6 on BlueBerry PCB)

Default is 0Ω (jumper) — valid **only** for blue LEDs in short pulsed mode at 3.3V.

```
R = (Vcc - Vf) / If_peak

Where:
  Vcc = 3.3V (LDO output on BlueBerry)
  Vf  = LED forward voltage (blue ≈ 3.0–3.2V, red ≈ 1.8–2.2V, green ≈ 2.0–2.4V)
  If_peak = desired peak current (blue μLEDs: 1–5 mA typical; check datasheet)
```

For **continuous** mode or high-duty-cycle pulsing, always calculate and install resistors — leaving 0Ω for continuous mode will overdrive the LED and shorten device life.

---

## BLE Debugging

### Scan for BlueBerry devices
```bash
# On Pi:
python3 -c "
import asyncio
from bleak import BleakScanner
async def scan():
    devices = await BleakScanner.discover(timeout=5.0)
    for d in devices:
        if 'BLUEBERRY' in (d.name or ''):
            print(d.name, d.address, d.rssi)
asyncio.run(scan())
"
```

### Check BLE service/characteristic
```bash
pip install bleak
python3 -c "
import asyncio
from bleak import BleakClient
ADDR = 'XX:XX:XX:XX:XX:XX'  # from scan above
async def inspect():
    async with BleakClient(ADDR) as c:
        for s in c.services:
            print('SERVICE', s.uuid)
            for ch in s.characteristics:
                print('  CHAR', ch.uuid, ch.properties)
asyncio.run(inspect())
"
```

### Common issues
| Symptom | Cause | Fix |
|---|---|---|
| Device not found in scan | BLE not advertising | Power-cycle BlueBerry; verify battery charged; check slide switch on BlueHub is in correct position |
| Connect succeeds but write fails | Wrong characteristic UUID | Verify UUID with inspect script above |
| Device found only sometimes | Low RSSI / range | Move within 2m; check antenna orientation |
| `bleak` not found | Not installed | `pip install bleak` |
| Permission denied on BLE | Linux Bluetooth perms | `sudo setcap cap_net_raw+eip $(which python3)` or run as root |

---

## Assembly / Hardware Notes (for hardware meetings)

- **Implant PCB is 0.24mm thick** — most fab houses require ≥0.6mm. Verify with fabricator (recommended: PCBGoGo).
- **Stencil alignment jig** (3D-printed STL in `BlueBerry_HW.zip`) is required for solder paste application on the 10.6×11mm BlueBerry PCB.
- **Firmware is two-step**: (1) Flash ATtiny85 via Arduino-as-ISP programmer, clock set to "Internal 1 MHz". (2) Run `BlueBerry_BLE_Config.sh` via USB-serial to program RN4871 BLE module with device name + UUIDs.
- **Mill-Max connectors** (2×2, 1.27mm pitch) must match on both BlueBerry and implant sides.
- **Deep brain implant** is hand-assembled: Wurth 150283BS73103 LED + 400µm optic fiber polished flat + Norland 61 UV adhesive + 3D-printed coupler.
- **License**: Hardware = UNIGE Academic (non-commercial). Software = Apache 2.0.

---

## Reference: Parameter Limits (from BlueHub firmware)
| Parameter | Min | Max | Notes |
|---|---|---|---|
| Frequency | 1 Hz | 99 Hz | |
| Pulse width | 1 ms | 50 ms | Must be < 1000/freq |
| Pulse count | 0 | 99 | 0 = continuous |
| Device ID | 1 | 9 | One hub controls up to 9 devices |
| LED channel | 1–3 | 6–8 (cont) | See channel table above |
