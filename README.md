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

The GitHub buttons on the page link to the **research code repository**, `Ray-Tiann/AutoRSE`. The separate `AutoRSE_WEB` repository hosts the website.

If the website repository is renamed, update the canonical and Open Graph URLs in `index.html`, plus `robots.txt` and `sitemap.xml`.

## Reported results

The interactive table presents the paper's reported results, rather than a live leaderboard. The 16.1% headline is the unweighted mean relative gain across 42 task–agent configurations. The idea-injection comparison uses Claude Code × DeepSeek V4 Flash. Figures and scientific values are preserved from the manuscript.
