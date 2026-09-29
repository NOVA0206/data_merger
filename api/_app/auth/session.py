"""Minimal stateless session tokens (JWT) issued after Google OAuth login.

We do not store a server-side session table; the JWT carries the user's email
and is verified on every request. It never carries the Google access/refresh
token itself (those stay encrypted in Postgres, keyed by email).
"""
from __future__ import annotations

import time

import jwt
from fastapi import Header, HTTPException

from ..config import settings

SESSION_TTL_SECONDS = 60 * 60 * 24 * 7  # 7 days


def _secret() -> str:
    secret = settings.GOOGLE_TOKEN_ENCRYPTION_KEY
    if not secret:
        raise RuntimeError("GOOGLE_TOKEN_ENCRYPTION_KEY must be set to sign session tokens.")
    return secret


def issue_session_token(user_email: str) -> str:
    payload = {"sub": user_email, "iat": int(time.time()), "exp": int(time.time()) + SESSION_TTL_SECONDS}
    return jwt.encode(payload, _secret(), algorithm="HS256")


def verify_session_token(token: str) -> str:
    try:
        payload = jwt.decode(token, _secret(), algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail=f"Invalid or expired session: {exc}")
    return payload["sub"]


def require_user(authorization: str | None = Header(default=None)) -> str:
    """FastAPI dependency: extracts and verifies the bearer session token."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer session token.")
    token = authorization.split(" ", 1)[1].strip()
    return verify_session_token(token)
