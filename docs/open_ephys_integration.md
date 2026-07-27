# Integrating Open Ephys with MICS over the Network

**Audience:** product / decision-maker overview
**Goal:** control the Open Ephys acquisition system *and* receive its neural data directly from our MICS Python application — over the network, no extra wiring.

---

## The idea in one line

Treat Open Ephys as **just another piece of hardware in a MICS task** — something we can *start*, *stop*, and *read from* through software, exactly like we already do with valves, lick sensors, and LEDs. No cables between the two systems.

## Two network channels

Open Ephys exposes two independent network interfaces. We use both.

| Channel | Direction | Protocol | What it's for |
|---|---|---|---|
| **Control** | MICS → Open Ephys | HTTP REST API (port **37497**) | Start/stop acquisition & recording, set save location, inject event markers |
| **Data** | Open Ephys → MICS | ZMQ stream (configurable port, default **5556**) | Live spikes, events, and continuous signal pushed to MICS in real time |

### Control — start ephys from a MICS task
The MICS app issues simple HTTP calls, e.g. set the system to `RECORD` when a session begins and back to `IDLE` when it ends:

```
PUT http://<ephys-host>:37497/api/status   { "mode": "RECORD" }
```

The same API lets us set the recording folder per subject/session and broadcast a message into the recording. This means **the researcher never has to touch the Open Ephys GUI** — the MICS session controls it automatically.

### Data — read spikes from ephys into a MICS task
The **ZMQ Interface plugin** publishes every spike, event, and data sample as a network message. A small MICS client subscribes and receives them live. Each message carries a JSON header (electrode name, sorted unit ID, thresholds, and a **sample number**) plus the raw waveform.

## Why this matters: neural data becomes a task input (hardware abstraction)

In MICS, a task's `View` already asks hardware *"what's your current value?"* (is the lick sensor triggered? is the LED on?). We plug the ephys stream into that same abstraction:

> **`view.get_value("spike_rate")`** behaves like any other sensor.

Once neural activity is a first-class task input, we can **close the loop**: trigger a reward, a light, or a state transition based on live spiking — not just on behavior. This is a genuinely new capability the current wired setup can't offer.

## Replacing the TTL sync cable

MICS already knows the exact moment of every behavioral event. Instead of relying on a physical TTL wire to mark those events on the ephys clock, MICS sends each event as a **timestamped network message** that Open Ephys records *inline in the data stream* — and, going the other way, every ZMQ message we receive carries Open Ephys's own **sample number**, so both systems can be co-registered in software after the fact.

Net result:
- **No TTL cable, no consumed digital I/O channels, no re-wiring between rigs.**
- Event markers are labeled text ("reward", "cue_on") rather than anonymous pulses — richer and self-documenting.
- One software path to configure instead of hardware + software.

**Honest caveat:** a hardware TTL has near-zero, deterministic latency; network messages carry small, variable jitter (sub-millisecond to a few ms). For most behavioral alignment this is well within tolerance. If an experiment ever needs *hardware-grade* sub-millisecond precision, we can keep a single TTL as a periodic "sync heartbeat" and use the network path for everything else — best of both worlds.

## What we'd build in MICS

1. **An Open Ephys "hardware" module** — start/stop/record via the REST API, wired into the session lifecycle.
2. **A ZMQ subscriber** feeding spikes/events into the task `View` as readable values.
3. **Event markers** sent from tasks to Open Ephys, replacing the TTL sends.

All three are standard, well-documented network calls — no changes required on the Open Ephys side beyond installing the (official) ZMQ Interface plugin.

---

*References: Open Ephys Remote Control (REST API) and the ZMQ Interface plugin, both maintained by the Open Ephys project.*
