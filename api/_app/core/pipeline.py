"""Orchestrates the full consolidation pipeline over a discovered local folder.

This is the source-agnostic core used by both the CLI runner and the chunked
FastAPI job runner; Drive-backed sources plug in by producing the same
(master DataFrame, {source_id: raw bytes/path}) shape.
"""
from __future__ import annotations

import os

from .director_extractor import extract_directors, load_company_sheet
from .consolidator import build_consolidated_rows
from .local_source import DiscoveredFolder, discover_local_folder
from .master_reader import extract_company_records, load_master_sheet, map_master_columns
from .matcher import CompanyMatcher
from .models import CompanyFile
from .normalizer import extract_company_name_from_filename
from .validator import run_validation


def run_local_pipeline(parent_folder: str, master_overrides: dict | None = None):
    discovered: DiscoveredFolder = discover_local_folder(parent_folder)

    master_df = load_master_sheet(discovered.master_file_path)
    mapping = map_master_columns(master_df, overrides=master_overrides)
    if "company_name" not in mapping.resolved:
        raise ValueError(
            "Could not confidently identify the company-name column in the master sheet. "
            f"Available columns: {list(master_df.columns)}"
        )
    master_records = extract_company_records(master_df, mapping)

    company_files: dict[str, CompanyFile] = {}
    for path in discovered.company_file_paths:
        file_name = os.path.basename(path)
        extracted_name = extract_company_name_from_filename(file_name)
        cf = CompanyFile(source_id=path, file_name=file_name, extracted_company_name=extracted_name)
        try:
            df = load_company_sheet(path)
            cf.directors = extract_directors(df)
        except Exception as exc:  # noqa: BLE001 - surfaced via Validation & Review, not silently dropped
            cf.read_error = f"Failed to read/parse file: {exc}"
        company_files[path] = cf

    matcher = CompanyMatcher(master_records)
    match_records = [
        matcher.match(cf.file_name, cf.extracted_company_name, cf.source_id)
        for cf in company_files.values()
    ]

    consolidated_rows = build_consolidated_rows(master_records, company_files, match_records)
    validation_issues, summary = run_validation(
        master_records, company_files, match_records, consolidated_rows
    )

    return {
        "mapping": mapping,
        "master_records": master_records,
        "company_files": company_files,
        "match_records": match_records,
        "consolidated_rows": consolidated_rows,
        "validation_issues": validation_issues,
        "summary": summary,
    }
