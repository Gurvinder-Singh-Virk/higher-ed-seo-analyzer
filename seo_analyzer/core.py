"""Deterministic offline analysis. No network requests or third-party dependencies."""

import csv
import json
import math
import re
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit


def normalize_url(value):
    """Keep queries/trailing slashes distinct; remove fragments and normalize origin."""
    parts = urlsplit(value.strip())
    if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
        raise ValueError(f"Expected an absolute HTTP(S) URL: {value!r}")
    if parts.username or parts.password:
        raise ValueError("URLs must not contain credentials")
    # Accessing port also validates malformed ports.
    port = parts.port
    host = parts.hostname.lower()
    if ":" in host:
        host = f"[{host}]"
    if port and (parts.scheme.lower(), port) not in {("http", 80), ("https", 443)}:
        host += f":{port}"
    return urlunsplit((parts.scheme.lower(), host, parts.path or "/", parts.query, ""))


def text_key(value):
    return " ".join(value.split()).casefold()


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.titles = []
        self.h1s = []
        self.descriptions = []
        self.canonicals = []
        self.robots = []
        self.links = []
        self.base = None
        self._title = None
        self._h1 = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "title":
            self._title = []
        if tag == "h1":
            self._h1 = []
        if tag == "meta":
            name = attrs.get("name", "").lower()
            if name == "description":
                self.descriptions.append(attrs.get("content", ""))
            if name in {"robots", "googlebot"}:
                self.robots.append(attrs.get("content", "").lower())
        if tag == "link" and "canonical" in attrs.get("rel", "").lower().split():
            self.canonicals.append(attrs.get("href", ""))
        if tag == "base" and self.base is None and attrs.get("href"):
            self.base = attrs["href"]
        if tag == "a" and attrs.get("href"):
            self.links.append(attrs["href"])

    def handle_data(self, data):
        if self._title is not None:
            self._title.append(data)
        if self._h1 is not None:
            self._h1.append(data)

    def handle_endtag(self, tag):
        if tag == "title" and self._title is not None:
            self.titles.append(" ".join("".join(self._title).split()))
            self._title = None
        if tag == "h1" and self._h1 is not None:
            self.h1s.append(" ".join("".join(self._h1).split()))
            self._h1 = None


def load_pages(manifest_path):
    path = Path(manifest_path).resolve()
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(manifest.get("synthetic"), bool):
        raise ValueError("Manifest must declare synthetic as true or false")
    if not isinstance(manifest.get("pages"), list) or not manifest["pages"]:
        raise ValueError("Manifest requires a nonempty pages list")
    pages = []
    seen = set()
    for item in manifest["pages"]:
        url = normalize_url(item["url"])
        if url in seen:
            raise ValueError(f"Duplicate page URL: {url}")
        seen.add(url)
        file = (path.parent / item["file"]).resolve()
        if not file.is_relative_to(path.parent):
            raise ValueError("Snapshot file must stay inside the manifest directory")
        parser = PageParser()
        parser.feed(file.read_text(encoding="utf-8"))
        parser.close()
        pages.append({"url": url, "parser": parser})
    return manifest, pages


def audit_pages(pages):
    known = {page["url"] for page in pages}
    title_counts = Counter(text_key(p["parser"].titles[0]) for p in pages
                           if p["parser"].titles and p["parser"].titles[0])
    description_counts = Counter(text_key(p["parser"].descriptions[0]) for p in pages
                                 if p["parser"].descriptions and p["parser"].descriptions[0].strip())
    inbound = {url: set() for url in known}
    findings, metrics = [], []

    for page in pages:
        url, parser = page["url"], page["parser"]

        def add(code, severity, evidence, action, owner="Content / SEO"):
            findings.append(dict(url=url, code=code, severity=severity, evidence=evidence,
                                 recommendation=action, owner=owner))

        title = parser.titles[0] if parser.titles else ""
        description = parser.descriptions[0].strip() if parser.descriptions else ""
        if not title:
            add("missing_title", "high", "No nonempty first title", "Write a descriptive, page-specific title.")
        elif title_counts[text_key(title)] > 1:
            add("duplicate_title", "medium", title, "Differentiate titles to reflect each page's purpose.")
        if title and not 30 <= len(title) <= 65:
            add("title_length_review", "low", f"{len(title)} characters", "Review clarity and truncation; length is a heuristic.")
        if len(parser.titles) > 1:
            add("multiple_titles", "medium", str(len(parser.titles)), "Keep one meaningful title element.", "Development")
        if not description:
            add("missing_description", "medium", "No nonempty first meta description", "Summarize the page's value for prospective students.")
        elif description_counts[text_key(description)] > 1:
            add("duplicate_description", "medium", description, "Write a distinct summary matching the page intent.")
        if description and not 70 <= len(description) <= 160:
            add("description_length_review", "low", f"{len(description)} characters", "Review summary quality; this is not a Google length requirement.")
        if len(parser.descriptions) > 1:
            add("multiple_descriptions", "low", str(len(parser.descriptions)), "Keep one clear meta description.", "Development")
        if not any(parser.h1s):
            add("missing_h1", "medium", "No nonempty H1", "Add a clear main heading describing the page.")
        elif len(parser.h1s) > 1:
            add("multiple_h1_review", "low", str(len(parser.h1s)), "Review the visual heading hierarchy; multiple H1s are not inherently a ranking penalty.")
        directives = set(re.split(r"[,\s]+", " ".join(parser.robots)))
        noindex = bool(directives & {"noindex", "none"})
        if noindex:
            add("noindex_review", "high", " ".join(parser.robots), "Verify indexing intent before changing directives.", "SEO / Development")
        if not parser.canonicals or not parser.canonicals[0].strip():
            add("missing_canonical_review", "low", "No canonical URL", "Review duplicate-URL risk and canonical policy.", "SEO / Development")
        else:
            try:
                canonical = normalize_url(urljoin(urljoin(url, parser.base or ""), parser.canonicals[0]))
                if canonical != url:
                    add("nonself_canonical_review", "medium", canonical, "Verify intentional consolidation to this canonical.", "SEO / Development")
            except ValueError:
                add("invalid_canonical", "medium", parser.canonicals[0], "Use a valid HTTP(S) canonical URL.", "Development")
        if len(parser.canonicals) > 1:
            add("multiple_canonicals", "medium", str(len(parser.canonicals)), "Resolve conflicting canonical declarations.", "Development")

        internal, unknown = set(), set()
        base = urljoin(url, parser.base or "")
        for href in parser.links:
            try:
                target = normalize_url(urljoin(base, href))
            except ValueError:
                continue
            if urlsplit(target).netloc == urlsplit(url).netloc:
                internal.add(target)
                if target in known and target != url:
                    inbound[target].add(url)
                elif target not in known:
                    unknown.add(target)
        if unknown:
            add("unverified_internal_targets", "low", " | ".join(sorted(unknown)),
                "Check these targets in a live crawl; absence from snapshots does not establish a broken link.", "Development")
        metrics.append(dict(url=url, title=title, title_characters=len(title),
                            description_characters=len(description), h1_count=len(parser.h1s),
                            internal_targets=len(internal), unverified_targets=len(unknown),
                            noindex=noindex))

    for row in metrics:
        row["inbound_snapshot_pages"] = len(inbound[row["url"]])
        if not inbound[row["url"]] and urlsplit(row["url"]).path != "/":
            findings.append(dict(url=row["url"], code="no_inbound_snapshot_links", severity="medium",
                                 evidence="0 inbound links from other provided pages",
                                 recommendation="Review relevant internal links; confirm against a full crawl.",
                                 owner="Content / SEO"))
    return metrics, findings


def load_search_data(path):
    required = {"date", "query", "page", "clicks", "impressions", "position"}
    rows, seen = [], set()
    with Path(path).open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if not required <= set(reader.fieldnames or []):
            raise ValueError(f"Search CSV requires columns: {', '.join(sorted(required))}")
        for number, row in enumerate(reader, start=2):
            try:
                from datetime import date
                date.fromisoformat(row["date"])
                page = normalize_url(row["page"])
                query = row["query"].strip()
                clicks, impressions = int(row["clicks"]), int(row["impressions"])
                position = float(row["position"])
                if not query or not 0 <= clicks <= impressions or impressions <= 0:
                    raise ValueError("Require query, positive impressions, and 0 <= clicks <= impressions")
                if not math.isfinite(position) or position < 1:
                    raise ValueError("Position must be finite and >= 1")
                key = (row["date"], query, page)
                if key in seen:
                    raise ValueError("Duplicate date/query/page; aggregate device/country dimensions first")
                seen.add(key)
                rows.append(dict(date=row["date"], query=query, page=page,
                                 clicks=clicks, impressions=impressions, position=position))
            except (ValueError, TypeError) as exc:
                raise ValueError(f"Invalid search data at line {number}: {exc}") from exc
    if not rows:
        raise ValueError("Search CSV has no data rows")
    return rows


def analyze_keywords(rows, target_ctr=0.05, min_impressions=100):
    if not math.isfinite(target_ctr) or not 0 < target_ctr <= 1:
        raise ValueError("target_ctr must be between 0 (exclusive) and 1")
    if min_impressions < 1:
        raise ValueError("min_impressions must be positive")
    groups = {}
    for row in rows:
        key = (row["query"], row["page"])
        group = groups.setdefault(key, dict(query=key[0], page=key[1], clicks=0,
                                           impressions=0, position_sum=0.0))
        group["clicks"] += row["clicks"]
        group["impressions"] += row["impressions"]
        group["position_sum"] += row["position"] * row["impressions"]
    opportunities = []
    for group in groups.values():
        impressions, clicks = group["impressions"], group["clicks"]
        ctr = clicks / impressions
        position = group.pop("position_sum") / impressions
        # A transparent scenario, not an empirical CTR curve or forecast.
        gap = max(0.0, impressions * target_ctr - clicks)
        eligible = impressions >= min_impressions and 4 <= position <= 20 and gap > 0
        group.update(ctr=round(ctr, 6), position=round(position, 3),
                     target_ctr=target_ctr, scenario_additional_clicks=round(gap, 2),
                     eligible=eligible, priority_score=round(gap if eligible else 0, 2),
                     recommendation=("Review search intent, title/snippet, program detail and internal links"
                                     if eligible else "Monitor; outside opportunity filters"))
        opportunities.append(group)
    return sorted(opportunities, key=lambda row: (-row["priority_score"], row["query"], row["page"]))


def summarize(rows):
    impressions = sum(row["impressions"] for row in rows)
    clicks = sum(row["clicks"] for row in rows)
    return dict(clicks=clicks, impressions=impressions, ctr=round(clicks / impressions, 6),
                position=round(sum(r["position"] * r["impressions"] for r in rows) / impressions, 3),
                start_date=min(r["date"] for r in rows), end_date=max(r["date"] for r in rows))
