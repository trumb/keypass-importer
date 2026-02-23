# KeePass to CyberArk Privilege Cloud Importer — Design Document

**Date:** 2026-02-23
**Status:** Approved

## Purpose

A Python CLI tool that reads KeePass (.kdbx) password database files and imports the entries into CyberArk Privilege Cloud as managed accounts.

## Architecture

```
┌─────────────┐     ┌──────────────────┐     ┌────────────────────┐
│  KeePass     │     │  Importer CLI    │     │  CyberArk Privilege│
│  .kdbx file  │────>│  (Python)        │────>│  Cloud REST API    │
└─────────────┘     │                  │     └────────────────────┘
                    │  1. Parse KDBX   │              ^
  ┌────────────┐    │  2. Map entries   │     ┌───────┴────────────┐
  │  Config     │──>│  3. Import       │     │  OAuth2 PKCE Flow  │
  │  (YAML)     │    │  4. Report       │     │  (browser + local  │
  └────────────┘    └──────────────────┘     │   callback server)  │
                                              └────────────────────┘
```

### Components

| Module | Responsibility |
|--------|----------------|
| `cli.py` | Click-based CLI with commands: `import`, `validate`, `list-safes` |
| `keepass_reader.py` | Parses .kdbx files using pykeepass, extracts entries with group hierarchy |
| `cyberark_auth.py` | OAuth2 PKCE flow: opens browser, runs local callback server, captures token |
| `cyberark_client.py` | REST API wrapper for CyberArk Privilege Cloud (Safes, Accounts) |
| `mapper.py` | Maps KeePass entries to CyberArk accounts with platform auto-detection |
| `reporter.py` | Generates import summary and duplicates/failed CSVs (no secrets) |
| `config.py` | Loads and validates YAML configuration |

## Authentication

OAuth2 Authorization Code flow with PKCE:

1. CLI prompts for CyberArk tenant URL
2. Generates PKCE code_verifier + code_challenge (SHA256)
3. Starts local HTTP server on `localhost:8443`
4. Opens browser to CyberArk Identity authorization endpoint
5. User logs in (password + MFA)
6. CyberArk redirects to `localhost:8443/callback?code=<auth_code>`
7. CLI exchanges auth_code + code_verifier for access_token
8. Token used in Authorization header for all API calls
9. Token auto-refreshes if it expires during long imports

**Prerequisites:**
- OIDC application registered in CyberArk Identity
- Redirect URI: `http://localhost:8443/callback`
- Client ID provided via config or `--client-id` flag

**Security:**
- Token stored only in memory, never written to disk
- Login timeout: 120 seconds
- KeePass master password prompted via `getpass` (not echoed)

## Mapping Modes

Three modes, selected via `--mapping-mode`:

| Mode | Flag | Behavior |
|------|------|----------|
| Single Safe (default) | `--mapping-mode single --safe <name>` | All entries into one safe |
| Groups to Safes | `--mapping-mode group` | Each KeePass group becomes a CyberArk Safe |
| Config-driven | `--mapping-mode config --map-file rules.yaml` | YAML rules define group-to-safe mappings |

## Platform Auto-Detection

Based on KeePass entry URL and fields:

| Pattern | CyberArk Platform ID |
|---------|---------------------|
| URL contains `ssh://` or port 22 | `UnixSSH` |
| URL contains port 3306 | `MySQL` |
| URL contains port 5432 | `PostgreSQL` |
| URL contains port 1433 | `MSSql` |
| URL contains `rdp://` or port 3389 | `WinServerLocal` |
| URL is HTTP/HTTPS or generic | `WinDesktopApplications` |
| Custom field `platform` set | Use specified value |

Override with `--default-platform <id>`.

## Duplicate Handling

- Before creating each account, query CyberArk for existing accounts matching `(address, userName)`
- If found: skip the entry, log warning, write row to `duplicates.csv`
- `duplicates.csv` columns: `group`, `title`, `username`, `url`, `cyberark_safe`, `cyberark_account_id`
- No secrets are ever written to CSV files
- Import is idempotent: running twice produces the same result

## Error Handling & Reporting

- **Dry-run mode** (`--dry-run`): validates everything without writing to CyberArk
- **Progress bar** via `tqdm` during import
- **Import summary** printed at completion:
  - Total entries found
  - Successfully imported
  - Skipped (duplicates)
  - Failed (with reasons)
- **Failed entries** logged to `failed.csv` with error reason (no secrets)

## CLI Interface

```
keypass-importer import <kdbx-file> [OPTIONS]

Options:
  --tenant-url TEXT        CyberArk Privilege Cloud tenant URL [required]
  --client-id TEXT         OIDC application client ID [required]
  --safe TEXT              Target safe name (for single mode)
  --mapping-mode [single|group|config]  Mapping mode (default: single)
  --map-file PATH          YAML mapping rules file (for config mode)
  --default-platform TEXT  Override platform detection
  --dry-run                Validate without importing
  --output-dir PATH        Directory for report CSVs (default: current dir)
  --config PATH            YAML config file
  --verbose                Enable debug logging

keypass-importer validate <kdbx-file>
  Validate a KeePass file can be parsed and show entry summary.

keypass-importer list-safes
  List available safes in CyberArk (requires auth).
```

## Project Structure

```
keypass-importer/
├── README.md
├── pyproject.toml
├── src/
│   └── keypass_importer/
│       ├── __init__.py
│       ├── cli.py
│       ├── keepass_reader.py
│       ├── cyberark_auth.py
│       ├── cyberark_client.py
│       ├── mapper.py
│       ├── reporter.py
│       └── config.py
├── tests/
│   ├── test_keepass_reader.py
│   ├── test_mapper.py
│   ├── test_cyberark_client.py
│   └── test_reporter.py
├── docs/
│   └── plans/
├── config.example.yaml
├── Dockerfile
└── .gitignore
```

## Dependencies

- `pykeepass` — KeePass .kdbx parsing
- `click` — CLI framework
- `httpx` — HTTP client for CyberArk API
- `pyyaml` — Config file parsing
- `tqdm` — Progress bars
- `pydantic` — Data models and validation

## Decisions

1. **OAuth2 PKCE** over Selenium/manual token — standard, reliable, works with MFA
2. **Python** over Go/TypeScript — best KeePass library support, fastest to build
3. **Click** over argparse — cleaner subcommand support
4. **httpx** over requests — async-capable, modern API
5. **No secrets in reports** — duplicates.csv and failed.csv never contain passwords
