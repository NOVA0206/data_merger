from _app.core.field_mapping import resolve_field_mapping


def test_never_confuses_ebitda_amount_with_margin():
    columns = ["Company Name", "EBITDA ", "EBITDA %", "EBITDA .1", "EBITDA %.1"]
    mapping = resolve_field_mapping(columns, ["ebitda"])
    assert mapping.resolved["ebitda"] == "EBITDA "


def test_never_confuses_revenue_with_growth_percent():
    columns = ["Company Name", "Total Revenue  *", "Revenue Growth %"]
    mapping = resolve_field_mapping(columns, ["revenue"])
    assert mapping.resolved["revenue"] == "Total Revenue  *"


def test_picks_first_of_duplicated_block_columns():
    columns = ["PAT ", "PAT .1", "PAT %"]
    mapping = resolve_field_mapping(columns, ["net_profit"])
    assert mapping.resolved["net_profit"] == "PAT "


def test_unresolved_field_reported_not_guessed():
    columns = ["Company Name", "Something Else"]
    mapping = resolve_field_mapping(columns, ["net_profit"])
    assert "net_profit" not in mapping.resolved
    assert "net_profit" in mapping.unresolved


def test_override_takes_precedence():
    columns = ["Company Name", "Custom Profit Column"]
    mapping = resolve_field_mapping(
        columns, ["net_profit"], overrides={"net_profit": "Custom Profit Column"}
    )
    assert mapping.resolved["net_profit"] == "Custom Profit Column"
