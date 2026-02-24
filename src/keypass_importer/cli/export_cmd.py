"""CLI export command."""

from __future__ import annotations

import sys
from pathlib import Path

import click

from keypass_importer.cli import cli
from keypass_importer.keepass.reader import read_keepass


@cli.command()
@click.argument("kdbx_file", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    default="export.csv",
    help="Output CSV path.",
)
@click.option("--no-notes", is_flag=True, help="Exclude notes from export.")
def export(kdbx_file: Path, output: Path, no_notes: bool):
    """Export KeePass entries to CSV for auditing (no passwords)."""
    password = click.prompt("KeePass master password", hide_input=True)
    try:
        entries = read_keepass(kdbx_file, password=password)
    except (ValueError, FileNotFoundError) as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    from keypass_importer.io.exporter import export_entries_csv

    count = export_entries_csv(entries, output, include_notes=not no_notes)
    click.echo(f"Exported {count} entries to {output}")
