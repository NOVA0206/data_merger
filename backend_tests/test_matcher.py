from _app.core.matcher import CompanyMatcher
from _app.core.models import CompanyRecord, MatchStatus


def _rec(idx, name):
    return CompanyRecord(row_index=idx, company_name=name)


def test_exact_match():
    m = CompanyMatcher([_rec(0, "ABC Pvt Ltd"), _rec(1, "XYZ Ltd")])
    result = m.match("f.xlsx", "ABC Pvt Ltd", "file-1")
    assert result.status == MatchStatus.EXACT
    assert result.matched_company == "ABC Pvt Ltd"


def test_normalized_match_handles_suffix_variants():
    m = CompanyMatcher([_rec(0, "ABC Private Limited")])
    result = m.match("f.xlsx", "ABC PVT LTD", "file-1")
    assert result.status == MatchStatus.NORMALIZED
    assert result.matched_company == "ABC Private Limited"


def test_fuzzy_match_is_flagged_not_silently_accepted():
    m = CompanyMatcher([_rec(0, "Autodynamic Technologies & Solutions Private Limited")])
    result = m.match(
        "f.xlsx", "AUTODYNAMIC TECHNOLOGIES SOLUTIONS PRIVATE LIMITED", "file-1"
    )
    assert result.status == MatchStatus.POSSIBLE
    assert result.confidence < 1.0
    assert result.matched_company is not None


def test_ambiguous_fuzzy_candidates_go_to_manual_review():
    # Two candidates equidistant from the target (differ only by a trailing digit)
    # must never be auto-resolved to either one.
    m = CompanyMatcher(
        [
            _rec(0, "Bharat Auto Components 1 Pvt Ltd"),
            _rec(1, "Bharat Auto Components 2 Pvt Ltd"),
        ]
    )
    result = m.match("f.xlsx", "BHARAT AUTO COMPONENTS PVT LTD", "file-1")
    assert result.status == MatchStatus.MANUAL_REVIEW
    assert result.matched_company is None


def test_no_match_for_unrelated_name():
    m = CompanyMatcher([_rec(0, "ABC Pvt Ltd")])
    result = m.match("f.xlsx", "COMPLETELY UNRELATED ENTERPRISE CORP", "file-1")
    assert result.status == MatchStatus.NO_MATCH
    assert result.matched_company is None


def test_duplicate_exact_names_require_manual_review():
    m = CompanyMatcher([_rec(0, "ABC Ltd"), _rec(1, "ABC Ltd")])
    result = m.match("f.xlsx", "ABC Ltd", "file-1")
    assert result.status == MatchStatus.MANUAL_REVIEW
    assert result.matched_row_index is None
