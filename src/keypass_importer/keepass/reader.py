"""Reads KeePass .kdbx files and returns structured entry data."""

from __future__ import annotations

import logging
from pathlib import Path

from keypass_importer.core.models import KeePassEntry
from keypass_importer.keepass.unlock import open_database

logger = logging.getLogger(__name__)


def _group_path(entry) -> list[str]:
    """Extract group hierarchy path, excluding the root group."""
    path_parts: list[str] = []
    group = entry.group
    while group and group.name and group.name != "Root":
        path_parts.append(group.name)
        group = group.parentgroup
    path_parts.reverse()
    return path_parts


def _custom_fields(entry) -> dict[str, str]:
    """Extract non-standard custom string fields from a KeePass entry."""
    props = entry.custom_properties or {}
    return {k: v for k, v in props.items() if v is not None}


def read_keepass(
    path: Path,
    password: str | None = None,
    keyfile: Path | None = None,
    use_windows_credential: bool = False,
) -> list[KeePassEntry]:
    """Open a .kdbx file and return all usable entries.

    Skips entries without a username (required for CyberArk accounts).
    """
    kp = open_database(
        path,
        password=password,
        keyfile=keyfile,
        use_windows_credential=use_windows_credential,
    )

    entries: list[KeePassEntry] = []
    for raw_entry in kp.entries:
        # Skip the recycle bin
        if raw_entry.group and raw_entry.group.name == "Recycle Bin":
            continue

        username = raw_entry.username or ""
        if not username.strip():
            logger.warning("Skipping entry '%s': no username", raw_entry.title)
            continue

        entries.append(
            KeePassEntry(
                title=raw_entry.title or "(untitled)",
                username=username,
                password=raw_entry.password or "",
                url=raw_entry.url,
                group_path=_group_path(raw_entry),
                notes=raw_entry.notes,
                custom_fields=_custom_fields(raw_entry),
            )
        )

    logger.info("Read %d entries from %s", len(entries), path.name)
    return entries
