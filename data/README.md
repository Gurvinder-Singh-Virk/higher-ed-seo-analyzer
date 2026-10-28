# Synthetic demo data

Every HTML page and search metric in this directory is invented for the Higher Education SEO Analyzer. The fictional Northstar university is a demonstration label, not a representation of WGU or a real client. `www.example.edu` URLs are offline identifiers and are never fetched.

The dataset includes 8 snapshots and 48 records: 16 query/page pairs repeated over September 1–3, 2026 with multipliers 1, 2, and 1. Counts are deliberately simple to make aggregation verifiable; this is not a statistical sample of search behavior.

The fixtures intentionally include duplicated titles/descriptions, empty metadata, missing and multiple headings, a `noindex` directive, a non-self canonical, an unverified internal target, and a page without inbound links from the supplied set. The scholarship target has no snapshot: this demonstrates incomplete coverage, not a confirmed broken link.

The CSV grain is date/query/page. `position` is a synthetic average position for the row. `pages.json` maps each absolute URL to a local HTML snapshot and labels the bundle synthetic.

Do not use these figures as evidence of actual search traffic, university performance, SEO results, or enrollment impact.
