-- Reference schema (SQLAlchemy's Base.metadata.create_all() creates this
-- automatically on first cold start against DATABASE_URL). Kept here for
-- manual provisioning / review.

CREATE TABLE IF NOT EXISTS user_tokens (
    id UUID PRIMARY KEY,
    user_email VARCHAR NOT NULL UNIQUE,
    encrypted_refresh_token TEXT NOT NULL,
    scopes TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS jobs (
    id UUID PRIMARY KEY,
    user_id VARCHAR NOT NULL,
    source_type VARCHAR NOT NULL,
    drive_folder_id VARCHAR,
    local_path VARCHAR,
    status VARCHAR NOT NULL DEFAULT 'Pending',
    progress_current INTEGER NOT NULL DEFAULT 0,
    progress_total INTEGER NOT NULL DEFAULT 0,
    error_details TEXT,
    field_overrides JSON,
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now(),
    completed_at TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_jobs_user_id ON jobs (user_id);

CREATE TABLE IF NOT EXISTS job_state (
    job_id UUID PRIMARY KEY REFERENCES jobs(id),
    master_records JSON,
    pending_file_refs JSON,
    company_files JSON,
    match_records JSON,
    mapping_resolved JSON,
    mapping_unresolved JSON,
    mapping_ambiguous JSON,
    validation_issues JSON,
    summary JSON,
    manual_overrides JSON
);

CREATE TABLE IF NOT EXISTS job_outputs (
    job_id UUID PRIMARY KEY REFERENCES jobs(id),
    file_name VARCHAR NOT NULL,
    file_bytes BYTEA NOT NULL,
    created_at TIMESTAMP DEFAULT now()
);
