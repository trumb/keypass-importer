# keypass-importer

A Python CLI tool that imports KeePass (.kdbx) password databases into CyberArk Privilege Cloud. It reads entries from a KeePass database, auto-detects CyberArk platform types, maps entries to safes using flexible mapping modes, and creates accounts via the CyberArk REST API with OAuth2 PKCE authentication.

## Prerequisites

- Python 3.11 or later
- A CyberArk Privilege Cloud tenant
- An OIDC application registered in CyberArk Identity (for OAuth2 PKCE authentication)
- The OIDC app must have `http://localhost:8443/callback` configured as a redirect URI

## Installation

Clone the repository and install in development mode:

```bash
git clone <repo-url>
cd keypass-importer
python -m venv .venv
source .venv/bin/activate   # Linux/macOS
# .venv\Scripts\activate    # Windows
pip install -e ".[dev]"
```

This installs the `keypass-importer` CLI command.

## Quick Start

### Validate a KeePass File

Parse a .kdbx file and display a summary of all entries without connecting to CyberArk:

```bash
keypass-importer validate my-passwords.kdbx
```

You will be prompted for the KeePass master password. Output shows each entry with its group path, title, and username.

To unlock with a key file instead of (or in addition to) a master password:

```bash
keypass-importer validate my-passwords.kdbx --keyfile my-key.keyx
```

To unlock using Windows user account credentials (DPAPI):

```bash
keypass-importer validate my-passwords.kdbx --windows-credential
```

### List Available Safes

Authenticate to CyberArk and list all safes your account can access:

```bash
keypass-importer list-safes \
    --tenant-url https://mycompany.privilegecloud.cyberark.cloud \
    --client-id 01234567-abcd-ef01-2345-6789abcdef01
```

A browser window opens for OAuth2 PKCE authentication. After signing in, available safes are listed.

### Import Entries

Import all KeePass entries into a single CyberArk safe:

```bash
keypass-importer import my-passwords.kdbx \
    --tenant-url https://mycompany.privilegecloud.cyberark.cloud \
    --client-id 01234567-abcd-ef01-2345-6789abcdef01 \
    --safe MySafe \
    --mapping-mode single
```

Use `--dry-run` to preview what would be imported without making changes:

```bash
keypass-importer import my-passwords.kdbx \
    --tenant-url https://mycompany.privilegecloud.cyberark.cloud \
    --client-id 01234567-abcd-ef01-2345-6789abcdef01 \
    --safe MySafe \
    --dry-run
```

### Import from CSV

Import entries from a CSV file instead of a .kdbx file:

```bash
keypass-importer import \
    --from-csv entries.csv \
    --tenant-url https://mycompany.privilegecloud.cyberark.cloud \
    --client-id 01234567-abcd-ef01-2345-6789abcdef01 \
    --safe MySafe
```

### Export Entries to CSV

Dump all KeePass entries to CSV for auditing. Passwords are never included in the export:

```bash
keypass-importer export my-passwords.kdbx -o audit.csv
```

## KeePass Unlock Methods

The tool supports three ways to unlock KeePass .kdbx databases. These can be combined:

| Method | Flag | Description |
|--------|------|-------------|
| Master password | (prompted) | Standard KeePass master password |
| Key file | `--keyfile PATH` | .key or .keyx key file for composite key unlock |
| Windows credential | `--windows-credential` | DPAPI decryption using the Windows user account |

When `--keyfile` or `--windows-credential` is provided, the master password prompt becomes optional (press Enter to skip). You can combine methods for composite key databases:

```bash
# Password + key file
keypass-importer validate db.kdbx --keyfile my-key.keyx

# Key file only (press Enter at password prompt to skip)
keypass-importer validate db.kdbx --keyfile my-key.keyx

# Windows credential only
keypass-importer validate db.kdbx --windows-credential

# All three
keypass-importer validate db.kdbx --keyfile my-key.keyx --windows-credential
```

The `--windows-credential` option reads the encrypted user key from `%APPDATA%\KeePass\ProtectedUserKey.bin` and decrypts it using the Windows DPAPI. This only works on the same Windows user account that created the protected key.

## CLI Reference

### Global Options

```
keypass-importer [--verbose] <command>
```

| Option      | Description                |
|-------------|----------------------------|
| `--verbose` | Enable debug logging       |

### Commands

#### `validate`

```
keypass-importer validate <kdbx-file> [--keyfile PATH] [--windows-credential]
```

Validate a KeePass file can be parsed and display an entry summary. Prompts for the master password unless an alternative unlock method is provided. Does not require CyberArk credentials.

| Option                 | Required | Description                                           |
|------------------------|----------|-------------------------------------------------------|
| `--keyfile`            | No       | Path to a .key/.keyx key file for composite key unlock |
| `--windows-credential` | No       | Use Windows user account (DPAPI) to unlock            |

#### `list-safes`

```
keypass-importer list-safes --tenant-url TEXT --client-id TEXT
```

List available safes in CyberArk. Opens a browser for OAuth2 authentication.

| Option         | Required | Description                          |
|----------------|----------|--------------------------------------|
| `--tenant-url` | Yes      | CyberArk Privilege Cloud tenant URL  |
| `--client-id`  | Yes      | OIDC application client ID           |

#### `export`

```
keypass-importer export <kdbx-file> [OPTIONS]
```

Export KeePass entries to a CSV file for auditing. Passwords are never included in the output. Prompts for the master password unless an alternative unlock method is provided.

| Option                 | Required | Default      | Description                                           |
|------------------------|----------|--------------|-------------------------------------------------------|
| `--output`/`-o`        | No       | `export.csv` | Output CSV file path                                  |
| `--no-notes`           | No       | false        | Exclude the notes column from export                  |
| `--keyfile`            | No       |              | Path to a .key/.keyx key file for composite key unlock |
| `--windows-credential` | No       | false        | Use Windows user account (DPAPI) to unlock            |

The exported CSV contains the columns: `group`, `title`, `username`, `url`, `detected_platform`, `notes`, and `custom_fields`.

#### `import`

```
keypass-importer import [KDBX_FILE] [OPTIONS]
```

Import entries into CyberArk Privilege Cloud from a KeePass .kdbx file or a CSV file. When using a .kdbx file, prompts for the master password. Authenticates via OAuth2 PKCE, maps entries to accounts, creates them in CyberArk, and writes CSV reports. Either a `KDBX_FILE` argument or `--from-csv` must be provided.

| Option               | Required | Default | Description                                       |
|----------------------|----------|---------|---------------------------------------------------|
| `--tenant-url`       | Yes      |         | CyberArk Privilege Cloud tenant URL               |
| `--client-id`        | Yes      |         | OIDC application client ID                        |
| `--safe`             | No       |         | Target safe name (required for single mode)       |
| `--mapping-mode`     | No       | single  | Mapping mode: `single`, `group`, or `config`      |
| `--map-file`         | No       |         | YAML mapping rules file (for config mode)         |
| `--default-platform` | No       |         | Override automatic platform detection             |
| `--dry-run`          | No       | false   | Validate and preview mapping without importing    |
| `--output-dir`       | No       | `.`     | Directory for CSV report output                   |
| `--config`           | No       |         | YAML config file (CLI flags override config)      |
| `--from-csv`         | No       |         | Read entries from a CSV file instead of .kdbx     |
| `--keyfile`          | No       |         | Path to a .key/.keyx key file for composite key   |
| `--windows-credential` | No     | false   | Use Windows user account (DPAPI) to unlock        |

After import, three CSV reports are written to the output directory:

- `results.csv` -- All entries with their import status
- `duplicates.csv` -- Entries that already existed in CyberArk
- `failed.csv` -- Entries that failed to import

Each report row includes: `entry_title`, `entry_group`, `status`, `safe_name`, `account_id`, `detected_platform`, `url`, `timestamp`, and `error` (if applicable). The `detected_platform` column shows the auto-detected CyberArk platform ID, `url` shows the source URL, and `timestamp` records the UTC time of each import attempt.

### CSV Input Format

When using `--from-csv`, the input CSV must contain a header row. The following columns are supported:

| Column     | Required | Description                                                    |
|------------|----------|----------------------------------------------------------------|
| `title`    | Yes      | Entry title (rows without a title default to "(untitled)")     |
| `username` | Yes      | Account username (rows with empty username are skipped)        |
| `password` | Yes      | Account password                                               |
| `url`      | No       | URL for platform auto-detection                                |
| `group`    | No       | Group path, slash-separated (e.g. `Servers/Linux`)             |
| `notes`    | No       | Free-text notes                                                |

Example CSV:

```csv
title,username,password,url,group,notes
Web App Admin,admin,s3cret,https://app.example.com,Internet/WebApps,Production admin
Linux Root,root,hunter2,ssh://10.0.1.5,Servers/Linux,
```

## Configuration

All CLI options can be provided via a YAML configuration file:

```yaml
tenant_url: https://mycompany.privilegecloud.cyberark.cloud
client_id: 01234567-abcd-ef01-2345-6789abcdef01
safe: MySafe
mapping_mode: single
default_platform: WinDesktopApplications
output_dir: ./reports
```

Use with:

```bash
keypass-importer import my-passwords.kdbx --config config.yaml
```

CLI flags take precedence over config file values.

## Mapping Modes

The `--mapping-mode` option controls how KeePass entries are assigned to CyberArk safes.

### single (default)

All entries go into a single safe specified by `--safe`:

```bash
keypass-importer import db.kdbx --safe MySafe --mapping-mode single ...
```

### group

Each KeePass group maps to a safe named after the group path. Group path segments are joined with hyphens. For example, an entry in `Internet/Email` maps to safe `Internet-Email`. Root-level entries use the `--safe` value as a fallback.

```bash
keypass-importer import db.kdbx --safe FallbackSafe --mapping-mode group ...
```

### config

Use a YAML file to define explicit group-to-safe mappings. Entries in groups not covered by any rule fall back to the `--safe` value.

```yaml
tenant_url: https://mycompany.privilegecloud.cyberark.cloud
client_id: 01234567-abcd-ef01-2345-6789abcdef01
mapping_mode: config
safe: DefaultSafe
mapping_rules:
  - group: Internet
    safe: WebAccountsSafe
  - group: Servers/Linux
    safe: LinuxSafe
    platform: UnixSSH
  - group: Databases
    safe: DatabaseSafe
```

```bash
keypass-importer import db.kdbx --map-file mapping.yaml ...
```

Rules match by exact group path or prefix (entries in `Servers/Linux/Production` match the `Servers/Linux` rule). If a rule specifies a `platform`, it overrides auto-detection for matching entries.

## Platform Auto-Detection

The tool automatically detects the CyberArk platform ID from each KeePass entry's URL field. Detection follows this priority:

1. Custom field named `platform` on the KeePass entry (highest priority)
2. `--default-platform` CLI option or config value
3. Platform specified in a matching config-mode mapping rule
4. Auto-detection from URL (lowest priority)

URL-based auto-detection rules:

| URL Pattern                              | CyberArk Platform ID      |
|------------------------------------------|---------------------------|
| Scheme `ssh://` or port 22               | `UnixSSH`                 |
| Port 3306                                | `MySQL`                   |
| Port 5432                                | `PostgreSQL`              |
| Port 1433                                | `MSSql`                   |
| Scheme `rdp://` or port 3389            | `WinServerLocal`          |
| Scheme `http://` or `https://`           | `WinDesktopApplications`  |
| No URL or unrecognized pattern           | `WinDesktopApplications`  |

## Docker

Build the image:

```bash
docker build -t keypass-importer .
```

Run a command (mount a directory containing your .kdbx file):

```bash
docker run -it --rm \
    -v /path/to/data:/data \
    keypass-importer validate /data/my-passwords.kdbx
```

Import with dry run:

```bash
docker run -it --rm \
    -v /path/to/data:/data \
    -p 8443:8443 \
    keypass-importer import /data/my-passwords.kdbx \
        --tenant-url https://mycompany.privilegecloud.cyberark.cloud \
        --client-id 01234567-abcd-ef01-2345-6789abcdef01 \
        --safe MySafe \
        --dry-run \
        --output-dir /data/reports
```

Note: The `import` and `list-safes` commands require OAuth2 PKCE authentication, which opens a browser on the host. When running in Docker, expose port 8443 for the callback and open the authorization URL printed in the logs manually.

## Development

### Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Running Tests

```bash
pytest -v
```

With coverage:

```bash
pytest --cov=keypass_importer --cov-report=term-missing -v
```

### Project Structure

```
keypass-importer/
  src/keypass_importer/
    __init__.py              -- Package version + backward-compat shims
    core/
        models.py            -- Pydantic data models (KeePassEntry, CyberArkAccount, etc.)
        config.py            -- YAML config loading with Pydantic validation
        errors.py            -- Shared exception hierarchy
    keepass/
        reader.py            -- .kdbx file parsing with pykeepass
        unlock.py            -- Composite key builder (password, keyfile, DPAPI)
        _dpapi.py            -- Windows DPAPI decryption for user key unlock
    cyberark/
        auth.py              -- OAuth2 PKCE authentication
        client.py            -- CyberArk REST API client
    io/
        mapper.py            -- Entry-to-account mapping and platform detection
        csv_reader.py        -- CSV file parsing (alternative to .kdbx)
        exporter.py          -- CSV export for auditing (no passwords)
        reporter.py          -- CSV report generation
    cli/
        __init__.py          -- Click group definition
        validate_cmd.py      -- validate command
        safes_cmd.py         -- list-safes command
        export_cmd.py        -- export command
        import_cmd.py        -- import command
    sync/                    -- Reserved for bidirectional sync (future)
    service/                 -- Reserved for service layer (future)
  tests/                     -- Test suite (185 tests, 100% coverage)
  Dockerfile                 -- Multi-stage container build
  pyproject.toml             -- Build configuration and dependencies
```

## License

See LICENSE file for details.
