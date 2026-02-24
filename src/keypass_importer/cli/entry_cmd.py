"""CLI entry management commands (add, edit, delete)."""

from __future__ import annotations

import sys
from pathlib import Path

import click

from keypass_importer.cli import cli
from keypass_importer.cli.helpers import prompt_password


@cli.group()
def entry():
    """Manage KeePass database entries."""


@entry.command("add")
@click.argument("kdbx_file", type=click.Path(exists=True, path_type=Path))
@click.option("--title", required=True, help="Entry title.")
@click.option("--username", required=True, help="Entry username.")
@click.option("--password", "entry_password", required=True, help="Entry password.")
@click.option("--url", default=None, help="Entry URL.")
@click.option("--group", "group_str", default=None, help="Group path (e.g. 'Servers/Linux').")
@click.option("--notes", default=None, help="Entry notes.")
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
def entry_add(
    kdbx_file: Path,
    title: str,
    username: str,
    entry_password: str,
    url: str | None,
    group_str: str | None,
    notes: str | None,
    keyfile: Path | None,
    windows_credential: bool,
):
    """Add a new entry to the KeePass database."""
    password = prompt_password(keyfile, windows_credential)

    from keypass_importer.keepass.unlock import open_database
    from keypass_importer.keepass.writer import add_entry, save

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

    group_path = group_str.split("/") if group_str else []
    add_entry(db, group_path, title, username, entry_password, url=url, notes=notes)
    save(db)
    click.echo(f"Added entry '{title}'")


@entry.command("edit")
@click.argument("kdbx_file", type=click.Path(exists=True, path_type=Path))
@click.option("--title", required=True, help="Title of the entry to edit.")
@click.option("--group", "group_str", default=None, help="Group path to scope search.")
@click.option("--new-title", default=None, help="New title.")
@click.option("--username", default=None, help="New username.")
@click.option("--password", "entry_password", default=None, help="New password.")
@click.option("--url", default=None, help="New URL.")
@click.option("--notes", default=None, help="New notes.")
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
def entry_edit(
    kdbx_file: Path,
    title: str,
    group_str: str | None,
    new_title: str | None,
    username: str | None,
    entry_password: str | None,
    url: str | None,
    notes: str | None,
    keyfile: Path | None,
    windows_credential: bool,
):
    """Edit an existing entry in the KeePass database."""
    password = prompt_password(keyfile, windows_credential)

    from keypass_importer.keepass.unlock import open_database
    from keypass_importer.keepass.writer import find_entry, save, update_entry

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

    group_path = group_str.split("/") if group_str else None
    raw_entry = find_entry(db, title, group_path=group_path)
    if raw_entry is None:
        click.echo(f"Error: Entry '{title}' not found.", err=True)
        sys.exit(1)

    changes: dict = {}
    if new_title is not None:
        changes["title"] = new_title
    if username is not None:
        changes["username"] = username
    if entry_password is not None:
        changes["password"] = entry_password
    if url is not None:
        changes["url"] = url
    if notes is not None:
        changes["notes"] = notes

    if not changes:
        click.echo("No changes specified.")
        return

    update_entry(db, raw_entry, **changes)
    save(db)
    click.echo(f"Updated entry '{title}'")


@entry.command("delete")
@click.argument("kdbx_file", type=click.Path(exists=True, path_type=Path))
@click.option("--title", required=True, help="Title of the entry to delete.")
@click.option("--group", "group_str", default=None, help="Group path to scope search.")
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
def entry_delete(
    kdbx_file: Path,
    title: str,
    group_str: str | None,
    keyfile: Path | None,
    windows_credential: bool,
):
    """Delete an entry from the KeePass database."""
    password = prompt_password(keyfile, windows_credential)

    from keypass_importer.keepass.unlock import open_database
    from keypass_importer.keepass.writer import delete_entry, find_entry, save

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

    group_path = group_str.split("/") if group_str else None
    raw_entry = find_entry(db, title, group_path=group_path)
    if raw_entry is None:
        click.echo(f"Error: Entry '{title}' not found.", err=True)
        sys.exit(1)

    delete_entry(db, raw_entry)
    save(db)
    click.echo(f"Deleted entry '{title}'")
