"""Builds the one-row-per-company Final Consolidated Data table.

Multiple directors for the same company are combined into semicolon-separated
values, preserving positional alignment between name/email/phone. Financial data
always comes from the master sheet row that a spreadsheet was matched to; it is
never invented, and it is never copied from a different company's row.
"""
from __future__ import annotations

from .models import CompanyFile, CompanyRecord, ConsolidatedRow, MatchRecord, MatchStatus

ACCEPTED_STATUSES = {MatchStatus.EXACT, MatchStatus.NORMALIZED, MatchStatus.POSSIBLE}


def build_consolidated_rows(
    master_records: list[CompanyRecord],
    company_files: dict[str, CompanyFile],  # keyed by source_id
    match_records: list[MatchRecord],
) -> list[ConsolidatedRow]:
    """One row per master company. Companies with no accepted match still appear
    (with blank director fields) so every master company is represented; companies
    whose spreadsheet could not be confidently matched are NOT merged onto them.
    """
    matches_by_row_index: dict[int, list[MatchRecord]] = {}
    for m in match_records:
        if m.status in ACCEPTED_STATUSES and m.matched_row_index is not None:
            matches_by_row_index.setdefault(m.matched_row_index, []).append(m)

    rows: list[ConsolidatedRow] = []
    for rec in master_records:
        matches = matches_by_row_index.get(rec.row_index, [])

        names: list[str] = []
        emails: list[str] = []
        phones: list[str] = []
        source_files: list[str] = []

        for m in matches:
            cf = company_files.get(m.source_file_id)
            if not cf:
                continue
            source_files.append(cf.file_name)
            for d in cf.directors:
                names.append(d.name or "")
                emails.append(d.email or "")
                phones.append(d.phone or "")

        rows.append(
            ConsolidatedRow(
                company_name=rec.company_name,
                director_name="; ".join(names),
                director_email="; ".join(emails),
                director_contact_numbers="; ".join(phones),
                net_profit=rec.net_profit,
                revenue=rec.revenue,
                ebitda=rec.ebitda,
                city=rec.city,
                company_products=rec.company_products,
                source_files="; ".join(source_files),
            )
        )
    return rows
