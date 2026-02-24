"""Click-based CLI for KeePass to CyberArk importer."""

from __future__ import annotations

import logging

import click


@click.group()
@click.option("--verbose", is_flag=True, help="Enable debug logging.")
def cli(verbose: bool):
    """KeePass to CyberArk Privilege Cloud importer."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(levelname)s: %(message)s",
    )


# Register sub-commands (import order matters: each module decorates cli)
from keypass_importer.cli import validate_cmd  # noqa: E402, F401
from keypass_importer.cli import safes_cmd  # noqa: E402, F401
from keypass_importer.cli import export_cmd  # noqa: E402, F401
from keypass_importer.cli import import_cmd  # noqa: E402, F401
from keypass_importer.cli import entry_cmd  # noqa: E402, F401
from keypass_importer.cli import group_cmd  # noqa: E402, F401
