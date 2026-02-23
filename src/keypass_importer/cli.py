"""Click-based CLI for KeePass to CyberArk importer."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import click
from tqdm import tqdm

from keypass_importer.config import load_config
from keypass_importer.cyberark_auth import authenticate
from keypass_importer.cyberark_client import CyberArkClient
from keypass_importer.keepass_reader import read_keepass
from keypass_importer.mapper import map_entry
from keypass_importer.models import ImportResult, ImportSummary, MappingMode
from keypass_importer.reporter import write_results_csv, write_summary


@click.group()
@click.option("--verbose", is_flag=True, help="Enable debug logging.")
def cli(verbose: bool):
    """KeePass to CyberArk Privilege Cloud importer."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(levelname)s: %(message)s",
    )


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


@cli.command("import")
@click.argument("kdbx_file", type=click.Path(exists=True, path_type=Path))
@click.option("--tenant-url", required=True, help="CyberArk tenant URL.")
@click.option("--client-id", required=True, help="OIDC client ID.")
@click.option("--safe", default=None, help="Target safe (single mode).")
@click.option(
    "--mapping-mode",
    type=click.Choice(["single", "group", "config"]),
    default="single",
    help="Mapping mode.",
)
@click.option(
    "--map-file",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="YAML mapping rules.",
)
@click.option("--default-platform", default=None, help="Override platform detection.")
@click.option("--dry-run", is_flag=True, help="Validate without importing.")
@click.option(
    "--output-dir",
    type=click.Path(path_type=Path),
    default=".",
    help="Directory for CSV reports.",
)
@click.option(
    "--config",
    "config_path",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="YAML config file.",
)
def import_cmd(
    kdbx_file: Path,
    tenant_url: str,
    client_id: str,
    safe: str | None,
    mapping_mode: str,
    map_file: Path | None,
    default_platform: str | None,
    dry_run: bool,
    output_dir: Path,
    config_path: Path | None,
):
    """Import KeePass entries into CyberArk Privilege Cloud."""
    # Load config file if provided (CLI flags override config values)
    mapping_rules = None
    if config_path:
        cfg = load_config(config_path)
        tenant_url = tenant_url or cfg.tenant_url
        client_id = client_id or cfg.client_id
        safe = safe or cfg.safe
        mapping_mode = mapping_mode or cfg.mapping_mode
        default_platform = default_platform or cfg.default_platform
        if cfg.output_dir:
            output_dir = Path(cfg.output_dir)
        mapping_rules = cfg.mapping_rules or None

    if map_file:
        from keypass_importer.config import load_config as _load

        map_cfg = _load(map_file)
        mapping_rules = map_cfg.mapping_rules

    mode = MappingMode(mapping_mode)

    # Validate safe requirement
    if mode == MappingMode.SINGLE and not safe:
        click.echo("Error: --safe is required for single mapping mode.", err=True)
        sys.exit(1)

    # Read KeePass
    password = click.prompt("KeePass master password", hide_input=True)
    try:
        entries = read_keepass(kdbx_file, password=password)
    except (ValueError, FileNotFoundError) as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    click.echo(f"Found {len(entries)} entries in {kdbx_file.name}")

    if dry_run:
        click.echo("\n[Dry run] Mapping entries without importing...\n")

    # Authenticate (even in dry-run, to validate credentials)
    token = authenticate(tenant_url, client_id)
    client = CyberArkClient(tenant_url, token.access_token)

    results: list[ImportResult] = []
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        for entry in tqdm(entries, desc="Importing", disable=dry_run):
            try:
                account = map_entry(
                    entry,
                    mode=mode,
                    safe_name=safe,
                    default_platform=default_platform,
                    mapping_rules=mapping_rules,
                )

                if dry_run:
                    click.echo(
                        f"  [{entry.group_path_str or 'root'}] {entry.title} "
                        f"-> safe={account.safe_name} platform={account.platform_id}"
                    )
                    results.append(
                        ImportResult(
                            entry_title=entry.title,
                            entry_group=entry.group_path_str,
                            status="imported",
                            safe_name=account.safe_name,
                        )
                    )
                    continue

                # Check for duplicates
                existing_id = client.find_existing_account(
                    account.safe_name, account.address, account.username
                )
                if existing_id:
                    results.append(
                        ImportResult(
                            entry_title=entry.title,
                            entry_group=entry.group_path_str,
                            status="duplicate",
                            safe_name=account.safe_name,
                            account_id=existing_id,
                        )
                    )
                    continue

                # Create account
                account_id = client.create_account(account)
                results.append(
                    ImportResult(
                        entry_title=entry.title,
                        entry_group=entry.group_path_str,
                        status="imported",
                        safe_name=account.safe_name,
                        account_id=account_id,
                    )
                )

            except Exception as exc:
                results.append(
                    ImportResult(
                        entry_title=entry.title,
                        entry_group=entry.group_path_str,
                        status="failed",
                        error=str(exc),
                    )
                )

    finally:
        client.close()

    # Write reports
    write_results_csv(results, output_dir / "results.csv")
    write_results_csv(results, output_dir / "duplicates.csv", status_filter="duplicate")
    write_results_csv(results, output_dir / "failed.csv", status_filter="failed")

    summary = ImportSummary.from_results(results)
    write_summary(summary)

    if dry_run:
        click.echo("Dry run complete. No changes were made to CyberArk.")
