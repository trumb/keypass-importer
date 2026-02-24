"""Export KeePass entries to CSV for auditing (never contains passwords)."""

from __future__ import annotations

import csv
import logging
from pathlib import Path

from keypass_importer.io.mapper import detect_platform
from keypass_importer.core.models import KeePassEntry

logger = logging.getLogger(__name__)

_EXPORT_COLUMNS = [
    "group",
    "title",
    "username",
    "url",
    "detected_platform",
    "notes",
    "custom_fields",
]


def export_entries_csv(
    entries: list[KeePassEntry],
    output_path: Path,
    include_notes: bool = True,
) -> int:
    """Write KeePass entries to CSV for review. NEVER includes passwords.

    Returns the number of entries written.
    """
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_EXPORT_COLUMNS)
        writer.writeheader()
        for entry in entries:
            writer.writerow(
                {
                    "group": entry.group_path_str or "(root)",
                    "title": entry.title,
                    "username": entry.username,
                    "url": entry.url or "",
                    "detected_platform": detect_platform(entry.url),
                    "notes": (entry.notes or "") if include_notes else "",
                    "custom_fields": (
                        "; ".join(
                            f"{k}={v}" for k, v in entry.custom_fields.items()
                        )
                        if entry.custom_fields
                        else ""
                    ),
                }
            )

    count = len(entries)
    logger.info("Exported %d entries to %s", count, output_path)
    return count
