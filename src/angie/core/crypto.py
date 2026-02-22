"""AES encryption helpers for credential storage."""

from __future__ import annotations

import base64
import hashlib
import json
import logging

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    """Get or create a Fernet instance derived from SECRET_KEY."""
    global _fernet  # noqa: PLW0603
    if _fernet is None:
        from angie.config import get_settings

        secret = get_settings().secret_key
        key = hashlib.pbkdf2_hmac("sha256", secret.encode(), b"angie-connections", 100_000)
        fernet_key = base64.urlsafe_b64encode(key[:32])
        _fernet = Fernet(fernet_key)
    return _fernet


def encrypt_json(data: dict) -> str:
    """Encrypt a dict as a Fernet-encrypted base64 string."""
    plaintext = json.dumps(data).encode()
    return _get_fernet().encrypt(plaintext).decode()


def decrypt_json(ciphertext: str) -> dict:
    """Decrypt a Fernet-encrypted string back to a dict."""
    try:
        plaintext = _get_fernet().decrypt(ciphertext.encode())
        return json.loads(plaintext)
    except (InvalidToken, json.JSONDecodeError) as exc:
        logger.error("Failed to decrypt credentials: %s", type(exc).__name__)
        raise ValueError("Invalid or corrupted credential data") from exc


def mask_credential(value: str, visible: int = 4) -> str:
    """Mask a credential string, showing only the last N characters.

    Examples:
        mask_credential("ghp_abcdefghijk") → "ghp_*******ijk"
        mask_credential("short") → "***rt"
    """
    if len(value) <= visible:
        return "*" * len(value)
    return "*" * (len(value) - visible) + value[-visible:]


def reset_fernet() -> None:
    """Reset cached Fernet instance (for testing)."""
    global _fernet  # noqa: PLW0603
    _fernet = None
