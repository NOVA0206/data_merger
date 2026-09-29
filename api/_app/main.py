"""FastAPI application: auth, job management, preview, export.

Deployed on Vercel as a single Python serverless function behind /api/** (see
api/index.py). Each request is a fresh, short-lived invocation, which is why job
progress lives in Postgres (JobState) rather than in-process memory.
"""
from __future__ import annotations

import secrets
import time
import uuid
from datetime import datetime, timedelta

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, StreamingResponse
import io

from .auth.google_oauth import (
    build_authorization_url,
    credentials_to_encrypted_refresh_token,
    exchange_code_for_credentials,
)
from .auth.session import issue_session_token, require_user
from .config import settings
from .db.database import init_db, session_scope
from .db.models import Job, JobOutput, JobState, UserToken
from .jobs.job_runner import TERMINAL_STATUSES, advance_job

app = FastAPI(title="Company Data Consolidation API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL] if settings.FRONTEND_URL else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_oauth_states: dict[str, float] = {}  # in-memory CSRF state cache (best-effort; see note below)
STATE_TTL_SECONDS = 600


@app.on_event("startup")
def _startup() -> None:
    if settings.DATABASE_URL:
        init_db()


@app.get("/api/health")
def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Google OAuth
# ---------------------------------------------------------------------------
# NOTE: because Vercel serverless functions do not share memory across
# invocations, the CSRF `state` cache below is best-effort only (it protects
# same-instance replay within a warm container). For a stronger guarantee,
# swap this for a short-lived DB-backed state table.


@app.get("/api/auth/google/login")
def google_login():
    missing = [
        name
        for name in ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REDIRECT_URI")
        if not getattr(settings, name)
    ]
    if missing:
        raise HTTPException(
            status_code=500,
            detail=(
                "Google OAuth is not configured on the server. Missing environment "
                f"variable(s): {', '.join(missing)}. See .env.example."
            ),
        )
    state = secrets.token_urlsafe(24)
    _oauth_states[state] = time.time()
    url = build_authorization_url(state)
    return {"url": url}


@app.get("/api/auth/google/callback")
def google_callback(code: str, state: str):
    issued_at = _oauth_states.pop(state, None)
    if issued_at is None or (time.time() - issued_at) > STATE_TTL_SECONDS:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state.")

    creds = exchange_code_for_credentials(code, state)

    from google.oauth2 import id_token as google_id_token
    from google.auth.transport import requests as google_requests

    info = google_id_token.verify_oauth2_token(creds.id_token, google_requests.Request(), settings.GOOGLE_CLIENT_ID)
    email = info["email"]

    encrypted = credentials_to_encrypted_refresh_token(creds)
    with session_scope() as session:
        row = session.query(UserToken).filter(UserToken.user_email == email).one_or_none()
        if row:
            row.encrypted_refresh_token = encrypted
        else:
            session.add(UserToken(user_email=email, encrypted_refresh_token=encrypted))

    session_token = issue_session_token(email)
    return RedirectResponse(f"{settings.FRONTEND_URL}/auth/callback#token={session_token}")


@app.get("/api/me")
def me(user_email: str = Depends(require_user)):
    return {"email": user_email}


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------


def _job_to_dict(job: Job) -> dict:
    return {
        "id": job.id,
        "status": job.status,
        "progress_current": job.progress_current,
        "progress_total": job.progress_total,
        "source_type": job.source_type,
        "error_details": job.error_details,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "mapping_resolved": job.state.mapping_resolved if job.state else None,
        "mapping_unresolved": job.state.mapping_unresolved if job.state else None,
        "mapping_ambiguous": job.state.mapping_ambiguous if job.state else None,
        "summary": job.state.summary if job.state else None,
    }


@app.post("/api/jobs")
def create_job(payload: dict, request: Request):
    source_type = payload.get("source_type")
    if source_type not in ("local", "drive"):
        raise HTTPException(status_code=400, detail="source_type must be 'local' or 'drive'.")

    if source_type == "drive":
        auth_header = request.headers.get("authorization")
        if not auth_header:
            raise HTTPException(status_code=401, detail="Google sign-in required for Drive jobs.")
        from .auth.session import verify_session_token

        user_id = verify_session_token(auth_header.split(" ", 1)[1].strip())
        drive_folder_id = payload.get("drive_folder_id")
        if not drive_folder_id:
            raise HTTPException(status_code=400, detail="drive_folder_id is required.")
        local_path = None
    else:
        user_id = payload.get("user_id", "local-user")
        local_path = payload.get("local_path")
        if not local_path:
            raise HTTPException(status_code=400, detail="local_path is required for local jobs.")
        drive_folder_id = None

    with session_scope() as session:
        job = Job(
            id=str(uuid.uuid4()),
            user_id=user_id,
            source_type=source_type,
            drive_folder_id=drive_folder_id,
            local_path=local_path,
            status="Pending",
            field_overrides=payload.get("field_overrides") or {},
        )
        session.add(job)
        session.flush()
        job_id = job.id

    return {"job_id": job_id}


@app.post("/api/jobs/{job_id}/advance")
def advance(job_id: str):
    with session_scope() as session:
        job = session.get(Job, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found.")
        advance_job(session, job)
        return _job_to_dict(job)


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    with session_scope() as session:
        job = session.get(Job, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found.")
        return _job_to_dict(job)


@app.get("/api/jobs/{job_id}/preview")
def preview_job(job_id: str):
    with session_scope() as session:
        job = session.get(Job, job_id)
        if not job or not job.state:
            raise HTTPException(status_code=404, detail="Job or job state not found.")
        state = job.state
        return {
            "master_companies": [r["company_name"] for r in (state.master_records or [])],
            "company_files": [
                {"source_id": k, "file_name": v["file_name"], "extracted_company_name": v["extracted_company_name"], "read_error": v.get("read_error")}
                for k, v in (state.company_files or {}).items()
            ],
            "match_records": state.match_records or [],
            "validation_issues": state.validation_issues or [],
            "summary": state.summary,
        }


@app.post("/api/jobs/{job_id}/manual-match")
def manual_match(job_id: str, payload: dict):
    source_id = payload.get("source_id")
    master_row_index = payload.get("master_row_index")
    if source_id is None or master_row_index is None:
        raise HTTPException(status_code=400, detail="source_id and master_row_index are required.")

    with session_scope() as session:
        job = session.get(Job, job_id)
        if not job or not job.state:
            raise HTTPException(status_code=404, detail="Job or job state not found.")
        overrides = dict(job.state.manual_overrides or {})
        overrides[source_id] = master_row_index
        job.state.manual_overrides = overrides
        # Re-run downstream steps to reflect the correction.
        if job.status in TERMINAL_STATUSES.union({"Validating", "Exporting"}):
            job.status = "Matching"
        return {"status": job.status}


@app.get("/api/jobs/{job_id}/download")
def download_job(job_id: str):
    with session_scope() as session:
        job = session.get(Job, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found.")
        if job.status != "Completed":
            raise HTTPException(status_code=409, detail=f"Job is not complete (status: {job.status}).")
        output = session.get(JobOutput, job_id)
        if not output:
            raise HTTPException(status_code=404, detail="Output not found.")
        return StreamingResponse(
            io.BytesIO(output.file_bytes),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{output.file_name}"'},
        )


@app.post("/api/jobs/{job_id}/export-to-sheets")
def export_to_sheets(job_id: str, request: Request):
    auth_header = request.headers.get("authorization")
    if not auth_header:
        raise HTTPException(status_code=401, detail="Google sign-in required.")
    from .auth.session import verify_session_token

    user_email = verify_session_token(auth_header.split(" ", 1)[1].strip())

    with session_scope() as session:
        job = session.get(Job, job_id)
        if not job or job.status != "Completed" or not job.state:
            raise HTTPException(status_code=409, detail="Job must be completed first.")

        from .auth.google_oauth import credentials_from_encrypted_refresh_token
        from .core.drive_connector import DriveClient
        from .core.consolidator import build_consolidated_rows
        from .core.serialization import company_file_from_dict, company_record_from_dict, match_record_from_dict
        from .core.sheets_exporter import build_sheets_payload

        token_row = session.query(UserToken).filter(UserToken.user_email == user_email).one_or_none()
        if not token_row:
            raise HTTPException(status_code=401, detail="No stored Google credentials for this user.")
        creds = credentials_from_encrypted_refresh_token(token_row.encrypted_refresh_token)
        client = DriveClient(creds)

        state = job.state
        master_records = [company_record_from_dict(d) for d in state.master_records]
        company_files = {k: company_file_from_dict(v) for k, v in (state.company_files or {}).items()}
        match_records = [match_record_from_dict(d) for d in state.match_records]
        consolidated_rows = build_consolidated_rows(master_records, company_files, match_records)

        from .core.models import ValidationIssue

        validation_issues = [ValidationIssue(**d) for d in (state.validation_issues or [])]
        payload = build_sheets_payload(consolidated_rows, validation_issues, match_records, state.summary or {})
        spreadsheet_id = client.create_spreadsheet_from_rows("Consolidated Company Data", payload)

    return {"spreadsheet_url": f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit"}


# ---------------------------------------------------------------------------
# Vercel Cron safety net: advances any stale in-progress job.
# ---------------------------------------------------------------------------


@app.get("/api/cron/advance-jobs")
def cron_advance_jobs(request: Request):
    if settings.CRON_SECRET:
        auth_header = request.headers.get("authorization")
        if not auth_header or auth_header != f"Bearer {settings.CRON_SECRET}":
            raise HTTPException(status_code=401, detail="Invalid cron secret.")

    advanced = []
    with session_scope() as session:
        stale_before = datetime.utcnow() - timedelta(seconds=90)
        jobs = (
            session.query(Job)
            .filter(Job.status.notin_(list(TERMINAL_STATUSES)))
            .filter(Job.updated_at < stale_before)
            .limit(20)
            .all()
        )
        for job in jobs:
            advance_job(session, job)
            advanced.append(job.id)
    return {"advanced": advanced}
