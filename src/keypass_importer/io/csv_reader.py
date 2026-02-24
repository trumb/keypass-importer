"""Read entries from CSV files as alternative to KeePass .kdbx."""

from __future__ import annotations

import csv
import logging
from pathlib import Path

from keypass_importer.core.models import KeePassEntry

logger = logging.getLogger(__name__)

# Required columns
REQUIRED_COLUMNS = {"title", "username", "password"}
# Optional columns with defaults
OPTIONAL_COLUMNS = {"url": None, "group": None, "notes": None}


def read_csv_entries(path: Path) -> list[KeePassEntry]:
    """Read entries from a CSV file into KeePassEntry models.

    Required columns: title, username, password
    Optional columns: url, group, notes
    Group can be slash-separated (e.g. "Servers/Linux").
    """
    if not path.exists():
        raise FileNotFoundError(f"CSV file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        if reader.fieldnames is None:
            raise ValueError(f"CSV file is empty: {path}")

        missing = REQUIRED_COLUMNS - set(reader.fieldnames)
        if missing:
            raise ValueError(
                f"CSV missing required columns: {', '.join(sorted(missing))}"
            )

        entries: list[KeePassEntry] = []
        for i, row in enumerate(reader, start=2):  # line 2 = first data row
            title = row.get("title", "").strip()
            username = row.get("username", "").strip()
            password = row.get("password", "")

            if not username:
                logger.warning("Skipping row %d: no username", i)
                continue

            group_str = row.get("group", "") or ""
            group_path = [p.strip() for p in group_str.split("/") if p.strip()]

            entries.append(
                KeePassEntry(
                    title=title or "(untitled)",
                    username=username,
                    password=password,
                    url=row.get("url") or None,
                    group_path=group_path,
                    notes=row.get("notes") or None,
                )
            )

    logger.info("Read %d entries from CSV %s", len(entries), path.name)
    return entries
