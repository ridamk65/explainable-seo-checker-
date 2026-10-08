# Explainable SEO Checker

A small Python CLI that audits any website against 7 core SEO checks — and instead of just handing back a score, it explains *why* each check passed or failed.

Built as a weekend project to actually understand SEO fundamentals hands-on, rather than reading about them.

## Why "explainable"?

Most SEO scorers give you a number and leave you to guess why. Every check in this tool returns a `(passed, explanation)` pair — the reasoning is the point, not just the verdict. It's the same instinct behind the explainability-focused ML work in my other projects (decision trees + SHAP over black-box classifiers): don't just flag something, show your work for why.

## What it checks

| Check | Weight | What it looks at |
|---|---|---|
| Page title | 15 | `<title>` exists, roughly 10–60 characters |
| Meta description | 15 | `<meta name="description">` exists, ≤160 characters |
| Heading structure | 15 | Exactly one `<h1>` present |
| Image alt text | 10 | All `<img>` tags have `alt` attributes |
| Load time | 15 | Response time under 2.5s |
| Mobile viewport | 15 | `<meta name="viewport">` present |
| Internal links | 15 | At least one internal link found |

Score is out of 100, weighted by check.

## Installation

```bash
git clone https://github.com/ridamk65/explainable-seo-checker.git
cd explainable-seo-checker
pip install -r requirements.txt
```

## Usage

```bash
python seo_checker.py https://example.com
python seo_checker.py https://example.com --save report.json
```

## Sample output

Real run against `pypi.org`:

```
SEO Report for https://pypi.org
Score: 90/100 (90%)
Load time: 0.05s
------------------------------------------------------------
[PASS] Page title (weight 15)
        Title exists and is a reasonable length for search results.
        detail: PyPI · The Python Package Index

[FAIL] Image alt text (weight 10)
        15 of 16 images are missing alt text. Search engines (and screen
        readers) can't 'see' an image — alt text is the only way they
        know what it shows.

[PASS] Internal links (weight 15)
        Found 27 internal links, helping search engines navigate the
        page's structure.
```

Full example reports for `pypi.org` and `github.com` are in [`examples/`](examples/).

## A bug I found (and what it taught me)

The internal-links check originally only counted links starting with `/` or `#`. Running it against Hacker News, it reported just **1** internal link — technically true by the code's logic, since HN's links look like `item?id=44012345` with no leading slash, but obviously wrong in reality.

Fixing the pattern brought the count to **192**. The site's actual score didn't change (the check had already been passing on a technicality) — what changed was whether the report could be trusted. A tool that gives the right verdict for the wrong reason is still broken.

## Known limitations

- **Bot-blocked sites**: some sites (StackOverflow, npm) return HTTP 403 for non-browser requests. The tool surfaces this as a clear error rather than pretending to succeed.
- **Static HTML only**: reads the raw HTML response, so it can't audit JavaScript-rendered single-page apps the way a browser would.
- **Load time is a heuristic**: measured from wherever the script runs, not a real Lighthouse/Core Web Vitals score.

## Built with

Python 3, [`requests`](https://pypi.org/project/requests/), [`beautifulsoup4`](https://pypi.org/project/beautifulsoup4/)

## Author

**Ridam Kumar** — Final-year CSE, Blockchain Technology
