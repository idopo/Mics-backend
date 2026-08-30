# Open items from the 2026-08-30 session

Findings that are NOT Phase 34 work but surfaced during it. Each has an unfinished action.
Nothing here is fixed unless it says so.

---

## 1. SECURITY — secrets are in a PUBLIC git repo (PARTIALLY FIXED)

`secrets/{smb_pass,smb_user,pg_password}.txt` were **tracked** and pushed to `origin/claude` with
real content. `idopo/Mics-backend` is **PUBLIC** (`gh repo view --json visibility` -> PUBLIC).
`origin/main` does NOT carry them; the exposure is the `claude` branch.

**Done:** commit `5413c77` untracked all three and added `secrets/` to `.gitignore`. Files are
byte-identical on disk (checksummed before/after) so the containers still read them. Verified
`git add -A --dry-run` now stages 0 secret paths.

**NOT done — still exposed, still your call:**

- [ ] **Rotate the Postgres password.** `secrets/pg_password.txt` (9 bytes) is reachable on
      `origin/claude` right now and is almost certainly still live — local `pg_dump` succeeds with
      it nightly.
- [ ] **Purge the blobs from history** on `claude` (filter-repo / BFG + force-push), or make the
      repo private. Untracking stops NEW leaks; it does not remove the old ones.
- [ ] The SMB password was already rotated by the org (that is what broke the backups, item 2),
      so the exposed SMB value is spent — but the username `pori` and domain `wismain` are not.

**Live trip-wire while this stands:** the rotated SMB password now sits in the working tree at
`secrets/smb_pass.txt`. It is gitignored, so a normal `git add -A` cannot stage it — but do not
force-add that path. `git push origin claude` is otherwise safe and was NOT run today.

---

## 2. BACKUPS — 43 nights failed silently (FIXED, with a gap)

The nightly `backup` container failed **59 runs, first on 2026-07-18**, every night since.
`pg_dump` and the ES snapshot both SUCCEEDED every time; only the SMB upload failed:

```
[smb] uploading postgres_mics_db_2026-08-29_23-59-00.sql.gz -> yizharlab/Mics/database_backup/postgress
session setup failed: NT_STATUS_LOGON_FAILURE
```

Cause: the org rotated the SMB password; `secrets/smb_pass.txt` still held the old one. This also
explains the stale `/mnt/mics-smb` CIFS mount ("Host is down" while the server pings in 0.5ms and
445 is open).

**Done:** password updated in `secrets/smb_pass.txt`, `backup` container restarted and confirmed
authenticating from inside. The 2026-08-29 pg dump + ES archive were uploaded manually and
verified byte-exact (`214622` and `1034409227`).

**NOT done:**

- [ ] **42 nights remain local-only.** The `backup_work` volume holds 95 ES archives, **72 GB**,
      growing ~1GB/night. Disk is fine (761 GB free) but there is no offsite copy for that window.
      A catch-up batch upload was explicitly deferred ("update just latest snapshot").
- [ ] **There is no alerting on backup failure.** 43 nights passed unnoticed. The only signal is
      `docker logs mics_backup`. Worth a health check.
- [ ] `/mnt/mics-smb` is still a stale mount — needs `sudo umount -l /mnt/mics-smb && sudo mount -a`
      (not required for backups, which use `smbclient` directly).

---

## 3. GPIO hardware lib — `np.int` on Python 3.13 (FIXED for task def 434 only)

Pilot 3 (`RecordingBox`, .213) failed to instantiate `Left_LED` and `Mid_LED` on every run:

```
AttributeError: module 'numpy' has no attribute 'int'
  File "<string>", line 367, in __init__
```

`<string>` = a DB-sourced hardware lib. Traced to **lib 8 "GPIO Driver" v4 (version_id 25)**,
line 367 `.astype(np.int)` (also 506, 1039, 1042, 1077). `np.int` was removed in numpy 1.24;
`.213` runs Python 3.13 with a modern numpy. The Pi's OS moved forward; the DB-pinned lib did not.

**Done:** task def 434's pin moved `8: 25 -> 174` (v7). Confirmed on hardware in run 583 —
`Left_LED`/`Mid_LED` now reach `set` in ES where they previously only reached `assign_cb`, and the
user confirmed the tracebacks are gone from the pilot journal.
Rollback: `UPDATE task_definitions SET hw_lib_versions = jsonb_set(hw_lib_versions,'{8}','25'::jsonb) WHERE id=434;`
Prior value: `{"7":13,"8":25,"9":144,"10":16,"11":17,"45":41,"162":119,"163":125,"164":121}`

**NOT done:**

- [ ] **`hardware_libs.stable_version_id` for lib 8 still points at the broken v4 (id 25)**, while
      `active_version_id` is 174. Every resolution that falls through to the "stable" rung still
      inherits `np.int`. This is the root cause; 434 was only the symptom.
- [ ] **Task defs 186 (pins 25) and 179 (pins 19)** are still on broken versions.
- [ ] **The preflight lib test does not catch this class of failure.** The orchestrator logged
      `HARDWARE_LIB_TEST_RESULT version_id=25 ok=True` for the lib that then crashed twice: numpy
      resolves removed aliases through a module-level `__getattr__`, so `np.int` only raises when
      the attribute is ACCESSED (inside `__init__`), not at import. The test proves a module
      imports, not that its classes instantiate.

**Note v7 is not a bare rename.** It is the Phase 31 GPIO driver — stock upstream pigpio plus a
CLOCK_MONOTONIC adapter — and it DROPS logs for edges whose tick cannot be converted rather than
software-stamping them. Not exercised by the extlink FDA, which reads no GPIO. v5 (id 159) is the
intermediate if v7 misbehaves: same `np.int` fix, same adapter, but software-stamps instead.

---

## 4. Task def 434 pins three libs that do not exist (NOT FIXED, inert)

`hw_lib_versions` carries `"162": 119, "163": 125, "164": 121`. Hardware libs 162/163/164 do not
exist, and neither do version ids 119/121/125. Inert today because toolkit 100 does not link those
libs, so nothing tries to resolve them.

- [ ] **`resolve_lib_version_id` returns a pinned version id WITHOUT checking it exists**
      (`if pinned_version_id: return pinned_version_id, "pin"`). If any toolkit ever linked those
      libs, they would silently resolve to nothing rather than erroring. Worth a guard.

---

## 5. Minor / recorded, no action assigned

- **Lib 177 state inconsistency:** `hardware_libs.stable_version_id = 137` while version 137's own
  `state` column reads `beta`. The orchestrator logs `reason=stable` off the pointer. Harmless
  today; pointer and row disagree.
- **`event_data.value` is an int-cast**, not the signal value (0.7 -> 0). `value_raw` carries the
  float. Any future ES analysis of extlink signals must read `value_raw`. This misled the first
  pass at diagnosing run 581.
- **SDK `stats.sent` counts heartbeats**, so the documented invariant
  `enqueued == sent + dropped + abandoned + send_failed + pending` does not hold as printed once
  the client is assembled (run 582 printed `enqueued=6 sent=13`). The unit tests exercise
  `BoundedSender` in isolation where there are no heartbeats. Cosmetic but confusing.
- **`send_failed=0` proved the socket had a real peer** — a ZMQ DEALER with no connected peer
  returns EAGAIN under NOBLOCK. That counter is how the network was ruled out during the run-581
  diagnosis. Useful diagnostic property, worth keeping in mind.
