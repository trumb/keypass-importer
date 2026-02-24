"""CLI group management commands (add, delete)."""

from __future__ import annotations

import sys
from pathlib import Path

import click

from keypass_importer.cli import cli
from keypass_importer.cli.helpers import prompt_password
from keypass_importer.keepass.unlock import open_database
from keypass_importer.keepass.writer import add_group, delete_group, save


@cli.group("group")
def group_cli():
    """Manage KeePass database groups."""


@group_cli.command("add")
@click.argument("kdbx_file", type=click.Path(exists=True, path_type=Path))
@click.option("--name", required=True, help="Name of the new group.")
@click.option("--parent", "parent_str", default=None, help="Parent group path (e.g. 'Servers/Linux').")
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
def group_add(
    kdbx_file: Path,
    name: str,
    parent_str: str | None,
    keyfile: Path | None,
    windows_credential: bool,
):
    """Add a new group to the KeePass database."""
    password = prompt_password(keyfile, windows_credential)

    try:
        db = open_database(
            kdbx_file,
            password=password,
            keyfile=keyfile,
            use_windows_credential=windows_credential,
        )
    except (ValueError, FileNotFoundError) as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    parent_path = parent_str.split("/") if parent_str else []

    try:
        add_group(db, parent_path, name)
    except ValueError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    save(db)
    click.echo(f"Added group '{name}'")


@group_cli.command("delete")
@click.argument("kdbx_file", type=click.Path(exists=True, path_type=Path))
@click.option("--name", required=True, help="Group path to delete (e.g. 'Servers/Linux').")
@click.option("--recursive", is_flag=True, help="Delete group even if it has children.")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt.")
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
def group_delete(
    kdbx_file: Path,
    name: str,
    recursive: bool,
    yes: bool,
    keyfile: Path | None,
    windows_credential: bool,
):
    """Delete a group from the KeePass database."""
    label = f"group '{name}'" + (" and all children" if recursive else "")
    if not yes and not click.confirm(f"Delete {label}?"):
        click.echo("Aborted.")
        return

    password = prompt_password(keyfile, windows_credential)

    try:
        db = open_database(
            kdbx_file,
            password=password,
            keyfile=keyfile,
            use_windows_credential=windows_credential,
        )
    except (ValueError, FileNotFoundError) as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    group_path = name.split("/") if name else []

    try:
        delete_group(db, group_path, recursive=recursive)
    except ValueError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    save(db)
    click.echo(f"Deleted group '{name}'")
