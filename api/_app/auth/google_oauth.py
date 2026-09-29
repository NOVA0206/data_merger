"""Google OAuth 2.0 authorization-code flow for Drive + Sheets access.

Requests only the scopes needed to read source files and create the output
spreadsheet (drive.readonly for reading the source folder, plus a per-file
scope for creating the new consolidated spreadsheet — never broad Drive write
access).
"""
from __future__ import annotations

from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials

from ..config import settings
from .crypto import decrypt_token, encrypt_token

SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/spreadsheets",
]


def _client_config() -> dict:
    if not (settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET and settings.GOOGLE_REDIRECT_URI):
        raise RuntimeError(
            "GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET / GOOGLE_REDIRECT_URI must be set."
        )
    return {
        "web": {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [settings.GOOGLE_REDIRECT_URI],
        }
    }


def build_authorization_url(state: str) -> str:
    flow = Flow.from_client_config(_client_config(), scopes=SCOPES, state=state)
    flow.redirect_uri = settings.GOOGLE_REDIRECT_URI
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    return auth_url


def exchange_code_for_credentials(code: str, state: str) -> Credentials:
    flow = Flow.from_client_config(_client_config(), scopes=SCOPES, state=state)
    flow.redirect_uri = settings.GOOGLE_REDIRECT_URI
    flow.fetch_token(code=code)
    return flow.credentials


def credentials_to_encrypted_refresh_token(creds: Credentials) -> str:
    if not creds.refresh_token:
        raise RuntimeError(
            "Google did not return a refresh token. Ensure prompt=consent and "
            "access_type=offline were used, and that this is the user's first consent."
        )
    return encrypt_token(creds.refresh_token)


def credentials_from_encrypted_refresh_token(encrypted_refresh_token: str) -> Credentials:
    refresh_token = decrypt_token(encrypted_refresh_token)
    return Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        scopes=SCOPES,
    )
