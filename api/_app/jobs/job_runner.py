"""Chunked job state machine: Pending -> Scanning -> Processing -> Matching ->
Validating -> Exporting -> Completed | Failed.

Each call to `advance_job` does ONE bounded unit of work (one status transition,
or one batch of files within "Processing") and returns. This is what lets the
whole pipeline run inside Vercel's per-invocation time limit: the frontend (or a
Vercel Cron safety-net) simply calls `advance_job` repeatedly until the job
reaches a terminal status.
"""
from __future__ import annotations

import io
from datetime import datetime

from sqlalchemy.orm import Session

from ..config import settings
from ..core.consolidator import build_consolidated_rows
from ..core.director_extractor import extract_directors, load_company_sheet
from ..core.drive_connector import DriveClient
from ..core.excel_exporter import export_workbook
from ..core.local_source import discover_local_folder
from ..core.master_reader import extract_company_records, load_master_sheet, map_master_columns
from ..core.matcher import CompanyMatcher
from ..core.models import CompanyFile, MatchMethod, MatchStatus
from ..core.normalizer import extract_company_name_from_filename
from ..core.serialization import (
    company_file_from_dict,
    company_file_to_dict,
    company_record_from_dict,
    company_record_to_dict,
    match_record_from_dict,
    match_record_to_dict,
)
from ..core.validator import run_validation
from ..db.models import Job, JobOutput, JobState

TERMINAL_STATUSES = {"Completed", "Failed"}


def _fail(job: Job, message: str) -> None:
    job.status = "Failed"
    job.error_details = message
    job.completed_at = datetime.utcnow()


def _get_drive_client(job: Job, session: Session) -> DriveClient:
    from ..auth.google_oauth import credentials_from_encrypted_refresh_token
    from ..db.models import UserToken

    token_row = (
        session.query(UserToken).filter(UserToken.user_email == job.user_id).one_or_none()
    )
    if not token_row:
        raise RuntimeError(f"No stored Google credentials for user {job.user_id}.")
    creds = credentials_from_encrypted_refresh_token(token_row.encrypted_refresh_token)
    return DriveClient(creds)


def advance_job(session: Session, job: Job) -> Job:
    if job.status in TERMINAL_STATUSES:
        return job

    state = job.state
    if state is None:
        state = JobState(job_id=job.id)
        session.add(state)

    try:
        if job.status == "Pending":
            _run_scanning(job, state, session)
        elif job.status == "Scanning":
            job.status = "Processing"
        elif job.status == "Processing":
            _run_processing_batch(job, state, session)
        elif job.status == "Matching":
            _run_matching(job, state)
        elif job.status == "Validating":
            _run_validating(job, state)
        elif job.status == "Exporting":
            _run_exporting(job, state, session)
        else:
            _fail(job, f"Unknown job status: {job.status}")
    except Exception as exc:  # noqa: BLE001 - persisted as a job failure, never silent
        _fail(job, f"{type(exc).__name__}: {exc}")

    job.updated_at = datetime.utcnow()
    return job


def _run_scanning(job: Job, state: JobState, session: Session) -> None:
    job.status = "Scanning"

    if job.source_type == "local":
        discovered = discover_local_folder(job.local_path)
        master_bytes_or_path = discovered.master_file_path
        file_refs = [
            {"source_id": p, "file_name": p.split("/")[-1].split("\\")[-1]}
            for p in discovered.company_file_paths
        ]
        master_df = load_master_sheet(master_bytes_or_path)
    elif job.source_type == "drive":
        client = _get_drive_client(job, session)
        discovered = client.discover_folder(job.drive_folder_id)
        master_bytes = client.read_file_bytes(discovered.master_file)
        master_df = load_master_sheet(io.BytesIO(master_bytes))
        file_refs = [
            {"source_id": f.file_id, "file_name": f.name, "mime_type": f.mime_type}
            for f in discovered.company_files
        ]
    else:
        raise ValueError(f"Unknown source_type: {job.source_type}")

    mapping = map_master_columns(master_df, overrides=job.field_overrides or {})
    if "company_name" not in mapping.resolved:
        raise ValueError(
            "Could not identify the company-name column in the master sheet. "
            f"Available columns: {list(master_df.columns)}. Resubmit the job with "
            "field_overrides={'company_name': '<actual column>'}."
        )
    master_records = extract_company_records(master_df, mapping)

    state.master_records = [company_record_to_dict(r) for r in master_records]
    state.pending_file_refs = file_refs
    state.company_files = {}
    state.match_records = []
    state.mapping_resolved = mapping.resolved
    state.mapping_unresolved = mapping.unresolved
    state.mapping_ambiguous = mapping.ambiguous

    job.progress_total = len(file_refs)
    job.progress_current = 0
    job.status = "Processing"


def _run_processing_batch(job: Job, state: JobState, session: Session) -> None:
    pending = list(state.pending_file_refs or [])
    if not pending:
        job.status = "Matching"
        return

    batch, rest = pending[: settings.JOB_BATCH_SIZE], pending[settings.JOB_BATCH_SIZE :]
    company_files = dict(state.company_files or {})

    client = None
    if job.source_type == "drive":
        client = _get_drive_client(job, session)

    for ref in batch:
        source_id = ref["source_id"]
        file_name = ref["file_name"]
        extracted_name = extract_company_name_from_filename(file_name)
        cf = CompanyFile(source_id=source_id, file_name=file_name, extracted_company_name=extracted_name)
        try:
            if job.source_type == "local":
                df = load_company_sheet(source_id)
            else:
                from ..core.drive_connector import DriveFileRef

                ref_obj = DriveFileRef(source_id, file_name, ref.get("mime_type", ""))
                file_bytes = client.read_file_bytes(ref_obj)
                df = load_company_sheet(io.BytesIO(file_bytes))
            cf.directors = extract_directors(df)
        except Exception as exc:  # noqa: BLE001 - recorded, not silently dropped
            cf.read_error = f"Failed to read/parse file: {exc}"
        company_files[source_id] = company_file_to_dict(cf)

    state.pending_file_refs = rest
    state.company_files = company_files
    job.progress_current = (job.progress_current or 0) + len(batch)

    if not rest:
        job.status = "Matching"


def _run_matching(job: Job, state: JobState) -> None:
    master_records = [company_record_from_dict(d) for d in state.master_records]
    company_files = {k: company_file_from_dict(v) for k, v in (state.company_files or {}).items()}

    matcher = CompanyMatcher(master_records)
    manual_overrides = state.manual_overrides or {}

    match_records = []
    for source_id, cf in company_files.items():
        if source_id in manual_overrides:
            row_index = manual_overrides[source_id]
            target = next((r for r in master_records if r.row_index == row_index), None)
            if target:
                from ..core.models import MatchRecord

                match_records.append(
                    MatchRecord(
                        file_name=cf.file_name,
                        extracted_company_name=cf.extracted_company_name,
                        matched_company=target.company_name,
                        matched_row_index=target.row_index,
                        status=MatchStatus.EXACT,
                        method=MatchMethod.MANUAL,
                        confidence=1.0,
                        source_file_id=source_id,
                        notes="Manually confirmed by user.",
                    )
                )
                continue
        match_records.append(matcher.match(cf.file_name, cf.extracted_company_name, source_id))

    state.match_records = [match_record_to_dict(m) for m in match_records]
    job.status = "Validating"


def _run_validating(job: Job, state: JobState) -> None:
    master_records = [company_record_from_dict(d) for d in state.master_records]
    company_files = {k: company_file_from_dict(v) for k, v in (state.company_files or {}).items()}
    match_records = [match_record_from_dict(d) for d in state.match_records]

    consolidated_rows = build_consolidated_rows(master_records, company_files, match_records)
    validation_issues, summary = run_validation(master_records, company_files, match_records, consolidated_rows)

    from dataclasses import asdict

    state.validation_issues = [asdict(i) for i in validation_issues]
    state.summary = summary
    job.status = "Exporting"


def _run_exporting(job: Job, state: JobState, session: Session) -> None:
    master_records = [company_record_from_dict(d) for d in state.master_records]
    company_files = {k: company_file_from_dict(v) for k, v in (state.company_files or {}).items()}
    match_records = [match_record_from_dict(d) for d in state.match_records]
    consolidated_rows = build_consolidated_rows(master_records, company_files, match_records)

    from ..core.models import ValidationIssue

    validation_issues = [ValidationIssue(**d) for d in (state.validation_issues or [])]

    buf = io.BytesIO()
    export_workbook(consolidated_rows, validation_issues, match_records, state.summary or {}, buf)
    buf.seek(0)

    output = session.get(JobOutput, job.id)
    if output is None:
        output = JobOutput(job_id=job.id, file_name="Consolidated_Output.xlsx", file_bytes=buf.read())
        session.add(output)
    else:
        output.file_bytes = buf.getvalue()

    job.status = "Completed"
    job.completed_at = datetime.utcnow()
