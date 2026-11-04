# Hosted evaluation

Run maintainer commands below from the **AutoRSE_WEB repository root** with
Python 3.12. Agent runs and public-data installation use the
[AutoRSE framework repository](https://github.com/Ray-Tiann/AutoRSE).

## Self-hosted deployment target — public cutover pending provider domain allowlist

The self-hosted deployment target is [AutoRSE](https://114.66.48.196/evaluate/).
The candidate is installed for internal validation; public cutover is pending the
provider's domain allowlist and external HTTPS verification. Keep using the
existing [HF evaluator](https://huggingface.co/spaces/Ray0311/AutoRSE-Evaluator)
and GitHub/HF website entry points until that verification succeeds.
It uses the fixed `numpy-cpu-v1` metric backend and accepts one complete six-task
prediction ZIP per evaluation without a login. Enter a display name and retain
the browser's anonymous-session cookie while collecting three
independent complete trial sets and signed receipts for a formal submission. Demo receipts are
excluded from the community ranking. See the [submission guide](../leaderboard/SUBMIT.md)
for the ZIP/run evidence, review and automatic publication process.

The self-hosted application and deployment instructions are in [`selfhost/`](../selfhost/README.md).
The private evaluator inputs remain server-side and outside every public web root.
The receipt verification public keys are
in [trusted-keys.json](../leaderboard/trusted-keys.json); no signing private key
belongs in GitHub or a participant submission. Each trusted key is explicitly scoped
to its metric backend and participant identity kind. The CPU service signs
`participant_kind: anonymous-session` with a server-generated identifier; the
display name does not authenticate a person or HF account.
A new deployment key requires a reviewed registry change;
declaring a CPU backend does not make an unknown signature trustworthy.

The existing [HF evaluator](https://huggingface.co/spaces/Ray0311/AutoRSE-Evaluator/tree/main)
remains the public service during migration and uses the `pytorch-fp64-cuda` backend. Its existing official signed receipts remain
valid under the original CUDA/account-scoped key; its source and results are not rewritten.
The older `space/` CPU reference below is a separate demonstration template and
does not issue official signed community leaderboard receipts.
The public input repository is the
[Ray0311/AutoRSE Dataset](https://huggingface.co/datasets/Ray0311/AutoRSE).

## Legacy CPU Space reference setup

Participants run models/agents locally, select configurations using public validation
data, then upload **only the prediction file** to the AutoRSE Space. Hidden test
labels remain in a private Dataset owned by the maintainers. The public validator
checks formats; it does not compute a hidden-test score.

## Three separate repositories

| Repository | Visibility | Contents |
|---|---|---|
| `Ray0311/AutoRSE` (Dataset) | Public | Reviewed public input ZIP, manifest, dataset card |
| `RayTian/AutoRSE-private` (Dataset) | **Private** | Twelve opaque evaluator files and `private-manifest.json` |
| `RayTian/AutoRSE` (Space, Docker) | Public or protected | Application source, no labels or tokens |

Dataset and Space are different repository types. The public Dataset is the
current download source; the private Dataset and CPU Space names are reference
setup examples and do not identify the live service above.

## 1. Use the reviewed public inputs

Use the reviewed `huggingface-dataset/` release for the public Dataset.
The [public installer](https://github.com/Ray-Tiann/AutoRSE/blob/main/tools/install_public_data.py)
runs from the framework checkout. Keep the ZIP filename unchanged; the installer
pins its SHA256. The [dataset reference](DATASET.md) preserves the release provenance.
Do not upload the old v1 bundle: its OneTrans event table and IntSR session/history
tables exposed held-out outcomes. See the v2 dataset card for the redaction scope.
The corrected public inputs are a new data revision, not a claim of reproducing
historical paper scores.

## 2. Provision private evaluator inputs

On a trusted maintainer machine which already holds the original evaluator files:

```bash
python tools/package_private_evaluator.py \
  --source-benchmark /trusted/path/to/benchmark \
  --intsr-identities /path/to/public-hf-folder/intsr-test-identity.npz \
  --private-output /trusted/private-evaluator-upload
```

This copies only fixed evaluator filenames and hashes their bytes without parsing
their values. IntSR's identity-only expected array comes from the reviewed v2
public inputs, so its candidate order matches the newly randomized test requests;
the original hidden positive-label file stays unchanged. The public identity NPZ
contains no targets and is published beside the data ZIP. Upload the generated
folder to the **private** Dataset. Record its exact
40-character commit ID and the printed manifest SHA256. Never include the folder
in the public Dataset, GitHub repository, or Space source tree.

## 3. Deploy Space source

```bash
python tools/prepare_space.py --output /tmp/autorse-space-upload
```

Create a Docker Space named `RayTian/AutoRSE`, then upload the **contents** of
the generated directory. Its root README enables HF OAuth and its root Dockerfile
starts the application. No GPU is needed for scoring prediction files.

Set these in **Space Settings → Variables and secrets**:

| Name | Kind | Value |
|---|---|---|
| `HF_TOKEN` | **Secret** | Fine-grained read token for the private Dataset only |
| `AUTORSE_PRIVATE_REPO` | Variable | `RayTian/AutoRSE-private` |
| `AUTORSE_PRIVATE_REVISION` | Variable | Exact private Dataset commit ID (40 hex characters) |
| `AUTORSE_PRIVATE_MANIFEST_SHA256` | Variable | SHA256 printed by the packager |
| `AUTORSE_STATE_DIR` | Variable, optional | `/data/autorse-state` when persistent storage is enabled |
| `AUTORSE_DAILY_LIMIT` | Variable, optional | Default `5` attempts per account/task/UTC day |

Without persistent storage the quota database resets when the Space restarts.
The source checks that the evaluator repository is private, pins its revision,
checks every private file's size/SHA and its pairing to the public data revision,
and blocks the private cache from Gradio's
file-serving endpoint. Submitted files are bounded, checked without pickle, and
scored in a fresh subprocess. The subprocess does not inherit the HF token.
Only aggregate metrics and the submission SHA are returned; errors do not expose
label values or internal file paths. Invalid submissions consume an attempt too.

After startup, sign in and test one known prediction per task against the trusted
original scorer before announcing the endpoint. Local synthetic tests cover all
six metric paths and malformed inputs, but cannot validate your HF secrets or
private Dataset upload. A numeric score is not a certification of experimental
protocol, source completeness, or full-duration research completion.

## Submission formats

| Task | File | Required contents | Main metric |
|---|---|---|---|
| HSTU / TIGER | `submission.npz` | `user_ids`, integer `top_items[N,10]` | NDCG@10 |
| IntSR | `submission.npz` | `sample_ids`, `task_ids`, unchanged `candidate_items[N,100]`, finite `scores[N,100]` | Mean rec/src NDCG@10 |
| WuKong | `submission.csv.gz` | Header `sample_id,score` | AUC |
| RankMixer | `submission.npz` | int64 `sample_ids`, probability `scores` | AUC |
| OneTrans | `submission.csv` | Header `sample_id,prediction` | Click AUC |

Keep public test IDs and row order unchanged. Upload predictions; never upload
checkpoints, Python code, executables, or pickled objects. Local public-validation
metrics are available from each baseline; official hidden metrics come from Space.

Primary deployment references: [HF Spaces OAuth](https://huggingface.co/docs/hub/spaces-oauth),
[HF Spaces configuration](https://huggingface.co/docs/hub/spaces-config-reference),
[Gradio file access](https://www.gradio.app/guides/file-access).
