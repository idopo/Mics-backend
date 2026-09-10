"""The paced video-loop core and its pure verdict helpers (D-29, D-30, D-42, D-47,
D-51, D-53, D-55).

`run_video_loop` IS the live pipeline with a file OR a camera substituted for the frame
source: pacing at the video's native fps (file) or running unpaced against a camera's
own delivery rate is what makes `stale_after_ms` exercised on the same timebase a real
camera will produce. `cv2` and `dlclive` are NEVER imported here -- the CLI that does
those deferred imports and all the source-specific wiring lives in `dlc_link.live_cli`
(split out, same precedent as `dlc_link.generate`/`generate_cli`, so this module and its
pure functions (`run_video_loop`, `compare_pose_order`, `check_corner_geometry`) stay
importable and testable with neither library installed.

`_CORNERS`, `check_corner_geometry` and `compare_pose_order` stay in THIS module rather
than moving to `live_cli` because `dlc_link.live_probe` imports all three FROM here --
moving them would break that import.

**D-47: this tool writes NOTHING, anywhere, by default.** No log file, no stats file,
no cache, no DLC-Live output artefact, no temporary file beside the video or the model.
Every count goes to stdout. See `dlc_link.live_cli` for the `display=False` pin and the
full rationale -- this module has no knowledge of `DLCLive` at all.
"""
import sys
import time

__all__ = ["run_video_loop", "main", "compare_pose_order", "check_corner_geometry"]

_CORNERS = ("NW", "NE", "SE", "SW")


def run_video_loop(
    link, frames, infer, processor, pacer, fps, max_frames=None, should_stop=None,
    observer=None, max_seconds=None, clock=time.monotonic,
):
    """Drive `infer(frame)` once per frame from `frames`. `link` is accepted for
    lifecycle parity with the caller's `with connect(...)` block but is NEVER touched
    here -- `processor` (which already owns `link`) is what actually sends.

    `pacer=None` means UNPACED: no `wait_until` call is made at all, and the returned
    `behind_count` is `None`, never `0` (D-53) -- a camera source paces itself and a
    second pacer on top would double-throttle it (D-51).

    `should_stop` (checked once per frame, before inference; `None` means never stop)
    and `max_seconds` (measured against `clock()` from this call's own start) are the
    two additional deliberate-stop mechanisms beyond `max_frames` and the iterable's own
    end (D-55) -- together with a `KeyboardInterrupt`, handled by the caller.

    `observer(frame, pose)`, when given, is called once per inferred frame with
    whatever `infer(frame)` returned, inside a `try/except Exception` that increments
    `observer_errors` in the result. **The observer may never break the run** -- that is
    the rule that lets a viewer hang off this hook without risking the experiment.

    Returns a counts-only record: `frames_read`, `frames_inferred`, `behind_count`,
    `observer_errors`, and `processor.snapshot()`. Never creates or closes `link`.
    """
    frames_read = 0
    frames_inferred = 0
    observer_errors = 0
    loop_start = clock() if max_seconds is not None else None

    for frame in frames:
        if max_frames is not None and frames_read >= max_frames:
            break
        if max_seconds is not None and (clock() - loop_start) >= max_seconds:
            break
        if should_stop is not None and should_stop():
            break

        frames_read += 1
        # D-29: dropping this ONE line is very nearly the entire change required to
        # swap in a live camera -- `pacer is None` (D-51) is how a camera tells this
        # loop it paces itself, so the line below simply never runs for one.
        if pacer is not None:
            pacer.wait_until(frames_read / fps)

        pose = infer(frame)
        frames_inferred += 1

        if observer is not None:
            try:
                observer(frame, pose)
            except Exception:
                observer_errors += 1

    return {
        "frames_read": frames_read,
        "frames_inferred": frames_inferred,
        "behind_count": pacer.behind_count() if pacer is not None else None,
        "observer_errors": observer_errors,
        "processor_snapshot": processor.snapshot(),
    }


def compare_pose_order(expected_order, observed_order):
    """Pure. `expected_order` is the signal map's `POSE_ORDER`; `observed_order` is
    whatever ordering `--probe-pose` discovered on the constructed `DLCLive` runner (or
    `None` when nothing was found). Returns `(verdict, message)`, verdict one of
    `"match"`, `"mismatch"`, `"ordering-not-discoverable"`.
    """
    if observed_order is None:
        return (
            "ordering-not-discoverable",
            "no bodypart-ordering attribute was found on the constructed DLCLive runner",
        )
    if list(expected_order) == list(observed_order):
        return "match", "POSE_ORDER matches the discovered ordering ({} entries)".format(
            len(observed_order)
        )
    if len(expected_order) != len(observed_order):
        return "mismatch", "row count differs: POSE_ORDER has {}, discovered has {}".format(
            len(expected_order), len(observed_order)
        )
    return "mismatch", "same length ({}) but different order".format(len(expected_order))


def check_corner_geometry(positions, likelihoods, margin, min_likelihood):
    """Pure geometric ordering check (T-35-16c): the four arena corners must land in
    their own quadrants, in normalised image coordinates with y increasing DOWNWARD.
    `positions`: `{"NW": (x, y), ...}`. `likelihoods`: `{"NW": float, ...}`. Returns
    `(verdict, message)`; verdict is exactly one of `PASS`/`FAIL`/`UNRELIABLE`/
    `UNAVAILABLE`.

    LIMIT, stated here and in `--probe-pose`'s printed output: this pins the ordering at
    four positions. A permutation that leaves all four corners in place but swaps two
    OTHER parts (LED_on with LED_off, say) still passes it. Plan 35-07 Task 3's
    independent temporal check against the operator's own LED actions is the complement,
    not a superset -- neither check subsumes the other.
    """
    missing = [c for c in _CORNERS if c not in positions or c not in likelihoods]
    if missing:
        return "UNAVAILABLE", "corner(s) not resolved against the discovered pose order: {}".format(
            missing
        )

    unreliable = [c for c in _CORNERS if likelihoods[c] < min_likelihood]
    if unreliable:
        details = ", ".join("{}={!r}".format(c, likelihoods[c]) for c in unreliable)
        return "UNRELIABLE", (
            "corner(s) below --geometry-min-likelihood={}: {} -- this is NOT a pass and "
            "NOT an ordering failure; the corners were not detected confidently enough "
            "to test the ordering on this frame. Re-run with --geometry-frames 30 or a "
            "different video segment.".format(min_likelihood, details)
        )

    nw, ne, se, sw = positions["NW"], positions["NE"], positions["SE"], positions["SW"]
    checks = [
        ("NW.x < NE.x", ne[0] - nw[0]),
        ("SW.x < SE.x", se[0] - sw[0]),
        ("NW.y < SW.y", sw[1] - nw[1]),
        ("NE.y < SE.y", se[1] - ne[1]),
    ]
    failures = [
        "{} holds by {:.4f}, needs >= {:.4f} margin".format(label, diff, margin)
        for label, diff in checks
        if diff < margin
    ]
    if failures:
        return "FAIL", "; ".join(failures)
    return "PASS", "all four corner inequalities hold with margin >= {}".format(margin)


def main(argv=None):
    """Thin re-export so `dlc-link-live = dlc_link.live:main` (pyproject.toml) keeps
    working; the real CLI lives in `dlc_link.live_cli` (import deferred to avoid a
    module-load-time circular import, since `dlc_link.live_probe` imports FROM this
    module and `live_cli` imports `live_probe`)."""
    from dlc_link.live_cli import main as _main

    return _main(argv)


if __name__ == "__main__":
    sys.exit(main())
