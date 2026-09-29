"""Builds the {sheet_name: rows} payload used to create a Google Spreadsheet
mirroring the same 3 sheets as the Excel export, via DriveClient.create_spreadsheet_from_rows.
"""
from __future__ import annotations

from .excel_exporter import FINAL_COLUMNS, MATCHING_LOG_COLUMNS, VALIDATION_COLUMNS
from .models import ConsolidatedRow, MatchRecord, ValidationIssue


def build_sheets_payload(
    consolidated_rows: list[ConsolidatedRow],
    validation_issues: list[ValidationIssue],
    match_records: list[MatchRecord],
    summary: dict,
) -> dict[str, list[list]]:
    final_rows = [FINAL_COLUMNS] + [
        [
            r.company_name,
            r.director_email,
            r.director_name,
            r.director_contact_numbers,
            r.revenue,
            r.ebitda,
            r.net_profit,
        ]
        for r in consolidated_rows
    ]

    validation_rows = [VALIDATION_COLUMNS] + [
        [i.issue_type, i.company_or_sheet_name, i.matched_company, i.problem, i.recommended_action, i.source_file, i.status]
        for i in validation_issues
    ]

    log_rows = [MATCHING_LOG_COLUMNS] + [
        [m.file_name, m.extracted_company_name, m.matched_company or "", m.status.value, m.method.value, m.confidence, m.source_file_id, m.notes]
        for m in match_records
    ]

    summary_rows = [["Metric", "Value"]] + [[k.replace("_", " ").title(), v] for k, v in summary.items()]

    return {
        "Final Consolidated Data": final_rows,
        "Validation & Review": validation_rows,
        "Matching Log": log_rows,
        "Validation Summary": summary_rows,
    }
