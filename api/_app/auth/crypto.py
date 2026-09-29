"""Symmetric encryption for Google OAuth refresh tokens at rest.

GOOGLE_TOKEN_ENCRYPTION_KEY must be a urlsafe-base64 32-byte Fernet key,
generated once with `Fernet.generate_key()` and stored only as an environment
variable (never committed, never logged).
"""
from __future__ import annotations

from functools import lru_cache

from cryptography.fernet import Fernet

from ..config import settings


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    key = settings.GOOGLE_TOKEN_ENCRYPTION_KEY
    if not key:
        raise RuntimeError(
            "GOOGLE_TOKEN_ENCRYPTION_KEY is not set. Generate one with: "
            "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_token(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_token(ciphertext: str) -> str:
    return _fernet().decrypt(ciphertext.encode()).decode()
