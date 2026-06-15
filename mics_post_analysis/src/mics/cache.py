"""Per-session pickle cache for expensive intermediates (events, aligned DF, spikes).

Used by later phases. Cache lives under ``./cache/<key>/`` (gitignored).
"""

from __future__ import annotations

import pickle
from pathlib import Path
from typing import Callable, TypeVar

T = TypeVar("T")

CACHE_ROOT = Path("cache")


def cache_dir(key: str) -> Path:
    d = CACHE_ROOT / key
    d.mkdir(parents=True, exist_ok=True)
    return d


def cached_pickle(key: str, name: str, build_fn: Callable[[], T], force: bool = False) -> T:
    """Return ``<cache>/<key>/<name>.pkl``, building + caching it on first use.

    Pass ``force=True`` to rebuild and overwrite.
    """
    path = cache_dir(key) / f"{name}.pkl"
    if path.exists() and not force:
        with path.open("rb") as fh:
            return pickle.load(fh)
    value = build_fn()
    with path.open("wb") as fh:
        pickle.dump(value, fh)
    return value
