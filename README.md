# Higher Education SEO Audit & Keyword Opportunity Analyzer

An offline Python analytics project that turns HTML snapshots and Search Console-style query data into an actionable SEO review backlog and a portable HTML report. Built by **Gurvinder Singh Virk** to demonstrate on-page analysis, KPI reporting, transparent prioritization, and collaboration between SEO, content, and development teams.

**All included university pages and search metrics are synthetic. This is an independent portfolio demonstration, not a WGU audit, client engagement, or claim of achieved traffic growth.** The fictional Northstar university uses `www.example.edu` URLs as identifiers; the tool never requests them.

## Run the demo

Requires Python 3.10 or newer. No runtime dependencies, API keys, account access, or internet connection are needed. Run commands from the project root:

```bash
python -m seo_analyzer
python -m unittest discover -s tests -v
```

Open [`reports/report.html`](reports/report.html) in your browser. A pre-generated report is included, so you can review it before running any code.

To explore a different prioritization assumption:

```bash
python -m seo_analyzer --target-ctr 0.03 --min-impressions 500 --output reports/scenario-3pct
```

The optional package entry point is available after `python -m pip install -e .`: `seo-analyzer`. Installation can require internet access for the build tooling; the direct module command above does not.

## Demo findings

The three-day fictional dataset contains **8 HTML snapshots**, **48 daily query/page rows**, **59,520 impressions**, and **2,520 clicks**. CTR is **4.23%**, and impression-weighted position is **9.69**. These are input-data summaries, not improvements delivered by this project.

The audit identifies **14 review items** and **12 eligible query/page opportunities** under the default filters.

| Priority review | Evidence in demo | Proposed next step |
| --- | --- | --- |
| Indexing intent | Admissions snapshot has `noindex` | Confirm intended visibility with the SEO owner before editing |
| Metadata | Data science and cybersecurity share titles and descriptions | Write page-specific copy reflecting program intent |
| Program page clarity | Business page lacks a description and H1; canonical points elsewhere | Review template and canonical policy with development |
| Career content | Data analyst page has an empty title | Add a descriptive title and review query alignment |
| Internal discovery | Transfer-credit page has no inbound links in provided snapshots | Confirm coverage in a full crawl, then add relevant links |

Top keyword scenarios use an **assumed 5% CTR target**, applied to the same observed impressions:

| Query | Impressions | Observed clicks | Avg. position | Scenario additional clicks |
| --- | ---: | ---: | ---: | ---: |
| how to become a data analyst | 9,600 | 144 | 14.2 | 336 |
| online business degree | 7,200 | 120 | 9.4 | 240 |
| online cybersecurity degree | 6,400 | 88 | 6.8 | 232 |

These scenarios rank review work. They are not forecasts, measured gains, or estimates based on a fitted CTR model.

## What it checks

- Missing, duplicate, or multiple title and meta-description elements.
- Title and description character ranges as editorial review prompts.
- Missing H1 and multiple H1 elements for heading hierarchy review.
- HTML robots directives including `noindex` and `none`.
- Missing, multiple, invalid, and non-self canonical declarations for review.
- Unique internal link targets and inbound source-page counts within the supplied snapshots.
- Internal targets not present in the snapshot set, labeled **unverified**, never automatically broken.
- Query/page CTR, impression-weighted position, and configurable click-gap scenarios.
- Input coverage gaps when search-data pages have no supplied HTML snapshot.

Each audit finding includes evidence, a recommendation, severity, and a suggested owner. Severity is a project-defined triage heuristic, not a search-engine score.

## How prioritization works

1. Aggregate daily records by exact query and normalized page URL.
2. Calculate `CTR = sum(clicks) / sum(impressions)`.
3. Calculate `position = sum(position × impressions) / sum(impressions)`.
4. Calculate `scenario_additional_clicks = max(0, impressions × target_ctr − clicks)`.
5. Include pairs with at least 100 impressions, average position 4–20 inclusive, and a positive scenario click gap.
6. Rank by scenario additional clicks, descending; break ties by query and page for reproducible output.

`priority_score` equals the scenario click gap for eligible rows and zero otherwise. The 5% target and 4–20 position window are explicit assumptions, not universal SEO benchmarks. The CSV includes every pair, including excluded pairs, so the decision is inspectable. Branded and nonbranded queries are not automatically classified.

## Use your own data

Save authorized HTML snapshots locally and create a JSON manifest next to them:

```json
{
  "synthetic": false,
  "dataset_name": "Authorized snapshot audit",
  "pages": [
    {"url": "https://your-domain.edu/programs/", "file": "pages/programs.html"}
  ]
}
```

Paths must remain inside the manifest directory. Duplicate normalized page URLs are rejected. The manifest's `synthetic` flag labels the entire input bundle; set it truthfully and document mixed-source datasets explicitly. The program does not independently verify provenance.

Prepare a UTF-8 CSV with these columns:

```csv
date,query,page,clicks,impressions,position
2026-09-01,online degree,https://your-domain.edu/programs/,12,1000,8.5
```

| Field | Expected value |
| --- | --- |
| `date` | ISO calendar date, e.g. `2026-09-01` |
| `query` | Nonempty search query, preserved as supplied after trimming |
| `page` | Absolute HTTP(S) URL |
| `clicks` | Nonnegative integer, no greater than impressions |
| `impressions` | Positive integer; omit zero-impression records |
| `position` | Finite number at least 1 |

The expected grain is **one row per date/query/page**, with no duplicate keys. Aggregate country/device dimensions first. This normalized schema is not a direct import of every Search Console UI export; use an export or API pipeline that supplies all required dimensions and metrics. Query/page totals can differ from property totals because of aggregation and omitted query data. Protect private search data when publishing.

```bash
python -m seo_analyzer --manifest my-data/pages.json --search-data my-data/search.csv --output my-report
```

## Output files

| File | Purpose |
| --- | --- |
| `reports/report.html` | Self-contained report with KPI cards, opportunity queue, audit backlog, coverage notes, and suggested workflow |
| `reports/page_metrics.csv` | Extracted metadata lengths, heading counts, link counts, and noindex flag |
| `reports/audit_findings.csv` | Review items with evidence, recommendation, severity, and owner |
| `reports/keyword_opportunities.csv` | All query/page pairs, observed metrics, scenario assumptions, and eligibility |
| `reports/summary.json` | Machine-readable KPIs, assumptions, provenance flag, and coverage gaps |

Generated files are deterministic for identical inputs and settings. CSV text beginning with spreadsheet formula prefixes is escaped with an apostrophe; HTML output escapes imported text. Re-running into the same directory replaces generated reports. An audit with no findings produces an empty findings CSV.

## Project structure

```text
seo_analyzer/       HTML extraction, auditing, analytics, CLI and report rendering
data/pages/        Eight intentionally imperfect synthetic HTML snapshots
data/pages.json    Snapshot URL-to-file manifest and provenance label
data/search_performance.csv   Synthetic daily query/page performance
tests/             Analytics, HTML parsing, validation and end-to-end checks
reports/           Reproducible demo outputs
.github/workflows/ GitHub Actions checks for Python 3.10–3.13
```

## Validation

The standard-library test suite checks weighted aggregation, ratio-of-sums CTR, click-gap arithmetic, filtering, duplicate metadata, relative/base URL handling, inbound link counts, HTML/CSV escaping, invalid metrics, duplicate input grain, path containment, and the full demo pipeline. GitHub Actions runs tests and the demo when pushed. CI configuration is included; remote CI execution is not implied by this package.

## Limits and next steps

This tool analyzes local HTML, not a live crawl or a rendered browser DOM. It does not verify HTTP responses, redirects, robots.txt, response-header indexing directives, Core Web Vitals, structured-data eligibility, backlinks, competitors, conversions, or enrollment outcomes. HTML parsing uses Python's tolerant parser and may differ from a browser on malformed markup. International URL aliases, redirects, tracking parameters, and trailing slashes need a deliberate normalization policy; this version preserves queries and trailing slashes and removes fragments.

The three-day synthetic dataset is intentionally small and has repeated proportions; it cannot demonstrate seasonality, causal impact, real demand, or actual university performance. A production extension would add authorized crawling, validated search exports, intent-specific CTR baselines, and conversion measurement. After implementation, compare equivalent periods and account for seasonality and concurrent changes.

## Publish on GitHub

Suggested repository: **`higher-ed-seo-analyzer`** under [Gurvinder-Singh-Virk](https://github.com/Gurvinder-Singh-Virk).

1. Create an empty repository with that name on GitHub. Leave automatic README, license, and `.gitignore` creation unchecked; they are already included here.
2. Extract this project, open a terminal in its root, and run:

```bash
git init -b main
git add .
git commit -m "Add higher education SEO audit and keyword analyzer"
git remote add origin https://github.com/Gurvinder-Singh-Virk/higher-ed-seo-analyzer.git
git push -u origin main
```

Suggested repository description: `Offline Python SEO auditor and keyword opportunity analyzer with synthetic higher-education data, transparent prioritization, and an HTML report.`

Suggested topics: `python`, `seo`, `search-analytics`, `higher-education`, `technical-seo`, `portfolio-project`.

## References

- [Google Search Central: Title links](https://developers.google.com/search/docs/appearance/title-link) — informative, distinct titles; displayed titles may be generated from multiple sources.
- [Google Search Central: Snippets](https://developers.google.com/search/docs/appearance/snippet) — descriptions may inform snippets; no fixed description character limit is prescribed.
- [Google Search Console: Performance report](https://support.google.com/webmasters/answer/7576553) — clicks, impressions, CTR, position, and aggregation context.
- [Search Console API: Search Analytics query](https://developers.google.com/webmaster-tools/v1/searchanalytics/query) — dimensions and metrics for a future authorized data pipeline.

This project uses 30–65 title characters and 70–160 description characters as editorial prompts only. Google does not prescribe these ranges as ranking requirements.

## License

MIT. Included demo data and HTML fixtures were created for this project and may be reused under the same license.
