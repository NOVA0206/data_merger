from _app.core.consolidator import build_consolidated_rows
from _app.core.models import (
    CompanyFile,
    CompanyRecord,
    DirectorRecord,
    MatchMethod,
    MatchRecord,
    MatchStatus,
)


def test_multiple_directors_preserve_positional_alignment():
    """The classic failure mode: director 2's phone must never end up next to
    director 1's email. This locks that invariant down.
    """
    master = [CompanyRecord(row_index=0, company_name="ABC Pvt Ltd", net_profit=10)]
    cf = CompanyFile(
        source_id="file-1",
        file_name="ABC_DirectorsList.xlsx",
        extracted_company_name="ABC Pvt Ltd",
        directors=[
            DirectorRecord(name="Rahul Sharma", email="rahul@example.com", phone="9876543210"),
            DirectorRecord(name="Amit Patel", email="amit@example.com", phone="9823456789"),
        ],
    )
    matches = [
        MatchRecord(
            file_name=cf.file_name,
            extracted_company_name=cf.extracted_company_name,
            matched_company="ABC Pvt Ltd",
            matched_row_index=0,
            status=MatchStatus.EXACT,
            method=MatchMethod.EXACT,
            confidence=1.0,
            source_file_id="file-1",
        )
    ]
    rows = build_consolidated_rows(master, {"file-1": cf}, matches)
    assert len(rows) == 2
    assert rows[0].director_name == "Rahul Sharma"
    assert rows[0].director_email == "rahul@example.com"
    assert rows[0].director_contact_numbers == "9876543210"
    assert rows[1].director_name == "Amit Patel"
    assert rows[1].director_email == "amit@example.com"
    assert rows[1].director_contact_numbers == "9823456789"


def test_missing_email_leaves_blank_slot_without_shifting():
    master = [CompanyRecord(row_index=0, company_name="ABC Pvt Ltd")]
    cf = CompanyFile(
        source_id="file-1",
        file_name="ABC.xlsx",
        extracted_company_name="ABC Pvt Ltd",
        directors=[
            DirectorRecord(name="Rahul Sharma", email=None, phone="9876543210"),
            DirectorRecord(name="Amit Patel", email="amit@example.com", phone="9823456789"),
        ],
    )
    matches = [
        MatchRecord(
            file_name=cf.file_name,
            extracted_company_name=cf.extracted_company_name,
            matched_company="ABC Pvt Ltd",
            matched_row_index=0,
            status=MatchStatus.EXACT,
            method=MatchMethod.EXACT,
            confidence=1.0,
            source_file_id="file-1",
        )
    ]
    rows = build_consolidated_rows(master, {"file-1": cf}, matches)
    assert len(rows) == 2
    assert rows[0].director_email == ""
    assert rows[1].director_email == "amit@example.com"
    assert rows[0].director_name == "Rahul Sharma"
    assert rows[1].director_name == "Amit Patel"


def test_unmatched_company_gets_no_director_data():
    master = [CompanyRecord(row_index=0, company_name="ABC Pvt Ltd")]
    cf = CompanyFile(
        source_id="file-1",
        file_name="UNRELATED.xlsx",
        extracted_company_name="Totally Different Co",
        directors=[DirectorRecord(name="Someone Else", email="x@y.com", phone="123")],
    )
    matches = [
        MatchRecord(
            file_name=cf.file_name,
            extracted_company_name=cf.extracted_company_name,
            matched_company=None,
            matched_row_index=None,
            status=MatchStatus.NO_MATCH,
            method=MatchMethod.FUZZY,
            confidence=0.2,
            source_file_id="file-1",
        )
    ]
    rows = build_consolidated_rows(master, {"file-1": cf}, matches)
    assert len(rows) == 1
    assert rows[0].director_name == ""
    assert rows[0].company_name == "ABC Pvt Ltd"


def test_financial_data_never_copied_across_companies():
    master = [
        CompanyRecord(row_index=0, company_name="ABC Pvt Ltd", net_profit=100),
        CompanyRecord(row_index=1, company_name="XYZ Pvt Ltd", net_profit=200),
    ]
    rows = build_consolidated_rows(master, {}, [])
    by_name = {r.company_name: r for r in rows}
    assert by_name["ABC Pvt Ltd"].net_profit == 100
    assert by_name["XYZ Pvt Ltd"].net_profit == 200
