"""Company-name normalization for matching (not for display).

Normalization is deliberately conservative: it standardizes legal-suffix spelling,
punctuation, spacing and case so that superficially different spellings of the SAME
company compare equal, without collapsing distinct words that could distinguish two
DIFFERENT companies (e.g. it never strips "AUTOMOTIVE", "SYSTEMS", "INDIA", etc.).
"""
from __future__ import annotations

import re

# Order matters: longer/more specific phrases first.
_SUFFIX_MAP = [
    (r"\bPRIVATE\s+LIMITED\b", "PVT LTD"),
    (r"\bPVT\.?\s+LTD\.?\b", "PVT LTD"),
    (r"\bPUBLIC\s+LIMITED\b", "LTD"),
    (r"\bLIMITED\b", "LTD"),
    (r"\bLTD\.?\b", "LTD"),
    (r"\bCOMPANY\b", "CO"),
    (r"\bCO\.\b", "CO"),
    (r"\b&\b", "AND"),
]

_FILENAME_SUFFIX_RE = re.compile(
    r"[_\-\s]*(directorslist|directors[_\- ]?list|export)?[_\-\s]*\d{5,}\s*$",
    re.IGNORECASE,
)
_FILE_EXT_RE = re.compile(r"\.(xlsx|xls|csv)$", re.IGNORECASE)


def extract_company_name_from_filename(filename: str) -> str:
    """Derive a candidate company name from a source filename.

    Example:
        "AAKASH-PRESS-PARTS-PRIVATE-LIMITED_DirectorsList_export_1787054963853.xlsx"
        -> "AAKASH PRESS PARTS PRIVATE LIMITED"
    """
    name = _FILE_EXT_RE.sub("", filename)
    # Strip trailing "_DirectorsList_export_<digits>" / similar telemetry suffixes.
    name = _FILENAME_SUFFIX_RE.sub("", name)
    name = re.sub(r"directorslist|directors[_\- ]?list", "", name, flags=re.IGNORECASE)
    name = name.replace("_", " ").replace("-", " ")
    name = re.sub(r"\s+", " ", name).strip()
    return name


def normalize_company_name(name: str) -> str:
    """Normalize a company name into a canonical form for equality comparison."""
    if not name:
        return ""
    n = str(name).upper()
    n = n.replace("_", " ").replace("-", " ").replace("/", " ")
    n = re.sub(r"[.,()\[\]]", " ", n)
    n = re.sub(r"\s+", " ", n).strip()
    for pattern, repl in _SUFFIX_MAP:
        n = re.sub(pattern, repl, n)
    n = re.sub(r"\s+", " ", n).strip()
    return n


def normalized_key(name: str) -> str:
    """Fully squashed key (no spaces) for exact/normalized-tier comparisons."""
    return normalize_company_name(name).replace(" ", "")
