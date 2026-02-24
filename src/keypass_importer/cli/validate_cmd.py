"""CLI validate command."""

from __future__ import annotations

import sys
from pathlib import Path

import click

from keypass_importer.cli import cli
from keypass_importer.keepass.reader import read_keepass


@cli.command()
@click.argument("kdbx_file", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--keyfile",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Path to .key/.keyx key file.",
)
@click.option(
    "--windows-credential",
    is_flag=True,
    default=False,
    help="Use Windows user account (DPAPI) to unlock.",
)
def validate(kdbx_file: Path, keyfile: Path | None, windows_credential: bool):
    """Validate a KeePass file and show entry summary."""
    need_password = not (windows_credential or keyfile)
    if need_password:
        password = click.prompt("KeePass master password", hide_input=True)
    else:
        password = click.prompt(
            "KeePass master password (press Enter to skip)",
            hide_input=True,
            default="",
            show_default=False,
        )
        password = password or None

    try:
        entries = read_keepass(
            kdbx_file,
            password=password,
            keyfile=keyfile,
            use_windows_credential=windows_credential,
        )
    except (ValueError, FileNotFoundError) as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    click.echo(f"\nFound {len(entries)} entries:\n")
    for entry in entries:
        group = entry.group_path_str or "(root)"
        click.echo(f"  [{group}] {entry.title} ({entry.username})")
