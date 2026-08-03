"""Seed compute lib -- a `Hardware` subclass exposing the CONTEXT-locked stdlib random/numeric
ops every fresh DB ships with.

Uploaded into the DB by `seed_compute.seed_compute_ops_lib()` as a `hardware_libs` row with
`filename='compute_ops.py'`, `kind='compute'`. Every op here is scientifically material --
`@log_action` records the operation (name + args) as a `Hardware_Event`, independent of the
`Tracker.set()` event that records the RESULT once the state body's `output` writes it into a
declared variable. Both events must reach the log (CMP-16) -- neither alone is sufficient.

`hardware_state` is always CLOSED for a compute class (no pin, no GPIO), so `@log_action` always
logs `level=0` -- semantically meaningless here, harmless, expected (Research, Architecture
Patterns). `release()` is a mandatory no-op override: `Task.end()` calls `release()`
unconditionally on every hardware object on every run; the `Hardware` base raises if a subclass
doesn't override it.

No comparison/boolean-logic ops -- branching stays in FDA transitions (CONTEXT, locked). Stdlib
`random`/builtins only (CMP-19 allowlist; see `seed_compute.COMPUTE_STDLIB_ALLOWLIST`).
"""
from autopilot.hardware import Hardware
from autopilot.utils.logging_utils import log_action
import random


class ComputeOps(Hardware):
    """Stdlib random/numeric compute ops.

    No `__init__` override -- `init_hardware()` injects `name`/`type`/`group`; adding a
    constructor here would break the zero-param `pilot_hardware_config` contract every
    compute module relies on (CONTEXT: Pi-side registration, auto-provisioned).
    """

    def release(self):
        # Task.end() calls release() unconditionally on every hardware object; the base
        # raises if not overridden. A compute op holds no system resource to release.
        pass

    @log_action
    def random_choice(self, options: list):
        return random.choice(options)

    @log_action
    def random_int(self, low: int, high: int):
        return random.randint(low, high)

    @log_action
    def random_float(self, low: float, high: float):
        return random.uniform(low, high)

    @log_action
    def random_bool(self, p: float = 0.5):
        return random.random() < p

    @log_action
    def assign(self, value):
        return value

    @log_action
    def add(self, a: float, b: float):
        return a + b

    @log_action
    def subtract(self, a: float, b: float):
        return a - b

    @log_action
    def multiply(self, a: float, b: float):
        return a * b

    @log_action
    def divide(self, a: float, b: float):
        if b == 0:
            raise ZeroDivisionError("divide: b must not be 0")
        return a / b

    @log_action
    def modulo(self, a: float, b: float):
        if b == 0:
            raise ZeroDivisionError("modulo: b must not be 0")
        return a % b

    @log_action
    def minimum(self, a: float, b: float):
        return min(a, b)

    @log_action
    def maximum(self, a: float, b: float):
        return max(a, b)

    @log_action
    def clamp(self, value: float, low: float, high: float):
        return max(low, min(value, high))
