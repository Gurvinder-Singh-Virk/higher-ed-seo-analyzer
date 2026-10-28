import csv
import json
import tempfile
import unittest
from pathlib import Path

from seo_analyzer.cli import main, table, write_csv
from seo_analyzer.core import (PageParser, analyze_keywords, audit_pages, load_pages,
                               load_search_data, normalize_url, summarize)


def page(url, html):
    parser = PageParser()
    parser.feed(html)
    return dict(url=url, parser=parser)


class AuditTests(unittest.TestCase):
    def test_nested_heading_and_relative_links(self):
        pages = [page("https://example.edu/", '<title>Home</title><h1>Learn <span>online</span></h1><a href="/degree/#info">Degree</a>'),
                 page("https://example.edu/degree/", '<title>Degree</title><h1>Degree</h1>')]
        metrics, issues = audit_pages(pages)
        self.assertEqual(pages[0]["parser"].h1s, ["Learn online"])
        self.assertEqual(metrics[1]["inbound_snapshot_pages"], 1)
        self.assertNotIn("no_inbound_snapshot_links", [i["code"] for i in issues if i["url"].endswith("/degree/")])

    def test_duplicates_case_whitespace_and_empty_titles(self):
        pages = [page("https://example.edu/a", '<title>Online Degree</title>'),
                 page("https://example.edu/b", '<title> ONLINE   DEGREE </title>'),
                 page("https://example.edu/c", '<title> </title>')]
        _, issues = audit_pages(pages)
        self.assertEqual(sum(i["code"] == "duplicate_title" for i in issues), 2)
        self.assertEqual(sum(i["code"] == "missing_title" for i in issues), 1)

    def test_unknown_links_and_noindex_are_reviews(self):
        _, issues = audit_pages([page("https://example.edu/", '<meta name="ROBOTS" content="none"><a href="/unknown/">Unknown</a><a href="mailto:a@example.edu">Email</a>')])
        codes = {i["code"] for i in issues}
        self.assertIn("unverified_internal_targets", codes)
        self.assertIn("noindex_review", codes)
        self.assertNotIn("broken_link", codes)

    def test_base_and_distinct_inbound_sources(self):
        metrics, _ = audit_pages([page("https://example.edu/", '<base href="/programs/"><a href="degree/">A</a><a href="degree/#x">B</a>'),
                                 page("https://example.edu/programs/degree/", '<title>Degree</title>')])
        self.assertEqual(metrics[1]["inbound_snapshot_pages"], 1)

    def test_normalization_preserves_query_and_slash(self):
        self.assertEqual(normalize_url("HTTPS://EXAMPLE.EDU:443/a?q=1#x"), "https://example.edu/a?q=1")
        self.assertNotEqual(normalize_url("https://example.edu/a"), normalize_url("https://example.edu/a/"))


class AnalyticsTests(unittest.TestCase):
    def setUp(self):
        self.rows = [dict(date="2026-09-01", query="degree", page="https://example.edu/a", clicks=1, impressions=100, position=4),
                     dict(date="2026-09-02", query="degree", page="https://example.edu/a", clicks=9, impressions=900, position=10)]

    def test_weighted_metrics_and_click_scenario(self):
        result = analyze_keywords(self.rows)[0]
        self.assertEqual(result["position"], 9.4)
        self.assertEqual(result["ctr"], .01)
        self.assertEqual(result["scenario_additional_clicks"], 40)
        self.assertEqual(summarize(self.rows)["position"], 9.4)

    def test_ctr_is_ratio_of_sums(self):
        self.rows[0]["clicks"] = 50
        self.assertEqual(summarize(self.rows)["ctr"], .059)

    def test_zero_gap_and_outside_position_are_ineligible(self):
        self.rows[0]["clicks"] = 100
        self.assertFalse(analyze_keywords(self.rows)[0]["eligible"])
        self.rows[0]["clicks"] = 1
        self.rows[1]["position"] = 30
        self.assertEqual(analyze_keywords(self.rows)[0]["priority_score"], 0)

    def test_invalid_scenario_rejected(self):
        for ctr in [0, -1, 1.1, float("nan"), float("inf")]:
            with self.assertRaises(ValueError):
                analyze_keywords(self.rows, ctr)


class IOTests(unittest.TestCase):
    def test_invalid_search_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "search.csv"
            for values in ["2026-09-01,x,https://example.edu,3,2,4", "2026-09-01,x,https://example.edu,0,0,4",
                           "2026-09-01,x,https://example.edu,1,2,nan", "bad,x,https://example.edu,1,2,4"]:
                path.write_text("date,query,page,clicks,impressions,position\n" + values + "\n")
                with self.assertRaises(ValueError):
                    load_search_data(path)

    def test_duplicate_grain_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "search.csv"
            path.write_text("date,query,page,clicks,impressions,position\n" + "2026-09-01,x,https://example.edu,1,100,4\n" * 2)
            with self.assertRaisesRegex(ValueError, "Duplicate"):
                load_search_data(path)

    def test_snapshot_path_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pages.json"
            path.write_text(json.dumps(dict(synthetic=True, pages=[dict(url="https://example.edu", file="../outside.html")])))
            with self.assertRaisesRegex(ValueError, "inside"):
                load_pages(path)

    def test_html_and_csv_output_escaping(self):
        self.assertNotIn("<script>", table(["Query"], [["<script>alert(1)</script>"]]))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "data.csv"
            write_csv(path, [dict(query="=1+1", clicks=5)])
            with path.open() as file:
                self.assertEqual(next(csv.DictReader(file))["query"], "'=1+1")

    def test_full_demo_pipeline(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            main(["--manifest", str(root / "data/pages.json"), "--search-data", str(root / "data/search_performance.csv"), "--output", directory])
            summary = json.loads((Path(directory) / "summary.json").read_text())
            self.assertTrue(summary["synthetic"])
            self.assertEqual(summary["snapshot_pages"], 8)
            self.assertEqual(summary["clicks"], 2520)
            self.assertEqual(summary["impressions"], 59520)
            self.assertEqual(summary["eligible_opportunities"], 12)
            self.assertIn("SYNTHETIC DEMO", (Path(directory) / "report.html").read_text())


if __name__ == "__main__":
    unittest.main()
