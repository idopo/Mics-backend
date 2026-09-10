"""FrameReader -- the camera reader thread that fills a LatestSlot, with the cv2
capture injected (D-52, D-55).

**`cv2` is not imported here.** The constructor takes a `read` callable (in production
`cap.read`; in tests a fake returning queued `(ok, frame)` pairs), so this module is
importable and testable on a host with no cv2, no dlclive and no camera -- exactly the
dev host this whole package targets.

`read_retries` and the terminal-on-failure policy come from `dlc_link.source` (D-55): a
file's failed read is end-of-file and ends the run on the first failure; a camera's is a
hiccup, retried a bounded number of times before the run gives up. A `read()` that raises
is caught, counted, and treated as a failed read -- a driver hiccup must not kill the
thread silently and leave the main loop waiting forever.

`FrameReader` never calls `release()` on the capture it was given -- the caller's
`finally` owns that, exactly as `run_video_loop` never closes `link`. It never touches
`link` either.
"""
import threading
import time


class FrameReader(threading.Thread):
    """A `threading.Thread` that calls `read()` in a loop and puts every successfully
    read frame into `slot`. `terminal_on_failure=True` (a file source) stops the reader
    on the first failed read; `False` (a camera/stream source) retries up to
    `read_retries` consecutive failures before giving up."""

    def __init__(
        self, read, slot, terminal_on_failure, read_retries=5, retry_interval_s=0.05,
        sleep=time.sleep,
    ):
        super().__init__(daemon=True)
        self._read = read
        self._slot = slot
        self._terminal_on_failure = terminal_on_failure
        self._read_retries = read_retries
        self._retry_interval_s = retry_interval_s
        self._sleep = sleep
        self._stop_flag = threading.Event()
        self._consecutive_failures = 0

        self.frames_read = 0
        self.read_failures = 0
        self.read_exceptions = 0
        self.stopped_reason = None

    def run(self):
        while not self._stop_flag.is_set():
            try:
                ok, frame = self._read()
            except Exception:
                self.read_exceptions += 1
                ok, frame = False, None

            if ok:
                self._slot.put(frame)
                self.frames_read += 1
                self._consecutive_failures = 0
                continue

            self.read_failures += 1
            if self._terminal_on_failure:
                self.stopped_reason = "end-of-stream"
                return

            self._consecutive_failures += 1
            if self._consecutive_failures >= self._read_retries:
                self.stopped_reason = "read-failures-exhausted"
                return
            self._sleep(self._retry_interval_s)

        self.stopped_reason = "stopped"

    def stop(self):
        """Idempotent: calling it twice, or calling it before `start()`, raises
        nothing -- the loop in `run()` simply checks the flag on its next iteration."""
        self._stop_flag.set()

    def snapshot(self):
        """Counts and one reason string, plus the slot's own snapshot nested under
        `slot`. Nothing else."""
        return {
            "frames_read": self.frames_read,
            "read_failures": self.read_failures,
            "read_exceptions": self.read_exceptions,
            "stopped_reason": self.stopped_reason,
            "slot": self._slot.snapshot(),
        }
