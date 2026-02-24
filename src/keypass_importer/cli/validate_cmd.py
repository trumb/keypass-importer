"""CLI validate command."""

from __future__ import annotations

import sys
from pathlib import Path

import click

from keypass_importer.cli import cli
from keypass_importer.keepass.reader import read_keepass


@cli.command()
@click.argument("kdbx_file", type=click.Path(exists=True, path_type=Path))
def validate(kdbx_file: Path):
    """Validate a KeePass file and show entry summary."""
    password = click.prompt("KeePass master password", hide_input=True)
    try:
        entries = read_keepass(kdbx_file, password=password)
    except (ValueError, FileNotFoundError) as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    click.echo(f"\nFound {len(entries)} entries:\n")
    for entry in entries:
        group = entry.group_path_str or "(root)"
        click.echo(f"  [{group}] {entry.title} ({entry.username})")
