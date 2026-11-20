import json
import os
import tempfile

import openpyxl
import pandas as pd

from _app.core.consolidator import build_consolidated_rows
from _app.core.director_extractor import extract_directors
from _app.core.excel_exporter import FINAL_COLUMNS, export_workbook, row_to_final_values
from _app.core.master_reader import _clean_cell
from _app.core.models import (
    CompanyFile,
    CompanyRecord,
    DirectorRecord,
    MatchMethod,
    MatchRecord,
    MatchStatus,
)
from _app.core.sheets_exporter import build_sheets_payload
from _app.core.validator import run_validation


def test_final_columns_count_and_boundaries():
    assert len(FINAL_COLUMNS) == 85
    assert FINAL_COLUMNS[0] == "Company Name"
    assert FINAL_COLUMNS[71] == "Pin Code"
    assert FINAL_COLUMNS[72] == "NAME"
    assert FINAL_COLUMNS[84] == "REMARKS"


def test_director_extractor_extracts_all_13_fields():
    df = pd.DataFrame(
        [
            {
                "NAME": "RAHUL SHARMA 01/06/1975",
                "DIN OR DPIN (PAN)": "03012236 (AFHPK6471M)",
                "DIN STATUS": "Approved",
                "DSC STATUS": "Active",
                "ADDRESS": "Pune, Maharashtra 411001",
                "DESIGNATION (CATEGORY)": "Director (Promoter)",
                "APPOINTMENT AT CURRENT DESIGNATION ON": "26/04/2010",
                "ORIGINALLY APPOINTED ON": "26/04/2010",
                "CESSATION DATE": "-",
                "% SHAREHOLDING": "50.00 %",
                "EMAIL ID": "rahul@example.com",
                "PHONE NUMBER": 919970055139.0,
                "REMARKS": "-",
            }
        ]
    )
    directors = extract_directors(df)
    assert len(directors) == 1
    d = directors[0]
    assert d.name == "RAHUL SHARMA"
    assert d.din_or_dpin_pan == "03012236 (AFHPK6471M)"
    assert d.din_status == "Approved"
    assert d.dsc_status == "Active"
    assert d.address == "Pune, Maharashtra 411001"
    assert d.designation == "Director (Promoter)"
    assert d.appointment_at_current_designation_on == "26/04/2010"
    assert d.originally_appointed_on == "26/04/2010"
    assert d.cessation_date is None
    assert d.shareholding_pct == "50.00 %"
    assert d.email == "rahul@example.com"
    assert d.phone == "919970055139"
    assert d.remarks is None


def test_excel_and_sheets_export_85_columns_and_ignore_duplicate_suffix():
    master = [
        CompanyRecord(
            row_index=0,
            company_name="ABC Pvt Ltd",
            net_profit=12.5,
            revenue=100.0,
            ebitda=20.0,
            city="Pune",
            company_products="Auto Parts",
            raw={
                "Company Name": "ABC Pvt Ltd",
                "CIN": "U12345PN2020PTC000001",
                "City": "Pune",
                "City.1": "Duplicate City",
                "Products": "Auto Parts",
                "Sector": "Auto Ancillary",
                "Corpository Sector": "Auto",
                "Total Revenue  *": 100.0,
                "EBITDA ": 20.0,
                "PAT ": 12.5,
                "Pin Code": 411001,
            },
        )
    ]
    cf = CompanyFile(
        source_id="f1",
        file_name="ABC.xlsx",
        extracted_company_name="ABC Pvt Ltd",
        directors=[
            DirectorRecord(
                name="Rahul Sharma",
                email="rahul@example.com",
                phone="919876543210",
                designation="Director (Promoter)",
                address="Pune",
                din_or_dpin_pan="03012236 (AFHPK6471M)",
                din_status="Approved",
                dsc_status="Active",
                appointment_at_current_designation_on="01/01/2020",
                originally_appointed_on="01/01/2020",
                shareholding_pct="50%",
            )
        ],
    )
    matches = [
        MatchRecord(
            file_name="ABC.xlsx",
            extracted_company_name="ABC Pvt Ltd",
            matched_company="ABC Pvt Ltd",
            matched_row_index=0,
            status=MatchStatus.EXACT,
            method=MatchMethod.EXACT,
            confidence=1.0,
            source_file_id="f1",
        )
    ]
    rows = build_consolidated_rows(master, {"f1": cf}, matches)
    assert len(rows) == 1
    vals = row_to_final_values(rows[0])
    assert len(vals) == 85
    assert vals[0] == "ABC Pvt Ltd"
    assert vals[1] == "U12345PN2020PTC000001"
    assert vals[3] == "Pune"
    assert vals[8] == "Auto Ancillary"
    assert vals[15] == 100.0
    assert vals[16] == 20.0
    assert vals[17] == 12.5
    assert vals[71] == 411001
    assert vals[72] == "Rahul Sharma"
    assert vals[73] == "03012236 (AFHPK6471M)"
    assert vals[82] == "rahul@example.com"
    assert vals[83] == "919876543210"

    issues, summary = run_validation(master, {"f1": cf}, matches, rows)
    payload = build_sheets_payload(rows, issues, matches, summary)
    assert payload["Final Consolidated Data"][0] == FINAL_COLUMNS
    assert len(payload["Final Consolidated Data"][1]) == 85

    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        export_workbook(rows, issues, matches, summary, tmp_path)
        wb = openpyxl.load_workbook(tmp_path)
        ws = wb["Final Consolidated Data"]
        headers = [ws.cell(row=1, column=i).value for i in range(1, 86)]
        assert headers == FINAL_COLUMNS
        assert ws.cell(row=2, column=1).value == "ABC Pvt Ltd"
        assert ws.cell(row=2, column=84).value == "919876543210"
        assert ws.cell(row=2, column=84).number_format == "@"
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_clean_cell_is_json_serializable():
    ts = pd.Timestamp("2025-03-31")
    cleaned = _clean_cell(ts)
    assert cleaned == "31/03/2025"
    json.dumps(cleaned)


def test_validator_does_not_duplicate_company_issues_per_director():
    master = [CompanyRecord(row_index=0, company_name="ABC Pvt Ltd", city=None)]
    cf = CompanyFile(
        source_id="f1",
        file_name="ABC.xlsx",
        extracted_company_name="ABC Pvt Ltd",
        directors=[
            DirectorRecord(name="Dir 1", email="d1@x.com", phone="111"),
            DirectorRecord(name="Dir 2", email="d2@x.com", phone="222"),
        ],
    )
    matches = [
        MatchRecord(
            file_name="ABC.xlsx",
            extracted_company_name="ABC Pvt Ltd",
            matched_company="ABC Pvt Ltd",
            matched_row_index=0,
            status=MatchStatus.EXACT,
            method=MatchMethod.EXACT,
            confidence=1.0,
            source_file_id="f1",
        )
    ]
    rows = build_consolidated_rows(master, {"f1": cf}, matches)
    issues, _ = run_validation(master, {"f1": cf}, matches, rows)
    city_issues = [i for i in issues if i.issue_type == "Missing City"]
    assert len(city_issues) == 1
