"""D-42's `--probe-pose` implementation, split out of `dlc_link.live` to keep that module
under the project's 300-line production-file limit (same split precedent as
`dlc_link.generate`/`generate_cli`, plan 35-03). `compare_pose_order` and
`check_corner_geometry` are imported FROM `dlc_link.live` rather than duplicated -- the
pure verdict logic has exactly one home; this module is orchestration around it.

Never imports `cv2` or `dlclive` at module scope: `dclive_cls` and `cap` are handed in
by `dlc_link.live.main()`, which has already done those deferred imports.

**D-62: `smap` may be `None`.** `--probe-pose` no longer requires `--signal-map` (the
argparse/validation half of this lives in `live_cli_args.py`), so the chicken-and-egg
9c defect (`35-HARDWARE-VALIDATION.md` §9c) is closed: probe first, read the row count
and order off the screen, paste the printed `--pose-order` line into
`dlc-link-generate`, then re-probe WITH the generated map to confirm `row_count_match`.
With no map there is nothing to compare against, so the `POSE_ORDER`/`VERDICT` lines are
skipped entirely rather than printed against nothing.
"""
import statistics

from dlc_link.live import _CORNERS, check_corner_geometry, compare_pose_order

_POSE_ORDER_ATTR_CANDIDATES = ("cfg", "dlc_config", "pose_cfg")
_COLUMN_LABELS = {0: "x", 1: "y", 2: "likelihood"}
_UNCHARACTERISED = "uncharacterised - nothing in this package reads this column"


def _median_corner_measurements(samples):
    """`samples`: `{corner: [(x, y, likelihood), ...]}` across N frames. Returns
    `{corner: (median_x, median_y, median_likelihood)}` -- the per-axis MEDIAN, never the
    mean (sensitive to one bad frame) nor the last frame (arbitrary). Pure."""
    aggregated = {}
    for corner, measurements in samples.items():
        xs = [m[0] for m in measurements]
        ys = [m[1] for m in measurements]
        likelihoods = [m[2] for m in measurements]
        aggregated[corner] = (
            statistics.median(xs),
            statistics.median(ys),
            statistics.median(likelihoods),
        )
    return aggregated


def _discover_pose_order(live):
    """Search `live` for the bodypart-ordering attribute it exposes. Returns
    `(attr_name, order)` or `(None, None)`. This is what DLC-Live SAYS it does, not what
    it DID on this frame -- `check_corner_geometry` is the runtime proof for that gap."""
    for attr_name in _POSE_ORDER_ATTR_CANDIDATES:
        value = getattr(live, attr_name, None)
        if value is None:
            continue
        if isinstance(value, dict) and "all_joints_names" in value:
            return attr_name, list(value["all_joints_names"])
        names = getattr(value, "all_joints_names", None)
        if names:
            return attr_name, list(names)
    return None, None


def _print_row0_columns(row0):
    """Print every column of row 0, labelling 0/1/2 as x/y/likelihood and everything
    beyond as uncharacterised (35-HARDWARE-VALIDATION.md §4: DLC-Live's docs say
    `(num_bodyparts, 3)`, the rig observed 5). Measures the next model's array instead
    of assuming it carries the same shape."""
    print("row 0, every column (35-HARDWARE-VALIDATION.md Sec4: docs say 3, rig saw 5):")
    for col_idx, value in enumerate(row0):
        label = _COLUMN_LABELS.get(col_idx, _UNCHARACTERISED)
        print("  column [{}] ({}): {!r}".format(col_idx, label, value))


def _print_pose_order_line(discovered_order, row_count):
    """The paste-ready `--pose-order` line `dlc-link-generate` takes verbatim. When no
    ordering was discovered, the placeholder names POSITIONS, never bodypart names --
    pasting a position as though it were a name sends the WRONG keypoint's numbers out
    under the RIGHT signal name, silently, because nothing about that failure looks
    broken."""
    if discovered_order is not None:
        print("--pose-order {}".format(",".join(discovered_order)))
        return
    placeholder = ",".join("row_{}".format(i) for i in range(row_count))
    print("--pose-order {}".format(placeholder))
    print(
        "NOTE: row_0,row_1,... are POSITIONS, not names. Bodypart ordering was not "
        "discoverable from this runner, so the names above must come from your own "
        "project's config.yaml -- never assumed from position."
    )


def run_probe_pose(args, smap, dclive_cls, cap, first_frame, width, height):
    """D-42's probe: never connects to the Pi, sends nothing. Reads the first frame(s),
    prints pose shape/ordering/POSE_ORDER, then runs the corner-geometry assertion."""
    live = dclive_cls(
        args.model_path, model_type="pytorch", single_animal=True, resize=args.resize,
        display=False,  # D-47: pinned explicitly, never left to DLCLive's own default.
    )
    pose = live.init_inference(first_frame)
    print("pose.shape: {!r}".format(getattr(pose, "shape", (len(pose),))))
    print("pose row count: {}".format(len(pose)))

    attr_name, discovered_order = _discover_pose_order(live)
    if discovered_order is not None:
        print("bodypart ordering found under attribute: {}".format(attr_name))
        print("discovered order: {!r}".format(discovered_order))
    else:
        print(
            "bodypart ordering: NOT FOUND (tried attributes: {})".format(
                ", ".join(_POSE_ORDER_ATTR_CANDIDATES)
            )
        )

    # D-62: these two lines, and the VERDICT below, are the only output that depends on
    # a --signal-map having been given -- with no map there is nothing to compare.
    if smap is not None:
        print("signal map POSE_ORDER: {!r}".format(list(smap.POSE_ORDER)))
        print("signal map POSE_ORDER_SOURCE: {!r}".format(smap.POSE_ORDER_SOURCE))

    for i in range(len(pose)):
        label = discovered_order[i] if discovered_order and i < len(discovered_order) else "row_{}".format(i)
        x, y, likelihood = pose[i][0], pose[i][1], pose[i][2]
        print("  [{}] {}: x={:.4f} y={:.4f} likelihood={:.4f}".format(
            i, label, x / width, y / height, likelihood
        ))

    _print_row0_columns(pose[0])
    _print_pose_order_line(discovered_order, len(pose))
    print(
        "next: dlc-link-generate --config <your config.yaml> --source-id <your id> "
        "--bodyparts <...> --pose-order <the line above> --out-dir <outside the "
        "project> -- writes exactly two files into --out-dir, nothing else"
    )

    if smap is not None:
        verdict, message = compare_pose_order(list(smap.POSE_ORDER), discovered_order)
        print("VERDICT: row_count_match={} ordering={} -- {}".format(
            len(pose) == len(smap.POSE_ORDER), verdict, message
        ))

    parts = [p.strip() for p in args.geometry_parts.split(",") if p.strip()]
    if discovered_order is None:
        print("CORNER GEOMETRY: UNAVAILABLE -- bodypart ordering was not discovered")
        return 0

    samples = {part: [] for part in parts}

    def _collect(one_pose):
        for part in parts:
            if part in discovered_order:
                idx = discovered_order.index(part)
                row = one_pose[idx]
                samples[part].append((row[0] / width, row[1] / height, row[2]))

    _collect(pose)
    for _ in range(max(0, args.geometry_frames - 1)):
        ok, frame = cap.read()
        if not ok:
            break
        _collect(live.get_pose(frame))

    missing_parts = [p for p in parts if not samples[p]]
    if missing_parts:
        print("CORNER GEOMETRY: UNAVAILABLE -- {} not in the discovered pose order".format(missing_parts))
        return 0

    aggregated = _median_corner_measurements(samples)
    positions = {corner: (vals[0], vals[1]) for corner, vals in aggregated.items()}
    likelihoods = {corner: vals[2] for corner, vals in aggregated.items()}
    for corner in parts:
        print("  corner {}: x={:.4f} y={:.4f} likelihood={:.4f}".format(
            corner, positions[corner][0], positions[corner][1], likelihoods[corner]
        ))

    if set(parts) >= set(_CORNERS):
        verdict, message = check_corner_geometry(
            positions, likelihoods, args.geometry_margin, args.geometry_min_likelihood
        )
        print("CORNER GEOMETRY: {} -- {}".format(verdict, message))
        print(
            "LIMIT: pins the ordering at four positions only; a permutation leaving all "
            "four corners in place (e.g. swapping LED_on with LED_off) still passes it. "
            "Plan 35-07 Task 3's temporal check against the operator's own LED actions "
            "is the complement, not a superset."
        )
    else:
        print("CORNER GEOMETRY: UNAVAILABLE -- --geometry-parts does not cover NW,NE,SE,SW")
    return 0
