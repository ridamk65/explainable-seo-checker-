"""
seo_checker.py

A small, explainable SEO checker.

The point of this script isn't just to score a page — it's to EXPLAIN why
it scored that way, the same way MetricGuard/VEXIS/The Lockout explain
their findings instead of just flagging them. Every check below returns
a (passed, explanation) pair, not just a pass/fail.

Usage:
    python seo_checker.py https://example.com
    python seo_checker.py https://example.com --save report.json
"""

import argparse
import json
import time
from dataclasses import dataclass, field, asdict
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------
# Using a dataclass here instead of a plain dict keeps the shape of a
# "check result" consistent everywhere it's used, and gives you free
# type hints + a to-dict conversion (asdict) for JSON export later.

@dataclass
class CheckResult:
    name: str            # e.g. "Meta description"
    passed: bool         # did it pass the check?
    weight: int          # how much this check counts toward the total score
    explanation: str      # WHY it passed or failed — the explainable part
    detail: str = ""      # optional extra info (e.g. the actual title text)


@dataclass
class Report:
    url: str
    score: int = 0
    max_score: int = 0
    load_time_seconds: float = 0.0
    checks: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------

def fetch_page(url: str) -> tuple[requests.Response, float]:
    """Fetch a URL and time how long it takes. Returns (response, seconds)."""
    start = time.time()
    # A real browser sends a User-Agent header; some sites block requests
    # that don't have one, so we set a simple one here.
    headers = {"User-Agent": "Mozilla/5.0 (SEOChecker/1.0)"}
    response = requests.get(url, headers=headers, timeout=15)
    elapsed = time.time() - start
    response.raise_for_status()  # raises an exception on 4xx/5xx responses
    return response, elapsed


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------
# Each function takes the parsed page (and sometimes the raw response) and
# returns a single CheckResult. Keeping them separate like this means you
# can add a new check later just by writing one more function and adding
# it to the `run_all_checks` list at the bottom.

def check_title(soup: BeautifulSoup) -> CheckResult:
    tag = soup.find("title")
    text = tag.get_text(strip=True) if tag else ""

    if not text:
        return CheckResult(
            name="Page title",
            passed=False,
            weight=15,
            explanation="No <title> tag found. This is the headline search "
                        "engines show in results — without it, Google falls "
                        "back to guessing from page content.",
        )
    if len(text) < 10 or len(text) > 60:
        return CheckResult(
            name="Page title",
            passed=False,
            weight=15,
            explanation=f"Title is {len(text)} characters. Google typically "
                        f"displays ~50-60 characters, so titles outside "
                        f"roughly 10-60 characters get cut off or look thin.",
            detail=text,
        )
    return CheckResult(
        name="Page title",
        passed=True,
        weight=15,
        explanation="Title exists and is a reasonable length for search results.",
        detail=text,
    )


def check_meta_description(soup: BeautifulSoup) -> CheckResult:
    tag = soup.find("meta", attrs={"name": "description"})
    content = tag.get("content", "").strip() if tag else ""

    if not content:
        return CheckResult(
            name="Meta description",
            passed=False,
            weight=15,
            explanation="No meta description found. Without one, search "
                        "engines auto-generate a snippet from random page "
                        "text, which usually looks worse and doesn't sell "
                        "the page.",
        )
    if len(content) > 160:
        return CheckResult(
            name="Meta description",
            passed=False,
            weight=15,
            explanation=f"Meta description is {len(content)} characters — "
                        f"search engines usually truncate around 155-160, "
                        f"so the end of it won't be shown.",
            detail=content,
        )
    return CheckResult(
        name="Meta description",
        passed=True,
        weight=15,
        explanation="Meta description exists and fits within the typical "
                    "search-result display length.",
        detail=content,
    )


def check_heading_structure(soup: BeautifulSoup) -> CheckResult:
    h1s = soup.find_all("h1")

    if len(h1s) == 0:
        return CheckResult(
            name="Heading structure",
            passed=False,
            weight=15,
            explanation="No <h1> found. Search engines use the H1 as the "
                        "main topic signal for the page — without one, "
                        "there's no clear 'this page is about X' marker.",
        )
    if len(h1s) > 1:
        return CheckResult(
            name="Heading structure",
            passed=False,
            weight=15,
            explanation=f"Found {len(h1s)} <h1> tags. Multiple H1s dilute "
                        f"the 'main topic' signal — a page should generally "
                        f"have exactly one.",
        )
    return CheckResult(
        name="Heading structure",
        passed=True,
        weight=15,
        explanation="Exactly one <h1> found, giving search engines a clear "
                    "main-topic signal.",
        detail=h1s[0].get_text(strip=True),
    )


def check_image_alt_text(soup: BeautifulSoup) -> CheckResult:
    images = soup.find_all("img")

    if not images:
        return CheckResult(
            name="Image alt text",
            passed=True,
            weight=10,
            explanation="No images on the page, so there's nothing to check "
                        "here.",
        )

    missing = [img for img in images if not img.get("alt", "").strip()]
    if missing:
        return CheckResult(
            name="Image alt text",
            passed=False,
            weight=10,
            explanation=f"{len(missing)} of {len(images)} images are missing "
                        f"alt text. Search engines (and screen readers) "
                        f"can't 'see' an image — alt text is the only way "
                        f"they know what it shows.",
        )
    return CheckResult(
        name="Image alt text",
        passed=True,
        weight=10,
        explanation=f"All {len(images)} images have alt text.",
    )


def check_page_speed_heuristic(response: requests.Response, load_time: float) -> CheckResult:
    # This is a heuristic, not a real Lighthouse-style audit — it's a
    # rough proxy using response time and page size, both of which are
    # things we can measure without a headless browser.
    size_kb = len(response.content) / 1024

    if load_time > 2.5:
        return CheckResult(
            name="Load time",
            passed=False,
            weight=15,
            explanation=f"Page took {load_time:.2f}s to respond. Slow pages "
                        f"lose both ranking (Google factors in speed) and "
                        f"real visitors, who tend to leave after ~3 seconds.",
            detail=f"{size_kb:.0f} KB response size",
        )
    return CheckResult(
        name="Load time",
        passed=True,
        weight=15,
        explanation=f"Page responded in {load_time:.2f}s, within a reasonable "
                    f"range.",
        detail=f"{size_kb:.0f} KB response size",
    )


def check_mobile_viewport(soup: BeautifulSoup) -> CheckResult:
    tag = soup.find("meta", attrs={"name": "viewport"})

    if not tag:
        return CheckResult(
            name="Mobile viewport",
            passed=False,
            weight=15,
            explanation="No <meta name=\"viewport\"> tag found. Without it, "
                        "mobile browsers render the page at desktop width "
                        "and zoom out — most recruiters open portfolio "
                        "links on their phone first.",
        )
    return CheckResult(
        name="Mobile viewport",
        passed=True,
        weight=15,
        explanation="Viewport meta tag present, so mobile browsers will "
                    "render the page at the correct width.",
    )


def check_internal_links(soup: BeautifulSoup, url: str) -> CheckResult:
    domain = urlparse(url).netloc
    links = soup.find_all("a", href=True)
    internal = [a for a in links if domain in a["href"] or a["href"].startswith("#") or a["href"].startswith("/")]

    if len(internal) == 0:
        return CheckResult(
            name="Internal links",
            passed=False,
            weight=15,
            explanation="No internal links found (links to other sections "
                        "or pages on the same site). Internal links help "
                        "search engines discover and understand page "
                        "structure — for a single-page site, this usually "
                        "means anchor links like #projects.",
        )
    return CheckResult(
        name="Internal links",
        passed=True,
        weight=15,
        explanation=f"Found {len(internal)} internal links, helping search "
                    f"engines navigate the page's structure.",
    )


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def run_all_checks(url: str) -> Report:
    response, load_time = fetch_page(url)
    soup = BeautifulSoup(response.text, "html.parser")

    checks = [
        check_title(soup),
        check_meta_description(soup),
        check_heading_structure(soup),
        check_image_alt_text(soup),
        check_page_speed_heuristic(response, load_time),
        check_mobile_viewport(soup),
        check_internal_links(soup, url),
    ]

    score = sum(c.weight for c in checks if c.passed)
    max_score = sum(c.weight for c in checks)

    return Report(
        url=url,
        score=score,
        max_score=max_score,
        load_time_seconds=round(load_time, 2),
        checks=checks,
    )


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def print_report(report: Report) -> None:
    pct = round(100 * report.score / report.max_score) if report.max_score else 0
    print(f"\nSEO Report for {report.url}")
    print(f"Score: {report.score}/{report.max_score} ({pct}%)")
    print(f"Load time: {report.load_time_seconds}s")
    print("-" * 60)

    for check in report.checks:
        status = "PASS" if check.passed else "FAIL"
        print(f"[{status}] {check.name} (weight {check.weight})")
        print(f"        {check.explanation}")
        if check.detail:
            print(f"        detail: {check.detail}")
        print()


def save_report_json(report: Report, path: str) -> None:
    # asdict() converts the dataclasses (including the nested list of
    # CheckResult objects) into plain dicts, which json.dump can handle.
    with open(path, "w") as f:
        json.dump(asdict(report), f, indent=2)
    print(f"Saved JSON report to {path}")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="A small, explainable SEO checker.")
    parser.add_argument("url", help="The URL to check, e.g. https://example.com")
    parser.add_argument("--save", metavar="FILE", help="Save the report as JSON to this file")
    args = parser.parse_args()

    report = run_all_checks(args.url)
    print_report(report)

    if args.save:
        save_report_json(report, args.save)


if __name__ == "__main__":
    main()
