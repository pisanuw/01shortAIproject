#!/usr/bin/env python3
"""Download UW quarter schedule HTML files for any campus and department."""
from __future__ import annotations

import argparse
import json
import re
from http.cookiejar import Cookie, CookieJar, MozillaCookieJar
from html import unescape
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import HTTPCookieProcessor, Request, build_opener as _build_opener

from terms import (
    ADDITIONAL_TERM_URLS,
    CAMPUSES,
    EXTRA_TERM_CODES,
    TERMS,
    configured_term_codes,
    dept_html_urls,
    index_page_urls,
)

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
DEPTS_DIR = ROOT / "data" / "depts"


# ── HTTP helpers ───────────────────────────────────────────────────────────────

def build_opener_with_cookies(cookie_file: str | None):
    if not cookie_file:
        return _build_opener()
    jar = load_cookie_jar(cookie_file)
    return _build_opener(HTTPCookieProcessor(jar))


def load_cookie_jar(cookie_file: str) -> CookieJar:
    path = Path(cookie_file)
    if not path.exists():
        raise FileNotFoundError(f"Cookie file not found: {path}")
    if path.suffix.lower() == ".json":
        return _load_json_cookie_jar(path)
    jar = MozillaCookieJar(str(path))
    jar.load(ignore_discard=True, ignore_expires=True)
    return jar


def _load_json_cookie_jar(path: Path) -> CookieJar:
    raw = json.loads(path.read_text(encoding="utf-8"))
    cookies = raw.get("cookies", []) if isinstance(raw, dict) else (raw if isinstance(raw, list) else [])
    jar = CookieJar()
    for entry in cookies:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name", "")).strip()
        value = str(entry.get("value", ""))
        domain = str(entry.get("domain", "")).strip()
        if not name or not domain:
            continue
        path_value = str(entry.get("path", "/") or "/")
        expires = entry.get("expirationDate")
        try:
            expires = int(expires) if expires not in (None, "") else None
        except (TypeError, ValueError):
            expires = None
        secure = bool(entry.get("secure", False))
        http_only = bool(entry.get("httpOnly", False))
        domain_initial_dot = domain.startswith(".")
        jar.set_cookie(Cookie(
            version=0, name=name, value=value, port=None, port_specified=False,
            domain=domain, domain_specified=True, domain_initial_dot=domain_initial_dot,
            path=path_value, path_specified=True, secure=secure, expires=expires,
            discard=expires is None, comment=None, comment_url=None,
            rest={"HttpOnly": http_only}, rfc2109=False,
        ))
    return jar


def fetch_html(opener, url: str) -> tuple[str | None, str]:
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with opener.open(req, timeout=30) as resp:
            html = resp.read().decode("utf-8", errors="replace")
            if "Shibboleth Authentication Request" in html:
                return None, "requires-uw-login"
            html = re.sub(r'<!--Created by chtml.*?-->\n?', '', html)
            return html, "downloaded"
    except (HTTPError, URLError, TimeoutError) as exc:
        return None, f"request-failed: {exc.__class__.__name__}"


def fetch_first_html(opener, urls: list[str]) -> tuple[str | None, str, str | None]:
    """Try candidate URLs in order, returning the first successful HTML payload."""
    last_status = "unavailable"
    for url in urls:
        html, status = fetch_html(opener, url)
        if html is not None:
            return html, status, url
        last_status = status
    return None, last_status, None


# ── Department discovery ───────────────────────────────────────────────────────

def _current_heading(html_text: str, pos: int) -> str:
    """Return the most recent h2/h3 heading before pos in html_text."""

    snippet = html_text[:pos]
    matches = list(re.finditer(r'<h[23][^>]*>([^<]+)</h[23]>', snippet, re.IGNORECASE))
    if matches:
        return re.sub(r'\s+', ' ', matches[-1].group(1)).strip()
    return "General"


def _clean_text(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value)
    value = unescape(value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _is_placeholder_label(label: str) -> bool:
    token = re.sub(r"[^a-z]", "", str(label or "").lower())
    return token in {"description", "schedule"}

def infer_bothell_display_name(html: str, position: int, dept_code: str) -> str:
    """Infer a department display name from the surrounding list item text."""
    li_start = html.rfind("<li", 0, position)
    if li_start == -1:
        return dept_code.upper()
    li_close = html.find(">", li_start)
    if li_close == -1:
        return dept_code.upper()
    li_end = html.find("</li>", li_close)
    if li_end == -1:
        return dept_code.upper()

    li_html = html[li_close + 1:li_end]
    li_text = _clean_text(li_html)
    li_text = re.sub(r'\bDescription\b', '', li_text, flags=re.IGNORECASE)
    li_text = re.sub(r'\bSchedule\b', '', li_text, flags=re.IGNORECASE)
    li_text = re.sub(r'\s*,\s*', ' ', li_text)
    li_text = re.sub(r'\s+', ' ', li_text).strip(' -,:;')

    # Prefer text before the course-code parentheses, e.g. "Business Economics (B BECN)"
    m = re.search(r'^(.*?)\s*\((?:[A-Z]\s+)?[A-Z0-9]{2,}(?:\s+[A-Z0-9]{2,})*\)', li_text)
    if m:
        candidate = m.group(1).strip(' -,:;')
        if candidate and candidate.lower() not in {"description", "schedule"}:
            return candidate

    if li_text and li_text.lower() not in {"description", "schedule"}:
        return li_text
    return dept_code.upper()

def discover_depts_bothell(opener, term_code: str) -> list[dict]:
    """Scrape the UWB registrar page to find all Bothell dept codes for a term."""
    urls = index_page_urls("B", term_code)
    html, status, used_url = fetch_first_html(opener, urls)
    if not html:
        print(f"  [B/{term_code}] index page: {status} ({urls[0]})")
        return []

    # Links like: pub/B/SPR2026/css.html or pub/B/SPR2026/95css.html
    dept_re = re.compile(
        r'href="[^"]*pub/B/' + re.escape(term_code) + r'/(?P<file>[^"]+\.html)"[^>]*>(?P<name>[^<]+)<',
        re.IGNORECASE,
    )
    # Generic fallback for pages that use local links like href=bjapan.html
    generic_link_re = re.compile(
        r'href=["\']?(?:[^"\'>\s]*/)?(?P<file>[a-z0-9]+\.html)["\']?[^>]*>\s*(?P<name>[^<(]+)',
        re.IGNORECASE,
    )
    heading_re = re.compile(r'<h[23][^>]*>([^<]+)</h[23]>', re.IGNORECASE)

    depts: list[dict] = []
    seen: set[str] = set()
    current_school = "General"

    # Walk through headings and links together
    events: list[tuple[int, str, re.Match]] = []
    for m in heading_re.finditer(html):
        events.append((m.start(), "heading", m))
    for m in dept_re.finditer(html):
        events.append((m.start(), "link", m))
    events.sort(key=lambda x: x[0])

    for _, kind, m in events:
        if kind == "heading":
            text = re.sub(r'\s+', ' ', m.group(1)).strip()
            if text:
                current_school = text
        else:
            filename = m.group("file")
            # Skip 95* fee-based variants — same dept, different registration path
            if filename.startswith("95"):
                continue
            dept_code = Path(filename).stem.lower()
            display_name = re.sub(r'\s+', ' ', m.group("name")).strip()
            # Strip trailing description cruft like " – Fee Based" or "[Description]"
            display_name = re.split(r'\s*[–\[\(]', display_name)[0].strip()
            if _is_placeholder_label(display_name):
                display_name = infer_bothell_display_name(html, m.start(), dept_code)
            if not display_name:
                display_name = dept_code.upper()
            if dept_code and dept_code not in seen:
                seen.add(dept_code)
                depts.append({
                    "code": dept_code,
                    "name": display_name,
                    "school": current_school,
                })

    # Fallback: if no depts found with explicit pub/B links, use generic link parsing.
    if not depts:
        current_school = "General"
        events = []
        for m in heading_re.finditer(html):
            events.append((m.start(), "heading", m))
        for m in generic_link_re.finditer(html):
            events.append((m.start(), "link", m))
        events.sort(key=lambda x: x[0])

        seen.clear()
        for _, kind, m in events:
            if kind == "heading":
                text = re.sub(r'\s+', ' ', m.group(1)).strip()
                if text and "schedule" not in text.lower() and "course" not in text.lower():
                    current_school = text
                continue

            filename = m.group("file").lower()
            if filename.startswith("95") or filename in ("index.html", "calendar.html"):
                continue
            dept_code = Path(filename).stem.lower()
            display_name = re.sub(r'\s+', ' ', m.group("name")).strip()
            display_name = re.split(r'\s*[–\[\(]', display_name)[0].strip()
            if _is_placeholder_label(display_name):
                display_name = infer_bothell_display_name(html, m.start(), dept_code)
            if not display_name:
                display_name = dept_code.upper()
            if not dept_code or len(display_name) < 3:
                continue
            if dept_code not in seen:
                seen.add(dept_code)
                depts.append({
                    "code": dept_code,
                    "name": display_name,
                    "school": current_school,
                })

    print(f"  [B/{term_code}] discovered {len(depts)} depts from {used_url}")
    return depts


def discover_depts_tacoma_seattle(opener, campus: str, term_code: str) -> list[dict]:
    """Scrape washington.edu pub index for Tacoma or Seattle depts."""
    urls = index_page_urls(campus, term_code)
    html, status, used_url = fetch_first_html(opener, urls)
    if not html:
        print(f"  [{campus}/{term_code}] index page: {status} ({urls[0]})")
        return []

    # Links in the index: href=".../{deptfile}.html" or href=deptfile.html (unquoted)
    # Tacoma uses unquoted hrefs like <a href=tcss.html>, Seattle uses quoted.
    link_re = re.compile(
        r'href=["\']?(?:[^"\'>\s]*/)?(?P<file>[a-z0-9]+\.html)["\']?[^>]*>\s*(?P<name>[^<(]+)',
        re.IGNORECASE,
    )
    heading_re = re.compile(r'<h[23][^>]*>([^<]+)</h[23]>', re.IGNORECASE)

    depts: list[dict] = []
    seen: set[str] = set()
    current_school = "General"

    events: list[tuple[int, str, re.Match]] = []
    for m in heading_re.finditer(html):
        events.append((m.start(), "heading", m))
    for m in link_re.finditer(html):
        events.append((m.start(), "link", m))
    events.sort(key=lambda x: x[0])

    for _, kind, m in events:
        if kind == "heading":
            text = re.sub(r'\s+', ' ', m.group(1)).strip()
            if text and "schedule" not in text.lower() and "course" not in text.lower():
                current_school = text
        else:
            filename = m.group("file").lower()
            if filename.startswith("95") or filename in ("index.html", "calendar.html"):
                continue
            dept_code = Path(filename).stem.lower()
            display_name = re.sub(r'\s+', ' ', m.group("name")).strip()
            display_name = re.split(r'\s*[–\[\(]', display_name)[0].strip()
            # Filter out nav links (very short or clearly non-dept)
            if not dept_code or len(display_name) < 3:
                continue
            if dept_code not in seen:
                seen.add(dept_code)
                depts.append({
                    "code": dept_code,
                    "name": display_name,
                    "school": current_school,
                })

    print(f"  [{campus}/{term_code}] discovered {len(depts)} depts from {used_url}")
    return depts


def discover_depts(opener, campus: str, term_code: str) -> list[dict]:
    if campus == "B":
        return discover_depts_bothell(opener, term_code)
    return discover_depts_tacoma_seattle(opener, campus, term_code)


def save_depts(campus: str, term_code: str, depts: list[dict]) -> None:
    out_dir = DEPTS_DIR / campus
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{term_code}.json"
    out_path.write_text(json.dumps(depts, indent=2), encoding="utf-8")


def load_depts(campus: str, term_code: str) -> list[dict]:
    path = DEPTS_DIR / campus / f"{term_code}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return []


def merge_depts(existing: list[dict], incoming: list[dict]) -> list[dict]:
    """Merge dept lists by code, preserving first-seen ordering and metadata."""
    merged: dict[str, dict] = {}
    for dept in [*existing, *incoming]:
        code = str(dept.get("code", "")).strip().lower()
        if not code:
            continue
        if code not in merged:
            merged[code] = {
                "code": code,
                "name": dept.get("name", code),
                "school": dept.get("school", "General"),
            }
    return list(merged.values())


# ── Campus download ────────────────────────────────────────────────────────────

def raw_path_campus(campus: str, term_code: str, dept_code: str) -> Path:
    return RAW_DIR / campus / f"{term_code}_{dept_code}.html"


def download_campus(opener, campus: str, term_codes: list[str],
                    discover: bool = True) -> None:
    """Download all dept pages for a campus across all term_codes."""
    campus_name = CAMPUSES.get(campus, campus)
    print(f"\n=== {campus_name} campus ({len(term_codes)} terms) ===")

    # Prefer newest terms for discovery, but fall back through the range.
    discovery_term = None
    known_depts: list[dict] = []
    for candidate_term in reversed(term_codes):
        cached = load_depts(campus, candidate_term)
        if cached and not discover:
            known_depts = merge_depts(known_depts, cached)
            discovery_term = candidate_term
            break
        probed = discover_depts(opener, campus, candidate_term)
        if probed:
            save_depts(campus, candidate_term, probed)
            known_depts = merge_depts(known_depts, probed)
            discovery_term = candidate_term
            break

    if not known_depts:
        print(f"  No dept list available for {campus}. Skipping.")
        return

    if discovery_term:
        print(f"  Using {len(known_depts)} seed departments discovered from {discovery_term}")

    raw_campus_dir = RAW_DIR / campus
    raw_campus_dir.mkdir(parents=True, exist_ok=True)

    total_saved = 0
    # Newest-to-oldest improves fallback coverage for historical terms whose
    # index pages are missing (e.g., AUT2022) by learning dept codes first.
    for term_code in reversed(term_codes):
        # Prefer term-specific dept list when available/discoverable.
        term_depts = load_depts(campus, term_code)
        if not term_depts and discover:
            discovered = discover_depts(opener, campus, term_code)
            if discovered:
                save_depts(campus, term_code, discovered)
                term_depts = discovered

        if term_depts:
            known_depts = merge_depts(known_depts, term_depts)
        else:
            # Bothell historical quarters often have no public registrar index page;
            # fallback to known dept URL patterns and substitute only the term code.
            term_depts = known_depts
            print(f"  {term_code}: no index/dept list; falling back to {len(term_depts)} known dept URLs")

        term_saved = 0
        for dept in term_depts:
            dept_code = dept["code"]
            target = raw_path_campus(campus, term_code, dept_code)
            if target.exists():
                continue  # already downloaded

            url_candidates = dept_html_urls(campus, term_code, dept_code)
            html, status, _ = fetch_first_html(opener, url_candidates)
            if html is None:
                if status != "request-failed: HTTPError":  # 404s are normal for old terms
                    print(f"  {term_code}/{dept_code}: {status}")
                continue

            target.write_text(html, encoding="utf-8")
            term_saved += 1

        if term_saved:
            print(f"  {term_code}: saved {term_saved} dept files")
        total_saved += term_saved

    print(f"  Total new files saved: {total_saved}")


# ── Legacy Bothell-CSS-only download (backward compat) ────────────────────────

def raw_path_for_url(term_code: str, url: str) -> Path:
    name = Path(urlparse(url).path).name or "catalog.html"
    stem = Path(name).stem
    return RAW_DIR / f"{term_code}_{stem}.html"


def download_legacy_css(opener) -> None:
    """Original behavior: download Bothell CSS pages into data/raw/ (flat)."""
    print("\n=== Legacy Bothell CSS download ===")
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for term in TERMS:
        urls = [term.url, *ADDITIONAL_TERM_URLS.get(term.code, [])]
        for url in urls:
            html, status = fetch_html(opener, url)
            target = raw_path_for_url(term.code, url)
            if html is None:
                print(f"- {term.code} {Path(url).name}: {status}")
                continue
            target.write_text(html, encoding="utf-8")
            print(f"- {term.code} {Path(url).name}: saved")


# ── CLI ────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download UW quarter schedule HTML for any campus/dept."
    )
    parser.add_argument(
        "--campus",
        default="legacy",
        choices=["legacy", "B", "T", "S", "all"],
        help=(
            "Campus to download: legacy=Bothell CSS only (default), "
            "B=Bothell all depts, T=Tacoma, S=Seattle, all=all campuses"
        ),
    )
    parser.add_argument(
        "--since",
        default=None,
        metavar="TERM",
        help="Only download terms at or after this term code (e.g. AUT2020). "
             "Useful to limit Seattle's large dataset.",
    )
    parser.add_argument(
        "--until",
        default=None,
        metavar="TERM",
        help="Only download terms at or before this term code (e.g. SPR2026).",
    )
    parser.add_argument(
        "--add-term",
        action="append",
        default=[],
        metavar="TERM",
        help="Add one-off term code(s) to this run (e.g. --add-term SUM2026).",
    )
    parser.add_argument(
        "--no-discover",
        action="store_true",
        help="Skip dept discovery; use cached dept list from data/depts/.",
    )
    parser.add_argument(
        "--cookie-file",
        default="",
        help="Path to UW cookie file (Netscape or JSON) for protected terms.",
    )
    args = parser.parse_args()

    try:
        opener = build_opener_with_cookies(args.cookie_file or None)
    except Exception as exc:
        raise SystemExit(f"Failed to load cookie file: {exc}") from exc

    if args.campus == "legacy":
        download_legacy_css(opener)
        return

    try:
        term_codes = configured_term_codes(extra_term_codes=EXTRA_TERM_CODES + args.add_term)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    if not term_codes:
        raise SystemExit("No term codes configured.")

    # Filter by --since
    if args.since:
        try:
            since_idx = term_codes.index(args.since)
            term_codes = term_codes[since_idx:]
        except ValueError:
            raise SystemExit(f"Unknown term code: {args.since!r}")

    # Filter by --until
    if args.until:
        try:
            until_idx = term_codes.index(args.until)
            term_codes = term_codes[:until_idx + 1]
        except ValueError:
            raise SystemExit(f"Unknown term code: {args.until!r}")

    if not term_codes:
        raise SystemExit("No terms left after applying --since/--until filters.")

    campuses = list(CAMPUSES.keys()) if args.campus == "all" else [args.campus]
    print(f"Downloading: campus={campuses}, terms={term_codes[0]}..{term_codes[-1]}")

    for campus in campuses:
        download_campus(
            opener,
            campus,
            term_codes,
            discover=not args.no_discover,
        )


if __name__ == "__main__":
    main()
