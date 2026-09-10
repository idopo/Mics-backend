# mics-link

A client library that lets any machine push signals and events into a running MICS
task, over the network, and observe the result in that task's state machine and in
Elasticsearch.

## 1. What this is

`mics_link` is a client library that lets any machine -- a laptop, a lab workstation, a
Windows vision box running a live inference pipeline -- push signals and events into a
running MICS task's state machine (its FDA, "finite deterministic automaton") over the
network. It knows nothing about your device: it does not know what a signal *means*,
does not care what produced the value, and has no opinion about your acquisition
hardware or software. You call `send_signal`/`send_event`; the receiving pilot's FDA
reacts however its own transitions say to react.

## 2. Install

`mics_link` has exactly two runtime dependencies -- `pyzmq` and `msgpack` -- and
requires Python 3.8+. It runs on macOS, Windows and Linux, including inside an existing
conda or other scientific-Python environment: the dependency floors are chosen to already
be satisfied by a typical install, so adding `mics_link` does not force an upgrade of
your existing stack.

Always invoke with `python -m pip`, never bare `pip`. On a Windows box with a `py`
launcher and two or three Pythons installed, bare `pip` can silently install into the
wrong interpreter -- you then get a `ModuleNotFoundError` inside the environment you
actually meant to use, with no clue why.

```bash
python -m pip install mics-link
```

That is the whole install. You do not need git, a GitHub account, access to any lab
repository, or a file from a network share -- `mics-link` is published on PyPI and
resolves by name from anywhere with an internet connection.

Note the hyphen: you `pip install mics-link`, and you `import mics_link`. That split is
normal Python packaging, not a typo.

**Offline fallback** (no internet at all -- e.g. an isolated vision-box subnet): download
the wheel on a machine that does have internet, using the SAME interpreter version and
platform you will install onto...

```bash
python -m pip download mics-link --dest ./mics-link-offline
```

...copy that folder across by any means (USB drive, internal file share), then install
from it without touching the network:

```bash
python -m pip install --no-index --find-links ./mics-link-offline mics-link
```

This installs the identical artifact the online path resolves -- only how it reaches the
machine differs.

## 3. What must already exist on the rig

Before anything can be sent, a researcher needs to create four things on the MICS side,
through the MICS web UI (authoring them is not covered here -- see the toolkit /
hardware-module / task-definition documentation for that workflow):

1. A **hardware module** of a class that accepts external signals (e.g. `ExtlinkDemo`).
2. A **`pilot_hardware_config` row** on the target pilot, wiring that module's `config`
   to a `role: "router_bind"` shape (section 4 below has the exact fields).
3. A **toolkit** that includes the module.
4. A **task definition** whose FDA has transitions that read the signals/events you
   intend to send.

**Worked example** -- the standing fixture every sender in this document targets:

| Thing | Value |
|---|---|
| Pilot | pilot 1 (`pilot_raspberry_lior`), host `192.0.2.10` |
| Toolkit | 100 |
| Hardware module | 62 (`ExtlinkDemo`) |
| Hardware lib | 177 |
| Task definition | 434 (`extlink_demo`) |
| `pilot_hardware_config` row | 21 |

A NEW integration -- a different rig, a different module -- needs a researcher to create
the equivalent four things first. This README documents what the sender needs from
them once they exist, not how to author them.

**Every address in this document is a placeholder**, drawn from the ranges RFC 5737
reserves for documentation (`192.0.2.x`, `198.51.100.x`). They are not reachable and are
not anyone's rig. Substitute your own pilot's address, which you read from that pilot's
record in the MICS web UI -- see the load-bearing warning in section 4 about which
address that is.

## 4. The exact `pilot_hardware_config.config` shape

The worked example's row (21), verbatim:

```json
{"class_name":"ExtlinkDemo","role":"router_bind","listen_port":5599,
 "host":"198.51.100.20","source_id":"demo","stale_ms":3000,
 "required":true,"wait_timeout_s":30,"egress_fail_threshold":3}
```

| Field | Meaning | Does the sender need it? |
|---|---|---|
| `source_id` | The DEALER identity the sender MUST connect with. A mismatch is dropped **silently** by the Pi's ROUTER -- no NAK (EXTLINK-02). | **Yes.** |
| `listen_port` | The port the Pi's ROUTER is bound on. | **Yes.** |
| the pilot's own host/IP | Where the sender dials in. **Not** the `host` field below -- see the warning. | **Yes** -- read it from the pilot record, not this JSON. |
| `role` | Always `"router_bind"` -- the Pi binds, the sender dials in as a DEALER. The only role this SDK supports. | No -- informational. |
| `stale_ms` | Per-source liveness window checked on the Pi side. | No -- the SDK's default heartbeat (1.0s) is safe for any `stale_ms` at or above ~3s. |
| `required` / `wait_timeout_s` | The readiness gate: a run on this pilot blocks up to `wait_timeout_s` and FAILS if this source never connects. | No -- but know it exists, since a typo'd `source_id` will silently trip it. |
| `host` / `egress_fail_threshold` | This module's own OUTBOUND probe target and failure threshold -- nothing to do with your sender. | No. |

**Warning, load-bearing:** `host` in this JSON (`198.51.100.20` above) is the module's
own *egress* probe target -- a completely different address from the pilot you actually
connect to. Pointing your client at `host` instead of the pilot's own IP is the single
most common way to misread this config.

## 5. A working sender

**The pull-loop shape** -- for when you already have a loop that produces values (a
camera read, a sensor poll, a per-sample model output). This is
`sdk/examples/ten_line_sender.py`, verbatim, and is ten lines or fewer of real code --
enforced by `sdk/tests/test_readme_contract.py`, not by eyeballing:

```python
"""Ten-line MICS-Link sender. Docstrings and comments do not count.

This is ADDITIVE: three real lines dropped into a loop you already have.
`my_existing_loop()` below is a PLACEHOLDER -- swap it for whatever already produces
your values (a camera read, a model inference step, a sensor poll). `mics_link` does
not know or does not care what it is; that is the point.
"""
from mics_link import connect

# my_existing_loop() is a stand-in for your own acquisition loop -- not part of mics_link.
with connect("192.0.2.10", 5599, "demo") as link:
    for x in my_existing_loop():
        link.send_signal("left_paw_x", x)
```

**The callback / push shape** -- for when a library hands you values instead of you
asking for them. Many vendor acquisition and inference SDKs work this way: they call
YOUR function, on THEIR thread, once per sample, and often expect their own value handed
straight back. This is `sdk/examples/callback_sender.py` (exempt from the ten-line bar,
which only applies to the pull-loop example above):

```python
from mics_link import connect
from mics_link.values import as_scalar

with connect("192.0.2.10", 5599, "demo") as link:

    def on_sample(value):  # your library calls this, on its own thread
        link.send_signal("left_paw_x", as_scalar(value))
        return value  # hand the host back what it expects

    run_my_acquisition(on_sample)
```

Three rules make this shape safe, and they are load-bearing, not stylistic:

1. **The client is created OUTSIDE the callback and OUTLIVES it** -- the `with` block
   owns the lifetime; the callback only borrows `link`.
2. **The callback returns whatever its host expects.** A foreign library that hands you
   a value usually wants it back; forgetting to return it breaks the host.
3. **Per-callback state (deadbands, last-values) lives on the callback object, not the
   SDK.** Decimation and sampling policy are the caller's business; `mics_link` has no
   opinion about rates.

Never open a client inside a callback, and never rely on a library's teardown hook to
close it -- some hosts have no guaranteed teardown, so a client created inside a
callback object's constructor may never be closed.

### API reference

Every name below is importable from `mics_link` and appears in `mics_link.__all__`.

```python
def connect(host, port, source_id, **kwargs) -> MicsLink: ...
```

`connect` validates `(host, port, source_id)`, runs an internal self-check, and returns
a connected `MicsLink`. Extra keyword arguments are passed straight through to
`MicsLink`: `heartbeat_s` (override the default 1.0s heartbeat interval), `queue_size`
(override the default 256-frame bounded send queue), `on_state_change` (a
`callback(connected: bool)` fired on connect/disconnect edges -- see section 8's
identity warning), `on_drop` (a `callback(frame)` fired when a frame is dropped because
the send queue is full).

```python
class MicsLink:
    def send_signal(self, name: str, value) -> bool: ...      # True == enqueued, False == dropped
    def send_event(self, name: str, payload: dict) -> bool: ...
    def command(self, name): ...                               # decorator: @link.command("stop")
    def close(self) -> None: ...                                # idempotent, never raises
    def __enter__(self): ...
    def __exit__(self, *exc): ...
    @property
    def stats -> SenderStats: ...       # .enqueued / .sent / .dropped / .abandoned
    @property
    def connected -> bool: ...
    @property
    def source_id -> str: ...
```

`send_signal`/`send_event` enqueue onto a bounded, drop-newest-on-overflow queue drained
by a background IO thread; they never block, never touch the network directly, and are
safe to call from a foreign library's own callback thread at frame rate. The one
exception either can raise is `InvalidValueError` (subclasses both `MicsLinkError` and
`TypeError`) -- a value whose exact type is not one of `bool`/`int`/`float`/`str`
(section 8 has the numpy case). `MicsLinkError` is the single base class every exception
this package raises inherits from.

`close()` (also reachable via the `with` statement) stops accepting new sends, gives the
IO thread a bounded window to flush whatever is already queued, then abandons and counts
(`stats.abandoned`) anything still queued past that window, and closes the underlying
socket. It is idempotent and never raises -- a researcher's loop that outlives the
`with` block will not crash on a second `close()`.

`mics_link.__version__` is the installed package's version string (e.g. `"0.1.0"`).

## 6. How to observe the result

**In the FDA:** the worked example's task definition (434, `extlink_demo`) cycles
`wait -> armed -> fired -> wait`: `wait -> armed` when `demo.left_paw_x > 0.5`,
`armed -> fired` when `demo.left_paw_x < 0.2`, `fired -> wait` unconditionally, with no
terminal state. Send values that cross those thresholds and watch the pilot's live
state in the MICS web UI.

**In Elasticsearch:** live rig data lives on your lab's ES host (ask whoever runs the
backend; it is not the pilot and not the MICS API), index `event_log_v2`.
Isolate one run with `subject: bp_s<session>_r<run_id>` (the session and run id come
from the MICS web UI's session view). Every `send_signal`/`send_event` call your sender
makes is logged there once the Pi has processed it.

## 7. Replay

`mics-link-replay` plays a recorded `(t, signal, value)` file through the client -- at
real time, at a scale factor, or as fast as possible. It is the phase's own regression
vehicle, and the way to re-run a recorded acquisition deterministically, without the
original hardware or software that produced it.

```bash
mics-link-replay --host 192.0.2.10 --port 5599 --source-id demo --file recording.csv \
                  [--mode realtime|scaled|fast] [--scale 2.0] \
                  [--heartbeat-s 1.0] [--queue-size 256]
```

If the console script is not on `PATH` (a known Windows packaging quirk -- installed
scripts land in `<env>\Scripts\`, which is not always on `PATH`), the guaranteed
equivalent is:

```bash
python -m mics_link.replay --host 192.0.2.10 --port 5599 --source-id demo --file recording.csv
```

**Two file shapes**, detected from the header/keys -- never a flag:

Long (one row per sample) -- `sdk/tests/fixtures/replay_sample.csv`:
```csv
t,signal,value
0.00,nose_p,0.98
0.00,tail_p,0.41
0.03,count,3
0.03,visible,true
0.03,label,left
```

Wide (one row per timestamp, one column per signal; an empty cell means "no sample this
frame") -- `sdk/tests/fixtures/replay_sample_wide.csv`:
```csv
t,nose_p,tail_p,count,visible,label
0.00,0.98,0.41,,,
0.03,,,3,true,left
```

Both CSV and JSONL are accepted, dispatched by file suffix (case-insensitive); both
shapes above produce the byte-identical `(t, signal, value)` send sequence.

**Timing modes:** `realtime` paces to wall-clock `t`; `scaled` divides elapsed time by
`--scale`; `fast` sends with no pacing at all. All three are driven by
`mics_link.timing.Pacer` -- origin-relative (every wait measures from the first row's
timestamp, never cumulatively against the previous row), so a slow row never produces a
negative sleep or a catch-up burst. `Pacer` is public (`from mics_link import Pacer`)
for exactly this reason: any frame-paced loop you write yourself can reuse the same
drift-free scheduler `mics-link-replay` uses, instead of re-implementing pacing.

**Malformed rows are counted, never fatal:** a missing column, an unparseable
timestamp, an empty signal name, or a value the SDK cannot send is skipped and counted
in the printed `rows_malformed` total -- one bad row never aborts the rest of the file.

## 8. Things that will waste your afternoon

1. **A mismatched `source_id` looks like a working connection.**
   `on_state_change(True)` means the DEALER's TCP-level connection to the Pi's ROUTER is
   up -- **not** that the Pi is accepting your identity. A typo'd `source_id` produces a
   perfectly "connected" client whose every frame is silently discarded by the Pi's
   ROUTER (EXTLINK-02, no NAK). This is the single most likely way to waste an
   afternoon; double-check `source_id` against the `pilot_hardware_config` row before
   debugging anything else.
2. **numpy scalars are rejected, not coerced.** `send_signal`/`send_event` require the
   value's EXACT type to be `int`, `float`, `bool` or `str` -- a `numpy.float32` raises
   `InvalidValueError` at your own call site, and `numpy.float64` (which *looks* like a
   plain `float`) is rejected on purpose, for the same reason. Convert explicitly with
   `mics_link.values.as_scalar(v)` -- it uses `.item()`, which preserves the
   int/bool/float distinction the way `float(...)` does not (`float(True) == 1.0`
   silently turns a `bool` into a `float`). Do not "fix" this with `float(...)`.
3. **One `source_id`, one connection.** The Pi's ROUTER keys off DEALER identity ==
   `source_id`. Two processes on the same box under one `source_id`, or a relaunch while
   the old process still holds the socket, collide silently. Two senders means two
   separate `pilot_hardware_config` rows (two distinct `source_id`s), never one shared
   one.
4. **Windows `time.sleep` granularity.** Below Python 3.11, `time.sleep()` resolution on
   Windows is roughly 15.6ms -- `mics-link-replay`'s `realtime`/`scaled` modes are only
   as precise as that floor allows, above roughly 60Hz. `python -m mics_link.replay`
   (section 7) is the guaranteed alternative to the console script when it is not on
   `PATH`.
5. A value outside `int`/`float`/`bool`/`str` raises `InvalidValueError` at the call
   site (see #2 above) -- it never silently reaches the Pi as a dropped frame.
6. A `bool`-declared signal fed an `int` (or vice versa) is dropped Pi-side, invisibly
   to the sender -- match your value's type to what the FDA transition expects.
7. Drops are always counted and logged (`stats.dropped`), never silent -- but a full
   send queue still drops the newest frame rather than blocking your loop.
8. `required: true` in the `pilot_hardware_config` row makes a run on that pilot FAIL at
   the readiness gate if your sender is not connected within `wait_timeout_s`.

## 9. Why there is no latency readout

Comparing a sender machine's send-timestamp against the Pi's own receive timestamp would
measure clock skew between the two machines, not latency -- they are not NTP-synced to
each other. That measurement belongs to a dedicated timing-validation phase of this
project, not this SDK. `mics-link-replay`'s summary, and every log line this SDK prints,
report counts and a plain wall-clock duration only -- never a latency, jitter, drift, or
round-trip number, deliberately: printing one would report a value that is not what it
claims to be.
