"""Command-line entry point and portable report exports."""

import argparse
import csv
import json
from collections import Counter
from html import escape
from pathlib import Path

from .core import analyze_keywords, audit_pages, load_pages, load_search_data, summarize


def write_csv(path, rows):
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        # Prevent spreadsheet formula interpretation of imported text fields.
        for row in rows:
            writer.writerow({k: "'" + v if isinstance(v, str) and v.lstrip().startswith(("=", "+", "-", "@"))
                             else v for k, v in row.items()})


def table(headers, rows):
    head = "".join(f"<th>{escape(str(h))}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{escape(str(v))}</td>" for v in row) + "</tr>" for row in rows)
    return f"<div class='scroll'><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>"


def write_report(out, manifest, metrics, issues, opportunities, summary, target_ctr, min_impressions):
    eligible = [r for r in opportunities if r["eligible"]]
    synthetic = manifest["synthetic"]
    label = "SYNTHETIC DEMO · NOT WGU DATA" if synthetic else "USER-SUPPLIED DATA · PROVENANCE NOT VERIFIED"
    source = str(manifest.get("dataset_name", "User-supplied dataset"))
    counts = Counter(i["severity"] for i in issues)
    audit_table = table(["Page", "Review item", "Severity", "Evidence", "Next action", "Owner"],
                        [(i["url"], i["code"], i["severity"], i["evidence"], i["recommendation"], i["owner"]) for i in issues])
    keyword_table = table(["Query", "Page", "Impressions", "Clicks", "CTR", "Avg. position", "Scenario extra clicks"],
                          [(r["query"], r["page"], r["impressions"], r["clicks"], f'{r["ctr"]:.2%}',
                            r["position"], r["scenario_additional_clicks"]) for r in eligible])
    coverage = summary["search_pages_without_snapshot"]
    coverage_table = table(["Search page without an HTML snapshot"], [(p,) for p in coverage]) if coverage else "<p>All search-data URLs have a supplied HTML snapshot.</p>"
    report = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Higher Education SEO | Audit report</title>
<style>
:root{{color-scheme:light;--ink:#152b38;--muted:#506676;--accent:#006c67;--line:#d9e4e9}}
*{{box-sizing:border-box}}body{{margin:0;background:#f3f7f8;color:var(--ink);font:16px/1.6 system-ui,sans-serif}}
header{{background:#12333e;color:white;padding:48px max(24px,calc((100vw - 1200px)/2))}}
header p{{max-width:800px;color:#cde0e6}}h1{{font-size:clamp(28px,4vw,46px);line-height:1.15;max-width:900px;margin:16px 0}}
.eyebrow{{font-size:12px;font-weight:700;letter-spacing:2px;color:#8fe3cc}}
main{{max-width:1248px;margin:auto;padding:28px 24px 60px}}.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:16px}}
.card,section{{background:white;border:1px solid var(--line);border-radius:12px;padding:24px;margin-bottom:24px}}
.card strong{{display:block;font-size:32px;color:var(--accent)}}.card span,.note{{color:var(--muted)}}h2{{font-size:23px;margin:0 0 10px}}
.scroll{{overflow-x:auto}}table{{width:100%;border-collapse:collapse;font-size:14px}}th{{text-align:left;background:#edf4f5}}
th,td{{padding:12px;border-bottom:1px solid var(--line);vertical-align:top}}td{{overflow-wrap:anywhere;min-width:100px}}
.tag{{display:inline-block;padding:4px 10px;border-radius:6px;background:#e2f4ed;color:#155c48;font-weight:600;font-size:13px}}
li{{margin:7px 0}}code{{background:#eef3f5;padding:2px 5px;border-radius:4px}}a{{color:#006c67}}
</style></head><body><header><div class="eyebrow">PORTFOLIO / SEARCH ANALYTICS</div>
<h1>Higher Education SEO Audit &amp; Keyword Opportunities</h1><p>Turn saved page snapshots and query performance into a practical content and development backlog.</p>
<div class="tag">{escape(label)}</div></header><main>
<p class="note">{escape(source)} · {summary['start_date']} through {summary['end_date']} · {len(metrics)} HTML snapshots</p>
<div class="cards"><div class="card"><span>Input impressions</span><strong>{summary['impressions']:,}</strong></div>
<div class="card"><span>Input clicks</span><strong>{summary['clicks']:,}</strong></div>
<div class="card"><span>Weighted CTR</span><strong>{summary['ctr']:.2%}</strong></div>
<div class="card"><span>Eligible query/page pairs</span><strong>{len(eligible)}</strong></div></div>
<section><h2>01 / Keyword opportunity queue</h2><p>Minimum {min_impressions:,} impressions, average position 4–20, and CTR below the {target_ctr:.1%} scenario target. Ranked by scenario additional clicks.</p>
{keyword_table}<p class="note">Scenario extra clicks = max(0, impressions × target CTR − clicks). This is a prioritization assumption, not a forecast or a measured lift. Different query intent and search layouts require different benchmarks.</p></section>
<section><h2>02 / On-page audit backlog</h2><p>{len(issues)} review items: {counts['high']} high, {counts['medium']} medium, {counts['low']} low. Severity is a project heuristic, not a Google rating.</p>{audit_table}</section>
<section><h2>03 / Coverage and interpretation</h2>{coverage_table}<ul>
<li>HTML snapshots only: no HTTP status, robots.txt, JavaScript rendering, Core Web Vitals, backlink or competitor validation.</li>
<li>Inbound counts refer only to supplied snapshots. Unverified targets are not confirmed broken links.</li>
<li>Character ranges and heading checks prompt editorial review; they are not ranking rules.</li>
<li>CTR is total clicks ÷ total impressions. Position is weighted by impressions; query/page totals may differ from Search Console property totals.</li>
<li>Correctness and completeness of user-supplied data remain the analyst's responsibility.</li></ul></section>
<section><h2>04 / Suggested work sequence</h2><ol><li>Confirm noindex and canonical intent with the SEO owner.</li>
<li>Repair missing or duplicated metadata and clarify program page headings.</li><li>Review top query/page pairs for search intent, program detail and internal-link opportunities.</li>
<li>Record each change and compare equivalent post-change periods in Search Console; account for seasonality and other changes.</li></ol>
<p class="note">Generated by Higher Education SEO Analyzer · Gurvinder Singh Virk</p></section></main></body></html>'''
    (out / "report.html").write_text(report, encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Audit HTML snapshots and prioritize query/page opportunities offline.")
    parser.add_argument("--manifest", type=Path, default=Path("data/pages.json"))
    parser.add_argument("--search-data", type=Path, default=Path("data/search_performance.csv"))
    parser.add_argument("--output", type=Path, default=Path("reports"))
    parser.add_argument("--target-ctr", type=float, default=0.05, help="Scenario assumption, not an industry benchmark (default: .05)")
    parser.add_argument("--min-impressions", type=int, default=100)
    args = parser.parse_args(argv)
    try:
        manifest, pages = load_pages(args.manifest)
        rows = load_search_data(args.search_data)
        opportunities = analyze_keywords(rows, args.target_ctr, args.min_impressions)
        metrics, issues = audit_pages(pages)
        summary = summarize(rows)
        known = {p["url"] for p in pages}
        summary.update(synthetic=manifest["synthetic"], dataset_name=manifest.get("dataset_name", "User-supplied dataset"),
                       snapshot_pages=len(pages), review_items=len(issues),
                       eligible_opportunities=sum(r["eligible"] for r in opportunities),
                       target_ctr=args.target_ctr, min_impressions=args.min_impressions,
                       search_pages_without_snapshot=sorted({r["page"] for r in rows} - known))
        # Output must not overlap inputs; avoid destroying a supplied data file.
        inputs = {args.manifest.resolve(), args.search_data.resolve()}
        for item in manifest["pages"]:
            inputs.add((args.manifest.resolve().parent / item["file"]).resolve())
        for name in ("page_metrics.csv", "audit_findings.csv", "keyword_opportunities.csv", "summary.json", "report.html"):
            if (args.output / name).resolve() in inputs:
                raise ValueError("Output would overwrite an input file; choose a different output directory")
        args.output.mkdir(parents=True, exist_ok=True)
        write_csv(args.output / "page_metrics.csv", metrics)
        write_csv(args.output / "audit_findings.csv", issues)
        write_csv(args.output / "keyword_opportunities.csv", opportunities)
        (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        write_report(args.output, manifest, metrics, issues, opportunities, summary, args.target_ctr, args.min_impressions)
    except (ValueError, KeyError, OSError, TypeError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    print(f"Audited {len(pages)} pages; {len(issues)} review items; {summary['eligible_opportunities']} eligible opportunities.")
    print(f"Report: {args.output / 'report.html'}")


if __name__ == "__main__":
    main()
