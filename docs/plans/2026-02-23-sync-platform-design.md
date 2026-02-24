# KeePass Sync Platform Design

**Date:** 2026-02-23
**Status:** Approved
**Approach:** B -- Layered Sub-packages

## Overview

Evolve keypass-importer from a one-shot importer into a bidirectional sync platform
with full KeePass CRUD, multiple unlock methods, configurable conflict resolution,
and a service/watch mode.

## Priority Tiers

### Tier 1 -- MVP (unlock methods + existing features preserved)

- Key file unlock (`.keyx`/`.key`)
- Windows DPAPI unlock (composite key via `CryptUnprotectData`)
- All unlock combinations: password-only, keyfile-only, password+keyfile,
  DPAPI+password, DPAPI+keyfile, all three
- Existing features preserved: import, validate, export, list-safes, dry-run, CSV input
- Duplicate detection (existing)

### Tier 2 -- Write-back and CRUD

- KeePass writer: create/update/delete entries and groups
- Write-back after import: tag entries with CyberArk account ID, safe, timestamp
- CLI commands: `entry add`, `entry edit`, `entry delete`, `group add`, `group delete`

### Tier 3 -- Sync engine

- Bidirectional sync between KeePass and CyberArk
- Conflict strategies: `keepass-wins`, `cyberark-wins`, `newest-wins`, `prompt`
  (configurable via CLI flag or config file)
- State tracking via sync metadata (custom fields in KeePass, properties in CyberArk)
- Local CSV mirror as offline fallback when CyberArk is unreachable

### Tier 4 -- Service/watch mode

- File watcher (filesystem events via `watchdog`) + CyberArk polling on interval
- Polling-only mode (simpler, more portable)
- One-shot sync (designed for Task Scheduler / cron)
- Daemon lifecycle with graceful shutdown

## Package Structure

```
src/keypass_importer/
    __init__.py              -- re-exports for backward compat
    core/
        __init__.py
        models.py            -- existing models + SyncState, ConflictResult
        config.py            -- existing config + sync/service config sections
        errors.py            -- shared exception hierarchy
    keepass/
        __init__.py
        reader.py            -- existing reader + keyfile/DPAPI params
        writer.py            -- NEW (Tier 2): create/update/delete entries+groups
        unlock.py            -- NEW (Tier 1): composite key builder
        watcher.py           -- NEW (Tier 4): file change detection
    cyberark/
        __init__.py
        auth.py              -- existing OAuth2 PKCE
        client.py            -- existing client + update/delete methods
    sync/
        __init__.py
        engine.py            -- NEW (Tier 3): bidirectional sync orchestrator
        conflict.py          -- NEW (Tier 3): conflict resolution strategies
        state.py             -- NEW (Tier 3): sync state tracking
        csv_mirror.py        -- NEW (Tier 3): local CSV fallback
    io/
        __init__.py
        csv_reader.py        -- existing
        csv_writer.py        -- existing exporter + reporter merged
        mapper.py            -- existing mapper
    cli/
        __init__.py          -- Click group
        import_cmd.py        -- existing import command
        validate_cmd.py      -- existing validate command
        export_cmd.py        -- existing export command
        safes_cmd.py         -- existing list-safes command
        entry_cmd.py         -- NEW (Tier 2): entry CRUD commands
        group_cmd.py         -- NEW (Tier 2): group management
        sync_cmd.py          -- NEW (Tier 3): sync command
        service_cmd.py       -- NEW (Tier 4): watch/daemon commands
    service/
        __init__.py
        daemon.py            -- NEW (Tier 4): long-running service lifecycle
        poller.py            -- NEW (Tier 4): interval-based polling
```

## Unlock Architecture (Tier 1)

```
unlock.py: open_database(path, password=None, keyfile=None, use_windows_credential=False)
    |
    +-- If use_windows_credential:
    |       dpapi_decrypt() -> transformed_key bytes
    |       PyKeePass(path, password=password, keyfile=keyfile,
    |                 transformed_key=transformed_key)
    |
    +-- Else:
            PyKeePass(path, password=password, keyfile=keyfile)
```

### DPAPI Implementation

KeePass 2.x stores a protected user key at:
`%APPDATA%\KeePass\ProtectedUserKey.bin`

Decryption uses Windows `CryptUnprotectData` via `ctypes` calling `crypt32.dll`.
No external dependency required. Only works on the same Windows user account that
created the key.

### CLI Changes (Tier 1)

Every command that prompts for a master password gains two new options:

```
--keyfile PATH           Path to .key/.keyx file
--windows-credential     Use Windows user account (DPAPI)
```

Password prompt becomes conditional: skip if `--windows-credential` is the sole
unlock method. If password is needed, prompt as before.

## Writer Architecture (Tier 2)

```python
# writer.py
add_entry(db, group_path, title, username, password, url=None,
          notes=None, custom_fields=None) -> Entry
update_entry(db, entry, **changes) -> Entry
delete_entry(db, entry) -> None
add_group(db, parent_path, name) -> Group
delete_group(db, group_path, recursive=False) -> None
save(db, backup=True)  # creates .kdbx.bak before saving
```

### Write-back After Import

The import command gains `--write-back` flag. After creating accounts in CyberArk,
it updates each KeePass entry with custom fields:

- `cyberark_account_id` -- CyberArk account identifier
- `cyberark_safe` -- Target safe name
- `cyberark_imported_at` -- ISO 8601 timestamp

## Sync Engine (Tier 3)

### State Tracking

- **KeePass side:** custom field `_sync_id` (UUID) + `_sync_modified` (ISO timestamp)
- **CyberArk side:** platform property `SyncId` + account `lastModifiedTime` from API
- **Local state file:** `.keypass-sync-state.json` mapping sync IDs to last-known hashes

### Sync Flow

1. Open KeePass, authenticate CyberArk
2. Build entry maps from both sides (keyed by sync ID)
3. Diff: new-local, new-remote, modified-local, modified-remote, conflicts, deleted
4. Apply conflict strategy to resolve conflicts
5. Push changes to both sides
6. Update state file
7. If CyberArk unreachable, write changes to CSV mirror instead

### Conflict Strategies

| Strategy | Behavior |
|----------|----------|
| `keepass-wins` | KeePass always wins. New CyberArk-only entries pulled back |
| `cyberark-wins` | CyberArk always wins. New KeePass-only entries pushed |
| `newest-wins` | Last-modified timestamp wins |
| `prompt` | Interactive prompt in CLI; log to conflicts file in service mode |

## Service Mode (Tier 4)

### Execution Modes

```
keypass-importer service watch     # filesystem events + CyberArk polling
keypass-importer service poll      # interval polling only
keypass-importer sync              # one-shot sync (for schedulers)
```

### Config File Extension

```yaml
service:
  mode: watch|poll
  poll_interval_seconds: 300
  on_conflict: keepass-wins|cyberark-wins|newest-wins|prompt
  csv_mirror_path: ./mirror.csv
  log_file: ./keypass-sync.log
```

## Backward Compatibility

- CLI entry point stays `keypass-importer`
- All existing commands and flags unchanged
- `__init__.py` re-exports preserve `from keypass_importer.models import ...` paths
- 132 existing tests validate behavior through the refactor

## New Dependencies

| Dependency | Tier | Purpose |
|------------|------|---------|
| `watchdog` | 4 | Filesystem event monitoring |

No new dependencies for Tiers 1-3. DPAPI uses stdlib `ctypes`. Key file support
is native to `pykeepass`.

## Testing Strategy

- Refactor step: all 132 existing tests must pass with zero behavior changes
- Tier 1: unit tests for unlock combinations, DPAPI mock on non-Windows
- Tier 2: unit tests for CRUD operations with in-memory .kdbx databases
- Tier 3: unit tests for sync engine with mocked KeePass + CyberArk sides
- Tier 4: unit tests for polling logic, integration tests for watcher
- Coverage target: 100% on all new code
