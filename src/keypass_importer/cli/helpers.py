"""Shared CLI helpers for password prompts and credential handling."""

from __future__ import annotations

from pathlib import Path

import click


def prompt_password(
    keyfile: Path | None,
    windows_credential: bool,
) -> str | None:
    """Prompt for KeePass master password, optional when alternatives exist.

    When a *keyfile* or *windows_credential* is provided the password becomes
    optional (user can press Enter to skip).  Otherwise the password is
    required.
    """
    if not (windows_credential or keyfile):
        return click.prompt("KeePass master password", hide_input=True)

    password = click.prompt(
        "KeePass master password (press Enter to skip)",
        hide_input=True,
        default="",
        show_default=False,
    )
    return password or None
