"""Symmetric encryption for Google OAuth refresh tokens at rest.

GOOGLE_TOKEN_ENCRYPTION_KEY must be a urlsafe-base64 32-byte Fernet key,
generated once with `Fernet.generate_key()` and stored only as an environment
variable (never committed, never logged).
"""
from __future__ import annotations

import base64
import hashlib
from functools import lru_cache

from cryptography.fernet import Fernet

from ..config import settings


def _normalize_fernet_key(raw_key: str) -> bytes:
    """Use raw_key directly if it is a valid Fernet key; otherwise derive one via SHA-256."""
    raw_bytes = raw_key.strip().encode()
    try:
        Fernet(raw_bytes)
        return raw_bytes
    except ValueError:
        return base64.urlsafe_b64encode(hashlib.sha256(raw_bytes).digest())


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    key = settings.GOOGLE_TOKEN_ENCRYPTION_KEY
    if not key:
        raise RuntimeError(
            "GOOGLE_TOKEN_ENCRYPTION_KEY is not set. Generate one with: "
            "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    return Fernet(_normalize_fernet_key(key))


def encrypt_token(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_token(ciphertext: str) -> str:
    return _fernet().decrypt(ciphertext.encode()).decode()
