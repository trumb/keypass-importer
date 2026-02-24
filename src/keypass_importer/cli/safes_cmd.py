"""CLI list-safes command."""

from __future__ import annotations

import click

from keypass_importer.cli import cli
from keypass_importer.cyberark.auth import authenticate
from keypass_importer.cyberark.client import CyberArkClient


@cli.command("list-safes")
@click.option("--tenant-url", required=True, help="CyberArk tenant URL.")
@click.option("--client-id", required=True, help="OIDC client ID.")
def list_safes(tenant_url: str, client_id: str):
    """List available safes in CyberArk."""
    token = authenticate(tenant_url, client_id)
    client = CyberArkClient(tenant_url, token.access_token)
    try:
        safes = client.list_safes()
        click.echo(f"\nAvailable safes ({len(safes)}):\n")
        for safe in safes:
            click.echo(f"  - {safe}")
    finally:
        client.close()
