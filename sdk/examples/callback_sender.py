"""Callback / push shape MICS-Link sender.

Many vendor acquisition and inference SDKs do not hand you a loop. They call YOUR
function, on THEIR thread, once per sample, and often expect their own value handed
straight back. This example shows the three load-bearing rules for that shape (see
sdk/README.md section 5, "A working sender"):

  1. The client is created OUTSIDE the callback and OUTLIVES it -- the `with` block owns
     the lifetime; the callback only borrows `link`.
  2. The callback returns whatever its host expects -- never swallow the return value.
  3. Per-callback state (deadbands, last-values, ...) lives on the callback object, not
     in the SDK -- decimation and rate policy are the caller's, not mics_link's.

Never open a client INSIDE a callback, and never rely on a library's teardown hook to
close it -- some hosts have no guaranteed teardown, so a client created inside a callback
object's constructor may never be closed.

This file is exempt from sdk/examples/ten_line_sender.py's ten-line bar (only that file
is counted) but is still syntax-checked and still checked against mics_link.__all__.
"""
from mics_link import connect
from mics_link.values import as_scalar


def run_my_acquisition(callback):
    """Placeholder for a vendor SDK that calls `callback(value)` on its own thread, once
    per sample, and expects the same value handed back. Not part of mics_link."""
    return [callback(sample) for sample in ()]


with connect("132.77.72.28", 5599, "demo") as link:

    def on_sample(value):  # your library calls this, on its own thread
        link.send_signal("left_paw_x", as_scalar(value))
        return value  # hand the host back what it expects

    run_my_acquisition(on_sample)
