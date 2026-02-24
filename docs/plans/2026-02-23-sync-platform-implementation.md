# KeePass Sync Platform Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Evolve keypass-importer from a one-shot importer into a bidirectional sync platform with full KeePass CRUD, multiple unlock methods (key file, DPAPI, composite), configurable conflict resolution, and a service/watch mode -- while preserving all existing functionality.

**Architecture:** Layered sub-packages (Approach B). Move existing flat modules into domain-organized sub-packages (`core/`, `keepass/`, `cyberark/`, `io/`, `cli/`, `sync/`, `service/`). Top-level `__init__.py` re-exports maintain backward compatibility. Each tier builds on the previous. TDD throughout.

**Tech Stack:** Python 3.11+, pykeepass, Click, httpx, Pydantic, PyYAML, ctypes (DPAPI), watchdog (Tier 4)

**MVP Definition:** Opening a KeePass file (all unlock methods), reading entries, exporting to CSV or CyberArk, duplicate detection. Everything beyond this is extra.

---

## Phase 0: Sub-package Refactor (No Behavior Changes)

Move existing flat modules into the layered sub-package structure. Zero behavior changes. All 132 existing tests must pass after each task.

### Task 0.1: Create Sub-package Directories and __init__.py Files

**Files:**
- Create: `src/keypass_importer/core/__init__.py`
- Create: `src/keypass_importer/keepass/__init__.py`
- Create: `src/keypass_importer/cyberark/__init__.py`
- Create: `src/keypass_importer/io/__init__.py`
- Create: `src/keypass_importer/cli/__init__.py`
- Create: `src/keypass_importer/sync/__init__.py`
- Create: `src/keypass_importer/service/__init__.py`

**Step 1: Create all sub-package directories with empty __init__.py**

```bash
mkdir -p src/keypass_importer/core
mkdir -p src/keypass_importer/keepass
mkdir -p src/keypass_importer/cyberark
mkdir -p src/keypass_importer/io
mkdir -p src/keypass_importer/cli
mkdir -p src/keypass_importer/sync
mkdir -p src/keypass_importer/service
```

Create each `__init__.py` as empty files for now (they get populated when modules move in).

**Step 2: Run tests to verify nothing is broken**

```bash
.venv/Scripts/python.exe -m pytest --cov=keypass_importer --cov-report=term-missing -v
```

Expected: 132 passed, 100% coverage (unchanged)

**Step 3: Commit**

```bash
git add -A
git commit -m "chore: create sub-package directory structure for Approach B refactor"
```

### Task 0.2: Move Core Modules (models.py, config.py) + Add errors.py

**Files:**
- Move: `src/keypass_importer/models.py` -> `src/keypass_importer/core/models.py`
- Move: `src/keypass_importer/config.py` -> `src/keypass_importer/core/config.py`
- Create: `src/keypass_importer/core/errors.py`
- Modify: `src/keypass_importer/core/__init__.py` (re-exports)
- Modify: `src/keypass_importer/__init__.py` (backward-compat re-exports)

**Step 1: Create `core/errors.py` with shared exception hierarchy**

```python
"""Shared exception hierarchy for keypass-importer."""

from __future__ import annotations


class KeyPassImporterError(Exception):
    """Base exception for all keypass-importer errors."""


class DatabaseError(KeyPassImporterError):
    """Error opening or reading a KeePass database."""


class AuthenticationError(KeyPassImporterError):
    """Error during CyberArk authentication."""


class ApiError(KeyPassImporterError):
    """Error communicating with CyberArk REST API."""


class ConfigError(KeyPassImporterError):
    """Error loading or validating configuration."""


class SyncError(KeyPassImporterError):
    """Error during bidirectional sync."""
```

**Step 2: Move `models.py` and `config.py` to `core/`**

```bash
git mv src/keypass_importer/models.py src/keypass_importer/core/models.py
git mv src/keypass_importer/config.py src/keypass_importer/core/config.py
```

**Step 3: Update `core/__init__.py` with re-exports**

```python
"""Core domain models, configuration, and error types."""

from keypass_importer.core.config import AppConfig, MappingRule, load_config
from keypass_importer.core.errors import (
    ApiError,
    AuthenticationError,
    ConfigError,
    DatabaseError,
    KeyPassImporterError,
    SyncError,
)
from keypass_importer.core.models import (
    CyberArkAccount,
    ImportResult,
    ImportSummary,
    KeePassEntry,
    MappingMode,
)

__all__ = [
    "AppConfig",
    "MappingRule",
    "load_config",
    "ApiError",
    "AuthenticationError",
    "ConfigError",
    "DatabaseError",
    "KeyPassImporterError",
    "SyncError",
    "CyberArkAccount",
    "ImportResult",
    "ImportSummary",
    "KeePassEntry",
    "MappingMode",
]
```

**Step 4: Add backward-compat re-exports to `src/keypass_importer/__init__.py`**

Keep the existing `__version__` and add:

```python
"""KeePass to CyberArk Privilege Cloud importer."""

__version__ = "0.1.0"

# Backward-compatible re-exports so existing imports still work.
# e.g. `from keypass_importer.models import KeePassEntry` still resolves.
from keypass_importer.core import models as models  # noqa: F401
from keypass_importer.core import config as config  # noqa: F401
```

**Step 5: Update all internal imports across source files that reference `models` or `config`**

Files to update (search-and-replace the import path):
- `src/keypass_importer/keepass_reader.py`: `from keypass_importer.models import` -> `from keypass_importer.core.models import`
- `src/keypass_importer/csv_reader.py`: same
- `src/keypass_importer/mapper.py`: both `models` and `config` imports
- `src/keypass_importer/cyberark_client.py`: `from keypass_importer.models import`
- `src/keypass_importer/reporter.py`: `from keypass_importer.models import`
- `src/keypass_importer/exporter.py`: `from keypass_importer.models import` and `from keypass_importer.mapper import`
- `src/keypass_importer/cli.py`: `from keypass_importer.config import` and `from keypass_importer.models import`

Note: Test files use `from keypass_importer.models import ...` etc. -- the backward-compat shims in `__init__.py` handle these. Do NOT update test imports yet.

**Step 6: Run tests**

```bash
.venv/Scripts/python.exe -m pytest --cov=keypass_importer --cov-report=term-missing -v
```

Expected: 132 passed. Coverage may shift slightly (new `errors.py` uncovered) -- that is fine, we add error tests later.

**Step 7: Commit**

```bash
git add -A
git commit -m "refactor(core): move models and config into core/ sub-package"
```

### Task 0.3: Move KeePass Module (keepass_reader.py)

**Files:**
- Move: `src/keypass_importer/keepass_reader.py` -> `src/keypass_importer/keepass/reader.py`
- Modify: `src/keypass_importer/keepass/__init__.py` (re-exports)
- Modify: `src/keypass_importer/__init__.py` (backward-compat shim)
- Modify: `src/keypass_importer/cli.py` (update import)

**Step 1: Move file**

```bash
git mv src/keypass_importer/keepass_reader.py src/keypass_importer/keepass/reader.py
```

**Step 2: Update `reader.py` internal import**

Change: `from keypass_importer.models import KeePassEntry`
To: `from keypass_importer.core.models import KeePassEntry`

**Step 3: Update `keepass/__init__.py`**

```python
"""KeePass database operations: read, write, unlock."""

from keypass_importer.keepass.reader import read_keepass

__all__ = ["read_keepass"]
```

**Step 4: Add backward-compat shim to `__init__.py`**

Add: `from keypass_importer.keepass import reader as keepass_reader  # noqa: F401`

**Step 5: Update `cli.py` import**

Change: `from keypass_importer.keepass_reader import read_keepass`
To: `from keypass_importer.keepass.reader import read_keepass`

**Step 6: Run tests, expect 132 passed**

**Step 7: Commit**

```bash
git add -A
git commit -m "refactor(keepass): move reader into keepass/ sub-package"
```

### Task 0.4: Move CyberArk Modules (cyberark_auth.py, cyberark_client.py)

**Files:**
- Move: `src/keypass_importer/cyberark_auth.py` -> `src/keypass_importer/cyberark/auth.py`
- Move: `src/keypass_importer/cyberark_client.py` -> `src/keypass_importer/cyberark/client.py`
- Modify: `src/keypass_importer/cyberark/__init__.py` (re-exports)
- Modify: `src/keypass_importer/__init__.py` (backward-compat shims)
- Modify: `src/keypass_importer/cli.py` (update imports)

**Step 1: Move files**

```bash
git mv src/keypass_importer/cyberark_auth.py src/keypass_importer/cyberark/auth.py
git mv src/keypass_importer/cyberark_client.py src/keypass_importer/cyberark/client.py
```

**Step 2: Update `client.py` internal import**

Change: `from keypass_importer.models import CyberArkAccount`
To: `from keypass_importer.core.models import CyberArkAccount`

**Step 3: Update `cyberark/__init__.py`**

```python
"""CyberArk authentication and REST API client."""

from keypass_importer.cyberark.auth import (
    PKCECallbackServer,
    TokenResponse,
    authenticate,
    build_authorize_url,
    exchange_code_for_token,
    generate_pkce_pair,
)
from keypass_importer.cyberark.client import CyberArkClient

__all__ = [
    "PKCECallbackServer",
    "TokenResponse",
    "authenticate",
    "build_authorize_url",
    "exchange_code_for_token",
    "generate_pkce_pair",
    "CyberArkClient",
]
```

**Step 4: Add backward-compat shims to `__init__.py`**

```python
from keypass_importer.cyberark import auth as cyberark_auth  # noqa: F401
from keypass_importer.cyberark import client as cyberark_client  # noqa: F401
```

**Step 5: Update `cli.py` imports**

Change:
```python
from keypass_importer.cyberark_auth import authenticate
from keypass_importer.cyberark_client import CyberArkClient
```
To:
```python
from keypass_importer.cyberark.auth import authenticate
from keypass_importer.cyberark.client import CyberArkClient
```

**Step 6: Run tests, expect 132 passed**

**Step 7: Commit**

```bash
git add -A
git commit -m "refactor(cyberark): move auth and client into cyberark/ sub-package"
```

### Task 0.5: Move IO Modules (mapper.py, csv_reader.py, exporter.py, reporter.py)

**Files:**
- Move: `src/keypass_importer/mapper.py` -> `src/keypass_importer/io/mapper.py`
- Move: `src/keypass_importer/csv_reader.py` -> `src/keypass_importer/io/csv_reader.py`
- Move: `src/keypass_importer/exporter.py` -> `src/keypass_importer/io/exporter.py`
- Move: `src/keypass_importer/reporter.py` -> `src/keypass_importer/io/reporter.py`
- Modify: `src/keypass_importer/io/__init__.py` (re-exports)
- Modify: `src/keypass_importer/__init__.py` (backward-compat shims)
- Modify: `src/keypass_importer/cli.py` (update imports)

**Step 1: Move files**

```bash
git mv src/keypass_importer/mapper.py src/keypass_importer/io/mapper.py
git mv src/keypass_importer/csv_reader.py src/keypass_importer/io/csv_reader.py
git mv src/keypass_importer/exporter.py src/keypass_importer/io/exporter.py
git mv src/keypass_importer/reporter.py src/keypass_importer/io/reporter.py
```

**Step 2: Update internal imports in moved files**

`io/mapper.py`:
- `from keypass_importer.config import MappingRule` -> `from keypass_importer.core.config import MappingRule`
- `from keypass_importer.models import ...` -> `from keypass_importer.core.models import ...`

`io/csv_reader.py`:
- `from keypass_importer.models import KeePassEntry` -> `from keypass_importer.core.models import KeePassEntry`

`io/exporter.py`:
- `from keypass_importer.mapper import detect_platform` -> `from keypass_importer.io.mapper import detect_platform`
- `from keypass_importer.models import KeePassEntry` -> `from keypass_importer.core.models import KeePassEntry`

`io/reporter.py`:
- `from keypass_importer.models import ...` -> `from keypass_importer.core.models import ...`

**Step 3: Update `io/__init__.py`**

```python
"""Input/output: mapping, CSV reading, exporting, and reporting."""

from keypass_importer.io.csv_reader import read_csv_entries
from keypass_importer.io.exporter import export_entries_csv
from keypass_importer.io.mapper import (
    detect_platform,
    map_entries,
    map_entry,
)
from keypass_importer.io.reporter import write_results_csv, write_summary

__all__ = [
    "read_csv_entries",
    "export_entries_csv",
    "detect_platform",
    "map_entries",
    "map_entry",
    "write_results_csv",
    "write_summary",
]
```

**Step 4: Add backward-compat shims to `__init__.py`**

```python
from keypass_importer.io import mapper as mapper  # noqa: F401
from keypass_importer.io import csv_reader as csv_reader  # noqa: F401
from keypass_importer.io import exporter as exporter  # noqa: F401
from keypass_importer.io import reporter as reporter  # noqa: F401
```

**Step 5: Update `cli.py` imports**

Change:
```python
from keypass_importer.config import load_config
from keypass_importer.mapper import detect_platform, map_entry
from keypass_importer.models import ImportResult, ImportSummary, MappingMode
from keypass_importer.reporter import write_results_csv, write_summary
```
To:
```python
from keypass_importer.core.config import load_config
from keypass_importer.core.models import ImportResult, ImportSummary, MappingMode
from keypass_importer.io.mapper import detect_platform, map_entry
from keypass_importer.io.reporter import write_results_csv, write_summary
```

Also update the lazy import inside `import_cmd`:
```python
# Line 85 in export command:
from keypass_importer.exporter import export_entries_csv
```
To:
```python
from keypass_importer.io.exporter import export_entries_csv
```

And:
```python
# Line 163 in import command:
from keypass_importer.config import load_config as _load
```
To:
```python
from keypass_importer.core.config import load_config as _load
```

And:
```python
# Line 177 in import command:
from keypass_importer.csv_reader import read_csv_entries
```
To:
```python
from keypass_importer.io.csv_reader import read_csv_entries
```

**Step 6: Run tests, expect 132 passed**

**Step 7: Commit**

```bash
git add -A
git commit -m "refactor(io): move mapper, csv_reader, exporter, reporter into io/ sub-package"
```

### Task 0.6: Move CLI Into cli/ Sub-package

**Files:**
- Move/split: `src/keypass_importer/cli.py` -> split into multiple files under `src/keypass_importer/cli/`
- Modify: `src/keypass_importer/cli/__init__.py` (Click group + command registration)
- Modify: `pyproject.toml` (update entry point)

**Step 1: Split cli.py into separate command files**

Create `src/keypass_importer/cli/__init__.py`:
```python
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


# Register commands -- import triggers decorator registration
from keypass_importer.cli.validate_cmd import validate  # noqa: E402, F401
from keypass_importer.cli.safes_cmd import list_safes  # noqa: E402, F401
from keypass_importer.cli.export_cmd import export  # noqa: E402, F401
from keypass_importer.cli.import_cmd import import_cmd  # noqa: E402, F401
```

Create `src/keypass_importer/cli/validate_cmd.py`:
```python
"""Validate command -- show KeePass entry summary."""

from __future__ import annotations

import sys
from pathlib import Path

import click

from keypass_importer.cli import cli
from keypass_importer.keepass.reader import read_keepass


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
```

Create `src/keypass_importer/cli/safes_cmd.py`:
```python
"""List-safes command -- enumerate CyberArk safes."""

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
```

Create `src/keypass_importer/cli/export_cmd.py`:
```python
"""Export command -- dump KeePass entries to CSV."""

from __future__ import annotations

import sys
from pathlib import Path

import click

from keypass_importer.cli import cli
from keypass_importer.keepass.reader import read_keepass


@cli.command()
@click.argument("kdbx_file", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    default="export.csv",
    help="Output CSV path.",
)
@click.option("--no-notes", is_flag=True, help="Exclude notes from export.")
def export(kdbx_file: Path, output: Path, no_notes: bool):
    """Export KeePass entries to CSV for auditing (no passwords)."""
    password = click.prompt("KeePass master password", hide_input=True)
    try:
        entries = read_keepass(kdbx_file, password=password)
    except (ValueError, FileNotFoundError) as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    from keypass_importer.io.exporter import export_entries_csv

    count = export_entries_csv(entries, output, include_notes=not no_notes)
    click.echo(f"Exported {count} entries to {output}")
```

Create `src/keypass_importer/cli/import_cmd.py` -- this is the largest file, containing the full import command logic from the current `cli.py` lines 91-318. Copy the exact current implementation with updated imports:
- `from keypass_importer.cli import cli`
- `from keypass_importer.core.config import load_config`
- `from keypass_importer.core.models import ImportResult, ImportSummary, MappingMode`
- `from keypass_importer.cyberark.auth import authenticate`
- `from keypass_importer.cyberark.client import CyberArkClient`
- `from keypass_importer.keepass.reader import read_keepass`
- `from keypass_importer.io.mapper import detect_platform, map_entry`
- `from keypass_importer.io.reporter import write_results_csv, write_summary`
- Lazy imports inside the function: `from keypass_importer.io.csv_reader import read_csv_entries` and `from keypass_importer.core.config import load_config as _load`

**Step 2: Delete old `src/keypass_importer/cli.py`**

```bash
git rm src/keypass_importer/cli.py
```

**Step 3: Update `pyproject.toml` entry point**

Change: `keypass-importer = "keypass_importer.cli:cli"`
To: `keypass-importer = "keypass_importer.cli:cli"`

(Same path -- the `cli` package's `__init__.py` exports `cli`. No change needed.)

**Step 4: Update backward-compat shim in `__init__.py`**

Remove any old `cli` import. The entry point already targets `keypass_importer.cli:cli` which resolves to the package.

**Step 5: Update ALL test files that patch cli functions**

Tests currently patch paths like `keypass_importer.cli.authenticate`, `keypass_importer.cli.read_keepass`, `keypass_importer.cli.CyberArkClient`, etc. These must be updated to the new module paths:

- `keypass_importer.cli.authenticate` -> `keypass_importer.cli.import_cmd.authenticate`
- `keypass_importer.cli.CyberArkClient` -> `keypass_importer.cli.import_cmd.CyberArkClient`
- `keypass_importer.cli.read_keepass` in import tests -> `keypass_importer.cli.import_cmd.read_keepass`
- `keypass_importer.cli.read_keepass` in validate tests -> `keypass_importer.cli.validate_cmd.read_keepass`
- `keypass_importer.cli.read_keepass` in export tests -> `keypass_importer.cli.export_cmd.read_keepass`
- `keypass_importer.cli.load_config` -> `keypass_importer.cli.import_cmd.load_config`

Each command file imports its own dependencies, so patches must target the command file where the name is looked up.

**Step 6: Run tests, expect 132 passed**

**Step 7: Commit**

```bash
git add -A
git commit -m "refactor(cli): split CLI into per-command modules under cli/ sub-package"
```

### Task 0.7: Clean Up Old Files and Verify Final State

**Step 1: Verify no old module files remain at top level**

The only files that should remain directly under `src/keypass_importer/` are:
- `__init__.py` (with backward-compat re-exports)

All other `.py` files should be in sub-packages. Verify:

```bash
ls src/keypass_importer/*.py
```

Expected: only `__init__.py`

**Step 2: Run full test suite with coverage**

```bash
.venv/Scripts/python.exe -m pytest --cov=keypass_importer --cov-report=term-missing -v
```

Expected: 132 passed, high coverage (errors.py may be uncovered -- that is acceptable, it gets covered in Tier 1 tests)

**Step 3: Add tests for core/errors.py**

Create `tests/test_errors.py`:
```python
"""Tests for shared exception hierarchy."""

from keypass_importer.core.errors import (
    ApiError,
    AuthenticationError,
    ConfigError,
    DatabaseError,
    KeyPassImporterError,
    SyncError,
)


class TestExceptionHierarchy:
    def test_base_is_exception(self):
        assert issubclass(KeyPassImporterError, Exception)

    def test_database_error_inherits_base(self):
        assert issubclass(DatabaseError, KeyPassImporterError)

    def test_auth_error_inherits_base(self):
        assert issubclass(AuthenticationError, KeyPassImporterError)

    def test_api_error_inherits_base(self):
        assert issubclass(ApiError, KeyPassImporterError)

    def test_config_error_inherits_base(self):
        assert issubclass(ConfigError, KeyPassImporterError)

    def test_sync_error_inherits_base(self):
        assert issubclass(SyncError, KeyPassImporterError)

    def test_can_catch_all_with_base(self):
        for cls in (DatabaseError, AuthenticationError, ApiError, ConfigError, SyncError):
            try:
                raise cls("test")
            except KeyPassImporterError:
                pass  # All caught by base
```

**Step 4: Run tests, expect 133+ passed, 100% coverage**

**Step 5: Commit**

```bash
git add -A
git commit -m "refactor: complete sub-package migration, add error hierarchy tests"
```

---

## Phase 1: MVP -- Unlock Methods (Tier 1)

### Task 1.1: Create unlock.py with Key File Support

**Files:**
- Create: `src/keypass_importer/keepass/unlock.py`
- Create: `tests/test_unlock.py`

**Step 1: Write failing tests for `open_database()`**

```python
"""Tests for KeePass database unlock module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from keypass_importer.keepass.unlock import open_database


class TestOpenDatabasePasswordOnly:
    @patch("keypass_importer.keepass.unlock.PyKeePass")
    def test_opens_with_password(self, mock_kp):
        mock_kp.return_value = MagicMock()
        db = open_database(Path("test.kdbx"), password="secret")
        mock_kp.assert_called_once_with(
            str(Path("test.kdbx")), password="secret", keyfile=None, transformed_key=None
        )
        assert db is mock_kp.return_value

    def test_missing_file_raises(self):
        with pytest.raises(FileNotFoundError, match="not found"):
            open_database(Path("/nonexistent/test.kdbx"), password="x")

    @patch("keypass_importer.keepass.unlock.PyKeePass")
    def test_bad_credentials_raises(self, mock_kp):
        from pykeepass.exceptions import CredentialsError
        mock_kp.side_effect = CredentialsError()
        with pytest.raises(ValueError, match="Failed to open"):
            open_database(Path("test.kdbx"), password="wrong")


class TestOpenDatabaseKeyFile:
    @patch("keypass_importer.keepass.unlock.PyKeePass")
    def test_opens_with_keyfile_only(self, mock_kp):
        mock_kp.return_value = MagicMock()
        db = open_database(Path("test.kdbx"), keyfile=Path("key.keyx"))
        mock_kp.assert_called_once_with(
            str(Path("test.kdbx")), password=None, keyfile=str(Path("key.keyx")),
            transformed_key=None
        )

    @patch("keypass_importer.keepass.unlock.PyKeePass")
    def test_opens_with_password_and_keyfile(self, mock_kp):
        mock_kp.return_value = MagicMock()
        db = open_database(Path("test.kdbx"), password="pw", keyfile=Path("key.keyx"))
        mock_kp.assert_called_once_with(
            str(Path("test.kdbx")), password="pw", keyfile=str(Path("key.keyx")),
            transformed_key=None
        )

    def test_keyfile_not_found_raises(self):
        with pytest.raises(FileNotFoundError, match="Key file not found"):
            open_database(Path("test.kdbx"), keyfile=Path("/no/such/key.keyx"))


class TestOpenDatabaseNoCredentials:
    def test_no_credentials_raises(self):
        with pytest.raises(ValueError, match="At least one"):
            open_database(Path("test.kdbx"))
```

**Step 2: Run tests to verify they fail**

```bash
.venv/Scripts/python.exe -m pytest tests/test_unlock.py -v
```

Expected: FAIL (module not found)

**Step 3: Implement `unlock.py`**

```python
"""Composite key builder for KeePass database unlock."""

from __future__ import annotations

import logging
from pathlib import Path

from pykeepass import PyKeePass
from pykeepass.exceptions import CredentialsError

logger = logging.getLogger(__name__)


def open_database(
    path: Path,
    password: str | None = None,
    keyfile: Path | None = None,
    use_windows_credential: bool = False,
) -> PyKeePass:
    """Open a KeePass .kdbx database with the given credentials.

    Supports: password-only, keyfile-only, password+keyfile,
    DPAPI (use_windows_credential), and any combination.

    Returns a PyKeePass instance for reading or writing entries.
    """
    if not path.exists():
        raise FileNotFoundError(f"KeePass file not found: {path}")

    if keyfile and not keyfile.exists():
        raise FileNotFoundError(f"Key file not found: {keyfile}")

    transformed_key: bytes | None = None

    if use_windows_credential:
        from keypass_importer.keepass._dpapi import dpapi_decrypt_user_key

        transformed_key = dpapi_decrypt_user_key()
        logger.info("Using Windows credential (DPAPI) for unlock")

    if not password and not keyfile and not use_windows_credential:
        raise ValueError(
            "At least one credential required: password, keyfile, or windows-credential"
        )

    keyfile_str = str(keyfile) if keyfile else None

    try:
        kp = PyKeePass(
            str(path),
            password=password,
            keyfile=keyfile_str,
            transformed_key=transformed_key,
        )
    except CredentialsError as exc:
        raise ValueError(f"Failed to open KeePass database: {exc}") from exc

    logger.info("Opened database: %s", path.name)
    return kp
```

**Step 4: Run tests to verify they pass**

```bash
.venv/Scripts/python.exe -m pytest tests/test_unlock.py -v
```

Expected: All pass

**Step 5: Commit**

```bash
git add -A
git commit -m "feat(keepass): add unlock module with key file support"
```

### Task 1.2: Add DPAPI Support (_dpapi.py)

**Files:**
- Create: `src/keypass_importer/keepass/_dpapi.py`
- Create: `tests/test_dpapi.py`

**Step 1: Write failing tests**

```python
"""Tests for Windows DPAPI user key decryption."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# Skip entire module on non-Windows
pytestmark = pytest.mark.skipif(
    sys.platform != "win32", reason="DPAPI only available on Windows"
)


class TestDpapiDecrypt:
    @patch("keypass_importer.keepass._dpapi._get_user_key_path")
    @patch("keypass_importer.keepass._dpapi._crypt_unprotect_data")
    def test_decrypts_user_key(self, mock_decrypt, mock_path):
        from keypass_importer.keepass._dpapi import dpapi_decrypt_user_key

        mock_path.return_value = Path("fake/ProtectedUserKey.bin")
        # Simulate reading the file and decrypting
        fake_encrypted = b"\x01\x02\x03\x04"
        mock_decrypt.return_value = b"\xaa\xbb\xcc\xdd" * 8  # 32 bytes

        with patch("builtins.open", create=True) as mock_open:
            mock_open.return_value.__enter__ = lambda s: s
            mock_open.return_value.__exit__ = MagicMock(return_value=False)
            mock_open.return_value.read = MagicMock(return_value=fake_encrypted)

            result = dpapi_decrypt_user_key()
            assert isinstance(result, bytes)
            assert len(result) == 32

    @patch("keypass_importer.keepass._dpapi._get_user_key_path")
    def test_missing_key_file_raises(self, mock_path):
        from keypass_importer.keepass._dpapi import dpapi_decrypt_user_key

        mock_path.return_value = Path("/nonexistent/ProtectedUserKey.bin")
        with pytest.raises(FileNotFoundError, match="ProtectedUserKey.bin"):
            dpapi_decrypt_user_key()


class TestDpapiAvailability:
    def test_import_succeeds_on_windows(self):
        """Module should import without error on Windows."""
        from keypass_importer.keepass import _dpapi  # noqa: F401
```

**Step 2: Run tests to verify they fail**

**Step 3: Implement `_dpapi.py`**

```python
"""Windows DPAPI decryption for KeePass user key.

KeePass 2.x stores a protected user key at:
    %APPDATA%/KeePass/ProtectedUserKey.bin

This module decrypts it using CryptUnprotectData via ctypes.
Only works on Windows, only on the same user account that created the key.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


class _DataBlob(ctypes.Structure):
    """DPAPI DATA_BLOB structure."""

    _fields_ = [
        ("cbData", ctypes.wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_ubyte)),
    ]


def _get_user_key_path() -> Path:
    """Return the path to the KeePass ProtectedUserKey.bin file."""
    appdata = os.environ.get("APPDATA", "")
    return Path(appdata) / "KeePass" / "ProtectedUserKey.bin"


def _crypt_unprotect_data(encrypted: bytes) -> bytes:
    """Decrypt data using Windows DPAPI CryptUnprotectData."""
    crypt32 = ctypes.windll.crypt32  # type: ignore[attr-defined]

    blob_in = _DataBlob()
    blob_in.cbData = len(encrypted)
    blob_in.pbData = ctypes.cast(
        ctypes.create_string_buffer(encrypted, len(encrypted)),
        ctypes.POINTER(ctypes.c_ubyte),
    )

    blob_out = _DataBlob()

    success = crypt32.CryptUnprotectData(
        ctypes.byref(blob_in),
        None,   # description
        None,   # optional entropy
        None,   # reserved
        None,   # prompt struct
        0,      # flags
        ctypes.byref(blob_out),
    )

    if not success:
        raise OSError("CryptUnprotectData failed (wrong user account?)")

    result = ctypes.string_at(blob_out.pbData, blob_out.cbData)

    # Free the output buffer allocated by Windows
    ctypes.windll.kernel32.LocalFree(blob_out.pbData)  # type: ignore[attr-defined]

    return result


def dpapi_decrypt_user_key() -> bytes:
    """Decrypt the KeePass ProtectedUserKey.bin file using DPAPI.

    Returns the raw 32-byte transformed key that can be passed to
    PyKeePass(transformed_key=...).

    Raises FileNotFoundError if the key file does not exist.
    Raises OSError if decryption fails (wrong user account).
    """
    key_path = _get_user_key_path()
    if not key_path.exists():
        raise FileNotFoundError(
            f"KeePass ProtectedUserKey.bin not found at {key_path}. "
            "Ensure KeePass is configured with Windows user account protection."
        )

    logger.info("Reading protected user key from %s", key_path)
    encrypted = key_path.read_bytes()

    decrypted = _crypt_unprotect_data(encrypted)
    logger.info("Successfully decrypted user key (%d bytes)", len(decrypted))

    return decrypted
```

**Step 4: Run tests**

```bash
.venv/Scripts/python.exe -m pytest tests/test_dpapi.py -v
```

Expected: Pass on Windows, skip on Linux/macOS

**Step 5: Commit**

```bash
git add -A
git commit -m "feat(keepass): add DPAPI decryption for Windows user key unlock"
```

### Task 1.3: Update Reader to Use unlock.py

**Files:**
- Modify: `src/keypass_importer/keepass/reader.py`
- Modify: `tests/test_keepass_reader.py` (add keyfile/DPAPI reader tests)

**Step 1: Refactor `read_keepass()` to delegate to `open_database()`**

Update `reader.py` to accept `keyfile` and `use_windows_credential` parameters and delegate database opening to `unlock.open_database()`:

```python
def read_keepass(
    path: Path,
    password: str | None = None,
    keyfile: Path | None = None,
    use_windows_credential: bool = False,
) -> list[KeePassEntry]:
    """Open a .kdbx file and return all usable entries."""
    from keypass_importer.keepass.unlock import open_database

    kp = open_database(
        path,
        password=password,
        keyfile=keyfile,
        use_windows_credential=use_windows_credential,
    )
    # ... rest of the entry extraction logic stays the same
```

Remove the direct `PyKeePass` import and the try/except `CredentialsError` block from `read_keepass` -- `open_database` handles that now.

**Step 2: Add reader tests for keyfile param forwarding**

```python
class TestReadKeepassKeyFile:
    @patch("keypass_importer.keepass.reader.open_database")
    def test_forwards_keyfile(self, mock_open):
        mock_kp = MagicMock()
        mock_kp.entries = []
        mock_open.return_value = mock_kp

        read_keepass(Path("test.kdbx"), password="pw", keyfile=Path("key.keyx"))
        mock_open.assert_called_once_with(
            Path("test.kdbx"), password="pw",
            keyfile=Path("key.keyx"), use_windows_credential=False
        )

    @patch("keypass_importer.keepass.reader.open_database")
    def test_forwards_windows_credential(self, mock_open):
        mock_kp = MagicMock()
        mock_kp.entries = []
        mock_open.return_value = mock_kp

        read_keepass(Path("test.kdbx"), use_windows_credential=True)
        mock_open.assert_called_once_with(
            Path("test.kdbx"), password=None,
            keyfile=None, use_windows_credential=True
        )
```

**Step 3: Run full test suite -- all existing tests must still pass**

```bash
.venv/Scripts/python.exe -m pytest --cov=keypass_importer --cov-report=term-missing -v
```

**Step 4: Commit**

```bash
git add -A
git commit -m "feat(keepass): wire reader to use unlock module for all credential types"
```

### Task 1.4: Add --keyfile and --windows-credential CLI Options

**Files:**
- Modify: `src/keypass_importer/cli/validate_cmd.py`
- Modify: `src/keypass_importer/cli/export_cmd.py`
- Modify: `src/keypass_importer/cli/import_cmd.py`
- Modify: `src/keypass_importer/cli/safes_cmd.py` (no KeePass access, skip)
- Modify: all relevant test files for CLI commands

**Step 1: Add options to validate command**

```python
@cli.command()
@click.argument("kdbx_file", type=click.Path(exists=True, path_type=Path))
@click.option("--keyfile", type=click.Path(exists=True, path_type=Path), default=None,
              help="Path to .key/.keyx file.")
@click.option("--windows-credential", is_flag=True, default=False,
              help="Use Windows user account (DPAPI) to unlock.")
def validate(kdbx_file: Path, keyfile: Path | None, windows_credential: bool):
    """Validate a KeePass file and show entry summary."""
    password = None
    if not windows_credential or keyfile:
        # Prompt for password unless Windows credential is the sole method
        password = click.prompt("KeePass master password", hide_input=True, default="",
                                show_default=False)
        password = password or None

    try:
        entries = read_keepass(
            kdbx_file, password=password, keyfile=keyfile,
            use_windows_credential=windows_credential
        )
    except (ValueError, FileNotFoundError) as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)
    # ... rest unchanged
```

Apply the same pattern to `export_cmd.py` and `import_cmd.py`. The import command already has a more complex flow (CSV vs kdbx) -- add the options only to the kdbx path.

**Step 2: Update CLI tests to exercise new options**

Add tests that pass `--keyfile` and `--windows-credential` flags and verify they get forwarded to `read_keepass`.

**Step 3: Run full test suite**

**Step 4: Commit**

```bash
git add -A
git commit -m "feat(cli): add --keyfile and --windows-credential options to all commands"
```

### Task 1.5: Phase 1 Integration Test and Coverage

**Step 1: Run full test suite with coverage**

```bash
.venv/Scripts/python.exe -m pytest --cov=keypass_importer --cov-report=term-missing -v
```

**Step 2: Identify and close any coverage gaps per standing orders**

Write targeted tests for any uncovered lines. Mark genuinely unreachable code with `# pragma: no cover`.

**Step 3: Commit coverage fixes**

```bash
git add -A
git commit -m "test: close coverage gaps after Tier 1 unlock methods"
```

---

## Phase 2: KeePass Writer and CRUD (Tier 2)

### Task 2.1: Create writer.py with add_entry and save

**Files:**
- Create: `src/keypass_importer/keepass/writer.py`
- Create: `tests/test_writer.py`

TDD: Write tests for `add_entry()`, `update_entry()`, `delete_entry()`, `add_group()`, `delete_group()`, `save()`. Each function gets its own test class.

Key behaviors:
- `save(db, backup=True)` creates `.kdbx.bak` before saving
- `add_entry()` validates that target group exists
- `delete_group(recursive=False)` raises if group has children
- All operations work on in-memory pykeepass databases (create with `PyKeePass.create()`)

### Task 2.2: Add Entry CRUD CLI Commands

**Files:**
- Create: `src/keypass_importer/cli/entry_cmd.py`
- Create: `src/keypass_importer/cli/group_cmd.py`
- Modify: `src/keypass_importer/cli/__init__.py` (register new commands)

Commands:
- `keypass-importer entry add <kdbx> --title --username --password [--url] [--group] [--keyfile] [--windows-credential]`
- `keypass-importer entry edit <kdbx> --title <existing> [--new-title] [--username] [--password] [--url]`
- `keypass-importer entry delete <kdbx> --title <existing> [--group]`
- `keypass-importer group add <kdbx> --name <name> [--parent <path>]`
- `keypass-importer group delete <kdbx> --name <path> [--recursive]`

### Task 2.3: Add --write-back Flag to Import Command

**Files:**
- Modify: `src/keypass_importer/cli/import_cmd.py`
- Modify: tests

After CyberArk account creation, if `--write-back` is set, update each KeePass entry with custom fields: `cyberark_account_id`, `cyberark_safe`, `cyberark_imported_at`.

### Task 2.4: Phase 2 Coverage and Tests

Close all coverage gaps. Target: 100%.

---

## Phase 3: Sync Engine (Tier 3)

### Task 3.1: Sync State Tracking

**Files:**
- Create: `src/keypass_importer/sync/state.py`
- Create: `tests/test_sync_state.py`

Manages `.keypass-sync-state.json`: maps sync IDs to last-known content hashes.

### Task 3.2: Conflict Resolution

**Files:**
- Create: `src/keypass_importer/sync/conflict.py`
- Create: `tests/test_conflict.py`

Four strategies: `keepass-wins`, `cyberark-wins`, `newest-wins`, `prompt`.

### Task 3.3: Sync Engine Orchestrator

**Files:**
- Create: `src/keypass_importer/sync/engine.py`
- Create: `tests/test_sync_engine.py`

Core diff-and-apply logic. Mocked KeePass + CyberArk sides in tests.

### Task 3.4: CSV Mirror Fallback

**Files:**
- Create: `src/keypass_importer/sync/csv_mirror.py`
- Create: `tests/test_csv_mirror.py`

Write pending changes to CSV when CyberArk is unreachable.

### Task 3.5: Sync CLI Command

**Files:**
- Create: `src/keypass_importer/cli/sync_cmd.py`

`keypass-importer sync <kdbx> --tenant-url ... --client-id ... [--conflict-strategy keepass-wins]`

### Task 3.6: Phase 3 Coverage and Tests

---

## Phase 4: Service/Watch Mode (Tier 4)

### Task 4.1: Add watchdog Dependency

Add `watchdog>=4.0.0` to `pyproject.toml` dependencies.

### Task 4.2: File Watcher

**Files:**
- Create: `src/keypass_importer/keepass/watcher.py`
- Create: `tests/test_watcher.py`

### Task 4.3: Poller

**Files:**
- Create: `src/keypass_importer/service/poller.py`
- Create: `tests/test_poller.py`

### Task 4.4: Daemon Lifecycle

**Files:**
- Create: `src/keypass_importer/service/daemon.py`
- Create: `tests/test_daemon.py`

### Task 4.5: Service CLI Commands

**Files:**
- Create: `src/keypass_importer/cli/service_cmd.py`

`keypass-importer service watch|poll [--interval 300]`

### Task 4.6: Phase 4 Coverage and Tests

---

## Phase 5: Documentation and Final Polish

### Task 5.1: Update README.md

Add all new CLI commands, options, and usage examples.

### Task 5.2: Update Config Example

Add `keyfile`, `windows_credential`, `write_back`, `sync`, and `service` sections.

### Task 5.3: Update Dockerfile

Ensure new sub-package structure and any new dependencies are included.

### Task 5.4: Update Status Docs

Per standing orders: CURRENT_STATUS.md, SESSION_LOG.md, wiki if applicable.

### Task 5.5: Final Commit and Push

```bash
git push origin main
```
