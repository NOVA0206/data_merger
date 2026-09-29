"""Validation engine: produces the Validation & Review issue list and a summary."""
from __future__ import annotations

from collections import Counter

from .models import (
    CompanyFile,
    CompanyRecord,
    ConsolidatedRow,
    MatchRecord,
    MatchStatus,
    ValidationIssue,
)


def _norm(name: str) -> str:
    return " ".join(str(name).strip().upper().split())


def run_validation(
    master_records: list[CompanyRecord],
    company_files: dict[str, CompanyFile],
    match_records: list[MatchRecord],
    consolidated_rows: list[ConsolidatedRow],
) -> tuple[list[ValidationIssue], dict]:
    issues: list[ValidationIssue] = []

    # 3. Duplicate company names in the master sheet.
    name_counts = Counter(_norm(r.company_name) for r in master_records)
    for name, count in name_counts.items():
        if count > 1:
            issues.append(
                ValidationIssue(
                    issue_type="Duplicate Company",
                    company_or_sheet_name=name,
                    matched_company=name,
                    problem=f"{count} rows in the master sheet share this company name.",
                    recommended_action="Review master sheet rows manually; do not auto-merge.",
                    source_file="Master Sheet",
                )
            )

    # 4. Duplicate individual spreadsheets (same extracted company name from >1 file).
    file_name_by_company: dict[str, list[str]] = {}
    for cf in company_files.values():
        file_name_by_company.setdefault(_norm(cf.extracted_company_name), []).append(cf.file_name)
    for company, files in file_name_by_company.items():
        if len(files) > 1:
            issues.append(
                ValidationIssue(
                    issue_type="Duplicate Spreadsheet",
                    company_or_sheet_name=company,
                    matched_company="",
                    problem=f"{len(files)} spreadsheets extracted to the same company name: {', '.join(files)}",
                    recommended_action="Confirm which file is authoritative; do not merge both.",
                    source_file="; ".join(files),
                )
            )

    # 6/7/8. Master companies without a spreadsheet; spreadsheets with no/ambiguous match.
    matched_row_indices = {
        m.matched_row_index
        for m in match_records
        if m.status in (MatchStatus.EXACT, MatchStatus.NORMALIZED, MatchStatus.POSSIBLE)
        and m.matched_row_index is not None
    }
    for rec in master_records:
        if rec.row_index not in matched_row_indices:
            issues.append(
                ValidationIssue(
                    issue_type="Sheet Not Found",
                    company_or_sheet_name=rec.company_name,
                    matched_company="",
                    problem="No individual company spreadsheet was matched to this master company.",
                    recommended_action="Check Google Drive for a spreadsheet with a similar file name.",
                    source_file="",
                )
            )

    for m in match_records:
        if m.status == MatchStatus.NO_MATCH:
            issues.append(
                ValidationIssue(
                    issue_type="Company Not Found",
                    company_or_sheet_name=m.extracted_company_name,
                    matched_company="",
                    problem="No master-sheet company matched this spreadsheet, even fuzzily.",
                    recommended_action="Verify company exists in master sheet; add manually if confirmed.",
                    source_file=m.file_name,
                )
            )
        elif m.status == MatchStatus.MANUAL_REVIEW:
            issues.append(
                ValidationIssue(
                    issue_type="Ambiguous Match",
                    company_or_sheet_name=m.extracted_company_name,
                    matched_company=m.matched_company or "",
                    problem=m.notes or "Match confidence too low or multiple equally-likely candidates.",
                    recommended_action="Manually confirm the correct master company before merging.",
                    source_file=m.file_name,
                )
            )
        elif m.status == MatchStatus.POSSIBLE:
            issues.append(
                ValidationIssue(
                    issue_type="Ambiguous Match",
                    company_or_sheet_name=m.extracted_company_name,
                    matched_company=m.matched_company or "",
                    problem=f"Fuzzy match accepted at {m.confidence:.0%} confidence; not a certain identity match.",
                    recommended_action="Spot-check this match before treating it as final.",
                    source_file=m.file_name,
                )
            )

    # Missing-field checks on consolidated rows.
    for row in consolidated_rows:
        if not row.director_name:
            issues.append(
                ValidationIssue(
                    issue_type="Missing Director Name",
                    company_or_sheet_name=row.company_name,
                    matched_company=row.company_name,
                    problem="No director information available for this company.",
                    recommended_action="Confirm a directors spreadsheet exists and was matched.",
                    source_file=row.source_files,
                )
            )
        else:
            names = [n for n in row.director_name.split(";")]
            phones = [p.strip() for p in row.director_contact_numbers.split(";")]
            emails = [e.strip() for e in row.director_email.split(";")]
            if any(p == "" for p in phones):
                issues.append(
                    ValidationIssue(
                        issue_type="Missing Contact Number",
                        company_or_sheet_name=row.company_name,
                        matched_company=row.company_name,
                        problem="One or more directors have no phone number on file.",
                        recommended_action="Check source spreadsheet for that director.",
                        source_file=row.source_files,
                    )
                )
            if any(e == "" for e in emails):
                issues.append(
                    ValidationIssue(
                        issue_type="Missing Email",
                        company_or_sheet_name=row.company_name,
                        matched_company=row.company_name,
                        problem="One or more directors have no email on file.",
                        recommended_action="Check source spreadsheet for that director.",
                        source_file=row.source_files,
                    )
                )
            dup_names = [n for n, c in Counter(n.strip().upper() for n in names if n.strip()).items() if c > 1]
            if dup_names:
                issues.append(
                    ValidationIssue(
                        issue_type="Possible Duplicate Director",
                        company_or_sheet_name=row.company_name,
                        matched_company=row.company_name,
                        problem=f"Director name(s) appear more than once: {', '.join(dup_names)}",
                        recommended_action="Verify these are not the same person listed twice.",
                        source_file=row.source_files,
                    )
                )

        if row.net_profit is None or row.revenue is None or row.ebitda is None:
            issues.append(
                ValidationIssue(
                    issue_type="Missing Financial Data",
                    company_or_sheet_name=row.company_name,
                    matched_company=row.company_name,
                    problem="One or more of Net Profit / Revenue / EBITDA is missing in the master sheet.",
                    recommended_action="Check master sheet for this company's financial columns.",
                    source_file="Master Sheet",
                )
            )
        if not row.city:
            issues.append(
                ValidationIssue(
                    issue_type="Missing City",
                    company_or_sheet_name=row.company_name,
                    matched_company=row.company_name,
                    problem="City is missing in the master sheet.",
                    recommended_action="Check master sheet for this company's city column.",
                    source_file="Master Sheet",
                )
            )
        if not row.company_products:
            issues.append(
                ValidationIssue(
                    issue_type="Missing Company Products",
                    company_or_sheet_name=row.company_name,
                    matched_company=row.company_name,
                    problem="Company products/business activity is missing in the master sheet.",
                    recommended_action="Check master sheet for this company's products column.",
                    source_file="Master Sheet",
                )
            )

    for cf in company_files.values():
        if cf.read_error:
            issues.append(
                ValidationIssue(
                    issue_type="Data Format Issue",
                    company_or_sheet_name=cf.extracted_company_name,
                    matched_company="",
                    problem=cf.read_error,
                    recommended_action="Inspect the file manually; it could not be parsed.",
                    source_file=cf.file_name,
                )
            )

    summary = {
        "total_master_companies": len(master_records),
        "total_individual_spreadsheets": len(company_files),
        "exact_matches": sum(1 for m in match_records if m.status == MatchStatus.EXACT),
        "normalized_matches": sum(1 for m in match_records if m.status == MatchStatus.NORMALIZED),
        "uncertain_matches": sum(
            1 for m in match_records if m.status in (MatchStatus.POSSIBLE, MatchStatus.MANUAL_REVIEW)
        ),
        "unmatched_spreadsheets": sum(1 for m in match_records if m.status == MatchStatus.NO_MATCH),
        "companies_without_director_info": sum(1 for r in consolidated_rows if not r.director_name),
        "companies_with_missing_contact_info": sum(
            1
            for r in consolidated_rows
            if r.director_name and ("" in [p.strip() for p in r.director_contact_numbers.split(";")])
        ),
        "total_companies_in_final_output": len(consolidated_rows),
    }
    return issues, summary
