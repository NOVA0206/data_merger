"""ORM models for job tracking and persisted OAuth tokens."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, LargeBinary, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _uuid() -> str:
    return str(uuid.uuid4())


class UserToken(Base):
    """Encrypted Google OAuth refresh token for one signed-in user."""

    __tablename__ = "user_tokens"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    user_email: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    encrypted_refresh_token: Mapped[str] = mapped_column(Text, nullable=False)
    scopes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String, nullable=False)  # "drive" | "local"
    drive_folder_id: Mapped[str | None] = mapped_column(String, nullable=True)
    local_path: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="Pending")
    progress_current: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    progress_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_details: Mapped[str | None] = mapped_column(Text, nullable=True)
    field_overrides: Mapped[dict[str, str] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    state: Mapped[JobState | None] = relationship("JobState", back_populates="job", uselist=False, cascade="all, delete-orphan")
    output: Mapped[JobOutput | None] = relationship("JobOutput", back_populates="job", uselist=False, cascade="all, delete-orphan")


class JobState(Base):
    """Serialized pipeline state carried between chunked processing steps."""

    __tablename__ = "job_state"

    job_id: Mapped[str] = mapped_column(String, ForeignKey("jobs.id"), primary_key=True)
    master_records: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    pending_file_refs: Mapped[list[dict[str, str]] | None] = mapped_column(JSON, nullable=True)
    company_files: Mapped[dict[str, dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    match_records: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    mapping_resolved: Mapped[dict[str, str] | None] = mapped_column(JSON, nullable=True)
    mapping_unresolved: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    mapping_ambiguous: Mapped[dict[str, list[str]] | None] = mapped_column(JSON, nullable=True)
    validation_issues: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    summary: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    manual_overrides: Mapped[dict[str, int] | None] = mapped_column(JSON, nullable=True)

    job: Mapped[Job] = relationship("Job", back_populates="state")


class JobOutput(Base):
    __tablename__ = "job_outputs"

    job_id: Mapped[str] = mapped_column(String, ForeignKey("jobs.id"), primary_key=True)
    file_name: Mapped[str] = mapped_column(String, nullable=False)
    file_bytes: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    job: Mapped[Job] = relationship("Job", back_populates="output")
