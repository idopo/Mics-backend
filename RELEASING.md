# Releasing the client packages

Scope: the two **researcher-facing** packages in this repo — `mics-link` (`sdk/`) and
`mics-dlc-link` (`dlc_link/`). Nothing else here is published; the services ship by
`docker compose` and must never reach PyPI.

The goal these serve, in one line: a researcher on a Windows/DeepLabCut box with no access
to this repository types `python -m pip install "mics-dlc-link[live]"` and is done.

---

## One-time setup, per package (a human must do this — it needs a PyPI account)

Do this **before** the first tag. Both project names were verified free on PyPI
2026-09-10; that is not a reservation, so claim them rather than assuming they wait.

1. Log in to https://pypi.org (2FA is mandatory on PyPI; set it up first if you have not).
2. Go to **https://pypi.org/manage/account/publishing/** — the ACCOUNT-level publishing
   page, not a project's settings. That distinction matters: neither project exists on
   PyPI yet, so there is no project page to configure. A *pending* publisher is exactly
   the mechanism for that — it authorises the workflow to create the project on its first
   upload, so even release #1 is tokenless.
3. Under **Add a new pending publisher**, choose **GitHub** and fill in, exactly:

   | Field | `mics-link` | `mics-dlc-link` |
   |---|---|---|
   | PyPI project name | `mics-link` | `mics-dlc-link` |
   | Owner | `idopo` | `idopo` |
   | Repository name | `Mics-backend` | `Mics-backend` |
   | Workflow name | `publish-clients.yml` | `publish-clients.yml` |
   | Environment name | `pypi` | `pypi` |

4. In GitHub → **Settings → Environments → New environment**, create one named `pypi`
   (exactly — it must match `environment: pypi` in the workflow). Add required reviewers
   there if you want a human approval gate on every release.

**Two fields are easy to get subtly wrong.** *Workflow name* is the FILENAME,
`publish-clients.yml`, not the `name:` line inside it (`publish clients`). And all five
fields are matched exactly by PyPI at upload time — a mismatch fails the release with a
permission error that does not say which field was wrong.

After the first successful upload the pending publisher becomes an ordinary trusted
publisher on the now-existing project. Nothing needs re-doing.

No API token is created, stored, or rotated at any point. That is deliberate: this repo is
public and has already had credentials in its history once
(`.planning/OPEN-ITEMS-2026-08-30.md` §1). Trusted Publishing has no secret to leak.

**If these packages later move to their own repo** (Phase 37), update the Owner/Repository
fields above in the same PyPI screen and move this workflow with them. Nothing else changes.

---

## Cutting a release

The tag drives everything. The version in the tag must equal the version in that package's
`pyproject.toml` — the workflow checks this and fails before building, because PyPI
releases are **immutable**: a wrong version can be yanked but never replaced.

```bash
# 1. Bump the version in the package's pyproject.toml, commit it.
#    sdk/pyproject.toml           -> mics-link
#    dlc_link/pyproject.toml      -> mics-dlc-link

# 2. Tag it. The prefix chooses the package; the two version lines are independent.
git tag mics-link-v0.2.0        # publishes sdk/
git tag mics-dlc-link-v0.2.0    # publishes dlc_link/

# 3. Push the tag. That is the release.
git push origin mics-link-v0.2.0
```

**Publish `mics-link` before `mics-dlc-link` on the very first release.** `mics-dlc-link`
declares `mics-link>=0.1.0`; uploaded to an index that has no `mics-link` yet, it installs
broken for anyone who is quick.

The workflow then: resolves the package from the tag → asserts tag version == pyproject
version → builds sdist + wheel → `twine check` (a README that renders broken on pypi.org is
the first thing an outside researcher sees, and cannot be fixed in place) → refuses to
upload if a lab address (`132.77.*`) reappears in the artifacts → publishes via OIDC.

---

## Version policy

The two packages version **independently**, and that is the reason they are two packages.
`mics-link` is a wire codec whose stability is the point, and its dependency floors were
chosen not to disturb a researcher's existing notebook stack (see
`.planning/phases/34-mics-link-sdk-client-package/34-CONTEXT.md`, SDK-14). A DLC-side fix
must never force anyone to re-resolve `pyzmq`.

Never upper-bound `pyzmq` or `msgpack` in `sdk/`, and never raise their floors casually.

---

## Retiring the SMB share

`\\isi.storwis.weizmann.ac.il\labs\yizharlab\Mics\wheel\` was the distribution channel
before PyPI. Once both packages are published it is **break-glass only** — an air-gapped
box with no route to pypi.org. Prefer the documented offline path in each README
(`pip download` on a connected machine, `pip install --no-index --find-links` on the
target), which fetches the same artifacts PyPI serves.

Phase 38 plans (38-04, 38-06) still describe staging wheels 0.2.0 and 0.3.0 over SMB. Those
should become tagged PyPI releases instead.
