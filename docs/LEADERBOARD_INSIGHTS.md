# Leaderboard insight charts

The leaderboard displays a cost–quality scatter plot, a cost ranking and a
six-task profile directly below the results table. All three charts remain
visible alongside either the Rank or Scores view; no separate Insights tab is
required. The Results selector updates the table and charts to the same cohort.
The main leaderboard opens in **Scores**, exposing the six task means and SDs;
**Rank** remains available with the same integer overall positions.
The existing ranking and scientific result table keep their original values and
rules. The interface is inspired by LiveBench; its example model names, scores
and prices are not AutoRSE data.

The shipped data is [`insights-data.json`](../hf-leaderboard/insights-data.json).
Its source list records hashes of the bounded trial-result metadata used for the
derivation. Native conversations, code execution logs, private targets, model
weights and prediction arrays are not part of this chart dataset.

The downloadable [`paper-run-resources.csv`](../hf-leaderboard/paper-run-resources.csv)
contains all 125 canonical run records, including logged cost, score, token
counts, agent execution duration and relative metadata paths with hashes.
Unrecorded costs are marked `null`. The JSON records the CSV's hash; its task points can
be reconstructed from these rows. The CSV contains no prediction arrays,
private labels, API credentials or conversation content. The bounded derivation
script is [`tools/derive_insights_data.py`](../tools/derive_insights_data.py).

## Per-task summary calculations

The separate [Research changes page](../hf-leaderboard/changes.html) presents
six task summaries and three documented examples of agent modifications. It
uses the existing public paper-reference JSON and shared chart core; it has no
new result dataset or Community selector. Case evidence and interpretation
limits are documented in [Research changes provenance](RESEARCH_CHANGES.md).

The `taskOverview` helper summarizes each of the six tasks with its metric,
baseline, observed score range and best configuration(s). Winners follow the
leaderboard's four-decimal, decimal-half-up tie rule. All tied configurations
are retained with their own mean, sample SD and trial count; the summary does
not select one arbitrarily or imply a statistically significant advantage.
The count above baseline compares each available mean against that task's
baseline. It does not pool AUC and NDCG scores.

Paper summaries preserve the published relative-gain values and original 42
mean/SD cells. A community task without a baseline in its own cohort shows no
baseline, relative gain or above-baseline count; it does not borrow a historical
paper baseline. Empty community results remain empty. These summaries do not
replace the main leaderboard's **Rank** and **Scores** views or alter its
configuration-level ordering.

## Cost and quality

**Cost** means the value recorded in `agent_result.cost_usd` for one native
research run. It is harness-reported accounting, potentially using historical
provider/adapter prices and cache conventions; it is not a verified invoice or
a newly repriced comparison across providers. It excludes GPU rental, server
hosting and project reimbursement totals. The charts do not use the project's
reimbursement amounts to infer configuration costs.

There are 125 canonical native runs and 101 runs with both a reported cost and a
score. The outer job aggregates are not additional independent runs. Missing
costs remain unknown; they are not zero, free usage or an estimated price.

| Configuration | Paired cost/score runs | Coverage detail |
| --- | ---: | --- |
| Claude Code × DeepSeek V4 Flash | 17/18 | HSTU trial 3 has no recorded cost. |
| Claude Code × Claude Opus 4.8 | 18/18 | All six tasks have three paired runs. |
| Codex × DeepSeek V4 Flash | 18/18 | All six tasks have three paired runs. |
| Codex × GPT-5.5 | 6/18 | Costs exist only for TIGER and RankMixer. |
| Terminus-2 × DeepSeek V4 Flash | 18/18 | All six tasks have three paired runs. |
| Terminus-2 × GPT-5.5 | 6/17 | Costs exist only for TIGER and RankMixer; the canonical OneTrans set contains two runs. |
| Terminus-2 × Claude Opus 4.8 | 18/18 | All six tasks have three paired runs. |

The initial task is **TIGER**: all seven configurations have 3/3 paired runs.
RankMixer also has complete paired coverage for all seven configurations.

For a selected task, the scatter's x and y values use the **same observed run
subset**: mean logged API cost and mean score. Hover/focus details report the
paired sample size and sample standard deviation when available. Thus the
Claude Code/DeepSeek HSTU point uses two runs for both coordinates, rather than
combining two cost records with all three scores. The default x scale is log10
for strictly positive costs. A recorded zero must remain visible with an
explicit alternative scale; it must not silently disappear from a logarithmic
axis. Cost-ranking bars start at zero and are sorted by their recorded means;
missing entries appear separately as N/A, rather than being ranked cheapest.

For the **six-task overall** view, each task must have at least one paired run.
The two GPT-5.5 configurations therefore have no overall cost–quality point.
The five eligible configurations use equal task weights:

```text
overall cost = mean over the six tasks of each task's paired mean cost
overall gain (%) = 100 × mean over the six tasks of (paired mean score / baseline − 1)
```

The baseline references are the six published four-decimal values in the data.
Raw AUC, NDCG@10 and Macro NDCG@10 are never averaged into a common score.
Overall SD is left unknown: the task-balanced statistic is not assigned a
fabricated uncertainty estimate.

The value frontier is descriptive. A point is dominated only if another point
costs no more and scores no lower, with at least one strict improvement. Equal
cost/score points remain tied. Frontier membership does not establish a
statistically significant advantage or a causal effect of spending.

## Six-task profile

Select two or three configurations from the current cohort. Every radial axis
uses the same explicit formula:

```text
normalized task score = 100 × (score − task minimum) / (task maximum − task minimum)
```

For each axis, the minimum and maximum use all available finite, nonnegative
task means in the **full current results cohort**. A missing score on another
task does not exclude a configuration from this axis. Adding or removing one of
the two or three displayed configurations
does not rescale the axes. The cohort minimum maps to 0 and the maximum to 100;
each axis shows relative position within its own task. If all available means
on an axis are equal, they map to 50 and the chart marks that axis as having no
variation. Missing task scores remain gaps; they are not plotted at zero or
connected across the missing axis. Values, SDs and trial counts remain available
in the existing table and chart details. The profile is not used to calculate
the official overall rank. Its 0–100 scale does not represent percentage
improvement over a baseline.

Paper-reference profiles use the preserved 42 published mean/SD cells. Community
profiles use only reviewed community rows. Empty community cohorts show an
empty-state message, and paper costs are never attached to a community row with
a similar name. New community cost records require their own explicit
provenance; a signed prediction receipt alone does not certify API spend.

## Historical source discrepancy

The bounded native metadata reproduce 41 of the 42 paper mean/SD cells at the
published four-decimal precision. The remaining cell is Terminus-2 × GPT-5.5 on
OneTrans: two canonical native runs give mean `0.6949017340274293` and sample SD
`0.0022685781715196993`, while the paper-reference cell is `0.7285 ± 0.0498`.
This update preserves the paper cell in the result table and profile. Neither
run has a recorded cost, so no OneTrans cost point is made from that mismatch.
The chart data retain the discrepancy in their audit metadata; resolving the
paper/source history requires a separate scientific audit.

Historical paper/native results and the sanitized public-v2 evaluation release
remain distinct data revisions. These charts are not new evaluations of the
public-v2 dataset.

## Verification and deployment

- `leaderboard/tests/test_insights.py` exercises the actual exported chart core
  with independent arithmetic and adversarial missing/tied values.
- The tests check original paper values, paired coverage, task-balanced overall
  values, zero/missing cost behavior and fixed-cohort profile normalization.
- `selfhost/build_release.py` copies only `insights.js`, `insights.css`,
  `insights-data.json`, `paper-run-resources.csv` and `changes.html` beside the standalone leaderboard and records their
  byte sizes and SHA256 values in the release manifest. It does not copy an
  arbitrary maintenance-directory tree into the web root.
- The self-hosted homepage maps the Research changes link to the same-origin
  `/leaderboard/changes.html`. The page reads `leaderboard-data.json`, generated
  from the unchanged paper seed during the release build.
- HF static deployments must publish these five assets together with the
  matching `index.html`; updating the HTML alone would leave broken chart links.
- Browser verification is still required for layout, keyboard access, tooltips
  and responsive behavior. Automated checks do not establish complete
  accessibility or scientific validity.

## Methodological tooling

The scientific-visualization procedure was used to review normalization,
missing-data treatment, encoding and evidence provenance. See Timothy Kassis,
Vinayak Agarwal, Yuhuan He, Darshil Patel and Aubrey M. Brueckner (2026),
*Scientific Agent Skills: A Library of Procedural Knowledge for Research
Agents*, [arXiv:2609.00065](https://doi.org/10.48550/arXiv.2609.00065).
