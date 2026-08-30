---
phase: 34-mics-link-sdk-client-package
plan: 02
subsystem: sdk
tags: [dtype-validation, zmq-transport, bounded-queue, numpy-scalars, drop-newest]

# Dependency graph
requires: ["34-01"]
provides:
  - "mics_link.errors — MicsLinkError, InvalidValueError (also a TypeError)"
  - "mics_link.values — validate_value/validate_payload (exact-type dtype check), as_scalar (numpy escape hatch), coerce_token (CSV/stdin token coercion)"
  - "mics_link.transport — Transport seam, endpoint()/validate_target(), ZmqTransport (DEALER identity lock, router_bind only, lazy zmq import)"
  - "mics_link.sender — SenderStats, should_log_drop, BoundedSender (threadless, drop-NEWEST, rate-limited log)"
  - "sdk/tests/fake_transport.py — FakeSocket + fake_socket_factory + FakeTransport, the in-memory Transport substitute every later plan's tests build on"
affects: [34-03, 34-04, 34-05, 34-06, 34-07, 34-08, 34-09]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Exact-type (`type(value) is X`) dtype checks, not isinstance — rejects numpy scalar subclasses that isinstance would silently admit (SDK-04 amendment)"
    - "socket_factory(context, host, port, source_id) owns the full create+identity+connect sequence, so ZmqTransport itself never touches a raw zmq constant outside function bodies, and a fake factory needs no zmq import at all"
    - "Leading-edge rate-limited logging: should_log_drop(None, ...) is always True, so the FIRST drop of any silence window logs immediately with the cumulative total at that instant; a later window's first drop again reports the cumulative total, not a delta — proven honest (not caplog-lazy-read-dependent) by a two-window test"

key-files:
  created:
    - sdk/src/mics_link/errors.py
    - sdk/src/mics_link/values.py
    - sdk/src/mics_link/transport.py
    - sdk/src/mics_link/sender.py
    - sdk/tests/fake_transport.py
    - sdk/tests/test_dtype_validation.py
    - sdk/tests/test_transport_config.py
    - sdk/tests/test_sender_bounded_drop.py
  modified: []

key-decisions:
  - "validate_value/validate_payload use type(value) is X (exact type), never isinstance — per the 34-02-PLAN.md 2026-08-30 amendment, isinstance(numpy.float64(...), float) is True and would silently admit a value msgpack cannot pack, resurfacing as an un-catchable TypeError on the IO thread. Pinned by FakeF64(float)/FakeStr(str) stand-ins exposing .item(), exactly mirroring real numpy scalar shape without adding numpy as a dependency."
  - "as_scalar implemented verbatim from the amendment text (getattr(.item)/callable/not-bytes-or-str check); validate_value's rejection message names 'as_scalar' whenever the rejected value exposes that same .item hook, so the error text itself points at the fix."
  - "ZmqTransport's injectable socket_factory(context, host, port, source_id) owns creating the DEALER, setting IDENTITY once, and connecting — all three in one function body (default implementation does `import zmq` there, never at module scope). This let the fake-factory test path use zero real zmq API surface (plain string tokens 'DEALER'/'IDENTITY' recorded on a FakeSocket) while the identity-set-once contract stays provably enforced from the fake's call-order assertion."
  - "Default context_factory creates a PRIVATE zmq.Context() per ZmqTransport instance, not the process-wide zmq.Context.instance() singleton — so close() can safely term() it without disturbing any other transport sharing the same process."
  - "BoundedSender writes stats.enqueued/dropped only; stats.sent/abandoned are left as plain, externally-settable counters for plan 34-06's IO thread (sent after a transport.send() actually succeeds) and close() (abandoned = whatever was still queued at shutdown) — BoundedSender itself can only honestly prove enqueued/dropped from inside its own bounded queue."
  - "Rewrote my own first draft of the rate-limited-log test after it exposed a design contradiction: should_log_drop(None, ...) is unconditionally True (independently pinned), so the FIRST drop of ANY burst logs immediately at whatever the count is at that instant — a single unbroken 100-drop burst can only ever produce a log line showing '1', never '100', without a deferred-read trick that would only work inside pytest's caplog (which stores raw records and calls .getMessage() lazily) and would NOT reproduce in a real synchronous log handler. Replaced with a two-window test that proves the honest, production-real property: a later window's log line already includes everything a prior window silently dropped (51, not '+1')."

patterns-established:
  - "TDD RED/GREEN cycle per task, matching 34-01's established rhythm: failing test committed first (test: prefix), then the minimal implementation (feat: prefix); one extra test-only commit here (fixing a discovered test-design flaw before GREEN) also carries the test: prefix."

requirements-completed: [SDK-03, SDK-04, SDK-06]

# Metrics
duration: ~40min
completed: 2026-08-30
---

# Phase 34 Plan 02: Dtype validation, transport seam, bounded sender Summary

**Call-site dtype validation with an exact-type check that closes the numpy-scalar isinstance trap (SDK-04, amended), a substitutable ZMQ DEALER transport with the identity locked at construction and no bind/sub_connect path (SDK-03), and a threadless bounded drop-NEWEST send queue with rate-limited, cumulative-count drop logging (SDK-06) — all three proven with zero sockets, zero network, zero Pi.**

## Performance

- **Duration:** ~40 min
- **Started:** 2026-08-30 (after worktree base correction to abb0229)
- **Completed:** 2026-08-30
- **Tasks:** 3/3 completed, each as a TDD RED -> GREEN pair (Task 3 additionally required a
  RED-phase test-design fix before GREEN, tracked as its own `test:` commit)
- **Files modified:** 8 created, 0 modified

## Accomplishments

- `mics_link.values.validate_value`/`validate_payload` reject anything whose EXACT type is
  not `bool`/`int`/`float`/`str` — pinned against the numpy-scalar-subclass trap with local
  `FakeF64(float)`/`FakeStr(str)` stand-ins exposing `.item()`, without adding numpy as a
  dependency. The rejection message names the signal, the offending type, the four allowed
  dtypes, and — only when the value exposes `.item` — the literal string `as_scalar`,
  satisfying the amendment's "the message must name the fix" requirement.
- `mics_link.values.as_scalar` implemented verbatim per the amendment; `coerce_token` lifted
  from `tools/extlink_driver/extlink_wire.py:coerce_value` with the JSON-dict branch made
  opt-in (`allow_json_dict=False` by default) and the bool-before-int docstring rationale
  carried forward rather than paraphrased away.
- `mics_link.transport.ZmqTransport` proves SDK-03 entirely offline: identity is set exactly
  once (`socket` -> `setsockopt(IDENTITY, ...)` -> `connect`, in that exact order, asserted
  against a `FakeSocket`'s call log), `source_id` is a read-only property with no setter
  (assigning raises `AttributeError`), and the only reference to the raw socket is
  underscore-only (asserted by scanning `vars(transport)` for public attributes). There is
  no `bind()` and no `sub_connect` anywhere in the module — `router_bind` is the only role.
- `zmq` is imported inside function bodies only (`_default_context_factory`,
  `_default_socket_factory`, `_attach_monitor`, `poll`, `events`, `close`) — never at module
  scope — so `mics_link.transport` itself imports cleanly with `zmq` blocked via the same
  `sys.meta_path` finder trick 34-01 used for `mics_link.wire`.
- `mics_link.sender.BoundedSender` proves SDK-06 entirely offline: overflow drops the
  NEWEST frame (`queue.Queue(maxsize=N)` + `put_nowait`/`queue.Full`, never a
  bounded-deque, which would evict the OLDEST), `enqueue` never blocks or raises even under
  sustained overflow, a raising `on_drop` callback never escapes and never stops
  `stats.dropped` from incrementing, and the rate-limited drop log reports the CUMULATIVE
  total (not a per-window delta) — proven with a two-window test where the second window's
  single log line already includes everything the first window silently dropped.
- `sdk/tests/fake_transport.py` ships `FakeSocket` (records `socket`/`setsockopt`/`connect`
  calls in order using zmq-free string tokens), `fake_socket_factory` (builds a
  `ZmqTransport`-compatible factory around a `FakeSocket`), and `FakeTransport` (in-memory
  `Transport` implementation with `fail_next` for proving no-exception-escapes in a later
  plan) — the shared substitute every non-codec test in this phase depends on.

## Task Commits

Each task followed the RED -> GREEN TDD cycle:

1. **Task 1 RED: failing dtype-validation tests** - `1f38634` (test)
2. **Task 1 GREEN: errors.py + values.py** - `3616ae1` (feat)
3. **Task 2 RED: failing transport-seam tests + fake_transport.py** - `2575ff1` (test)
4. **Task 2 GREEN: transport.py** - `1a9298c` (feat)
5. **Task 3 RED: failing sender tests** - `11bcd8e` (test)
6. **Task 3 RED-phase fix: honest cumulative-log test redesign** - `d6d914a` (test)
7. **Task 3 GREEN: sender.py** - `43a7289` (feat)

## Files Created

- `sdk/src/mics_link/errors.py` - `MicsLinkError`, `InvalidValueError` (also a `TypeError`)
- `sdk/src/mics_link/values.py` - `ALLOWED_DTYPES`, `validate_value`, `validate_payload`,
  `as_scalar`, `coerce_token`
- `sdk/src/mics_link/transport.py` - `MONITOR_CONNECTED`/`MONITOR_DISCONNECTED`/
  `MONITOR_RETRIED`, `endpoint`, `validate_target`, `Transport`, `ZmqTransport`
- `sdk/src/mics_link/sender.py` - `SenderStats`, `should_log_drop`, `BoundedSender`
- `sdk/tests/fake_transport.py` - `FakeSocket`, `fake_socket_factory`, `FakeTransport`
- `sdk/tests/test_dtype_validation.py` - 47 tests
- `sdk/tests/test_transport_config.py` - 23 tests
- `sdk/tests/test_sender_bounded_drop.py` - 16 tests

## Decisions Made

See `key-decisions` in the frontmatter for full rationale on: exact-type vs. isinstance
dtype checks, the `as_scalar` implementation and its message-naming behavior, the
`socket_factory(context, host, port, source_id)` seam shape and why it needs zero real zmq
API surface for the fake path, the private-per-instance `zmq.Context()` choice over the
process-wide singleton, and the `BoundedSender`/`stats.sent`/`stats.abandoned` ownership
split with plan 34-06.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `deque(maxlen` substring in sender.py's own docstring failed the
verification grep**
- **Found during:** Task 3, after writing `sender.py`'s module docstring explaining why
  `queue.Queue` was chosen over a bounded deque
- **Issue:** The plan's own `<verification>` block runs `grep -rn "deque(maxlen" sdk/src/`
  and expects zero matches (the "wrong drop end" check) — but my first draft's prose
  explaining the choice contained the literal substring `collections.deque(maxlen=N)`,
  failing that grep exactly the way 34-01's `wire.py` docstring failed the `zmq` substring
  check (documented there as its own Rule 1 deviation).
- **Fix:** Reworded the docstring to describe the rejected alternative ("a
  bounded-`collections.deque`, whose eviction rule discards the OLDEST item on overflow")
  without using the literal banned substring.
- **Files modified:** `sdk/src/mics_link/sender.py`
- **Verification:** `grep -rn "deque(maxlen" sdk/src/` — zero matches (after also clearing
  a stale `__pycache__/*.pyc` that briefly matched as a binary hit)
- **Committed in:** `43a7289`

**2. [Rule 1 - Bug] My own first draft of the rate-limited drop-log test was internally
inconsistent with an already-pinned pure-function contract**
- **Found during:** Task 3, GREEN phase — running `test_sender_bounded_drop.py` against the
  real `sender.py` implementation
- **Issue:** My initial test asserted that 100 drops occurring entirely within one
  `drop_log_interval_s` window would produce exactly one log record whose message contains
  the literal string `"100"`. But `should_log_drop(None, now, interval)` is unconditionally
  `True` on the first-ever call (a separate, already-passing test pins this), which means
  the FIRST drop of any burst logs immediately, at whatever `stats.dropped` equals at that
  instant — `1`, not the eventual total. No synchronous logging design can make the first
  log line of an unbroken burst show a count higher than what has actually happened by the
  time it fires, without relying on a deferred-`getMessage()` read (a caplog-only artifact
  that would NOT reproduce with a real synchronous log handler) — which would have made the
  test pass by exploiting test-harness behavior rather than proving real behavior.
- **Fix:** Replaced the single test with two: (1) the 100-drops-one-window case, now only
  asserting exactly one log record fires and `stats.dropped` reaches 100 (both true and
  honestly provable); (2) a new two-window test proving the actually-meaningful "cumulative,
  not delta" property from decision 4 — after an interval elapses, the next window's single
  log line already reports the FULL total including everything the prior window silently
  dropped (`51`, not `"+1"`), which is provable synchronously and reflects real handler
  behavior.
- **Files modified:** `sdk/tests/test_sender_bounded_drop.py`
- **Verification:** `cd sdk && python3 -m pytest -q tests/test_sender_bounded_drop.py` — all
  16 tests pass
- **Committed in:** `d6d914a` (test-only commit, before the `43a7289` GREEN commit)

---

**Total deviations:** 2 auto-fixed (both Rule 1 — a hygiene-grep substring bug and a
self-caught test-design bug). Both were caught and fixed before their respective GREEN
commits; neither changed the plan's public interfaces or behavior contract.
**Impact on plan:** No scope creep. The sender's logging *behavior* is unchanged from what
decision 4 specifies (leading-edge rate limit, cumulative not delta) — only my own test's
assertion of that behavior was corrected to be honestly provable.

## Issues Encountered

None beyond the two self-caught deviations above. The worktree's branch/base was already
correct at session start (no `git reset --hard` was needed this time, unlike 34-01's
worktree-drift issue).

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

`errors.py`, `values.py`, `transport.py`, and `sender.py` are ready for the parallel-wave
plans (34-03 `heartbeat.py`/`reconnect.py`, 34-04 `commands.py`) and for plan 34-06's client
assembly, which is expected to:
- Increment `SenderStats.sent` after each `transport.send()` call actually succeeds, and set
  `SenderStats.abandoned` inside its own `close()` for whatever is still queued at shutdown
  (both left as plain, writable counters by this plan, per the ownership split documented
  above).
- Add `as_scalar` to `mics_link.__all__` (per the 34-02-PLAN.md amendment, this is
  explicitly plan 34-06's responsibility, not this plan's).
- Call `selfcheck()` (from plan 34-01) at its one call site inside `connect()`.
- Wire `ZmqTransport`'s default `socket_factory`/`context_factory` in production and inject
  `fake_socket_factory`/`FakeTransport` from `sdk/tests/fake_transport.py` in its own tests.

`sdk/tests/fake_transport.py` is the shared substitute every later plan's non-codec tests
should import rather than re-implementing a fake socket/transport. No blockers.

---
*Phase: 34-mics-link-sdk-client-package*
*Completed: 2026-08-30*

## Self-Check: PASSED

All 8 claimed files verified present on disk. All 7 task commits
(`1f38634`, `3616ae1`, `2575ff1`, `1a9298c`, `11bcd8e`, `d6d914a`, `43a7289`) verified
present in `git log`.
