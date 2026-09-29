"""ORM models for job tracking and persisted OAuth tokens."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, LargeBinary, String, Text
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


def _uuid() -> str:
    return str(uuid.uuid4())


class UserToken(Base):
    """Encrypted Google OAuth refresh token for one signed-in user."""

    __tablename__ = "user_tokens"

    id = Column(String, primary_key=True, default=_uuid)
    user_email = Column(String, unique=True, nullable=False, index=True)
    encrypted_refresh_token = Column(Text, nullable=False)
    scopes = Column(Text, nullable=False, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Job(Base):
    __tablename__ = "jobs"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, nullable=False, index=True)
    source_type = Column(String, nullable=False)  # "drive" | "local"
    drive_folder_id = Column(String, nullable=True)
    local_path = Column(String, nullable=True)
    status = Column(String, nullable=False, default="Pending")
    progress_current = Column(Integer, nullable=False, default=0)
    progress_total = Column(Integer, nullable=False, default=0)
    error_details = Column(Text, nullable=True)
    field_overrides = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    state = relationship("JobState", back_populates="job", uselist=False, cascade="all, delete-orphan")
    output = relationship("JobOutput", back_populates="job", uselist=False, cascade="all, delete-orphan")


class JobState(Base):
    """Serialized pipeline state carried between chunked processing steps."""

    __tablename__ = "job_state"

    job_id = Column(String, ForeignKey("jobs.id"), primary_key=True)
    master_records = Column(JSON, nullable=True)
    pending_file_refs = Column(JSON, nullable=True)  # list of {source_id, file_name}
    company_files = Column(JSON, nullable=True)  # dict source_id -> serialized CompanyFile
    match_records = Column(JSON, nullable=True)
    mapping_resolved = Column(JSON, nullable=True)
    mapping_unresolved = Column(JSON, nullable=True)
    mapping_ambiguous = Column(JSON, nullable=True)
    validation_issues = Column(JSON, nullable=True)
    summary = Column(JSON, nullable=True)
    manual_overrides = Column(JSON, nullable=True)  # {source_id: master_row_index}

    job = relationship("Job", back_populates="state")


class JobOutput(Base):
    __tablename__ = "job_outputs"

    job_id = Column(String, ForeignKey("jobs.id"), primary_key=True)
    file_name = Column(String, nullable=False)
    file_bytes = Column(LargeBinary, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    job = relationship("Job", back_populates="output")
