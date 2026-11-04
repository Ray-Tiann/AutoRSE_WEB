# Maintainer setup: reviewed submission publication

This pipeline accepts one public submission JSON per PR, verifies signed evaluator receipts and pinned evidence, requires qualified human GitHub approval, and publishes reviewed results to the self-hosted website and the existing Static Space mirror. It does not launch research runs. Scoring-server deployment is described in [`selfhost/`](../selfhost/README.md).

## Bootstrap the trusted source

The code and approval records live in two repositories:

| Repository | Contents |
| --- | --- |
| [Ray-Tiann/AutoRSE_WEB](https://github.com/Ray-Tiann/AutoRSE_WEB) | `leaderboard/` validator, publisher, public verification keys, tests and guides; `hf-leaderboard/` static frontend. |
| [Ray-Tiann/AutoRSE](https://github.com/Ray-Tiann/AutoRSE) | Trusted `.github/workflows/validate-leaderboard.yml` and `publish-leaderboard.yml`; the JSON-only `.github/leaderboard-submissions/` registry. |

The framework workflows check out their trusted base or main snapshot, then check out an exact reviewed `AutoRSE_WEB` commit into `website-code/`. They run with `PYTHONPATH=website-code/leaderboard` from the framework checkout. Keep the web revision pinned to its full commit SHA: a participant PR or a mutable web branch must not select the validator that evaluates that PR. Update the web code first, then review a separate framework change that advances the workflow pin.

Review the validator, publisher, dependency pins, workflows and evaluator public keys before merging. The trusted key file contains **public verification keys only**. Keep each evaluator's private signing key in the scoring service's secret configuration; do not put private keys, labels or account credentials in GitHub or the Space. A receipt from an unknown evaluator key must fail validation.

Use an independent maintenance test workflow for source changes. The submission publisher listens only to `.github/leaderboard-submissions/**` on `main` and to an explicit manual run, so a code-only bootstrap commit does not publish results.

## Configure the Space's trusted publisher

The publisher still runs in `Ray-Tiann/AutoRSE`; moving its implementation into the web repository does not change the publishing identity. In [Ray0311/AutoRSE-Leaderboard settings](https://huggingface.co/spaces/Ray0311/AutoRSE-Leaderboard/settings), retain the GitHub Actions publisher with all three claims:

| Claim | Value |
| --- | --- |
| Repository | `Ray-Tiann/AutoRSE` |
| Branch | `main` |
| Workflow | `publish-leaderboard.yml` |

Use the workflow filename, not its display name. This workflow does not specify a GitHub environment. Its `HF_OIDC_RESOURCE` is `spaces/Ray0311/AutoRSE-Leaderboard`. Do not widen the trust rule to all branches or unrelated workflows.

Hugging Face exchanges the GitHub OIDC identity for a short-lived, repository-scoped credential. `huggingface-hub==2.3.0`, pinned in the requirements, handles this exchange. No long-lived `HF_TOKEN` repository secret or interactive login is required. Only the main publisher job has `id-token: write`; the PR validator has no OIDC permission. See the [official Trusted Publishers documentation](https://huggingface.co/docs/hub/trusted-publishers).

The Space frontend must read `community-leaderboard.json` for reviewed results and display the paper's historical reference data separately. The publisher also uploads `approval-ledger.json` and `submissions/<id>.json`. Its live connection check writes only `publisher-status.json`, containing the source commit and protocol status, without scores. It does not overwrite `index.html` or the historical paper data. An empty reviewed cohort must be shown honestly as empty; do not populate it with test receipts or transplant historical scores into the public-data cohort.

## Protect the review boundary

Protect `AutoRSE`'s `main` against direct participant pushes and require PR review. Enable dismissal of stale approvals and require the latest push to be reviewed. Assign trusted maintainers to framework workflow/pin changes and to web validator, publisher, dependency and key changes through each repository's review policy/CODEOWNERS. Changes to those components are maintenance changes, separate from submission PRs.

The submission validation workflow is path-filtered. **Do not make its status globally required on every PR**: GitHub can leave a required path-skipped check pending on unrelated maintenance changes. Require successful submission validation as part of submission review policy, and use an always-running maintenance check for globally required source CI. The post-merge publisher independently enforces signatures, evidence and GitHub approval even if an administrator bypasses a branch rule.

Eligible submission PRs add exactly one `.github/leaderboard-submissions/<id>.json`, with a matching ID and a maximum size of 2 MiB. Mixed code/submission PRs, modifications, renames, nested paths and invalid slugs fail. Code-only PRs do not trigger this submission workflow and do not receive a submission eligibility claim.

The validator uses `pull_request_target` only with the explicitly checked-out framework **base commit** and its pinned web implementation. It has `contents: read` and `pull-requests: read`, does not expose repository secrets or an OIDC token, disables persisted checkout credentials and never checks out or executes PR code. It fetches only the JSON blob through GitHub REST and treats all linked artifacts as bytes. Keep these properties intact: GitHub warns that executing untrusted PR code with `pull_request_target` can expose credentials. See [the event documentation](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#pull_request_target) and [secure use reference](https://docs.github.com/en/actions/reference/security/secure-use#mitigating-the-risks-of-untrusted-code-checkout).

After merge, `github_review collect` queries GitHub for the PR and its paginated reviews, verifies a merged main-branch PR adding the exact current bytes, and accepts only a current-head human approval by a non-author with current `write`, `maintain` or `admin` permission. A reviewer's latest approval/change-request/dismissal controls that reviewer's decision; later comments alone do not revoke approval. The ledger records the author, PR/head/merge SHAs, reviewer evidence and submission SHA256. GitHub API failures stop publication rather than assuming approval. The read-only Actions token must be able to query PR reviews and repository metadata; the workflow does not need GitHub write permission. [GitHub documents the reviewer-permission endpoint here](https://docs.github.com/en/rest/collaborators/collaborators#get-repository-permissions-for-a-user).

## What publication verifies

The automatic pipeline checks three complete signed six-task benchmark receipts, 18 unique task/trial records, distinct per-task seeds, pinned public-data protocol, one-GPU/12-hour declarations, timestamp order and public evidence bytes. Structured configuration and provenance must agree with the submission and signed prediction digests. The validator never executes participant commands or source archives.

The self-hosted CPU evaluator requires no login. Its trusted key is scoped to
`numpy-cpu-v1` and `anonymous-session`; it binds all three receipts to the same
server-generated anonymous identifier. A self-entered display name does not
verify a person or account. Legacy CUDA receipts without an identity-kind field
retain their original HF-account interpretation under the old trusted key.
Different identity kinds cannot be pooled merely because their identifier text
matches. Backend, identity, demo and evidence checks remain mandatory.

A maintainer must assess whether those declarations are true: actual runtime and resources, independent trials, complete trajectories, evaluated source reproducibility, hidden-label access and score manipulation. Signed scores prove what the evaluator scored, not that the preceding experiment followed every research rule. Test/demo receipts remain ineligible regardless of approval.

This release accepts only `autorse-public-v2-20261029` and its fixed bundle SHA256. Preserve the framework commit and exact model/agent versions in each entry. If datasets, evaluation protocol or execution environments change in ways that affect comparability, introduce a new protocol revision/cohort and review that change before accepting results. Do not silently pool incompatible versions or historical paper runs.

The publisher rechecks **every** approved JSON and its public, commit-pinned evidence before producing a snapshot. Any unapproved/test entry, altered approved bytes, failed receipt, unavailable artifact or integrity mismatch aborts the whole upload, preserving the existing published snapshot. Evidence lives in submitters' datasets; the publisher mirrors the JSON records and review ledger, not the underlying evidence archives. Public availability is therefore an ongoing dependency.

Main-tip checks at collection and immediately before upload reject an older GitHub snapshot after `main` advances. Publisher runs share a single concurrency group with cancellation disabled. The Hugging Face commit uses its previous commit as `parent_commit`, so a concurrent Space edit causes a conflict instead of silently overwriting a newer snapshot. Rerun the publisher from current `main` after resolving a failure.

## Test before the first real result

From the `AutoRSE_WEB` repository root, run the local test suite with Python 3.12:

```bash
python -m venv .venv-leaderboard
source .venv-leaderboard/bin/activate
python -m pip install -r leaderboard/requirements.txt
PYTHONPATH=leaderboard python -m unittest discover -s leaderboard/tests -v
```

Review tests use synthetic fixtures and temporary local Git history. They exercise JSON-only PR extraction, approval/reviewer state, current-head and main-tip checks, file hashes and fail-closed behavior; these fixtures are not publishable submissions.

After merging the trusted framework workflows, open **AutoRSE → Actions → Publish reviewed leaderboard → Run workflow** and select `main`. This checks the existing HF Trusted Publisher even when there are no approved results. The workflow collects the framework review ledger, then runs `check-publisher` with the pinned web code before the score publication step:

```bash
PYTHONPATH=website-code/leaderboard python -m autorse_leaderboard.cli check-publisher \
  --repo-id Ray0311/AutoRSE-Leaderboard \
  --sha "$GITHUB_SHA"
```

Run this through GitHub Actions so its short-lived OIDC identity is available. The command checks the current GitHub main commit and the fixed HF destination, and writes only `publisher-status.json` to the Space. Confirm that the Actions step succeeds and that this file appears at the expected HF commit. This verifies the live authentication and write path without adding simulated results, changing the leaderboard data or claiming that any benchmark entry has been approved. With an empty reviewed cohort, score publication is still skipped. A permission, trust-claim or stale-main failure must remain a failed check and be corrected before inviting submissions.

Once a genuine benchmark submission is merged and approved, use a clean checkout of current **AutoRSE `main`**, with the exact web commit pinned by its workflows checked out under `website-code/`, to inspect the generated snapshot without uploading. Run from the framework root so collection reads the framework's Git history and registry. Use an already authenticated read-only GitHub session for `GITHUB_TOKEN`; do not paste a token into command history or source files. Set `GITHUB_REPOSITORY=Ray-Tiann/AutoRSE` and `GITHUB_SHA` to the full checked-out framework main commit, then run:

```bash
PYTHONPATH=website-code/leaderboard python -m autorse_leaderboard.github_review collect \
  --repository "$GITHUB_REPOSITORY" \
  --sha "$GITHUB_SHA" \
  --submissions-dir .github/leaderboard-submissions \
  --approved-dir /tmp/autorse-approved-submissions \
  --output /tmp/autorse-approval-ledger.json

PYTHONPATH=website-code/leaderboard python -m autorse_leaderboard.cli publish \
  --submissions-dir /tmp/autorse-approved-submissions \
  --keys website-code/leaderboard/trusted-keys.json \
  --approval-ledger /tmp/autorse-approval-ledger.json \
  --output-dir /tmp/autorse-leaderboard-preview \
  --repo-id Ray0311/AutoRSE-Leaderboard \
  --dry-run
```

Use a new empty output path for `--approved-dir` each time. The collector refuses to overwrite an existing directory. Do not manufacture an approval ledger for a live publication. With zero submission JSONs, collection returns an empty ledger and Actions skips the publish step. The direct `publish` command refuses an empty source directory.

After a real merge, check the **Publish reviewed leaderboard** Actions run, its saved review/output artifacts and the new Space commit. Publication artifacts are retained for 90 days and validation reports for 30 days; the Space's review ledger and JSON snapshot provide the public publication record. A failing check or missing Trusted Publisher configuration is not a published result.

## Deliver the same reviewed snapshot to the website

The self-hosted site serves its own local leaderboard JSON. Browsers do not need
to load the HF leaderboard. The trusted `AutoRSE` main-branch publisher remains
the only authority which can approve a community entry; the website's scoring
endpoint cannot promote an upload directly into the public table.

After validating every approved submission and its public evidence, `cli publish`
also writes `snapshot-manifest.json`. The manifest binds the exact byte sizes and
SHA256 values of `community-leaderboard.json`, `approval-ledger.json` and
`submissions/<id>.json` to the framework source commit. Approved submission JSON
is copied byte-for-byte so its review-ledger digest remains valid.

The manifest is **not digitally signed**. The deployment trust comes from a
dedicated SSH key available only to the trusted main-branch publisher job. Its
expected manifest digest travels in the authenticated SSH command, separately
from the archive. A participant upload, a hash supplied by a participant, or a
JSON downloaded with a same-origin hash does not authorize publication.

### Server receiver

Install `leaderboard/receive_snapshot.py`, its package and Python environment
root-owned. A dedicated `autorse-publish` account may write only
`/var/lib/autorse/published`. It must not write application source, the evaluator's
private inputs, signing key, or `/etc/autorse/trusted-keys.json`. Keep that public
key registry root-owned and not group/world-writable.

An administrator-owned wrapper invokes isolated Python, for example:

```sh
#!/bin/sh
exec /opt/autorse/venv/bin/python -I /opt/autorse/app/leaderboard/receive_snapshot.py
```

Restrict the dedicated public key with an SSH `command=` forced command and
`restrict`; disable forwarding, PTY allocation and user RC execution. The account
must not obtain an arbitrary shell or SFTP path. The only accepted original
command is exactly `publish <64-lowercase-hex-manifest-SHA256>`; no caller-supplied
filesystem paths, extra arguments or shell fragments are accepted.

The receiver reads a ZIP from standard input. It accepts at most 256 regular JSON
members, at most 2 MiB per file, and at most 32 MiB both compressed and expanded.
Traversal, absolute paths, duplicate names, symlinks, encrypted ZIP members and
unlisted files fail closed. A single publication lock prevents concurrent updates.

It rechecks the manifest and every file digest, all trusted receipt signatures,
backend key scopes, participant/demo restrictions, exact review-ledger byte
bindings and reconstructed scores/ranks. The server uses an **offline evidence
mode only inside this authenticated forced-command receiver**: the CI publisher
attests that it already fetched and validated all pinned evidence. The receiver
does not independently fetch those evidence files or re-query GitHub reviewer
permissions. `verification.json` records that limitation explicitly. Ordinary PR
and publisher validation still require full evidence verification.

Verified releases live under
`/var/lib/autorse/published/snapshots/<manifest-SHA256>/`. Files and directories are
fsynced before an atomic `current` symlink switch. The web server reads
`/var/lib/autorse/published/current/community-leaderboard.json`; failed deliveries
leave the previous release visible. Keep `leaderboard-data.json` and all paper
reference rows in the static website release, separate from community snapshots.

### Main-branch delivery

Run this after the existing successful publish step, using its generated output:

```bash
PYTHONPATH=website-code/leaderboard python -m autorse_leaderboard.package_snapshot \
  --snapshot-dir /tmp/autorse-leaderboard-preview \
  --output /tmp/autorse-reviewed-snapshot.zip
```

The packager checks the manifest's file hashes and prints its digest. The workflow
then checks that the framework source is still the current `main` tip and sends
the ZIP to the forced command using strict, pinned SSH host verification. Do not
give this deployment key to PR workflows. Keep the original publication
concurrency group and HF OIDC identity; changing the website destination does not
widen either approval boundary.

### Empty initial community cohort

Before any real submission exists, an administrator may bootstrap an honest empty
snapshot from a fetched framework `origin/main` commit:

```bash
PYTHONPATH=leaderboard python -m autorse_leaderboard.bootstrap_empty \
  --source-checkout /path/to/AutoRSE \
  --source-commit FULL_40_CHARACTER_FETCHED_MAIN_COMMIT \
  --output-dir /tmp/autorse-empty-initial-snapshot

PYTHONPATH=leaderboard python -m autorse_leaderboard.package_snapshot \
  --snapshot-dir /tmp/autorse-empty-initial-snapshot \
  --output /tmp/autorse-empty-initial-snapshot.zip
```

The bootstrap checks the actual committed registry tree and refuses if any
submission JSON exists. It records the source commit/tree, produces zero rows
and `approvals: []`, and labels the manifest `empty-source-bootstrap`. It asserts
no human reviews, evidence checks or evaluated entries. It cannot import paper
reference scores or demos into Community. Use a new output directory; frozen
source records are never overwritten.

## Workflow dependency pins

Actions are pinned to verified upstream commit SHAs, rather than mutable release tags:

| Action | Verified release | Commit |
| --- | --- | --- |
| `actions/checkout` | v6.0.2 | [`de0fac2e4500dabe0009e67214ff5f5447ce83dd`](https://github.com/actions/checkout/commit/de0fac2e4500dabe0009e67214ff5f5447ce83dd) |
| `actions/setup-python` | v7.0.0 | [`5fda3b95a4ea91299a34e894583c3862153e4b97`](https://github.com/actions/setup-python/commit/5fda3b95a4ea91299a34e894583c3862153e4b97) |
| `actions/upload-artifact` | v7.0.2 | [`cf430e030ddbb5b0abf93d22962f4752f3646cd9`](https://github.com/actions/upload-artifact/commit/cf430e030ddbb5b0abf93d22962f4752f3646cd9) |

Review dependency upgrades through the trusted maintenance path. No account authentication or trusted-publisher configuration is created automatically by these files.
