"""Writes the final consolidated workbook: 3 sheets, formatted, formula-free data dump."""
from __future__ import annotations

from typing import IO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from .models import ConsolidatedRow, MatchRecord, ValidationIssue

HEADER_FILL = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
HEADER_FONT = Font(name="Arial", bold=True, color="FFFFFF")
BODY_FONT = Font(name="Arial")

COMPANY_COLUMNS = [
    "Company Name",
    "CIN",
    "Pan",
    "City",
    "State",
    "Status",
    "Listing Status",
    "Products",
    "Sector",
    "Whether Exporter",
    "Business Type",
    "Paid Up Capital",
    "Financial Year",
    "Latest Balance Sheet",
    "Consolidated/Standalone",
    "Total Revenue",
    "EBITDA",
    "PAT",
    "Networth",
    "Long-term Liabilities",
    "Total Borrowings",
    "IEC Code",
    "IEC Category",
    "Ownership",
    "Importer/Exporter?",
    "Date of Incorporation",
    "Total Open Charges",
    "Consortium Finance Involved?",
    "Credit Rated?",
    "Latest Ratings",
    "Total Revenue from Operations",
    "EBITDA %",
    "PAT %",
    "Long-term Borrowings",
    "Short-term Borrowings",
    "Cash & Cash Equivalents",
    "Current Investment",
    "Total Tangible Assets",
    "Fixed Assets",
    "Revenue Growth %",
    "Finance Cost (% of Sales)",
    "Current Ratio",
    "Receivables Days",
    "Inventory Days",
    "Total Debt/Equity",
    "Debt to EBITDA",
    "Interest Coverage",
    "Growth in Fixed Assets (%)",
    "EBT Margins %",
    "Emp Cost (% of Sales)",
    "Other Exp (% of Sales)",
    "RMC %",
    "ROE %",
    "FA T/O",
    "Working Capital Turnover",
    "Long-term Debt/Equity",
    "Deposits Matured but Not Claimed?",
    "Deposits Matured and Claimed but Not Paid?",
    "Financial Statement Qualified?",
    "CARO Applicable?",
    "BIFR?",
    "Willful Defaulter under CIBIL?",
    "Willful Defaulter under Equifax?",
    "Litigation?",
    "NCLT?",
    "SAT?",
    "Defaulter under MCA?",
    "Company Email Address",
    "Company Telephone Number",
    "Company Website",
    "Company Address",
    "Pin Code",
]

DIRECTOR_COLUMNS = [
    "NAME",
    "DIN OR DPIN (PAN)",
    "DIN STATUS",
    "DSC STATUS",
    "ADDRESS",
    "DESIGNATION (CATEGORY)",
    "APPOINTMENT AT CURRENT DESIGNATION ON",
    "ORIGINALLY APPOINTED ON",
    "CESSATION DATE",
    "% SHAREHOLDING",
    "EMAIL ID",
    "PHONE NUMBER",
    "REMARKS",
]

FINAL_COLUMNS = COMPANY_COLUMNS + DIRECTOR_COLUMNS

_TEXT_COLUMNS = {
    "Company Telephone Number",
    "Pin Code",
    "DIN OR DPIN (PAN)",
    "PHONE NUMBER",
}

_COMPANY_FALLBACKS = {
    "Company Name": lambda r: r.company_name,
    "City": lambda r: r.city,
    "Products": lambda r: r.company_products,
    "Total Revenue": lambda r: r.revenue,
    "EBITDA": lambda r: r.ebitda,
    "PAT": lambda r: r.net_profit,
}


def _norm_lookup_key(name: str) -> str:
    s = " ".join(str(name).strip().lower().split())
    if s.endswith("*"):
        s = s[:-1].strip()
    return s


def row_to_final_values(row: ConsolidatedRow) -> list:
    """Return the 85 cell values for one ConsolidatedRow in FINAL_COLUMNS order."""
    raw_lookup: dict[str, object] = {}
    for k, v in (row.master_raw or {}).items():
        nk = _norm_lookup_key(k)
        if nk not in raw_lookup:
            raw_lookup[nk] = v

    company_vals = []
    for col in COMPANY_COLUMNS:
        nk = _norm_lookup_key(col)
        if nk in raw_lookup:
            val = raw_lookup[nk]
        elif col in _COMPANY_FALLBACKS:
            val = _COMPANY_FALLBACKS[col](row)
        else:
            val = None
        company_vals.append(val)

    director_vals = [
        row.director_name,
        row.din_or_dpin_pan,
        row.din_status,
        row.dsc_status,
        row.director_address,
        row.director_designation,
        row.appointment_at_current_designation_on,
        row.originally_appointed_on,
        row.cessation_date,
        row.shareholding_pct,
        row.director_email,
        row.director_contact_numbers,
        row.director_remarks,
    ]
    return company_vals + director_vals

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
    output_path: str | IO[bytes],
) -> None:
    wb = Workbook()

    ws_final = wb.active
    assert ws_final is not None
    ws_final.title = "Final Consolidated Data"
    _write_header(ws_final, FINAL_COLUMNS)
    text_col_indices = {i for i, col in enumerate(FINAL_COLUMNS, start=1) if col in _TEXT_COLUMNS}
    for r, row in enumerate(consolidated_rows, start=2):
        for c_idx, val in enumerate(row_to_final_values(row), start=1):
            cell = ws_final.cell(row=r, column=c_idx, value=val)
            cell.font = BODY_FONT
            if c_idx in text_col_indices:
                cell.number_format = "@"  # text format to preserve leading zeros / long digit strings
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
