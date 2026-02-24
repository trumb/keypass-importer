"""Composite key builder for KeePass database unlock."""

from __future__ import annotations

import logging
from pathlib import Path

from pykeepass import PyKeePass
from pykeepass.exceptions import CredentialsError

logger = logging.getLogger(__name__)


def open_database(
    path: Path,
    password: str | None = None,
    keyfile: Path | None = None,
    use_windows_credential: bool = False,
) -> PyKeePass:
    """Open a KeePass .kdbx database with the given credentials.

    Supports: password-only, keyfile-only, password+keyfile,
    DPAPI (use_windows_credential), and any combination.
    """
    if not path.exists():
        raise FileNotFoundError(f"KeePass file not found: {path}")

    if keyfile and not keyfile.exists():
        raise FileNotFoundError(f"Key file not found: {keyfile}")

    transformed_key: bytes | None = None

    if use_windows_credential:
        from keypass_importer.keepass._dpapi import dpapi_decrypt_user_key

        transformed_key = dpapi_decrypt_user_key()
        logger.info("Using Windows credential (DPAPI) for unlock")

    if password is None and not keyfile and not use_windows_credential:
        raise ValueError(
            "At least one credential required: password, keyfile, or windows-credential"
        )

    keyfile_str = str(keyfile) if keyfile else None

    try:
        kp = PyKeePass(
            str(path),
            password=password,
            keyfile=keyfile_str,
            transformed_key=transformed_key,
        )
    except CredentialsError as exc:
        raise ValueError(f"Failed to open KeePass database: {exc}") from exc

    logger.info("Opened database: %s", path.name)
    return kp
