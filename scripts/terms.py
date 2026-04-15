#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Optional


@dataclass(frozen=True)
class Term:
    code: str
    url: str  # legacy CSS-only protected URL (kept for backward compat)


# ── Campus metadata ────────────────────────────────────────────────────────────

CAMPUSES: Dict[str, str] = {
    "B": "Bothell",
    "T": "Tacoma",
    "S": "Seattle",
}

QUARTER_ORDER = {"AUT": 0, "WIN": 1, "SPR": 2, "SUM": 3}

# Default dataset window for this project.
# Covers AUT2020 through SPR2026.
DEFAULT_START_AUTUMN_YEAR = 2020
DEFAULT_END_SPRING_YEAR = 2026

# Add future single terms here as they become available, e.g. "SUM2026".
# Keep codes in TERM format: AUTYYYY / WINYYYY / SPRYYYY / SUMYYYY.
EXTRA_TERM_CODES: List[str] = []


# ── URL helpers ────────────────────────────────────────────────────────────────

def term_to_uwb_slug(term_code: str) -> str:
    """Convert e.g. 'SPR2026' -> 'spring-2026' for uwb.edu registrar URLs."""
    prefix = term_code[:3].upper()
    year = term_code[3:]
    season_map = {"AUT": "autumn", "WIN": "winter", "SPR": "spring", "SUM": "summer"}
    season = season_map.get(prefix, prefix.lower())
    return f"{season}-{year}"


def _validate_term_code(term_code: str) -> str:
    code = str(term_code or "").strip().upper()
    if len(code) != 7 or code[:3] not in QUARTER_ORDER:
        raise ValueError(f"Invalid term code: {term_code!r}")
    int(code[3:])  # raises if not numeric
    return code


def index_page_url(campus: str, term_code: str) -> str:
    """Return the course-offerings index page URL for a given campus and term."""
    return index_page_urls(campus, term_code)[0]


def index_page_urls(campus: str, term_code: str) -> List[str]:
    """Return candidate index URLs (new and legacy patterns) for a campus/term."""
    code = _validate_term_code(term_code)
    if campus == "B":
        slug = term_to_uwb_slug(code)
        return [
            f"https://www.uwb.edu/registrar/time/{slug}",
            f"https://www.uwb.edu/registrar/time/{slug}-course-offerings",
            f"https://www.washington.edu/students/timeschd/B/{code}/",
            f"https://www.washington.edu/students/timeschd/pub/B/{code}/",
        ]
    if campus == "T":
        return [
            f"https://www.washington.edu/students/timeschd/T/{code}/",
            f"https://www.washington.edu/students/timeschd/pub/T/{code}/",
        ]
    if campus == "S":
        return [
            f"https://www.washington.edu/students/timeschd/{code}/",
            f"https://www.washington.edu/students/timeschd/pub/{code}/",
        ]
    raise ValueError(f"Unknown campus code: {campus!r}")


def dept_html_url(campus: str, term_code: str, dept_code: str) -> str:
    """Return the public per-dept schedule URL for a campus / term / dept_code."""
    return dept_html_urls(campus, term_code, dept_code)[0]


def dept_html_urls(campus: str, term_code: str, dept_code: str) -> List[str]:
    """Return candidate per-dept schedule URLs (new and legacy patterns)."""
    code = _validate_term_code(term_code)
    dept = str(dept_code or "").strip().lower()
    if campus == "B":
        return [
            f"https://www.washington.edu/students/timeschd/B/{code}/{dept}.html",
            f"https://www.washington.edu/students/timeschd/pub/B/{code}/{dept}.html",
        ]
    if campus == "T":
        return [
            f"https://www.washington.edu/students/timeschd/T/{code}/{dept}.html",
            f"https://www.washington.edu/students/timeschd/pub/T/{code}/{dept}.html",
        ]
    if campus == "S":
        return [
            f"https://www.washington.edu/students/timeschd/{code}/{dept}.html",
            f"https://www.washington.edu/students/timeschd/pub/{code}/{dept}.html",
        ]
    raise ValueError(f"Unknown campus code: {campus!r}")


# ── Term generation ────────────────────────────────────────────────────────────

def generate_term_codes(start_autumn_year: int = 2017, end_spring_year: int = 2026) -> List[str]:
    """Return all term codes from AUT{start} through the quarter ending in end_spring_year."""
    codes: List[str] = []
    for year in range(start_autumn_year, end_spring_year):
        codes.append(f"AUT{year}")
        next_year = year + 1
        codes.append(f"WIN{next_year}")
        codes.append(f"SPR{next_year}")
        if next_year < end_spring_year:
            codes.append(f"SUM{next_year}")
    return codes


def configured_term_codes(
    start_autumn_year: int = DEFAULT_START_AUTUMN_YEAR,
    end_spring_year: int = DEFAULT_END_SPRING_YEAR,
    extra_term_codes: Optional[List[str]] = None,
) -> List[str]:
    """Return base term window plus optional explicit extra terms, sorted and deduped."""
    base = generate_term_codes(start_autumn_year, end_spring_year)
    extras = extra_term_codes if extra_term_codes is not None else EXTRA_TERM_CODES
    merged = {code: code for code in base}
    for term in extras:
        normalized = _validate_term_code(term)
        merged[normalized] = normalized
    return sorted(merged.keys(), key=term_sort_key)


def latest_term_for_today(today: Optional[date] = None) -> str:
    current = today or date.today()
    year = current.year
    if current >= date(year, 9, 1):
        return f"AUT{year}"
    if current >= date(year, 6, 1):
        return f"SUM{year}"
    if current >= date(year, 3, 1):
        return f"SPR{year}"
    return f"WIN{year}"


def latest_spring_year_for_term(term_code: str) -> int:
    prefix = term_code[:3].upper()
    year = int(term_code[3:])
    return year + 1 if prefix == "AUT" else year


def generate_terms_to_latest(start_autumn_year: int = DEFAULT_START_AUTUMN_YEAR) -> List[Term]:
    # Kept for backward compatibility. Uses configured term window by default.
    codes = configured_term_codes(start_autumn_year=start_autumn_year)
    return [
        Term(
            code,
            f"https://www.washington.edu/students/timeschd/B/{code}/css.html",
        )
        for code in codes
    ]


def term_sort_key(term_code: str) -> tuple[int, int]:
    prefix = str(term_code or "")[:3].upper()
    year_part = str(term_code or "")[3:]
    try:
        year = int(year_part)
    except ValueError:
        return (9999, 99)
    quarter_idx = QUARTER_ORDER.get(prefix, 99)
    academic_year = year if prefix == "AUT" else year - 1
    return (academic_year, quarter_idx)


def all_term_codes_to_latest(start_autumn_year: int = DEFAULT_START_AUTUMN_YEAR) -> List[str]:
    # Kept for backward compatibility. Returns configured project window by default.
    return configured_term_codes(start_autumn_year=start_autumn_year)


# ── Backward-compat exports (used by legacy CSS-only paths) ───────────────────

TERMS = generate_terms_to_latest()


def generate_additional_term_urls(terms: List[Term]) -> Dict[str, List[str]]:
    return {
        term.code: [
            f"https://www.washington.edu/students/timeschd/B/{term.code}/95css.html"
        ]
        for term in terms
    }


ADDITIONAL_TERM_URLS = generate_additional_term_urls(TERMS)
