"""Configurable column-mapping system for the master financial sheet.

Column names in the source workbook vary across exports (extra spaces, asterisks,
percent vs amount variants). This module resolves a logical field (e.g. "net_profit")
to the correct physical column name using an ordered list of exact-match candidates
first, falling back to fuzzy matching only when no exact candidate is present.

Exact-match candidates are checked before fuzzy matching specifically to avoid
confusing an amount column (e.g. "EBITDA ") with its margin counterpart
(e.g. "EBITDA %"), which have high fuzzy-string similarity but different meaning.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from difflib import SequenceMatcher


def _norm_header(name: str) -> str:
    """Collapse whitespace and lowercase a header for comparison, keeping symbols."""
    return " ".join(str(name).strip().lower().split())


# Fields that must NEVER be satisfied by a column containing these substrings,
# even if the substring match looks close. Prevents amount/margin confusion.
EXCLUDE_SUBSTRINGS = {
    "net_profit": ["%", "margin", "growth"],
    "revenue": ["%", "growth", "margin"],
    "ebitda": ["%", "margin"],
}

# Logical field -> ordered list of exact header candidates (after _norm_header).
# Order matters: first match wins among exact candidates.
FIELD_SYNONYMS: dict[str, list[str]] = {
    "company_name": [
        "company name", "name of company", "entity name", "company",
    ],
    "net_profit": [
        "pat", "pat *", "net profit", "net income", "profit after tax",
        "pat (rs. in cr)", "profit after tax (pat)",
    ],
    "revenue": [
        "total revenue *", "total revenue", "revenue", "annual revenue",
        "turnover", "sales", "total revenue from operations",
        "total income",
    ],
    "ebitda": [
        "ebitda", "ebitda *", "ebitda value", "ebitda (rs. in cr)",
        "ebitda amount",
    ],
    "city": [
        "city", "registered city", "location",
    ],
    "company_products": [
        "products", "product description", "products manufactured",
        "business activities", "product portfolio", "products.1",
    ],
}

# Fuzzy fallback threshold (0-1). Only used when no exact candidate matched.
FUZZY_THRESHOLD = 0.72

# Synonyms for fields extracted from individual company (director) spreadsheets.
DIRECTOR_FIELD_SYNONYMS: dict[str, list[str]] = {
    "director_name": ["name", "director name", "full name", "director"],
    "director_email": ["email id", "email", "director email", "e-mail", "email address"],
    "director_phone": [
        "phone number", "phone", "contact number", "mobile", "mobile number",
        "director contact numbers", "contact",
    ],
    "designation": ["designation (category)", "designation", "category"],
    "address": ["address", "residential address"],
    "linkedin": ["linkedin", "linkedin url", "linkedin profile"],
}


@dataclass
class FieldMapping:
    """Result of resolving all logical fields against one sheet's headers."""

    resolved: dict[str, str] = field(default_factory=dict)  # logical -> actual column
    unresolved: list[str] = field(default_factory=list)
    ambiguous: dict[str, list[str]] = field(default_factory=dict)  # logical -> candidates


def _is_excluded(logical_field: str, header_norm: str) -> bool:
    for bad in EXCLUDE_SUBSTRINGS.get(logical_field, []):
        if bad in header_norm:
            return True
    return False


def resolve_field_mapping(
    columns: list[str],
    fields: list[str] | None = None,
    overrides: dict[str, str] | None = None,
    synonyms: dict[str, list[str]] | None = None,
) -> FieldMapping:
    """Resolve each logical field in `fields` to an actual column name.

    Strategy per field:
      1. If `overrides` names an actual column for this field, use it verbatim.
      2. Exact match (after header normalization) against FIELD_SYNONYMS, in order.
         The first synonym found among the sheet's columns wins.
      3. If duplicate-looking columns exist (e.g. "EBITDA " and "EBITDA .1") the
         first occurrence in `columns` order is used, since pandas appends ".1"
         to later duplicates of the same header and the earlier one is the
         canonical block in observed source files.
      4. Fuzzy fallback (difflib) only if no exact candidate exists at all.
         A field left unresolved by both steps is reported, not guessed.
    """
    synonyms_map = synonyms if synonyms is not None else FIELD_SYNONYMS
    fields = fields or list(synonyms_map.keys())
    overrides = overrides or {}
    header_norm_to_actual: dict[str, str] = {}
    for c in columns:
        n = _norm_header(c)
        if n not in header_norm_to_actual:
            header_norm_to_actual[n] = c  # keep first occurrence only

    result = FieldMapping()

    for lf in fields:
        if lf in overrides and overrides[lf] in columns:
            result.resolved[lf] = overrides[lf]
            continue

        synonyms = synonyms_map.get(lf, [])
        exact_hit = None
        for syn in synonyms:
            if syn in header_norm_to_actual and not _is_excluded(lf, syn):
                exact_hit = header_norm_to_actual[syn]
                break
        if exact_hit:
            result.resolved[lf] = exact_hit
            continue

        # Substring exact-ish: header contains synonym as whole word sequence
        # (handles trailing "*" / extra spaces in real headers not literally
        # listed as synonyms, e.g. "Total Revenue  * .1").
        substr_hit = None
        for syn in synonyms:
            for norm, actual in header_norm_to_actual.items():
                if syn and syn in norm and not _is_excluded(lf, norm):
                    substr_hit = actual
                    break
            if substr_hit:
                break
        if substr_hit:
            result.resolved[lf] = substr_hit
            continue

        # Fuzzy fallback
        best_score = 0.0
        best_col = None
        candidates = []
        for norm, actual in header_norm_to_actual.items():
            if _is_excluded(lf, norm):
                continue
            for syn in synonyms:
                score = SequenceMatcher(None, syn, norm).ratio()
                if score >= FUZZY_THRESHOLD:
                    candidates.append(actual)
                if score > best_score:
                    best_score = score
                    best_col = actual
        if best_col and best_score >= FUZZY_THRESHOLD:
            unique_candidates = sorted(set(candidates))
            if len(unique_candidates) > 1:
                result.ambiguous[lf] = unique_candidates
            else:
                result.resolved[lf] = best_col
        else:
            result.unresolved.append(lf)

    return result
