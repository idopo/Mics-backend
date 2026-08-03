"""Idempotent seeding of the Compute Ops lib -- the seed `hardware_libs`/`hardware_lib_versions`/
`hardware_modules` rows a fresh DB needs before any `compute` action can resolve on the Pi.

`COMPUTE_STDLIB_ALLOWLIST` is the single source of truth `routers.hardware_libs._validate_compute_lib`
imports at upload-time (CMP-19): a declared import outside this set is rejected with a message
naming the offender + this allowlist -- third-party packages are deferred pending per-Pi package
management.

Runs at api startup (`main.py`, alongside the migration block), raw SQL inside one
`engine.begin()` transaction -- this executes before the session factories are used, matching the
shape of every `run_*_migration` function in `db.py`. Wrapped in try/except: a seeding failure
must never stop the API from booting.
"""
import json
import logging
from datetime import datetime
from pathlib import Path

from sqlalchemy import text as sa_text

from routers.hardware_libs import extract_ast_metadata, sha256

logger = logging.getLogger(__name__)

COMPUTE_STDLIB_ALLOWLIST = {
    "random", "math", "statistics", "itertools", "functools", "collections",
}

SEED_LIB_FILENAME = "compute_ops.py"
SEED_MODULE_NAME = "COMPUTE"
SEED_CLASS_NAME = "ComputeOps"


def seed_compute_ops_lib(engine) -> dict:
    """Idempotent. Returns {"created": bool, "lib_id"?, "version_id"?, "module_id"?, "error"?}."""
    try:
        with engine.begin() as conn:
            existing = conn.execute(
                sa_text("SELECT id FROM hardware_libs WHERE filename = :f"),
                {"f": SEED_LIB_FILENAME},
            ).fetchone()
            if existing:
                return {"created": False}

            source_code = (Path(__file__).parent / "seed_libs" / SEED_LIB_FILENAME).read_text()
            ast_metadata = extract_ast_metadata(source_code)
            now = datetime.utcnow()

            lib_id = conn.execute(
                sa_text(
                    "INSERT INTO hardware_libs (name, filename, ast_metadata, kind, created_at, updated_at) "
                    "VALUES (:name, :filename, :ast_metadata, 'compute', :now, :now) RETURNING id"
                ),
                {
                    "name": "Compute Ops",
                    "filename": SEED_LIB_FILENAME,
                    "ast_metadata": json.dumps(ast_metadata),
                    "now": now,
                },
            ).scalar()

            version_id = conn.execute(
                sa_text(
                    "INSERT INTO hardware_lib_versions "
                    "(hardware_lib_id, version_number, source_code, sha256_hash, state, "
                    "ast_metadata, declared_imports, created_at, stable_at, stable_reason) "
                    "VALUES (:lib_id, 1, :source, :sha, 'stable', :ast_metadata, :imports, "
                    ":now, :now, 'seed') RETURNING id"
                ),
                {
                    "lib_id": lib_id,
                    "source": source_code,
                    "sha": sha256(source_code),
                    "ast_metadata": json.dumps(ast_metadata),
                    "imports": json.dumps(["random"]),
                    "now": now,
                },
            ).scalar()

            conn.execute(
                sa_text(
                    "UPDATE hardware_libs SET active_version_id = :v, stable_version_id = :v "
                    "WHERE id = :lib_id"
                ),
                {"v": version_id, "lib_id": lib_id},
            )

            module_id = conn.execute(
                sa_text(
                    "INSERT INTO hardware_modules (name, display_name, hardware_lib_id, class_name, created_at) "
                    "VALUES (:name, :display_name, :lib_id, :class_name, :now) RETURNING id"
                ),
                {
                    "name": SEED_MODULE_NAME,
                    "display_name": "Compute Ops",
                    "lib_id": lib_id,
                    "class_name": SEED_CLASS_NAME,
                    "now": now,
                },
            ).scalar()

        return {"created": True, "lib_id": lib_id, "version_id": version_id, "module_id": module_id}
    except Exception as e:
        logger.warning("seed_compute_ops_lib failed: %s", e)
        return {"created": False, "error": str(e)}
