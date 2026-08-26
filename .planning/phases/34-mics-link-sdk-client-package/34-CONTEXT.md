# Phase 34: MICS-Link SDK Client Package - Context

**Gathered:** 2026-08-26
**Status:** Ready for planning

<domain>
## Phase Boundary

A distributable Python client package (`mics-link`, import name `mics_link`) at
`mics-backend/sdk/` that lets a machine which is not a Pi and knows nothing about MICS push
signals and events into a running task's View / FDA framework. Ships with a replay entry
point, a README a programmer outside this lab can follow, and the retirement of the
sender-side wire duplicate in `tools/extlink_driver/extlink_wire.py`.

Fixed by ROADMAP.md and SDK-01–13. Discussion below clarifies HOW, never WHETHER to add more.

**Not in this phase:** DeepLabCut itself, stub generation, bootstrap-zip endpoints, the
"Download SDK" GUI button, `sub_connect` support, any change to the wire envelope or the Pi
ingress path, PyPI publication, latency/jitter measurement.

</domain>

<decisions>
## Implementation Decisions

### Guiding principle (user, this session — the north star for every fork below)

> *"I just want to be able for user to easily make their existing code communicate with the
> pi machine, as well as develop the dlc for general usage."*

Two consequences that bind the whole design:

1. **Additive, not architectural.** A researcher with an existing acquisition loop — DLC,
   photometry, a camera thread, anything — adds three or four lines to code they already
   have. They do not restructure their program around our client, do not inherit from our
   base class, and do not hand us their main loop. If the ten-line script in the README
   requires the caller to reorganise, the API is wrong.
2. **Device-neutral by construction.** Nothing in `mics_link` knows what a keypoint is.
   DLC (Phase 35) must be an ordinary customer of the public API, not a special case with
   privileged hooks. The test of this: Phase 35's adapter should be writable using only
   what the README documents.

### Distribution and install (user-decided this session)

- **Primary, documented path — a real one-liner, no credentials, no cloning, no zip:**
  ```
  pip install "git+https://github.com/idopo/Mics-backend.git#subdirectory=sdk"
  ```
  Viable because `idopo/Mics-backend` is a **public** GitHub repo (verified 2026-08-26 via
  `gh repo view`). Any machine on the internet can run this, including a vision box owned by
  someone else. `#subdirectory=sdk` is what makes the SDK build standalone without dragging
  the backend in — so `mics-backend/sdk/pyproject.toml` must be self-contained and must not
  reference anything above `sdk/`.
- **Offline fallback — a built wheel.** A vision box on an isolated subnet cannot reach
  GitHub. Ship a `python -m build`-produced `.whl` alongside; documented in the README as the
  no-internet path. Cheap once `pyproject.toml` exists.
- **`pip install mics-link` (bare name) is explicitly NOT this phase.** It requires PyPI,
  which SDK-13 rules out. See `<deferred>`. Nothing in the design blocks it — the same
  `pyproject.toml` publishes unchanged the day that decision is made.
- **⚠ Standing risk flagged to the user:** the credential-free install rests entirely on the
  repo staying public. If it is ever made private, the documented install line breaks for
  every outside machine and each user needs a GitHub token. The README should state this
  dependency rather than leave it implicit.

### Public API shape (principles locked; exact spelling is Claude's discretion)

- **The caller must not need to know the Pi's configuration.** SDK-05 says the heartbeat
  interval is "derived from or told about" the Pi's `stale_ms`, but the client cannot query
  the Pi — there is no such channel. Resolution: the SDK picks a **safe default interval**
  that keeps a quiet source alive under any sane `stale_ms`, overridable by a caller who
  knows better. Do not make the ten-line script contain a number the researcher has to look
  up in a database row.
- **`seq` is never surfaced to the caller.** The client owns it, keeps it monotonic, and
  maintains continuity across a reconnect. SDK-07 permits "maintained OR explicitly reset";
  **maintained is chosen** — a reset is a discontinuity the caller would have to understand,
  which violates the additive principle.
- **Deterministic lifecycle (SDK-09):** context manager plus an explicit `close()`. The
  context-manager form is what the README's ten-line script uses.
- **Dtype rejection is at the call site (SDK-04).** A bad value raises where the researcher
  called `send_signal`, with a message naming the allowed dtypes — never a frame the Pi
  silently counts as `type_mismatch` and drops, which is invisible from the sender.

### Loss and connection visibility

- **Drops: a readable counter AND a rate-limited log, both on by default.** SDK-06 permits
  "callback or log"; default-on log plus a counter means a silent drop is impossible, while
  rate-limiting stops a saturated loop from drowning the researcher's own output. An optional
  callback for callers who want to route it into their own telemetry.
- **`on_state_change`-style callback for connected/disconnected (SDK-07)**, which the caller
  is free to ignore entirely. Ignoring it must still be safe.
- **No exception ever escapes into the caller's loop.** This is absolute — a researcher who
  restarts a pilot must not have their acquisition die. It applies to reconnect, to command
  dispatch (SDK-08), and to the drop path.

### Replay driver (SDK-12 — Phase 35's regression vehicle)

- **Accept both CSV and JSONL.** SDK-12 allows either; a DLC export could plausibly be
  either, and "general usage" argues against forcing a conversion step on the user.
- Three timing modes as specified: real time, scaled by a factor, and as-fast-as-possible.
- A malformed row must not abort a replay — count it and continue, consistent with the
  ingress philosophy the Pi side already uses (EXTLINK-08).

### Wire parity and the golden corpus (SDK-02)

- **The canonical reference must be pinned to ONE path and named in the test**, not left
  ambiguous. `~/pi-mirror/autopilot/autopilot/hardware/external_hardware_wire.py` and
  `~/mics_core/autopilot/autopilot/hardware/external_hardware_wire.py` were verified
  **byte-identical on 2026-08-26**, but they are separate trees and the rig migration to
  `mics_core_repo` is mid-flight, so they can drift. The existing
  `tools/extlink_driver/test_extlink_wire.py` already hardcodes the `pi-mirror` path while
  the phase's own "Files to change" list names the `mics_core` one — planning must resolve
  this explicitly rather than inherit the inconsistency.
- **This phase must not edit `external_hardware_wire.py`.** It is a read-only reference. If a
  plan finds itself changing it, the design has gone wrong (roadmap, Phase 18's own rule).
- **Byte-for-byte parity constrains field insertion order.** `msgpack.packb` preserves dict
  insertion order, and the Pi's `encode()` builds `{"k": kind}` then `.update(fields)`. The
  SDK must match that order per kind, not merely the same key set.
- **Version skew is real and must be accounted for:** dev host has `msgpack 1.2.1` and
  `pyzmq 27.1.0`; the rig is pinned to `msgpack==1.0.5` on Python 3.7. The corpus must be
  valid under both, and the SDK targets Python 3.8+ (SDK-01).

### Driver retirement (SDK-10) — REVISED 2026-08-26, later the same day

> **This section originally specified a cutover** (delete `extlink_wire.py`, point
> `extlink_driver.py` at the SDK, keep its CLI and tests behaviourally unchanged). In a later
> session the same day the user scoped that work out: *"the laptop mac script was for the sake of
> a proof of concept, no need to touch it now — we will test the actual sdk properly by doing the
> dlc thing in phase 35."* SDK-10 and ROADMAP criterion 8 were amended to match. The cutover text
> is preserved above this line only as history; the decision below is what binds.

- **`tools/extlink_driver/` is deleted, not ported.** `extlink_wire.py`, `extlink_driver.py` and
  `test_extlink_wire.py` are removed outright. There is no `extlink_cli.py` and no retargeted
  driver. SDK-10 is satisfied by removal — exactly one sender-side wire implementation remains,
  `sdk/src/mics_link/wire.py`.
- **Two files are deliberately retained:** `extlink_demo_fda.json` (the rig fixture the 34-09
  checkpoint runs against) and `README.md`, rewritten as a redirect to the SDK. The README is the
  only written record outside the DB of the demo fixture's IDs — deleting it would break the rig
  checkpoint that depends on those facts.
- **The distribution question dissolves rather than being answered.** The driver reached laptops as
  a hand-copied bundle (`extlink_driver_mac.zip` at the repo root) carrying `extlink_wire.py` as a
  sibling. With the driver gone there is no second wire copy to keep in sync — which was the whole
  concern. The zip is untracked and the user's; the phase only notes it as stale.
- **What replaces it:** `sdk/examples/ten_line_sender.py` and `sdk/examples/rig_checkpoint_sender.py`
  (plans 34-08/34-09) are the worked senders, and Phase 35's DLC adapter is the real integration
  proof. A hand-driven sweep, if ever wanted again, is ~15 lines against the public API.
- **Traceability note:** the driver was Phase 18's EXTLINK-20 deliverable, completed 2026-08-09.
  EXTLINK-20 is marked SUPERSEDED in `REQUIREMENTS.md` — historically met, artifact since removed.

### Testing posture

- **Socketless by construction (SDK-11).** Note the stated premise is stale: `zmq 27.1.0` IS
  installed on this dev host, contradicting `test_extlink_wire.py`'s comment that it is
  absent. The seam requirement stands on its own merit — the rig is what is unavailable, and
  codec / queue-and-drop / heartbeat scheduling / reconnect state machine / command dispatch
  must all be provable with no socket — but planning should not repeat the false claim.
- **Verification split is fixed by the roadmap:** SDK and tests are agent-driven on the dev
  host. The rig checkpoint is **USER-RUN** — the agent supplies commands, the user runs the
  sender from a non-Pi machine and reports what the FDA did.

### Claude's Discretion

Explicitly delegated by the user this session ("not sure — I just want…"):
- Exact class and method naming, constructor vs factory function, module layout under
  `sdk/mics_link/`.
- The concrete heartbeat default interval and its derivation.
- Drop-log rate-limiting policy and counter/stats object shape.
- Replay file column schema and CLI invocation form.
- Internal seam design for the substitutable transport.
- README structure, beyond SDK-13's mandatory content list.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `tools/extlink_driver/extlink_wire.py` (3.3K) — the existing hand-rolled sender codec.
  `sig_frame` / `evt_frame` / `hb_frame` / `coerce_value` / `parse_command` are the proven
  starting shapes. `coerce_value` and `parse_command` are **driver CLI concerns, not SDK
  concerns** — the SDK takes typed Python values, so parsing a stdin token belongs with the
  driver even after the codec moves. Deleted at end of phase (SDK-10).
- `tools/extlink_driver/test_extlink_wire.py` (7.0K) — already contains the two patterns this
  phase needs: an **AST-based hygiene guard** proving no socket import, and an **interop test**
  that loads the Pi's real wire module by path via
  `importlib.util.spec_from_file_location`. Retarget rather than reinvent.
- `tools/extlink_driver/README.md` (5.6K) — existing researcher-facing doc; the SDK-13 README
  can inherit its structure and its rig-prerequisites section.
- `tools/extlink_driver/extlink_demo_fda.json` — the demo FDA behind the rig checkpoint.

### Established Patterns
- **Wire envelope, frozen (`external_hardware_wire.py`):**
  `SIG {k, ts_src, seq, sig, v}` · `EVT {k, ts_src, seq, evt, p}` · `HB {k, ts_src, seq}` ·
  `ACK {k, ts_src, cmd_id, result}` · `CMD {k, ts_pi, cmd_id, name, args}` (Pi→SDK only).
  Packed with `msgpack.packb(obj, use_bin_type=True)`, decoded with `unpackb(raw, raw=False)`.
- **The Pi's `encode()` stamps no clock and no `seq`** — every field arrives as a kwarg. The
  driver's `_envelope` is what stamps `ts_src`/`seq`. That responsibility moves into the SDK.
- **`ts_src` is wall-clock on purpose**, and the Pi ignores it for FDA purposes (`ts_pi_recv`
  is canonical). Do not "fix" it to a monotonic clock — that would make it look comparable
  across unsynced machines. **No latency is asserted anywhere in this phase** (Phase 28).
- **`bool` is special-cased against Python's int-subclass trap** on both existing sides
  (`float(True) == 1.0`) — the SDK's dtype validation must preserve this, per EXTLINK-12.
- **Counting replaces raising on ingress** (EXTLINK-08); `DecodeStats` is the Pi-side shape.
- **Codec / transport split** — `external_hardware_wire.py` (pure, socketless) vs
  `external_hardware_runtime.py`. The SDK mirrors this split; it is the same answer to the
  same constraint (SDK-11).

### Integration Points
- **New:** `mics-backend/sdk/` — package, `pyproject.toml`, `README.md`, `tests/`. Must NOT
  live under `~/pi-mirror/` or `~/mics_core/`, both rsynced to a Pi (SDK-01).
- **Deleted:** `tools/extlink_driver/extlink_wire.py`, `extlink_driver.py`,
  `test_extlink_wire.py`. **Retained:** `extlink_demo_fda.json` (unmodified) and `README.md`
  (rewritten as a redirect, rig facts preserved).
- **Read-only reference:** `external_hardware_wire.py` — golden corpus generated against it.
- **Rig fixture (already standing on pilot 1):** task def 434, toolkit 100, module 62,
  hw lib 177, `pilot_hardware_config` row 21.
- **⚠ Standing dependency inherited from Phase 18's teardown decision:** the `ExtlinkDemo`
  fixture requires a TCP echo listener on the dev host at `132.77.73.125:5597` to stay
  running. Without it `demo.alive` flips false after three egress-probe failures and the
  readiness gate times out. See `18-HARDWARE-VALIDATION.md` §3. **The rig checkpoint will
  fail confusingly if this is not up first** — planning should make it a precondition step,
  not a debugging surprise.

### Project rules that constrain execution
- **Never run git on the Pi**; never start/stop the pilot process; never run Python on the Pi.
  Supply commands and wait for the user (project memory + the phase's verification posture).
- Production files stay under 300 lines; split before exceeding. Tests exempt.
- Test-first: write the failing test, see it fail, then implement.

</code_context>

<specifics>
## Specific Ideas

- **"Ten lines" is a literal acceptance bar, not a figure of speech.** The README's example
  is counted. If it exceeds ten lines of real code, the API needs simplifying — that example
  is the phase's own usability test.
- **The install command is a deliverable in its own right.** A researcher should be able to
  copy one line into a terminal on a machine that has never heard of this lab and have a
  working client. Anything requiring a clone, a token, a zip, or a `PYTHONPATH` fails the
  user's stated goal.
- **Phase 35 is the acceptance test of device-neutrality.** When planning any API surface,
  ask: could the DLC adapter be written against this using only the README? If it would need
  something not documented, the public API is incomplete.

</specifics>

<deferred>
## Deferred Ideas

- **Publish to PyPI and claim the `mics-link` name** so the install becomes bare
  `pip install mics-link`. Raised by the user this session; excluded by SDK-13, which states
  the public name is a separate decision. Nothing in the design blocks it — the same
  `pyproject.toml` publishes unchanged. Revisit when the lab decides on a public package name.
- **Stub generation from a hardware lib's declared `@signal`s**, bootstrap-zip endpoints, and
  the "Download SDK" GUI button — all three remain deferred from Phase 18, still out of scope.
- **`sub_connect` support in the SDK** — deliberately never an SDK concern. A foreign
  publisher needs a `@decoder` in a hardware lib, not a client library.
- **Latency / jitter measurement** — Phase 28, which measures both paths inside one recording.
  Any number this phase printed would be NTP skew, not latency.
- **Refreshing / retiring `extlink_driver_mac.zip`** — the hand-copied bundle at the repo root
  becomes questionable once the driver depends on an installed SDK. Worth an explicit decision
  later; this phase only needs to avoid reintroducing a second wire copy through it.

</deferred>

---

*Phase: 34-mics-link-sdk-client-package*
*Context gathered: 2026-08-26*
