#!/usr/bin/env python3
"""Build catalog JSON from raw HTML schedule files.

Legacy mode (default):  reads data/raw/{TERM}_css.html  →  data/catalog.json
Multi-campus mode:      reads data/raw/{CAMPUS}/{TERM}_{dept}.html
                         →  data/shards/{CAMPUS}/{dept}.json
                         →  data/catalog_index.json
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from terms import (
    ADDITIONAL_TERM_URLS,
    CAMPUSES,
    EXTRA_TERM_CODES,
    TERMS,
    configured_term_codes,
    term_sort_key,
)

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
DEPTS_DIR = ROOT / "data" / "depts"
SHARDS_DIR = ROOT / "data" / "shards"
OUT_PATH = ROOT / "data" / "catalog.json"          # legacy
INDEX_PATH = ROOT / "data" / "catalog_index.json"  # new multi-campus
FIX_NAMES_PATH = ROOT / "fixNames.txt"


# ── Regexes ────────────────────────────────────────────────────────────────────

# Legacy CSS-only pattern (backward compat)
COURSE_HEADER_RE = re.compile(
    r"<A NAME=css(?P<num>\d{3})>CSS(?:&nbsp;|\s)+(?P=num)\s*</A>&nbsp;<A HREF=[^>]+>(?P<title>[^<]+)</A>",
    re.IGNORECASE,
)

SLN_LINE_RE = re.compile(r"SLN=(?P<sln>\d{5})", re.IGNORECASE)
SECTION_RE = re.compile(r">\d{5}</A>\s*(?P<section>[A-Z0-9])\b")
NAME_CANDIDATE_RE = re.compile(r"^[A-Za-z][A-Za-z,.' -]*[A-Za-z.]$")
ENROLLMENT_RE = re.compile(r"\b\d{1,4}\s*/\s*\d{1,4}[A-Z]?\b")
STATUS_TOKENS = {"open", "closed", "full", "cancelled"}
NON_INSTRUCTOR_RE = re.compile(
    r"^(?:\$\d+(?:\.\d+)?|CR/NC|C/NC|S/NS|NS|N|Y|%|\*+)$",
    re.IGNORECASE,
)
DAY_TOKEN_RE = re.compile(
    r"^(?:IS|M|T|W|Th|F|Sat\.?|Sun\.?|MW|WF|MWF|TTh|MTWTh|MTWThF)$",
    re.IGNORECASE,
)
INSTRUCTOR_TAIL_RE = re.compile(
    r"(?:\b(?:Open|Closed|Full|Cancelled)\b\s+)?"
    r"\d{1,4}\s*/\s*\d{1,4}[A-Z]?"
    r"(?:\s+(?:CR/NC|C/NC|S/NS|NS|N|Y))?"
    r"(?:\s+\$\d+(?:\.\d+)?)?"
    r"(?:\s+[%*]+)?"
    r"\s+(?P<instructor>[A-Za-z][A-Za-z,.' -]*[A-Za-z.])\s*$",
    re.IGNORECASE,
)


def make_course_header_re(anchor_prefix: str) -> re.Pattern:
    """
    Build a regex for course headers given the anchor prefix.
    Anchor prefix = lowercase dept code as it appears in <A NAME=...>.
    E.g. 'css' -> matches <A NAME=css143>CSS 143</A> ...
         'tcss' -> matches <A NAME=tcss143>TCSS 143</A> ...
    """
    lc = re.escape(anchor_prefix.lower())
    return re.compile(
        rf'<A\s+NAME={lc}(?P<num>\d+)>(?P<display>[^<]+)</A>(?:&nbsp;|\s)*<A\s+HREF=[^>]+>(?P<title>[^<]+)</A>',
        re.IGNORECASE,
    )


# ── Text cleaning ──────────────────────────────────────────────────────────────

def clean_text(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value)
    value = unescape(value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def strip_tags_preserve_spacing(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value)
    value = unescape(value)
    return value.replace("\xa0", " ")


# ── Name fixes ─────────────────────────────────────────────────────────────────

def load_name_fixes() -> dict[str, str]:
    if not FIX_NAMES_PATH.exists():
        return {}
    mapping: dict[str, str] = {}
    for raw_line in FIX_NAMES_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        bad, good = line.split("=", 1)
        bad_clean = bad.strip()
        good_clean = good.strip()
        if bad_clean and good_clean:
            mapping[bad_clean.lower()] = good_clean
    return mapping


def apply_name_fix(name: str, fixes: dict[str, str]) -> str:
    normalized = str(name or "").strip()
    if not normalized:
        return "TBA"
    return fixes.get(normalized.lower(), normalized)


# ── Instructor extraction ──────────────────────────────────────────────────────

def extract_instructor(text_line: str) -> str:
    chunks = [chunk.strip() for chunk in re.split(r"\s{2,}", text_line) if chunk.strip()]
    if len(chunks) < 2:
        return "TBA"

    def is_instructor_candidate(chunk: str) -> bool:
        token = chunk.strip()
        if not token:
            return False
        lower = token.lower()
        if lower in STATUS_TOKENS:
            return False
        if DAY_TOKEN_RE.match(token):
            return False
        if "to be arranged" in lower:
            return False
        if ENROLLMENT_RE.search(token):
            return False
        if NON_INSTRUCTOR_RE.match(token):
            return False
        return bool(NAME_CANDIDATE_RE.match(token))

    # First, try a direct match anchored on the enrollment column near row end.
    normalized_line = re.sub(r"\s+", " ", text_line).strip()
    tail_match = INSTRUCTOR_TAIL_RE.search(normalized_line)
    if tail_match:
        candidate = tail_match.group("instructor").strip()
        if is_instructor_candidate(candidate):
            return candidate

    # Current UW schedule format puts enrollment as a reliable anchor before
    # optional grade/fee columns and the instructor token at the far right.
    enrollment_idx = next((i for i, chunk in enumerate(chunks) if ENROLLMENT_RE.search(chunk)), None)
    if enrollment_idx is not None:
        for candidate in reversed(chunks[enrollment_idx + 1:]):
            if is_instructor_candidate(candidate):
                return candidate
        return "TBA"

    # Fallback for older rows that place instructor right before status columns.
    for i, chunk in enumerate(chunks):
        lower = chunk.lower()
        if lower in STATUS_TOKENS:
            if i == 0:
                return "TBA"
            candidate = chunks[i - 1]
            if is_instructor_candidate(candidate):
                return candidate
            return "TBA"

    return "TBA"


# ── Parser ─────────────────────────────────────────────────────────────────────

def parse_dept_html(
    term_code: str,
    html: str,
    name_fixes: dict[str, str],
    anchor_prefix: str,
    campus: str = "B",
    dept_code: str = "css",
    dept_name: str = "",
) -> list[dict]:
    """Parse a single dept HTML schedule page into a list of section records."""
    header_re = make_course_header_re(anchor_prefix)
    items: list[dict] = []
    headers = list(header_re.finditer(html))

    for i, header in enumerate(headers):
        course_num = header.group("num")
        course_display = clean_text(header.group("display"))  # e.g. "CSS 143" or "TCSS 143"
        course_title = clean_text(header.group("title"))
        start = header.end()
        end = headers[i + 1].start() if i + 1 < len(headers) else len(html)
        block = html[start:end]

        for line in block.splitlines():
            if not SLN_LINE_RE.search(line):
                continue
            section_match = SECTION_RE.search(line)
            if not section_match:
                continue
            text_line = strip_tags_preserve_spacing(line)
            instructor = extract_instructor(text_line)
            instructor = apply_name_fix(instructor, name_fixes)
            items.append({
                "campus": campus,
                "dept": dept_code,
                "deptName": dept_name,
                "term": term_code,
                "course": course_display,
                "courseTitle": course_title,
                "section": section_match.group("section"),
                "instructor": instructor,
            })

    # Deduplicate
    unique: dict[tuple, dict] = {}
    for item in items:
        key = (item["term"], item["course"], item["section"], item["instructor"])
        unique[key] = item
    return list(unique.values())


# ── Legacy parse (keeps catalog.json working) ──────────────────────────────────

def parse_term_legacy(term: str, html: str, name_fixes: dict[str, str]) -> list[dict]:
    items: list[dict] = []
    headers = list(COURSE_HEADER_RE.finditer(html))
    for i, header in enumerate(headers):
        course_num = header.group("num")
        course_title = clean_text(header.group("title"))
        start = header.end()
        end = headers[i + 1].start() if i + 1 < len(headers) else len(html)
        block = html[start:end]
        for line in block.splitlines():
            if not SLN_LINE_RE.search(line):
                continue
            section_match = SECTION_RE.search(line)
            if not section_match:
                continue
            text_line = strip_tags_preserve_spacing(line)
            instructor = extract_instructor(text_line)
            instructor = apply_name_fix(instructor, name_fixes)
            items.append({
                "term": term,
                "course": f"CSS {course_num}",
                "courseTitle": course_title,
                "section": section_match.group("section"),
                "instructor": instructor,
            })
    unique: dict[tuple, dict] = {}
    for item in items:
        key = (item["term"], item["course"], item["section"], item["instructor"])
        unique[key] = item
    return list(unique.values())


def fetch_or_read_term_page(term: str, url: str) -> tuple[Optional[str], str]:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    name = Path(urlparse(url).path).name or "catalog.html"
    stem = Path(name).stem
    raw_path = RAW_DIR / f"{term}_{stem}.html"
    if raw_path.exists():
        return raw_path.read_text(encoding="utf-8", errors="replace"), "local-file"
    return None, "unavailable"


# ── Multi-campus build ─────────────────────────────────────────────────────────

def load_depts_for_campus(campus: str) -> list[dict]:
    """
    Aggregate dept list for a campus from all discovered term dept files.
    Returns a deduplicated list with school groupings from the most recent term.
    """
    depts_campus_dir = DEPTS_DIR / campus
    if not depts_campus_dir.exists():
        return []

    # Use the most recent term's dept file for school groupings.
    # Sort by academic term ordering (AUT/WIN/SPR/SUM + year), not lexicographic filename.
    term_files = sorted(
        depts_campus_dir.glob("*.json"),
        key=lambda p: term_sort_key(p.stem),
        reverse=True,
    )
    if not term_files:
        return []

    return json.loads(term_files[0].read_text(encoding="utf-8"))


def build_shard(campus: str, dept: dict, all_term_codes: list[str],
                name_fixes: dict[str, str]) -> tuple[list[dict], int]:
    """Build the records for one dept shard. Returns (records, file_count)."""
    dept_code = dept["code"]
    dept_name = dept.get("name", dept_code)
    # The anchor prefix in the HTML is the stem of the filename (without 95 prefix)
    anchor_prefix = dept_code.lstrip("9").lstrip("5") if dept_code.startswith("95") else dept_code

    raw_campus_dir = RAW_DIR / campus
    all_items: list[dict] = []
    file_count = 0

    for term_code in all_term_codes:
        raw_path = raw_campus_dir / f"{term_code}_{dept_code}.html"
        if not raw_path.exists():
            continue
        html = raw_path.read_text(encoding="utf-8", errors="replace")
        items = parse_dept_html(
            term_code, html, name_fixes,
            anchor_prefix=anchor_prefix,
            campus=campus,
            dept_code=dept_code,
            dept_name=dept_name,
        )
        all_items.extend(items)
        file_count += 1

    # Also check for 95{dept} fee-based variant
    fee_code = f"95{dept_code}"
    for term_code in all_term_codes:
        raw_path = raw_campus_dir / f"{term_code}_{fee_code}.html"
        if not raw_path.exists():
            continue
        html = raw_path.read_text(encoding="utf-8", errors="replace")
        items = parse_dept_html(
            term_code, html, name_fixes,
            anchor_prefix=anchor_prefix,
            campus=campus,
            dept_code=dept_code,
            dept_name=dept_name,
        )
        all_items.extend(items)
        file_count += 1

    # Deduplicate across all terms
    unique: dict[tuple, dict] = {}
    for item in all_items:
        key = (item["term"], item["course"], item["section"], item["instructor"])
        unique[key] = item

    records = sorted(
        unique.values(),
        key=lambda x: (term_sort_key(x["term"]), x["course"], x["instructor"]),
    )
    return records, file_count


def build_campus_shards(
    campus: str,
    dept_filter: str | None,
    name_fixes: dict[str, str],
    term_codes: list[str],
) -> list[dict]:
    """
    Build all shards for a campus. Returns dept summary list for the index.
    """
    depts = load_depts_for_campus(campus)
    if not depts:
        print(f"  [{campus}] No dept list found in data/depts/{campus}/. "
              f"Run download_catalog.py --campus {campus} first.")
        return []

    shard_dir = SHARDS_DIR / campus
    shard_dir.mkdir(parents=True, exist_ok=True)

    campus_dept_summary: list[dict] = []
    for dept in depts:
        dept_code = dept["code"]
        if dept_filter and dept_code != dept_filter.lower():
            continue

        records, file_count = build_shard(campus, dept, term_codes, name_fixes)
        if not records and file_count == 0:
            continue  # no data downloaded yet

        out_path = shard_dir / f"{dept_code}.json"
        payload = {
            "generatedAt": _now_iso(),
            "campus": campus,
            "dept": dept_code,
            "deptName": dept.get("name", dept_code),
            "records": records,
        }
        out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"  [{campus}/{dept_code}] {len(records)} records from {file_count} files → {out_path.name}")

        # Keep empty shards on disk for diagnostics, but do not include depts
        # with zero records in the UI index/menu.
        if len(records) == 0:
            continue

        campus_dept_summary.append({
            "code": dept_code,
            "name": dept.get("name", dept_code),
            "school": dept.get("school", ""),
            "recordCount": len(records),
        })

    return campus_dept_summary


def build_catalog_index(campus_summaries: dict[str, list[dict]]) -> None:
    """Write data/catalog_index.json from aggregated campus dept summaries."""
    campuses_data: dict[str, dict] = {}

    for campus_code, depts_summary in campus_summaries.items():
        if not depts_summary:
            continue
        # Group depts by school
        schools_map: dict[str, list[dict]] = {}
        for dept in depts_summary:
            school = dept.get("school") or "General"
            schools_map.setdefault(school, []).append({
                "code": dept["code"],
                "name": dept["name"],
                "recordCount": dept["recordCount"],
            })

        schools = [
            {"name": school_name, "depts": dept_list}
            for school_name, dept_list in schools_map.items()
        ]
        campuses_data[campus_code] = {
            "name": CAMPUSES.get(campus_code, campus_code),
            "schools": schools,
        }

    payload = {
        "generatedAt": _now_iso(),
        "campuses": campuses_data,
    }
    INDEX_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\nWrote catalog_index.json with {len(campuses_data)} campus(es)")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


# ── CLI ────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build catalog JSON from raw schedule HTML."
    )
    parser.add_argument(
        "--campus",
        default="legacy",
        choices=["legacy", "B", "T", "S", "all"],
        help="Campus to build: legacy=Bothell CSS only (default), B/T/S=specific campus, all=all",
    )
    parser.add_argument(
        "--dept",
        default=None,
        metavar="CODE",
        help="Only build this dept code (e.g. css). Implies a specific campus.",
    )
    parser.add_argument(
        "--write-index",
        action="store_true",
        help="(Re)write catalog_index.json from existing shard metadata.",
    )
    parser.add_argument(
        "--since",
        default=None,
        metavar="TERM",
        help="Only build terms at or after this term code (e.g. AUT2020).",
    )
    parser.add_argument(
        "--until",
        default=None,
        metavar="TERM",
        help="Only build terms at or before this term code (e.g. SPR2026).",
    )
    parser.add_argument(
        "--add-term",
        action="append",
        default=[],
        metavar="TERM",
        help="Add one-off term code(s) to this build (e.g. --add-term SUM2026).",
    )
    args = parser.parse_args()

    name_fixes = load_name_fixes()

    # ── Legacy Bothell CSS → catalog.json ─────────────────────────────────────
    if args.campus == "legacy":
        all_items: list[dict] = []
        report = []
        for entry in TERMS:
            term = entry.code
            sources = []
            term_items: list[dict] = []
            for url in [entry.url, *ADDITIONAL_TERM_URLS.get(term, [])]:
                html, source = fetch_or_read_term_page(term, url)
                sources.append(source)
                if not html:
                    continue
                term_items.extend(parse_term_legacy(term, html, name_fixes))
            unique_term: dict[tuple, dict] = {}
            for item in term_items:
                key = (item["term"], item["course"], item["section"], item["instructor"])
                unique_term[key] = item
            deduped = list(unique_term.values())
            all_items.extend(deduped)
            report.append({"term": term, "source": "+".join(sorted(set(sources))), "records": len(deduped)})

        unique_all: dict[tuple, dict] = {}
        for item in all_items:
            key = (item["term"], item["course"], item["section"], item["instructor"])
            unique_all[key] = item
        deduped_items = list(unique_all.values())

        OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "generatedAt": _now_iso(),
            "records": sorted(
                deduped_items,
                key=lambda x: (term_sort_key(x["term"]), x["course"], x["instructor"], x["section"]),
            ),
            "report": report,
        }
        OUT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"Wrote {len(payload['records'])} records to {OUT_PATH}")
        for row in report:
            print(f"- {row['term']}: {row['records']} records ({row['source']})")
        return

    # ── Multi-campus shard build ───────────────────────────────────────────────
    campuses = list(CAMPUSES.keys()) if args.campus == "all" else [args.campus]
    all_summaries: dict[str, list[dict]] = {}

    try:
        term_codes = configured_term_codes(extra_term_codes=EXTRA_TERM_CODES + args.add_term)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    if args.since:
        try:
            since_idx = term_codes.index(args.since)
            term_codes = term_codes[since_idx:]
        except ValueError:
            raise SystemExit(f"Unknown term code: {args.since!r}")

    if args.until:
        try:
            until_idx = term_codes.index(args.until)
            term_codes = term_codes[:until_idx + 1]
        except ValueError:
            raise SystemExit(f"Unknown term code: {args.until!r}")

    if not term_codes:
        raise SystemExit("No terms left after applying --since/--until filters.")

    for campus in campuses:
        print(f"\n=== Building {CAMPUSES.get(campus, campus)} ===")
        summary = build_campus_shards(campus, args.dept, name_fixes, term_codes)
        all_summaries[campus] = summary

    # Rebuild index after any campus build
    if args.write_index or not args.dept:
        # Merge with any pre-existing index data for campuses we didn't rebuild
        existing_index: dict[str, list[dict]] = {}
        if INDEX_PATH.exists():
            try:
                idx = json.loads(INDEX_PATH.read_text())
                for camp, data in idx.get("campuses", {}).items():
                    existing_depts: list[dict] = []
                    for school in data.get("schools", []):
                        for dept in school.get("depts", []):
                            existing_depts.append({
                                "code": dept["code"],
                                "name": dept["name"],
                                "school": school["name"],
                                "recordCount": dept.get("recordCount", 0),
                            })
                    existing_index[camp] = existing_depts
            except Exception:
                pass

        merged: dict[str, list[dict]] = {**existing_index, **all_summaries}
        build_catalog_index(merged)


if __name__ == "__main__":
    main()
