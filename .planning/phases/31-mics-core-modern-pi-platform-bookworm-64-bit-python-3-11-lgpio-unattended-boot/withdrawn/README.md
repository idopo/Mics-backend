# Withdrawn plans

## 31-11 — "The deployed gpio.py IS the repo's gpio.py"

**Withdrawn 2026-08-24 by user decision, on a corrected premise.**

The plan's central finding was that "not one toolkit and not one task definition
resolves to gpio v159", and it treated that as drift to be closed by publishing the
repo file and **repointing existing toolkit pins** onto the new version.

That premise is wrong. The pinning is **deliberate design**: an old task definition
stays pinned to the hardware-lib version it was validated against, and `hardware_libs`
carries its own version history precisely so versions can be adopted one at a time and
tested manually. Repointing existing pins would silently move validated task
definitions onto untested code — the opposite of what the pin is for.

The correct way to exercise a new `gpio.py` is a **new toolkit with new task
definitions** pinned to the new version, leaving every existing task definition
untouched, and converting the relevant ones by hand once the new version is proven.
That asset is built by **plan 31-12 Tasks 1–2** (`tools/seed_clock_probe.py` + the two
clock-probe task definitions), which is why 11 is withdrawn rather than rewritten.

### Requirement fallout

| Req | Disposition |
|---|---|
| PLAT-28 | **Unaffected** — delivered by 31-C3, which has a SUMMARY. |
| PLAT-36 | **Withdrawn** with this plan. It mandated a publisher plus a drift check that fails when a lib's deployed version differs from its repo file. Under the version-pinning design, tree/DB divergence is the intended steady state, so the drift check would fail on correct configurations. |
| PLAT-37 | **DEFERRED, not withdrawn — needs a new home.** The clock-contract refusal (a pilot reporting `CONTRACT_VERSION` 2 must not be dispatched an adapterless gpio lib, and vice versa) is *more* useful under the pinning design, not less: it is the guard that stops an old pinned task definition being dispatched to a migrated pilot. Nothing implements it now. |
