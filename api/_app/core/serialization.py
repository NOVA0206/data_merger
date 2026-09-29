"""JSON (de)serialization for core dataclasses, used to persist job state in Postgres
between chunked processing steps (each Vercel invocation is stateless)."""
from __future__ import annotations

from dataclasses import asdict

from .models import (
    CompanyFile,
    CompanyRecord,
    DirectorRecord,
    MatchMethod,
    MatchRecord,
    MatchStatus,
)


def company_record_to_dict(r: CompanyRecord) -> dict:
    return asdict(r)


def company_record_from_dict(d: dict) -> CompanyRecord:
    return CompanyRecord(**d)


def director_record_to_dict(d: DirectorRecord) -> dict:
    return asdict(d)


def director_record_from_dict(d: dict) -> DirectorRecord:
    return DirectorRecord(**d)


def company_file_to_dict(cf: CompanyFile) -> dict:
    d = asdict(cf)
    return d


def company_file_from_dict(d: dict) -> CompanyFile:
    directors = [DirectorRecord(**x) for x in d.get("directors", [])]
    return CompanyFile(
        source_id=d["source_id"],
        file_name=d["file_name"],
        extracted_company_name=d["extracted_company_name"],
        directors=directors,
        read_error=d.get("read_error"),
    )


def match_record_to_dict(m: MatchRecord) -> dict:
    d = asdict(m)
    d["status"] = m.status.value
    d["method"] = m.method.value
    return d


def match_record_from_dict(d: dict) -> MatchRecord:
    return MatchRecord(
        file_name=d["file_name"],
        extracted_company_name=d["extracted_company_name"],
        matched_company=d.get("matched_company"),
        matched_row_index=d.get("matched_row_index"),
        status=MatchStatus(d["status"]),
        method=MatchMethod(d["method"]),
        confidence=d["confidence"],
        source_file_id=d["source_file_id"],
        notes=d.get("notes", ""),
    )
