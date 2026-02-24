"""CLI import command."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import click
from tqdm import tqdm

from keypass_importer.cli import cli
from keypass_importer.cli.helpers import prompt_password
from keypass_importer.core.config import load_config
from keypass_importer.core.models import ImportResult, ImportSummary, MappingMode
from keypass_importer.cyberark.auth import authenticate
from keypass_importer.cyberark.client import CyberArkClient
from keypass_importer.io.mapper import detect_platform, map_entry
from keypass_importer.io.reporter import write_results_csv, write_summary
from keypass_importer.keepass.reader import read_keepass


@cli.command("import")
@click.argument("kdbx_file", type=click.Path(exists=True, path_type=Path), required=False)
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
@click.option(
    "--from-csv",
    "from_csv",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Read entries from a CSV file instead of .kdbx.",
)
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
@click.option(
    "--write-back",
    is_flag=True,
    default=False,
    help="Update KeePass entries with CyberArk metadata after import.",
)
def import_cmd(
    kdbx_file: Path | None,
    tenant_url: str,
    client_id: str,
    safe: str | None,
    mapping_mode: str,
    map_file: Path | None,
    default_platform: str | None,
    dry_run: bool,
    output_dir: Path,
    config_path: Path | None,
    from_csv: Path | None,
    keyfile: Path | None,
    windows_credential: bool,
    write_back: bool,
):
    """Import KeePass entries into CyberArk Privilege Cloud."""
    # Validate input source
    if not kdbx_file and not from_csv:
        click.echo("Error: Provide a KDBX_FILE argument or --from-csv option.", err=True)
        sys.exit(1)

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
        from keypass_importer.core.config import load_config as _load

        map_cfg = _load(map_file)
        mapping_rules = map_cfg.mapping_rules

    mode = MappingMode(mapping_mode)

    # Validate safe requirement
    if mode == MappingMode.SINGLE and not safe:
        click.echo("Error: --safe is required for single mapping mode.", err=True)
        sys.exit(1)

    # Validate write-back constraints
    if write_back and from_csv:
        click.echo("Warning: --write-back is not supported with --from-csv; ignoring.", err=True)
        write_back = False

    if write_back and dry_run:
        write_back = False

    # Read entries from CSV or KeePass
    kp_db = None
    if from_csv:
        from keypass_importer.io.csv_reader import read_csv_entries

        try:
            entries = read_csv_entries(from_csv)
        except (ValueError, FileNotFoundError) as exc:
            click.echo(f"Error: {exc}", err=True)
            sys.exit(1)
        source_name = from_csv.name
    else:
        password = prompt_password(keyfile, windows_credential)

        if write_back:
            # Open once — use the raw PyKeePass handle for both reading
            # entries and writing back metadata (avoids double decrypt).
            from keypass_importer.keepass.unlock import open_database as _open_db
            from keypass_importer.keepass.reader import _group_path, _custom_fields
            from keypass_importer.core.models import KeePassEntry

            kp_db = _open_db(
                kdbx_file,
                password=password,
                keyfile=keyfile,
                use_windows_credential=windows_credential,
            )
            # Extract entries from the already-open handle
            entries = []
            for raw in kp_db.entries:
                if raw.group and raw.group.name == "Recycle Bin":
                    continue
                username = raw.username or ""
                if not username.strip():
                    continue
                entries.append(
                    KeePassEntry(
                        title=raw.title or "(untitled)",
                        username=username,
                        password=raw.password or "",
                        url=raw.url,
                        group_path=_group_path(raw),
                        notes=raw.notes,
                        custom_fields=_custom_fields(raw),
                    )
                )
        else:
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

        # Clear password from scope as early as possible
        password = None  # noqa: F841
        source_name = kdbx_file.name

    click.echo(f"Found {len(entries)} entries in {source_name}")

    results: list[ImportResult] = []
    output_dir.mkdir(parents=True, exist_ok=True)

    if dry_run:
        click.echo("\n[Dry run] Mapping entries without importing...\n")
        for entry in entries:
            try:
                account = map_entry(
                    entry,
                    mode=mode,
                    safe_name=safe,
                    default_platform=default_platform,
                    mapping_rules=mapping_rules,
                )
                _platform = detect_platform(entry.url)
                _ts = datetime.now(timezone.utc).isoformat()
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
                        detected_platform=_platform,
                        url=entry.url,
                        timestamp=_ts,
                    )
                )
            except Exception as exc:
                results.append(
                    ImportResult(
                        entry_title=entry.title,
                        entry_group=entry.group_path_str,
                        status="failed",
                        error=str(exc),
                        detected_platform=detect_platform(entry.url),
                        url=entry.url,
                        timestamp=datetime.now(timezone.utc).isoformat(),
                    )
                )
    else:
        # Authenticate only for real imports
        token = authenticate(tenant_url, client_id)
        client = CyberArkClient(tenant_url, token.access_token)

        try:
            for entry in tqdm(entries, desc="Importing"):
                try:
                    account = map_entry(
                        entry,
                        mode=mode,
                        safe_name=safe,
                        default_platform=default_platform,
                        mapping_rules=mapping_rules,
                    )

                    _platform = detect_platform(entry.url)
                    _ts = datetime.now(timezone.utc).isoformat()

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
                                detected_platform=_platform,
                                url=entry.url,
                                timestamp=_ts,
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
                            detected_platform=_platform,
                            url=entry.url,
                            timestamp=_ts,
                        )
                    )

                    # Tag the KeePass entry with CyberArk metadata
                    if write_back and kp_db:
                        # Scope lookup by group to avoid ambiguity
                        # with duplicate titles across groups.
                        raw_entry = kp_db.find_entries(
                            title=entry.title, first=True
                        )
                        # Narrow: prefer match in same group
                        if entry.group_path:
                            from keypass_importer.keepass.writer import find_entry as _find
                            scoped = _find(kp_db, entry.title, group_path=entry.group_path)
                            if scoped is not None:
                                raw_entry = scoped

                        if raw_entry:
                            raw_entry.set_custom_property(
                                "cyberark_account_id", account_id
                            )
                            raw_entry.set_custom_property(
                                "cyberark_safe", account.safe_name
                            )
                            raw_entry.set_custom_property(
                                "cyberark_imported_at", _ts
                            )

                except Exception as exc:
                    results.append(
                        ImportResult(
                            entry_title=entry.title,
                            entry_group=entry.group_path_str,
                            status="failed",
                            error=str(exc),
                            detected_platform=detect_platform(entry.url),
                            url=entry.url,
                            timestamp=datetime.now(timezone.utc).isoformat(),
                        )
                    )

        finally:
            client.close()

        # Save write-back metadata to the KeePass database
        if write_back and kp_db:
            from keypass_importer.keepass.writer import save as _save_db

            _save_db(kp_db)
            click.echo("KeePass database updated with CyberArk metadata.")

    # Write reports
    write_results_csv(results, output_dir / "results.csv")
    write_results_csv(results, output_dir / "duplicates.csv", status_filter="duplicate")
    write_results_csv(results, output_dir / "failed.csv", status_filter="failed")

    summary = ImportSummary.from_results(results)
    write_summary(summary)

    if dry_run:
        click.echo("Dry run complete. No changes were made to CyberArk.")
