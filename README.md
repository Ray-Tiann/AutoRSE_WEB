# AutoRSE project website

Project website for **AutoRSE: Evaluating LLM Agents as Recommendation Engineers for Self-Evolving Recommender Systems**.

- **Paper:** https://arxiv.org/abs/2610.37228
- **Research code:** https://github.com/Ray-Tiann/AutoRSE
- **Website repository:** https://github.com/Ray-Tiann/AutoRSE_WEB
- **Website address after deployment:** https://ray-tiann.github.io/AutoRSE_WEB/

This is a static website. It needs no package installation, build tool, API key, or backend service.

## Repository layout

```text
AutoRSE_WEB/
├── index.html                  # Page content, authors, links, and citation
├── assets/
│   ├── css/styles.css          # Typography, colors, and responsive layout
│   ├── js/
│   │   ├── data.js             # Task descriptions and manuscript results
│   │   └── app.js              # Filters, tabs, figure viewer, and copy button
│   ├── data/                  # Full trajectory observations and summaries
│   ├── images/                # Paper figures and site icon
│   └── pdf/workflow.pdf        # Vector framework figure
├── .github/workflows/deploy.yml
├── .gitignore
├── .nojekyll
├── robots.txt
├── sitemap.xml
└── README.md
```

## Publish to GitHub Pages

1. Upload or push **the contents of this folder** to the `main` branch of `Ray-Tiann/AutoRSE_WEB`. The repository root should contain `index.html` directly. Include the hidden `.github` directory.
2. Open the repository's **Settings → Pages**.
3. Under **Build and deployment → Source**, select **GitHub Actions**.
4. Open **Actions → Deploy AutoRSE website → Run workflow**, select `main`, and run it. If a deployment was triggered before Pages was enabled and failed, rerun it after step 3.
5. After deployment succeeds, open the URL shown in the workflow or the Pages settings:
   **https://ray-tiann.github.io/AutoRSE_WEB/**

After initial setup, pushes to `main` automatically redeploy the website. The workflow publishes only the static page and assets.

Official instructions: [GitHub Pages custom workflows](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages).

### 用浏览器上传时

- 解压文件后，上传本文件夹里的**内容**，不要上传 ZIP，也不要再套一层 `AutoRSE_WEB` 文件夹。
- macOS 访达里按 **Command + Shift + .** 显示隐藏文件，上传时把 **`.github` 文件夹**和其他文件一起带上。
- 上传后到 **Settings → Pages → Source** 选择 **GitHub Actions**，再到 **Actions** 手动运行一次 `Deploy AutoRSE website`。

## Local preview

Run this command from the repository root:

```bash
python3 -m http.server 8080
```

Then open http://localhost:8080/. The same files also work under the `/AutoRSE_WEB/` project path on GitHub Pages.

## Update the website

| File | What to edit |
|---|---|
| `index.html` | Titles, authors, affiliations, section text, paper/repository links, and BibTeX |
| `assets/css/styles.css` | Colors, type, spacing, and responsive layout |
| `assets/js/data.js` | Task metadata, result tables, and abstract |
| `assets/js/app.js` | Interaction behavior |
| `assets/images/` | Figures; update matching paths in `index.html` if names change |
| `assets/js/trajectories.js`, `assets/css/trajectories.css` | Interactive validation trajectories |
| `assets/data/trajectories*` | Exact numeric observations, summaries, and chart metadata |
| `assets/js/novelty-scatter.js`, `assets/css/novelty-scatter.css` | Interactive novelty-performance scatter |
| `assets/data/novelty.json`, `assets/data/novelty.csv` | All 42 exact scatter points and provenance |

The GitHub buttons on the page link to the **research code repository**, `Ray-Tiann/AutoRSE`. The separate `AutoRSE_WEB` repository hosts the website.

If the website repository is renamed, update the canonical and Open Graph URLs in `index.html`, plus `robots.txt` and `sitemap.xml`.

## Reported results

The interactive table presents the paper's reported results, rather than a live leaderboard. The 16.1% headline is the unweighted mean relative gain across 42 task–agent configurations. The idea-injection comparison uses Claude Code × DeepSeek V4 Flash. Static figures and reported test results are preserved from the manuscript. The interactive trajectory explorer uses the same audited curve values with validation reference baselines, as described below.


## Interactive validation trajectories

The explorer contains all six recommendation tasks and the three agent configurations plotted in the paper appendix: Claude Code × Claude Opus 4.8, Codex × GPT-5.5, and Claude Code × DeepSeek V4 Flash. These trajectories cover **53 included runs**, **17,647 confirmed validation observations**, and **4,832 summary knots**. They do not cover the four other configurations in the main results table.

- [Complete chart data (JSON)](assets/data/trajectories.json) includes every included run and exact summary values.
- [All observations (CSV)](assets/data/trajectories-observations.csv) includes raw validation scores and their within-run cumulative maxima.
- [All summaries (CSV)](assets/data/trajectories-summary.csv) includes medians, minima, maxima, and contributing run counts at every original summary knot.

The x coordinate is `100 × (evidence-containing trajectory step time − first step time) / (last step time − first step time)`, separately for each recorded run. It is recorded session progress, not exact metric-completion time; percentages are not converted to hours. The chart uses post-step carry-forward of the known best score, with no smoothing or backfill before the first observation. Summary lines aggregate the runs with an observation available at that time; bands are their minimum–maximum range, not confidence intervals. This changing availability can make an aggregate median decrease even though each individual best-so-far run never decreases.

Three trials are available per configuration except **IntSR × Codex/GPT-5.5**, which has two: the audited source figure excludes `GPT55_Codex_t3_0819`. Other source exclusions (smoke/timing/subset probes, diagnostic oracle or in-sample scores, and synthetic pipeline tests) are retained. Confirmed source-flagged full-validation OOF/CV feedback is retained. No new score-based exclusions are applied.

The interactive dashed lines explicitly use **validation baselines**. The original six-panel appendix figure used test reference scores; its curve values have not changed. IntSR's validation baseline was supplied by the authors. OneTrans uses the task-provided proxy validation profile (204,800 rows). Baseline scopes are included in the JSON and displayed in the chart's data notes.

Keyboard users can select a recommendation model, choose an agent configuration and view, and move the time slider to inspect values and expand **Data & downloads** for the corresponding numeric table, exports, and methods. The original static figure remains linked as a fallback.

### Visualization workflow reference

The data-integrity and accessibility review used the scientific-visualization workflow in Scientific Agent Skills: Timothy Kassis, Vinayak Agarwal, Yuhuan He, Darshil Patel, and Aubrey M. Brueckner (2026), [Scientific Agent Skills: A Library of Procedural Knowledge for Research Agents](https://arxiv.org/abs/2609.00065). This is a development-workflow acknowledgment, not a source of the experimental measurements.


## Analysis and idea-generation views

The optimization-strategy table replaces the redundant pie chart and preserves the paper's reported percentages across 4,425 segmented experiments: engineering optimizations 91.7% and algorithmic innovations 8.3%. Rounded category values (59.0%, 26.2%, 6.6%, 4.2%, 3.1%, 1.0%) sum to 100.1%; the published values have not been renormalized. The novelty plot reports Pearson r = 0.79 across task–agent configurations, using mean novelty and mean relative test-score gain. This is an association, not a causal estimate.

The three interactive idea-generation views preserve the study's settings: standard execution; explicit generation of eight ideas followed by selection of two or three; and access to an external idea library. The library is an input to the agent in the injected setting. The +13.35% result compares idea injection with self-generated ideas for Claude Code × DeepSeek V4 Flash, across six tasks and three trials per setting; it is not a claim about every evaluated agent configuration. Task-level scores remain available in the expandable comparison table.


## Interactive novelty and performance

The scatter contains all **42 task–agent configuration aggregates**: six recommendation tasks and all seven agent configurations. It replaces the original static plot with exact numeric data from the same source, without digitization, jitter, or score-based exclusions. The original figure remains the JavaScript-disabled fallback. [JSON](assets/data/novelty.json) includes metadata and all points; [CSV](assets/data/novelty.csv) contains all points with rating-round means and performance-trial counts.

Novelty is the equal-weight arithmetic mean of three displayed rating-round means, each reported to two decimal places. The chart uses this unrounded average rather than the rounded summary column. Relative performance gain is `100 × (mean final test score / corresponding baseline − 1)`, including negative gains. Final performance uses three trials except **OneTrans × Terminus-2/GPT-5.5**, which uses two; this count is retained per point. These points are configuration aggregates, not 126 individual runs.

Across all 42 points, Pearson r = **0.7910292168828743** (displayed as 0.79). The descriptive ordinary least-squares fit has slope **59.75950206195401** and intercept **−129.99141520170681**. Filters recompute Pearson r and the fit from the selected points; correlations are omitted for fewer than three points or zero variance. Axis limits remain fixed when filtering. Fitted lines cover only the observed novelty range, without extrapolation. A filtered view uses a neutral heading rather than implying every subset has a positive correlation. The pooled association is neither a within-task effect nor a causal estimate.

Hover, tap, or focus a point to read its task, agent configuration, novelty, and gain. Arrow keys and Home/End move between visible points. The expandable data section provides the selected points in a numeric table plus the complete CSV download. The original source figure SHA256 is `b93c64f11dd1ba6ebb087ab3744221c60b6374c2b4479c1bdf84741bf33936b4`.


The novelty scatter uses a less panoramic desktop plot (maximum 880px wide, 500px high), a higher-contrast fit line, and lighter grid lines for readability. This presentation change preserves all coordinates, fixed axis limits, the 42-point coverage, and the selected-subset statistics.
