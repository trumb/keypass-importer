"""CSV report generation for import results (never contains secrets)."""

from __future__ import annotations

import csv
import logging
from pathlib import Path

import click

from keypass_importer.models import ImportResult, ImportSummary

logger = logging.getLogger(__name__)

_CSV_COLUMNS = [
    "entry_title",
    "entry_group",
    "status",
    "safe_name",
    "account_id",
    "error",
    "detected_platform",
    "url",
    "timestamp",
]


def write_results_csv(
    results: list[ImportResult],
    output_path: Path,
    status_filter: str | None = None,
) -> None:
    """Write import results to CSV. Optionally filter by status."""
    filtered = results
    if status_filter:
        filtered = [r for r in results if r.status == status_filter]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_CSV_COLUMNS)
        writer.writeheader()
        for result in filtered:
            writer.writerow({
                "entry_title": result.entry_title,
                "entry_group": result.entry_group,
                "status": result.status,
                "safe_name": result.safe_name or "",
                "account_id": result.account_id or "",
                "error": result.error or "",
                "detected_platform": result.detected_platform or "",
                "url": result.url or "",
                "timestamp": result.timestamp or "",
            })

    logger.info("Wrote %d rows to %s", len(filtered), output_path)


def write_summary(summary: ImportSummary) -> None:
    """Print a human-readable import summary."""
    click.echo("\n--- Import Summary ---")
    click.echo(f"  Total entries:  {summary.total}")
    click.echo(f"  Imported:       {summary.imported}")
    click.echo(f"  Duplicates:     {summary.duplicates}")
    click.echo(f"  Failed:         {summary.failed}")
    click.echo("----------------------\n")
