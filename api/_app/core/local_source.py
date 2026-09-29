"""Local-folder data source: mirrors the expected Google Drive folder layout.

    <parent folder>/
        Main Sheet/<master workbook>.xlsx
        <company 1>.xlsx
        <company 2>.xlsx
        ...

Excludes the "Main Sheet" subfolder and any previously generated output files
(matched by a "consolidated" / "output" naming convention) when scanning for
individual company spreadsheets.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

MAIN_SHEET_DIRNAME = "main sheet"
EXCLUDE_NAME_HINTS = ("consolidated", "_output", "final consolidated", "~$")


@dataclass
class DiscoveredFolder:
    parent_path: str
    master_file_path: str
    company_file_paths: list[str]


def discover_local_folder(parent_path: str) -> DiscoveredFolder:
    if not os.path.isdir(parent_path):
        raise FileNotFoundError(f"Folder not found: {parent_path}")

    main_sheet_dir = None
    for entry in os.listdir(parent_path):
        full = os.path.join(parent_path, entry)
        if os.path.isdir(full) and entry.strip().lower() == MAIN_SHEET_DIRNAME:
            main_sheet_dir = full
            break
    if not main_sheet_dir:
        raise FileNotFoundError(
            f"No 'Main Sheet' subfolder found inside {parent_path}."
        )

    master_candidates = [
        os.path.join(main_sheet_dir, f)
        for f in os.listdir(main_sheet_dir)
        if f.lower().endswith((".xlsx", ".xls")) and not f.startswith("~$")
    ]
    if not master_candidates:
        raise FileNotFoundError(f"No master workbook found inside {main_sheet_dir}.")
    master_file_path = master_candidates[0]

    master_file_name = os.path.basename(master_file_path).strip().lower()

    company_file_paths = []
    for f in os.listdir(parent_path):
        full = os.path.join(parent_path, f)
        if os.path.isdir(full):
            continue
        if not f.lower().endswith((".xlsx", ".xls")):
            continue
        if f.startswith("~$"):
            continue
        if f.strip().lower() == master_file_name:
            continue  # stray duplicate of the master workbook sitting in the parent folder
        if any(hint in f.lower() for hint in EXCLUDE_NAME_HINTS):
            continue
        company_file_paths.append(full)

    return DiscoveredFolder(
        parent_path=parent_path,
        master_file_path=master_file_path,
        company_file_paths=sorted(company_file_paths),
    )
