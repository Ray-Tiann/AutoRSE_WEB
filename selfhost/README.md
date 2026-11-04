# Self-host AutoRSE

Run the project website, leaderboard, six-task prediction uploader, CPU scorer and
receipt service on one Ubuntu 24.04 server. Public benchmark data remains on
Hugging Face. Model training runs on participants' own GPUs.

Deployment target: **https://114.66.48.196/**. The leaderboard is at
`/leaderboard/` and prediction scoring at `/evaluate/`. Users enter a submission
name and upload predictions directly; there is no login or public admin page.

**Public cutover pending:** the candidate is installed for internal/SSH validation.
The provider must allow the chosen domain and external HTTPS must pass before
announcing this target. Existing GitHub/HF entry points remain available and have
not been switched to this server.

## 1. Build a source-only release

From the `AutoRSE_WEB` checkout, with Python 3.12:

```bash
python selfhost/build_release.py \
  --origin https://114.66.48.196 \
  --output /tmp/autorse-release-VERSION \
  --archive /tmp/autorse-release-VERSION.tar.gz

python selfhost/build_release.py --verify /tmp/autorse-release-VERSION
```

The builder copies only allowlisted site assets, application source, fixed CPU
scorers, public contracts and the reviewed snapshot receiver. It creates a full
byte-size/SHA256 manifest and `SHA256SUMS`. Private labels, signing/session keys,
uploaded predictions, model weights and original benchmark data are excluded.
The generated homepage iframe and evaluator links use the same origin; the
GitHub Pages source remains usable independently.

## 2. Prepare the server

Install Python 3.12 with `venv`, and a current Caddy release. Public IP certificates
require Caddy 2.11+ and a public ACME issuer supporting the `shortlived` profile.
TCP ports 80 and 443 must be publicly reachable. Do not use `tls internal` for the
public site. Validate actual public reachability before changing existing links.

Create a dedicated `autorse` service account. Keep source releases root-owned:

```text
/opt/autorse/
  releases/VERSION/         # immutable source release
  current -> releases/VERSION
  venv/                    # Python 3.12, pinned requirements.txt
/etc/autorse/selfhost.env  # root-owned 0600: public metadata and key file paths
/var/lib/autorse/           # root-owned 0755: traverse to public snapshots only
  state/                   # autorse-owned 0700: visitor sessions, quotas, jobs, receipts
  private/                 # autorse-owned 0700: verified private evaluator inputs
  secrets/                 # autorse-owned 0700: receipt.key and session.key, both 0600
  published/current/       # reviewed public leaderboard snapshot
```

The parent must be traversable by Caddy and `autorse-publish`; the three private
subdirectories stay service-owned `0700`. A service account's default `0750`
home-directory mode would prevent the separate publisher from reaching its own
snapshot directory.

Install only the release's CPU dependencies:

```bash
python3.12 -m venv /opt/autorse/venv
/opt/autorse/venv/bin/python -m pip install -r /opt/autorse/releases/VERSION/requirements.txt
```

Provision the exact private evaluator manifest and SHA-matching files through the
trusted maintainer channel, outside the release and public web root. Generate a
fresh Ed25519 receipt signing key and a separate random session key on the server
in the formats expected by `engine.py` and `auth.py`. Neither key belongs in
GitHub, an environment example, or a participant submission. Register only the
public receipt key in the trusted leaderboard key registry.

The CPU service uses the unchanged six fixed scorers and public submission
contracts. It does not execute uploaded code. New receipts explicitly record the
CPU backend and anonymous participant identity; the leaderboard verifier must
trust the deployment key/backend. A user-entered submission name is a display
label, not a verified person or Hugging Face account.

## 3. Configure and start

```bash
python selfhost/render_config.py \
  --origin https://114.66.48.196 \
  --output-dir /tmp/autorse-config-VERSION
```

Install the generated `selfhost.env` as `/etc/autorse/selfhost.env`, and the
`Caddyfile` as the Caddy service configuration. The environment file contains
only paths/public metadata. Install `deploy/autorse.service` as
`/etc/systemd/system/autorse.service`.

Verify the release SHA manifest, then switch `current` atomically to the new
release. Validate Caddy's configuration before starting services:

```bash
caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
systemctl daemon-reload
systemctl enable --now autorse
systemctl reload caddy
```

The app listens only on `127.0.0.1:8000`; Caddy exposes HTTPS. The systemd service
uses one queue worker, a 5 GiB memory cap, at most three CPU cores and
single-threaded numerical libraries. It writes only its state directory and
private temporary storage. Application access logging is disabled; HTTP requests
do not include login credentials or an external OAuth exchange.

While public access is pending, any SSH-only Caddy preview must explicitly use
`bind 127.0.0.1`; a `127.0.0.1` site label alone does not restrict its listening
socket to loopback.

## 4. Verify the deployment

- `/` loads the project homepage and a same-origin leaderboard.
- `/leaderboard/` supports Rank / Scores and Paper reference / Community.
- `/healthz` reports readiness without private paths or keys.
- `/evaluate/` accepts a submission name and one complete six-task prediction ZIP.
- A public demo ZIP returns six metrics and a signed receipt marked `demo`; it
  cannot enter the research leaderboard.
- Visitor/session and HMAC-derived network quotas persist across service restarts;
  rotating a visitor cookie does not remove the network limit.
- Private inputs, secrets, runtime source and other visitors' receipts are not
  downloadable. The public `/admin/` and previous OAuth routes return 404.
- Reviewed leaderboard snapshots update independently of immutable web releases;
  failed updates preserve the previous verified snapshot.

Use `selfhost.admin` only through SSH/local operations, under the service account,
for the submission overview. It does not approve research results or publish a
leaderboard row. Consult `python -m selfhost.admin --help` for its arguments.

This server is an initial low-concurrency deployment, not a throughput guarantee.
Persist quotas and receipts, bound temporary uploads and clear only expired
service-owned upload files. Back up state, keys and private evaluator inputs
through a private channel. Public data remains on HF.

## Reviewed leaderboard updates

Keep the JSON-only submission and qualified human review process in
`Ray-Tiann/AutoRSE`. Its trusted main-branch publication job checks the current
main tip, validates receipts and evidence, builds the approved public snapshot,
then sends it over a restricted SSH channel. Prediction uploads return scores;
research leaderboard publication still requires complete reviewed evidence.

Use a separate `autorse-publish` SSH account and a dedicated deployment key.
Force its authorized key to run:

```text
/opt/autorse/venv/bin/python -I /opt/autorse/current/publisher/receive_snapshot.py
```

Disable forwarding and TTY. Give this account write access only to
`/var/lib/autorse/published`; keep the receiver and
`/etc/autorse/trusted-keys.json` root-owned. Put the private deployment key only in
the main repository's `AUTORSE_DEPLOY_SSH_KEY` Actions secret. The workflow pins
the verified server ED25519 host key and never uses `ssh-keyscan`.

The receiver accepts only `publish MANIFEST_SHA256` and a bounded ZIP on stdin.
It rechecks inventory, review bindings, signed receipts and rebuilt rankings,
then atomically switches the snapshot. The authenticated main-branch publisher
attests that pinned public evidence passed its online checks; the restricted
receiver does not claim it independently fetched that evidence.

## Roll back

Keep the previous immutable release. Point `current` back to it with an atomic
symlink replacement, then restart `autorse`. Restore a previously validated Caddy
configuration only if the proxy configuration changed. Preserve state, private
inputs, signing/session keys and reviewed snapshots; rollback does not delete
user evidence or rewrite old receipts.
