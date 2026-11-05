# Research changes and evidence

The [research changes page](https://ray0311-autorse-leaderboard.static.hf.space/changes.html)
separates two views of the experiments:

- **Task-level outcomes:** the highest published mean for each task across the
  evaluated configurations, retaining ties, standard deviations and trial counts.
- **Representative code changes:** specific recorded implementations. These are
  examples, not a method attribution for every task's highest three-trial mean.

The six task summaries use the unchanged paper-reference leaderboard data.
They do not describe the state of a live run, a best individual iteration, or
an independently measured effect of a particular code change.

## HSTU: training and content representations

**Setting:** Standard; Claude Code × Claude Opus 4.8; public-validation comparison.

Two independent variants are compared against the same HSTU control, with the
HSTU blocks held fixed. One changes the training schedule to cosine decay with
warmup. The other projects the supplied frozen 768-dimensional item features
into the ID embedding space for content-aware representations and scoring.

| Variant | Validation NDCG@10 |
| --- | ---: |
| Shared control | 0.06770 |
| Training schedule | 0.06997 |
| Content fusion | 0.07216 |

These are separate comparisons against the control, not successive additions.
They are validation results, not the task's held-out test mean on the leaderboard.
See the paper's **Case Study: Algorithmic Innovation vs. Hyperparameter Tuning**.
[AutoRSE paper](https://arxiv.org/abs/2610.37228).

## TIGER: hybrid ranking

**Setting:** Standard; Claude Code × DeepSeek V4 Flash; trial 1; final held-out test.

The final ranking pipeline combines SASRec, HSTU and TIGER predictions with
item-similarity scores derived from the latest interaction. The final submission
has NDCG@10 **0.06306733086658861** (displayed as **0.0631**).

This is a single archived run, not a three-trial mean or an isolated ablation of
one component. The archived RQ2 case report identifies it as **Case 2: TIGER model
integration**. It is not presented as a case box in the current paper.

The run's identifier is `DPSKflash_ClaudeCode_t1_0815::tiger`. Its reported final
test score and result-metadata digest are included in the public
[run-level CSV](../hf-leaderboard/paper-run-resources.csv).

## IntSR: wider training contrast

**Setting:** Idea-injected; Claude Code × DeepSeek V4 Flash; guided implementation
with validation feedback.

The agent expands training candidates with in-batch positive items, retains
cross-entropy, and masks target duplicates and observed-history negatives.
Models trained with this augmentation are retained in the final ensemble.
Its isolated contribution to performance was not measured.

This is a guided-setting example, separate from the standard-setting task
summaries. See **Case Studies — IntSR: training contrast** in the paper's appendix
and the idea-injection experimental setting in the main text.
[AutoRSE paper](https://arxiv.org/abs/2610.37228).

## Source provenance

The bounded source records used to check these descriptions are identified below.
Native conversations, private test labels, credentials, prediction arrays and
model weights are not included on the page.

| Source record | SHA256 |
| --- | --- |
| Paper experimental section, `03_experiments.tex` | `f31a9252198beed6f950850595aa6afd3ace1e3fb309355fc34724db9e052493` |
| Paper appendix, `06_appendix.tex` | `de4420b2f84906695a53ba4c4b1c5dae01bd76e9f4d5a6ad5608f4431a591ba6` |
| Archived RQ2 `case_studies.tex` | `27216c6802c74f6e7ee9a4ee04e13c34f424931aae03d6cfbcea31ca493cf6fa` |
| HSTU shared-control case evidence README | `c5f47e41de85b3240a3b0514af2df4b6f0bb2c9501f16bcbb92e12e91fe9bebf` |
| TIGER trial-1 `experiments/RESULTS.md` | `c646027e2926072feea1b0655f21dde5f7b37628ea3222d1708707bfb35b17f7` |
| TIGER trial-1 `make_final_submission.py` | `b9c60a34fcbfeadd82f79855470d28d3192db38a5a37573cf60760581bd0c953` |
| TIGER trial-1 result metadata | `cad2b01a4a31095753b90c8b44eda415a60cafe323d94d54a2c5dacc0a956a71` |

Checksums identify the records used for this description; they do not imply
that the complete archived source bundle is publicly distributed. The task-level
cost and score aggregation rules are documented in
[Leaderboard insights](LEADERBOARD_INSIGHTS.md).
