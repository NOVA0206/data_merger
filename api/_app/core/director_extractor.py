"""Reads an individual company spreadsheet and extracts DirectorRecord rows.

Handles the observed export format where NAME embeds a trailing date-of-birth
("SHARANBASAPPA BASAWANTRAO KUMBHAR 01/06/1965") and missing EMAIL ID / PHONE
NUMBER cells are represented as a literal "-".
"""
from __future__ import annotations

import re

import pandas as pd

from .field_mapping import DIRECTOR_FIELD_SYNONYMS, resolve_field_mapping
from .models import DirectorRecord

_TRAILING_DOB_RE = re.compile(r"\s+\d{1,2}/\d{1,2}/\d{4}\s*$")
# Some rows have no DOB and the export leaves a bare "-" placeholder instead
# (same convention as EMAIL ID / PHONE NUMBER "-" for missing values).
_TRAILING_DOB_PLACEHOLDER_RE = re.compile(r"\s+-\s*$")
_PLACEHOLDER_VALUES = {"-", "--", "n/a", "na", "none", ""}


def _clean(value) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    s = str(value).strip()
    if s.lower() in _PLACEHOLDER_VALUES:
        return None
    return s


def _clean_phone(value) -> str | None:
    """Preserve phone numbers as strings, keeping leading zeros / country codes intact."""
    s = _clean(value)
    if s is None:
        return None
    # pandas may read a numeric-looking phone as float (e.g. 919970055139.0).
    if s.endswith(".0") and s[:-2].isdigit():
        s = s[:-2]
    return s


def _strip_trailing_dob(name: str) -> str:
    name = _TRAILING_DOB_RE.sub("", name)
    name = _TRAILING_DOB_PLACEHOLDER_RE.sub("", name)
    return name.strip()


def load_company_sheet(path_or_buffer) -> pd.DataFrame:
    """Load an individual company workbook's data sheet.

    Reads all columns as strings first (dtype=str for phone-safety on later parsing)
    isn't applied globally because names/addresses should stay natural text; instead
    the phone column is coerced defensively in `extract_directors`.
    """
    sheets = pd.read_excel(path_or_buffer, sheet_name=None)
    if not sheets:
        return pd.DataFrame()
    if len(sheets) == 1:
        return next(iter(sheets.values()))
    # Prefer a sheet literally named "data" (observed convention); else the largest.
    for name, df in sheets.items():
        if name.strip().lower() == "data":
            return df
    return max(sheets.values(), key=lambda df: df.shape[0] * df.shape[1])


def extract_directors(df: pd.DataFrame) -> list[DirectorRecord]:
    if df.empty:
        return []
    mapping = resolve_field_mapping(
        list(df.columns),
        fields=list(DIRECTOR_FIELD_SYNONYMS.keys()),
        synonyms=DIRECTOR_FIELD_SYNONYMS,
    )
    name_col = mapping.resolved.get("director_name")
    if not name_col:
        return []

    email_col = mapping.resolved.get("director_email")
    phone_col = mapping.resolved.get("director_phone")
    designation_col = mapping.resolved.get("designation")
    address_col = mapping.resolved.get("address")
    linkedin_col = mapping.resolved.get("linkedin")

    directors: list[DirectorRecord] = []
    for _, row in df.iterrows():
        raw_name = _clean(row.get(name_col))
        if not raw_name:
            continue
        name = _strip_trailing_dob(raw_name)
        directors.append(
            DirectorRecord(
                name=name,
                email=_clean(row.get(email_col)) if email_col else None,
                phone=_clean_phone(row.get(phone_col)) if phone_col else None,
                designation=_clean(row.get(designation_col)) if designation_col else None,
                address=_clean(row.get(address_col)) if address_col else None,
                linkedin=_clean(row.get(linkedin_col)) if linkedin_col else None,
            )
        )
    return directors
