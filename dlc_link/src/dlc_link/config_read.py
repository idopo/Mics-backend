"""config.yaml / pose_cfg.yaml readers producing one BodypartSource with provenance (D-13).

Reads a researcher's DeepLabCut project configuration and resolves the THREE bodypart
sources a project may declare (D-40, correcting D-13's single-case description): the
flat `bodyparts` list (single-animal), `multianimalbodyparts` + `individuals`, and
`uniquebodyparts`. In a multi-animal (maDLC) project, `bodyparts` holds the literal
sentinel string `MULTI!`, not a list -- this module records that sentinel and never
iterates it (a naive reader would silently emit the six characters `M`, `U`, `L`, `T`,
`I`, `!` as bodyparts).

This module assigns NO pose-array index. Which parts DLC-Live actually returns under
`single_animal=True`, and in what row order, is D-42's open empirical question; the
authoritative row order arrives as an explicit `--pose-order` argument to the generator,
settled by plan 35-07's probe.
"""
import hashlib
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


class ConfigReadError(ValueError):
    """Base for structural config.yaml / pose_cfg.yaml read failures."""


class YamlBackendMissingError(ConfigReadError, ImportError):
    """Neither `ruamel.yaml` nor `PyYAML` (import name `yaml`) is importable."""


class SentinelSelectedError(ConfigReadError):
    """A `select()` request named the maDLC `MULTI!` sentinel instead of a real bodypart."""


class UnknownBodypartsError(ConfigReadError):
    """A `select()` request named a bodypart absent from all three declared sources."""


def load_yaml(path):
    """Load one YAML file, safely, via ruamel.yaml if present else PyYAML.

    ruamel.yaml 0.19 removed the legacy module-level `safe_load` function, so the
    `YAML(typ="safe")` object API is the only correct call for that backend. The dev
    host has PyYAML and no ruamel, which is why the fallback exists and is exercised by
    the test suite; the target vision box has ruamel.yaml 0.19.1. Never an unsafe loader.
    """
    try:
        from ruamel.yaml import YAML

        ruamel_available = True
    except ImportError:
        ruamel_available = False

    if ruamel_available:
        yaml_loader = YAML(typ="safe")
        with open(path, "r") as handle:
            return yaml_loader.load(handle)

    try:
        import yaml as pyyaml
    except ImportError:
        raise YamlBackendMissingError(
            "neither 'ruamel.yaml' nor 'PyYAML' (import name 'yaml') is installed; "
            "install one of them to read DLC config.yaml / pose_cfg.yaml files"
        )
    with open(path, "r") as handle:
        return pyyaml.safe_load(handle)


def _string_list(value) -> List[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    return []


def _sha256_of_file(path) -> str:
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


@dataclass(frozen=True)
class BodypartSource:
    """One project's resolved bodypart declaration, with provenance (D-13).

    `bodyparts` is the flat single-animal list (empty in a maDLC project).
    `multianimal_bodyparts` / `unique_bodyparts` are the maDLC-style lists.
    `bodyparts_sentinel` is the literal string found under `bodyparts` when it was not a
    list (the `MULTI!` sentinel), else None. `identity` mirrors the config's own
    `identity` key (D-37); None when the source format has no such concept.
    """

    bodyparts: List[str] = field(default_factory=list)
    multianimal_bodyparts: List[str] = field(default_factory=list)
    unique_bodyparts: List[str] = field(default_factory=list)
    bodyparts_sentinel: Optional[str] = None
    engine: str = "unknown"
    source_format: str = "explicit-list"
    individuals: Optional[List[str]] = None
    multianimal: bool = False
    identity: Optional[bool] = None
    path: Optional[str] = None
    sha256: Optional[str] = None

    def candidate_names(self) -> List[Tuple[str, str]]:
        """Every declarable (name, class) pair this source structurally offers.

        A maDLC project's candidates are `individuals x multianimal_bodyparts` (class
        `"multianimal"`) plus `unique_bodyparts` (class `"unique"`) -- for the target
        project, 10 x 5 + 22 = 72 (D-39), which makes selective declaration structural.
        A single-animal project's candidates are its flat `bodyparts` (class `"flat"`)
        plus any `unique_bodyparts` it also declares.
        """
        candidates: List[Tuple[str, str]] = []
        if self.multianimal and self.individuals:
            for individual in self.individuals:
                for bodypart in self.multianimal_bodyparts:
                    candidates.append(("{}:{}".format(individual, bodypart), "multianimal"))
        else:
            for bodypart in self.bodyparts:
                candidates.append((bodypart, "flat"))
            for bodypart in self.multianimal_bodyparts:
                candidates.append((bodypart, "multianimal"))
        for bodypart in self.unique_bodyparts:
            candidates.append((bodypart, "unique"))
        return candidates

    def candidate_count(self) -> int:
        return len(self.candidate_names())


def read_dlc_config(path) -> BodypartSource:
    """Read a DLC 3.0 pytorch `config.yaml`, resolving all three bodypart sources.

    Resolution (per D-40): multi-animal iff `multianimalproject` is truthy, OR
    `bodyparts` is a `str` (the sentinel), OR `bodyparts` is absent. In that case
    `multianimal_bodyparts`/`unique_bodyparts` are read from their own keys and the flat
    `bodyparts` stays empty. Otherwise `bodyparts` is read from the flat list, with
    `unique_bodyparts` still read if the key exists.
    """
    data = load_yaml(path)
    if not isinstance(data, dict):
        raise ConfigReadError("config at {!r} did not parse to a mapping".format(path))

    multianimalproject = bool(data.get("multianimalproject"))
    raw_bodyparts = data.get("bodyparts")
    bodyparts_sentinel = raw_bodyparts if isinstance(raw_bodyparts, str) else None
    multianimal = multianimalproject or bodyparts_sentinel is not None or raw_bodyparts is None

    unique_bodyparts = _string_list(data.get("uniquebodyparts"))
    bodyparts: List[str] = []
    multianimal_bodyparts: List[str] = []
    if multianimal:
        multianimal_bodyparts = _string_list(data.get("multianimalbodyparts"))
    elif isinstance(raw_bodyparts, list):
        bodyparts = _string_list(raw_bodyparts)

    individuals = _string_list(data.get("individuals")) or None

    if not bodyparts and not multianimal_bodyparts and not unique_bodyparts:
        raise ConfigReadError(
            "config at {!r} yields no bodyparts from any of 'bodyparts', "
            "'multianimalbodyparts', 'uniquebodyparts'; keys present: {!r}".format(
                path, sorted(data.keys())
            )
        )

    identity_raw = data.get("identity")
    identity = bool(identity_raw) if isinstance(identity_raw, bool) else None

    return BodypartSource(
        bodyparts=bodyparts,
        multianimal_bodyparts=multianimal_bodyparts,
        unique_bodyparts=unique_bodyparts,
        bodyparts_sentinel=bodyparts_sentinel,
        # Confirmed from the target project's own `engine: pytorch` key (D-01, as
        # amended by the config read) rather than inferred from directory names.
        engine="pytorch",
        source_format="config.yaml",
        individuals=individuals,
        multianimal=multianimal,
        identity=identity,
        path=str(path),
        sha256=_sha256_of_file(path),
    )


def read_pose_cfg(path) -> BodypartSource:
    """Read a TensorFlow-engine exported `pose_cfg.yaml`'s `all_joints_names`."""
    data = load_yaml(path)
    if not isinstance(data, dict):
        raise ConfigReadError("pose_cfg at {!r} did not parse to a mapping".format(path))

    names = data.get("all_joints_names")
    if not isinstance(names, list) or not names:
        raise ConfigReadError(
            "pose_cfg at {!r} has no non-empty 'all_joints_names' list; keys present: "
            "{!r}".format(path, sorted(data.keys()))
        )

    return BodypartSource(
        bodyparts=_string_list(names),
        engine="tensorflow",
        source_format="pose_cfg.yaml",
        multianimal=False,
        individuals=None,
        path=str(path),
        sha256=_sha256_of_file(path),
    )


def from_explicit_list(bodyparts) -> BodypartSource:
    """Build a `BodypartSource` from a bare list of bodypart strings.

    Documented, provenance-labelled escape hatch (D-10) so plan 35-06 can generate the
    demo lib before the user's real `config.yaml` is in hand -- never the default.
    """
    return BodypartSource(
        bodyparts=list(bodyparts),
        engine="unknown",
        source_format="explicit-list",
    )


def select(source: BodypartSource, wanted) -> List[Tuple[str, str]]:
    """Validate `wanted` original bodypart strings against `source`.

    Returns `[(name, class), ...]` in `wanted`'s order, where `class` is whichever of
    `"flat"`, `"multianimal"`, `"unique"` the name came from. Assigns NO pose-array
    index -- indices come only from an explicit `--pose-order` (D-42).
    """
    class_by_name = {}
    for bodypart in source.bodyparts:
        class_by_name.setdefault(bodypart, "flat")
    for bodypart in source.multianimal_bodyparts:
        class_by_name.setdefault(bodypart, "multianimal")
    for bodypart in source.unique_bodyparts:
        class_by_name.setdefault(bodypart, "unique")

    result: List[Tuple[str, str]] = []
    missing: List[str] = []
    for name in wanted:
        if source.bodyparts_sentinel is not None and name == source.bodyparts_sentinel:
            raise SentinelSelectedError(
                "wanted entry {!r} is the maDLC sentinel {!r}, not a real bodypart; "
                "select from the real multianimal_bodyparts/unique_bodyparts names "
                "instead".format(name, source.bodyparts_sentinel)
            )
        if name not in class_by_name:
            missing.append(name)
            continue
        result.append((name, class_by_name[name]))

    if missing:
        raise UnknownBodypartsError(
            "wanted bodyparts {!r} are not present in this source; available: "
            "{!r}".format(missing, sorted(class_by_name))
        )
    return result


def warn_multianimal_identity(source: BodypartSource) -> Optional[str]:
    """Warning string when `source` is multi-animal with `identity: false`, else None.

    Individual identity is assigned post-hoc by `convert_detections2tracklets` and
    `stitch_tracklets`, which DLC-Live never runs live, so a per-individual signal would
    silently change which animal it refers to between frames (D-37).
    """
    if not source.multianimal:
        return None
    if source.identity is False:
        return (
            "warning: this project's multianimal 'identity' key is False. Individual "
            "identity is assigned post-hoc by convert_detections2tracklets and "
            "stitch_tracklets, which DLC-Live never runs live, so a per-individual "
            "signal would silently change which animal it refers to between frames "
            "(D-37)."
        )
    return None
