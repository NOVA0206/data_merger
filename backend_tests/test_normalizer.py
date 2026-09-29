from _app.core.normalizer import (
    extract_company_name_from_filename,
    normalize_company_name,
    normalized_key,
)


def test_filename_extraction_strips_export_suffix():
    assert (
        extract_company_name_from_filename(
            "AAKASH-PRESS-PARTS-PRIVATE-LIMITED_DirectorsList_export_1787054963853.xlsx"
        )
        == "AAKASH PRESS PARTS PRIVATE LIMITED"
    )


def test_normalize_equates_pvt_ltd_variants():
    a = normalize_company_name("ABC Pvt Ltd")
    b = normalize_company_name("ABC Private Limited")
    assert a == b == "ABC PVT LTD"


def test_normalize_equates_ltd_variants():
    assert normalize_company_name("Kinetic Engineering Ltd") == normalize_company_name(
        "Kinetic Engineering Limited"
    )


def test_normalize_collapses_spacing_and_punctuation():
    assert normalized_key("ABC   Pvt.  Ltd.") == normalized_key("ABC Pvt Ltd")


def test_normalize_does_not_collapse_distinct_companies():
    a = normalize_company_name("Autodynamic Technologies Private Limited")
    b = normalize_company_name("Autodynamic Technologies Solutions Private Limited")
    assert a != b
