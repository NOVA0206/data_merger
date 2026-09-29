"""Writes the final consolidated workbook: 3 sheets, formatted, formula-free data dump."""
from __future__ import annotations

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from .models import ConsolidatedRow, MatchRecord, ValidationIssue

HEADER_FILL = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
HEADER_FONT = Font(name="Arial", bold=True, color="FFFFFF")
BODY_FONT = Font(name="Arial")

FINAL_COLUMNS = [
    "Company Name",
    "Director Name",
    "Director Email",
    "Director Contact Numbers",
    "Net Profit",
    "Revenue",
    "EBITDA",
    "City",
    "Company Products",
]

VALIDATION_COLUMNS = [
    "Issue Type",
    "Company / Sheet Name",
    "Matched Company",
    "Problem",
    "Recommended Action",
    "Source File",
    "Status",
]

MATCHING_LOG_COLUMNS = [
    "Individual Sheet/File Name",
    "Extracted Company Name",
    "Matched Master Company",
    "Match Status",
    "Match Method",
    "Confidence",
    "Source File ID",
    "Notes",
]


def _write_header(ws: Worksheet, columns: list[str]) -> None:
    for i, col in enumerate(columns, start=1):
        cell = ws.cell(row=1, column=i, value=col)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(vertical="center", wrap_text=True)
    ws.freeze_panes = "A2"


def _autosize(ws: Worksheet, columns: list[str], max_width: int = 60) -> None:
    for i, col in enumerate(columns, start=1):
        letter = get_column_letter(i)
        best = len(col)
        for row in ws.iter_rows(min_col=i, max_col=i, min_row=2):
            for cell in row:
                if cell.value is not None:
                    best = max(best, min(len(str(cell.value)), max_width))
        ws.column_dimensions[letter].width = best + 2


def export_workbook(
    consolidated_rows: list[ConsolidatedRow],
    validation_issues: list[ValidationIssue],
    match_records: list[MatchRecord],
    summary: dict,
    output_path: str,
) -> None:
    wb = Workbook()

    ws_final = wb.active
    ws_final.title = "Final Consolidated Data"
    _write_header(ws_final, FINAL_COLUMNS)
    for r, row in enumerate(consolidated_rows, start=2):
        ws_final.cell(row=r, column=1, value=row.company_name).font = BODY_FONT
        ws_final.cell(row=r, column=2, value=row.director_name).font = BODY_FONT
        ws_final.cell(row=r, column=3, value=row.director_email).font = BODY_FONT
        c = ws_final.cell(row=r, column=4, value=row.director_contact_numbers)
        c.font = BODY_FONT
        c.number_format = "@"  # text format to preserve leading zeros / long digit strings
        ws_final.cell(row=r, column=5, value=row.net_profit).font = BODY_FONT
        ws_final.cell(row=r, column=6, value=row.revenue).font = BODY_FONT
        ws_final.cell(row=r, column=7, value=row.ebitda).font = BODY_FONT
        ws_final.cell(row=r, column=8, value=row.city).font = BODY_FONT
        ws_final.cell(row=r, column=9, value=row.company_products).font = BODY_FONT
    _autosize(ws_final, FINAL_COLUMNS)

    ws_val = wb.create_sheet("Validation & Review")
    _write_header(ws_val, VALIDATION_COLUMNS)
    for r, issue in enumerate(validation_issues, start=2):
        ws_val.cell(row=r, column=1, value=issue.issue_type).font = BODY_FONT
        ws_val.cell(row=r, column=2, value=issue.company_or_sheet_name).font = BODY_FONT
        ws_val.cell(row=r, column=3, value=issue.matched_company).font = BODY_FONT
        ws_val.cell(row=r, column=4, value=issue.problem).font = BODY_FONT
        ws_val.cell(row=r, column=5, value=issue.recommended_action).font = BODY_FONT
        ws_val.cell(row=r, column=6, value=issue.source_file).font = BODY_FONT
        ws_val.cell(row=r, column=7, value=issue.status).font = BODY_FONT
    _autosize(ws_val, VALIDATION_COLUMNS)

    ws_log = wb.create_sheet("Matching Log")
    _write_header(ws_log, MATCHING_LOG_COLUMNS)
    for r, m in enumerate(match_records, start=2):
        ws_log.cell(row=r, column=1, value=m.file_name).font = BODY_FONT
        ws_log.cell(row=r, column=2, value=m.extracted_company_name).font = BODY_FONT
        ws_log.cell(row=r, column=3, value=m.matched_company or "").font = BODY_FONT
        ws_log.cell(row=r, column=4, value=m.status.value).font = BODY_FONT
        ws_log.cell(row=r, column=5, value=m.method.value).font = BODY_FONT
        ws_log.cell(row=r, column=6, value=m.confidence).font = BODY_FONT
        ws_log.cell(row=r, column=7, value=m.source_file_id).font = BODY_FONT
        ws_log.cell(row=r, column=8, value=m.notes).font = BODY_FONT
    _autosize(ws_log, MATCHING_LOG_COLUMNS)

    ws_sum = wb.create_sheet("Validation Summary")
    ws_sum.cell(row=1, column=1, value="Metric").font = HEADER_FONT
    ws_sum.cell(row=1, column=1).fill = HEADER_FILL
    ws_sum.cell(row=1, column=2, value="Value").font = HEADER_FONT
    ws_sum.cell(row=1, column=2).fill = HEADER_FILL
    for r, (k, v) in enumerate(summary.items(), start=2):
        ws_sum.cell(row=r, column=1, value=k.replace("_", " ").title()).font = BODY_FONT
        ws_sum.cell(row=r, column=2, value=v).font = BODY_FONT
    ws_sum.column_dimensions["A"].width = 42
    ws_sum.column_dimensions["B"].width = 16

    wb.save(output_path)
