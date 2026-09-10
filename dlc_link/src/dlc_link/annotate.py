"""Pure pose -> draw-primitive planning (D-60, D-61).

**No cv2, no numpy, no PIL, at module scope or anywhere in this module.** This file
computes WHAT to draw; plan 38-03 executes the resulting primitives with whatever
rendering library is available on the runtime host. That split is what makes the
drawing decisions testable on a dev host with nothing installed -- the same trap
`35-04` avoided by keeping `cv2` and `dlclive` behind deferred imports in
`dlc_link.processor`.

**Pixel/normalised convention, mirrored from `dlc_link.processor.DLCProcessor.process`
(`processor.py:105-116`), never re-derived:** pose x/y are PIXELS in the (possibly
resized) frame; the SIGNAL values this package sends over the wire are normalised
0..1. `build_draw_plan` reads columns 0 (x), 1 (y), 2 (likelihood) of each declared
row and NOTHING else -- `35-HARDWARE-VALIDATION.md` §4 records that the observed pose
array has five columns whose last two are uncharacterised. The pixel<->normalised
conversion for overlay thresholds happens in exactly ONE place below, with a comment
naming both conventions, because mixing them is the single likeliest bug in this
module.

**D-61: nothing here hardcodes a row count or a bodypart name.** `build_draw_plan`
iterates `signal_map.SIGNALS` -- never a fixed bodypart list, never a fixed row
count -- so a future unique-bodypart-head reader that changes only the row count needs
no change here. A declared row index beyond the pose length is appended to
`problems`, never raised: that is what a future model, or a mismatched map, will look
like, and it must stay visible in a viewer rather than fatal.
"""
from dataclasses import dataclass, field
from typing import Optional

from dlc_link.overlay import evaluate

# Colour-blind-safe pair (Wong 2011 palette): blue for CONFIDENT, orange for
# UNCONFIDENT, deliberately NOT the red/green pair that is indistinguishable under
# red-green colour blindness. Colours are BGR tuples (cv2's convention) even though
# this module never imports cv2 -- the renderer in plan 38-03 consumes them as-is.
CONFIDENT = {"color": (189, 114, 0), "radius": 6, "thickness": 2}  # Wong blue, BGR
UNCONFIDENT = {"color": (0, 158, 230), "radius": 6, "thickness": 1}  # Wong orange, BGR


@dataclass(frozen=True)
class DrawPrimitive:
    """One drawing instruction. Only the fields its `kind` needs are populated; all
    coordinates are `int` pixel values -- nothing float reaches the renderer."""

    kind: str  # "circle" | "text" | "line"
    color: Optional[tuple] = None
    # circle
    center: Optional[tuple] = None
    radius: Optional[int] = None
    thickness: Optional[int] = None
    # text
    text: Optional[str] = None
    position: Optional[tuple] = None
    # line
    start: Optional[tuple] = None
    end: Optional[tuple] = None


@dataclass
class DrawPlan:
    primitives: list = field(default_factory=list)
    problems: list = field(default_factory=list)


def _style_for(likelihood, min_likelihood):
    return CONFIDENT if likelihood >= min_likelihood else UNCONFIDENT


def _threshold_line(clause, frame_width, frame_height):
    """One `_x` or `_y` overlay clause -> a line primitive at its threshold, scaled
    from the clause's NORMALISED 0..1 value (the FDA's convention) into PIXELS (the
    frame's convention) -- the one conversion site this module has for overlay
    thresholds. A likelihood clause has no position and returns nothing."""
    if clause.signal.endswith("_x"):
        threshold_px = int(clause.value * frame_width)
        return DrawPrimitive(kind="line", start=(threshold_px, 0), end=(threshold_px, int(frame_height)))
    if clause.signal.endswith("_y"):
        threshold_px = int(clause.value * frame_height)
        return DrawPrimitive(kind="line", start=(0, threshold_px), end=(int(frame_width), threshold_px))
    return None


def build_draw_plan(
    pose,
    signal_map,
    frame_width,
    frame_height,
    min_likelihood,
    overlay_clauses=None,
    overlay_values=None,
):
    """Compute the full draw plan for one pose row against one frame.

    Iterates `signal_map.SIGNALS` -- never a hardcoded bodypart list, never a
    hardcoded row count (D-61) -- so the identical code path produces a plan for a
    3-row pose and a 14-row pose alike. Reads columns 0/1/2 of each row and nothing
    else; see the module docstring for why.
    """
    plan = DrawPlan()

    for bodypart, entry in signal_map.SIGNALS.items():
        index = entry["index"]
        if index >= len(pose):
            plan.problems.append(
                "{}: declared row index {} exceeds pose length {}".format(
                    bodypart, index, len(pose)
                )
            )
            continue

        row = pose[index]
        x_px, y_px, likelihood = row[0], row[1], row[2]
        style = _style_for(likelihood, min_likelihood)

        if entry["coords"]:
            center = (int(x_px), int(y_px))
            plan.primitives.append(
                DrawPrimitive(
                    kind="circle",
                    center=center,
                    color=style["color"],
                    radius=style["radius"],
                    thickness=style["thickness"],
                )
            )
            label_position = center
        else:
            # No coords declared: likelihood is all that exists. No marker, label
            # only, anchored at the frame origin since there is no position to
            # anchor it to.
            label_position = (0, 0)

        plan.primitives.append(
            DrawPrimitive(
                kind="text",
                text="{} {:.3f}".format(bodypart, likelihood),
                position=label_position,
                color=style["color"],
            )
        )

    if overlay_clauses:
        for clause in overlay_clauses:
            line = _threshold_line(clause, frame_width, frame_height)
            if line is None:
                # A likelihood clause has no position and contributes no line.
                continue
            plan.primitives.append(line)
            plan.primitives.append(
                DrawPrimitive(kind="text", text=clause.text, position=line.start)
            )

    if overlay_clauses and overlay_values is not None:
        overall, _ = evaluate(overlay_clauses, overlay_values)
        plan.primitives.append(
            DrawPrimitive(
                kind="text",
                text="condition: {}".format("HOLDS" if overall else "does not hold"),
                position=(0, 0),
            )
        )
        # Not optional, not abbreviated (D-60): this is what stops the viewer from
        # being mistaken for the FDA's own ground truth.
        plan.primitives.append(
            DrawPrimitive(
                kind="text",
                text="overlay: authored locally, not read from the task definition",
                position=(0, 0),
            )
        )

    return plan
