"""Shared dataclasses passed between core engine modules."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class MatchStatus(str, Enum):
    EXACT = "Exact Match"
    NORMALIZED = "Normalized Match"
    POSSIBLE = "Possible Match"
    NO_MATCH = "No Match"
    MANUAL_REVIEW = "Manual Review Required"


class MatchMethod(str, Enum):
    EXACT = "Exact"
    NORMALIZED = "Normalized"
    FUZZY = "Fuzzy"
    MANUAL = "Manual"


@dataclass
class CompanyRecord:
    """One row extracted from the master financial sheet."""

    row_index: int
    company_name: str
    net_profit: object = None
    revenue: object = None
    ebitda: object = None
    city: object = None
    company_products: object = None
    raw: dict = field(default_factory=dict)


@dataclass
class DirectorRecord:
    """One director row extracted from an individual company spreadsheet."""

    name: str
    email: str | None
    phone: str | None
    designation: str | None = None
    address: str | None = None
    linkedin: str | None = None


@dataclass
class CompanyFile:
    """One individual company spreadsheet discovered on disk / in Drive."""

    source_id: str  # local path or Google Drive file ID
    file_name: str
    extracted_company_name: str
    directors: list[DirectorRecord] = field(default_factory=list)
    read_error: str | None = None


@dataclass
class MatchRecord:
    file_name: str
    extracted_company_name: str
    matched_company: str | None
    matched_row_index: int | None
    status: MatchStatus
    method: MatchMethod
    confidence: float
    source_file_id: str
    notes: str = ""


@dataclass
class ValidationIssue:
    issue_type: str
    company_or_sheet_name: str
    matched_company: str
    problem: str
    recommended_action: str
    source_file: str
    status: str = "Open"


@dataclass
class ConsolidatedRow:
    company_name: str
    director_name: str = ""
    director_email: str = ""
    director_contact_numbers: str = ""
    net_profit: object = None
    revenue: object = None
    ebitda: object = None
    city: object = None
    company_products: object = None
    source_files: str = ""
