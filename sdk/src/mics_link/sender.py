"""Bounded drop-NEWEST send queue (Phase 34, Plan 02, Task 3).

THREADLESS BY DESIGN (decision 3): this is a bounded queue plus drop accounting, nothing
more. ZMQ sockets are not thread-safe and exactly one thread may touch the socket; plan
34-06's client runs a single IO thread that `pop()`s from this queue and calls
`transport.send`. Putting a thread HERE would create a SECOND socket-toucher. Do not "fix"
this back into an `EgressWorker` clone (`external_hardware_runtime.py`) — that shape is
right for the Pi's one-worker-per-device ingress, wrong here.

The drop POLICY still mirrors `EgressWorker.enqueue` (`external_hardware_runtime.py:44-56`)
verbatim: `put_nowait` in a `try`, `queue.Full` -> `dropped += 1`, rate-limited log, guarded
`on_drop`, `return False`. `queue.Queue(maxsize=N)` is used deliberately — NOT a
bounded-`collections.deque`, whose eviction rule discards the OLDEST item on overflow
(34-RESEARCH.md "Don't Hand-Roll"); SDK-06 requires the NEWEST frame to be the one dropped,
and only `queue.Queue` + `put_nowait`/`queue.Full` expresses that natively.

No retry, ever: a retried frame lands at the wrong timestamp (EXTLINK-15's reasoning,
carried over to the sender side).

`stats.sent` and `stats.abandoned` are plain counters this module never writes to — plan
34-06's IO thread increments `sent` after a `transport.send()` actually succeeds, and its
`close()` sets `abandoned` for whatever is still queued at shutdown. `BoundedSender` only
knows about `enqueued`/`dropped`, the two counts a bounded queue can prove by itself.

`enqueued`/`dropped` are incremented under a small lock (34-06 addition, SDK-15): plan
34-06's `send_signal`/`send_event` are called from a FOREIGN library's callback thread at
frame rate, and `queue.Queue.put_nowait` being thread-safe does not make a bare
`self.stats.enqueued += 1` afterward thread-safe too — a compound read-modify-write on a
plain attribute can lose an update when two threads race it. `record_external_drop()` is
the one seam plan 34-06's `close()`-rejected sends use to record a drop that never reaches
`enqueue()` at all, through the same lock.

`stats.send_failed` (34-review CR-01 fix): a frame this module already handed off — it left
the bounded queue via `pop()` — is a DIFFERENT event than a `dropped` frame, which never
left the queue at all (backpressure, still sitting behind a full `maxsize`). A frame that
`transport.send()` raised on was attempted and lost, not refused for capacity reasons; the
distinct counter keeps that failure mode countable rather than folding it into a `dropped`
number whose meaning ("the queue was full") would then be wrong. `record_send_failure()` is
the one seam plan 34-06's IO thread uses when `transport.send()` raises, through the same
lock as every other counter here.
"""
import logging
import queue
import threading
import time


class SenderStats(object):
    """Plain, readable counters (CONTEXT.md: "a readable counter") a caller can print."""

    def __init__(self):
        self.enqueued = 0
        self.sent = 0
        self.dropped = 0
        self.abandoned = 0  # set by plan 34-06's close()
        self.send_failed = 0  # a dequeued frame transport.send() raised on (34-review CR-01)

    def snapshot(self):
        return {
            "enqueued": self.enqueued,
            "sent": self.sent,
            "dropped": self.dropped,
            "abandoned": self.abandoned,
            "send_failed": self.send_failed,
        }


def should_log_drop(last_log_at, now, interval_s):
    """Pure: True iff a drop-log line should be emitted now. `last_log_at is None` means
    "never logged yet", which is always True — decision 4's "a suppressed burst is never
    invisible" starts counting from the FIRST drop, not after a full interval has elapsed.
    """
    if last_log_at is None:
        return True
    return (now - last_log_at) >= interval_s


class BoundedSender(object):
    """THREADLESS by design — see module docstring. `enqueue` never blocks and never
    raises; a saturated queue drops the NEWEST frame (the one just offered), increments
    `stats.dropped`, logs at most once per `drop_log_interval_s` (reporting the CUMULATIVE
    dropped count), and calls an optional `on_drop` callback whose exceptions are swallowed
    (decision 5 — no exception from a researcher's own callback may reach their loop).
    """

    def __init__(
        self,
        maxsize=256,
        on_drop=None,
        log=True,
        logger=None,
        drop_log_interval_s=5.0,
        clock=time.monotonic,
    ):
        self._queue = queue.Queue(maxsize=maxsize)
        self._on_drop = on_drop
        self._log = log
        self._logger = logger if logger is not None else logging.getLogger("mics_link")
        self._drop_log_interval_s = drop_log_interval_s
        self._clock = clock
        self._last_log_at = None
        self._stats_lock = threading.Lock()
        self.stats = SenderStats()

    def enqueue(self, frame):
        """Never blocks, never raises. Returns `False` (and records the loss) when the
        queue is full — the dropped item is always the NEWEST one just offered, never one
        already queued.
        """
        try:
            self._queue.put_nowait(frame)
        except queue.Full:
            self._record_drop()
            self._maybe_log_drop()
            self._fire_on_drop(frame)
            return False
        with self._stats_lock:
            self.stats.enqueued += 1
        return True

    def record_external_drop(self):
        """Thread-safe increment of `stats.dropped` for a send that never reaches
        `enqueue()` at all — e.g. a closed `MicsLink` rejecting `send_signal` before it
        touches the queue. Uses the same lock as `enqueue()`'s own drop path so the two
        can never race each other's read-modify-write.
        """
        self._record_drop()

    def record_send_failure(self):
        """Thread-safe increment of `stats.send_failed` for a frame that already left the
        bounded queue (via `pop()`) but that `transport.send()` then raised on (34-review
        CR-01) — an attempted-and-lost send, not a capacity-refused `dropped` one. Uses the
        same lock as every other counter here.
        """
        with self._stats_lock:
            self.stats.send_failed += 1

    def _record_drop(self):
        with self._stats_lock:
            self.stats.dropped += 1

    def _maybe_log_drop(self):
        if not self._log:
            return
        now = self._clock()
        if should_log_drop(self._last_log_at, now, self._drop_log_interval_s):
            self._last_log_at = now
            self._logger.warning(
                "mics_link: dropped a frame (queue full) - %d dropped total",
                self.stats.dropped,
            )

    def _fire_on_drop(self, frame):
        if self._on_drop is None:
            return
        try:
            self._on_drop(frame)
        except Exception:
            pass

    def pop(self, timeout=0.1):
        """The next queued frame for the IO thread to hand to `transport.send`, or `None`
        if nothing arrives within `timeout` seconds. Never raises, never blocks forever.
        """
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def pending(self):
        return self._queue.qsize()
