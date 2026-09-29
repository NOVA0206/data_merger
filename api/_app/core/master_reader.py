"""Reads the master financial sheet and extracts CompanyRecord rows."""
from __future__ import annotations

import pandas as pd

from .field_mapping import FieldMapping, resolve_field_mapping
from .models import CompanyRecord

REQUIRED_FIELDS = [
    "company_name",
    "net_profit",
    "revenue",
    "ebitda",
    "city",
    "company_products",
]


def _clean_cell(value):
    if pd.isna(value):
        return None
    if isinstance(value, str):
        v = value.strip()
        return v if v else None
    return value


def load_master_sheet(path_or_buffer, sheet_name: int | str | None = 0) -> pd.DataFrame:
    """Load the master workbook's primary data sheet into a DataFrame.

    If `sheet_name` is None, the first sheet is used. Excel files exported with a
    single data sheet named something other than "Sheet1" (e.g. "Explore Excel")
    are handled automatically since we default to positional index 0.
    """
    sheets = pd.read_excel(path_or_buffer, sheet_name=None)
    if sheet_name is not None and sheet_name in sheets:
        return sheets[sheet_name]
    # Fall back to the first sheet, or the largest sheet if multiple exist.
    if len(sheets) == 1:
        return next(iter(sheets.values()))
    return max(sheets.values(), key=lambda df: df.shape[0] * df.shape[1])


def map_master_columns(
    df: pd.DataFrame, overrides: dict[str, str] | None = None
) -> FieldMapping:
    return resolve_field_mapping(list(df.columns), REQUIRED_FIELDS, overrides)


def extract_company_records(
    df: pd.DataFrame, mapping: FieldMapping
) -> list[CompanyRecord]:
    """Build one CompanyRecord per master-sheet row using the resolved mapping."""
    records: list[CompanyRecord] = []
    name_col = mapping.resolved.get("company_name")
    if not name_col:
        raise ValueError(
            "Could not identify the company-name column in the master sheet. "
            "Pass an explicit override via overrides={'company_name': '<actual column>'}."
        )

    for idx, row in df.iterrows():
        name = _clean_cell(row.get(name_col))
        if not name:
            continue
        rec = CompanyRecord(
            row_index=int(idx),
            company_name=str(name).strip(),
            net_profit=_clean_cell(row.get(mapping.resolved.get("net_profit", ""))),
            revenue=_clean_cell(row.get(mapping.resolved.get("revenue", ""))),
            ebitda=_clean_cell(row.get(mapping.resolved.get("ebitda", ""))),
            city=_clean_cell(row.get(mapping.resolved.get("city", ""))),
            company_products=_clean_cell(
                row.get(mapping.resolved.get("company_products", ""))
            ),
            raw={c: _clean_cell(row.get(c)) for c in df.columns},
        )
        records.append(rec)
    return records
