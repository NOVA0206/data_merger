"""CLI entry point: run the consolidation pipeline against a local folder.

Usage:
    python scripts/run_local.py "<parent folder>" [output.xlsx]
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "api"))

from _app.core.excel_exporter import export_workbook  # noqa: E402
from _app.core.pipeline import run_local_pipeline  # noqa: E402


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python scripts/run_local.py <parent_folder> [output.xlsx]")
        sys.exit(1)

    parent_folder = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else "Consolidated_Output.xlsx"

    result = run_local_pipeline(parent_folder)

    mapping = result["mapping"]
    print("Master column mapping resolved:")
    for k, v in mapping.resolved.items():
        print(f"  {k:20s} -> {v!r}")
    if mapping.unresolved:
        print("UNRESOLVED fields:", mapping.unresolved)
    if mapping.ambiguous:
        print("AMBIGUOUS fields:", mapping.ambiguous)

    print(f"\nMaster companies: {len(result['master_records'])}")
    print(f"Company files scanned: {len(result['company_files'])}")

    summary = result["summary"]
    print("\n--- Validation Summary ---")
    for k, v in summary.items():
        print(f"  {k}: {v}")

    export_workbook(
        result["consolidated_rows"],
        result["validation_issues"],
        result["match_records"],
        summary,
        output_path,
    )
    print(f"\nWrote {output_path}")


if __name__ == "__main__":
    main()
