"""CMP-17: the single pin -> toolkit_default -> stable -> active -> none resolution chain for
hardware-lib versions. Every site that decides which `source_code` is written to disk (dispatch),
exec'd on the Pi (orchestrator), or introspected for the FDA editor (hw_introspect) must call
into this module instead of re-deriving the chain — that was CMP-17's actual bug: `toolkit_dispatch.
get_dispatch_spec` and `orchestrator_station._send_hardware_libs_if_needed` each had their OWN
pin -> active_version_id chain, neither of which ever consulted the promoted `stable_version_id`,
and a stable-less unvalidated active version was silently dropped with only a log warning.

DEVIATION from CONTEXT's literal pin -> toolkit_default -> stable -> nothing-deployable chain
(see 23-05-PLAN.md objective): this resolver adds a FOURTH rung -- the active version, but ONLY
when its own `state` is 'beta' or 'stable' -- before giving up. Implemented literally, any lib
with no promoted stable version would stop dispatching entirely, breaking every existing
backend-authored toolkit on the rig (MPR121/TOUCH_INT and every task def using them, none of
which have been promoted to stable yet). The active rung is strictly better than today's
behaviour (it adds the missing stable rung, and turns a silent drop into a reported 'none'
reason instead of vanishing the module) and introduces zero regression versus today. Do not
remove this rung without first re-plumbing every existing toolkit's libs through the promotion
workflow.

Same no-connection posture as `api/hw_introspect.py`: every function here takes a caller-owned
`db` (raw SQLAlchemy Session, ORM or DI-provided) and issues its own `sqlalchemy.text()` queries.
"""
from sqlalchemy import text

RESOLUTION_REASONS = ("pin", "toolkit_default", "stable", "active", "none")


def resolve_lib_version_id(
    db,
    lib_id: int,
    toolkit_id: int | None = None,
    pinned_version_id: int | None = None,
) -> tuple[int | None, str]:
    """Resolve which `hardware_lib_versions.id` to use for `lib_id`, and why.

    Chain: pin -> toolkit_default -> stable -> active (only if state is beta/stable) -> none.
    """
    if pinned_version_id:
        return pinned_version_id, "pin"

    if toolkit_id is not None:
        link_row = db.execute(
            text(
                "SELECT default_version_id FROM toolkit_hardware_libs"
                " WHERE toolkit_id = :tid AND hardware_lib_id = :lib_id"
            ),
            {"tid": toolkit_id, "lib_id": lib_id},
        ).fetchone()
        if link_row and link_row.default_version_id:
            return link_row.default_version_id, "toolkit_default"

    lib = db.execute(
        text("SELECT stable_version_id, active_version_id FROM hardware_libs WHERE id = :id"),
        {"id": lib_id},
    ).fetchone()
    if not lib:
        return None, "none"

    if lib.stable_version_id:
        return lib.stable_version_id, "stable"

    if lib.active_version_id:
        version = db.execute(
            text("SELECT state FROM hardware_lib_versions WHERE id = :id"),
            {"id": lib.active_version_id},
        ).fetchone()
        if version and version.state in ("beta", "stable"):
            return lib.active_version_id, "active"

    return None, "none"


def resolve_lib_versions(
    db,
    lib_ids: list[int],
    toolkit_id: int | None = None,
    pinned: dict | None = None,
) -> dict[int, tuple[int | None, str]]:
    """Batch form of `resolve_lib_version_id` -- one call per lib_id, same chain.

    `pinned` maps lib_id -> pinned_version_id (e.g. a task definition's `hw_lib_versions` dict).
    """
    pinned = pinned or {}
    return {
        lib_id: resolve_lib_version_id(
            db, lib_id, toolkit_id=toolkit_id, pinned_version_id=pinned.get(lib_id),
        )
        for lib_id in lib_ids
    }
