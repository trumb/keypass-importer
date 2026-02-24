"""Windows DPAPI decryption for KeePass user key.

KeePass 2.x stores a protected user key at:
    %APPDATA%/KeePass/ProtectedUserKey.bin

Decrypts using CryptUnprotectData via ctypes.
Only works on Windows, only on the same user account.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


class _DataBlob(ctypes.Structure):
    """DPAPI DATA_BLOB structure."""

    _fields_ = [
        ("cbData", ctypes.wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_ubyte)),
    ]


def _get_user_key_path() -> Path:
    """Return the path to the KeePass ProtectedUserKey.bin file."""
    appdata = os.environ.get("APPDATA", "")
    return Path(appdata) / "KeePass" / "ProtectedUserKey.bin"


def _crypt_unprotect_data(encrypted: bytes) -> bytes:
    """Decrypt data using Windows DPAPI CryptUnprotectData."""
    crypt32 = ctypes.windll.crypt32

    blob_in = _DataBlob()
    blob_in.cbData = len(encrypted)
    blob_in.pbData = ctypes.cast(
        ctypes.create_string_buffer(encrypted, len(encrypted)),
        ctypes.POINTER(ctypes.c_ubyte),
    )

    blob_out = _DataBlob()

    success = crypt32.CryptUnprotectData(
        ctypes.byref(blob_in),
        None,
        None,
        None,
        None,
        0,
        ctypes.byref(blob_out),
    )

    if not success:
        raise OSError("CryptUnprotectData failed (wrong user account?)")

    result = ctypes.string_at(blob_out.pbData, blob_out.cbData)
    ctypes.windll.kernel32.LocalFree(blob_out.pbData)
    return result


def dpapi_decrypt_user_key() -> bytes:
    """Decrypt the KeePass ProtectedUserKey.bin using DPAPI.

    Returns raw transformed key bytes for PyKeePass(transformed_key=...).
    """
    key_path = _get_user_key_path()
    if not key_path.exists():
        raise FileNotFoundError(
            f"KeePass ProtectedUserKey.bin not found at {key_path}. "
            "Ensure KeePass is configured with Windows user account protection."
        )

    logger.info("Reading protected user key from %s", key_path)
    encrypted = key_path.read_bytes()
    decrypted = _crypt_unprotect_data(encrypted)
    logger.info("Successfully decrypted user key (%d bytes)", len(decrypted))
    return decrypted
