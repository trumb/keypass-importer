"""KeePass database write operations: create, update, delete entries and groups."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from pykeepass import PyKeePass

logger = logging.getLogger(__name__)


def find_or_create_group(db: PyKeePass, group_path: list[str]) -> object:
    """Navigate or create the group hierarchy.

    If the path is empty, return the root group.  For each segment in
    *group_path*, find an existing child group or create a new one.
    """
    current = db.root_group
    for segment in group_path:
        child = next(
            (g for g in (current.subgroups or []) if g.name == segment),
            None,
        )
        if child is None:
            child = db.add_group(current, segment)
            logger.debug("Created group '%s' under '%s'", segment, current.name)
        current = child
    return current


def add_entry(
    db: PyKeePass,
    group_path: list[str],
    title: str,
    username: str,
    password: str,
    url: str | None = None,
    notes: str | None = None,
    custom_fields: dict[str, str] | None = None,
) -> object:
    """Create a new entry in the specified group.

    The group hierarchy is created automatically if it does not exist.
    """
    group = find_or_create_group(db, group_path)
    entry = db.add_entry(group, title, username, password, url=url, notes=notes)

    if custom_fields:
        for key, value in custom_fields.items():
            entry.set_custom_property(key, value)

    logger.info("Added entry '%s' in group '%s'", title, group.name)
    return entry


def update_entry(db: PyKeePass, entry: object, **changes) -> object:
    """Update fields on an existing pykeepass entry object.

    Supported keyword arguments: ``title``, ``username``, ``password``,
    ``url``, ``notes``, and ``custom_fields`` (a ``dict[str, str]``).
    """
    simple_fields = ("title", "username", "password", "url", "notes")
    for field in simple_fields:
        if field in changes:
            setattr(entry, field, changes[field])

    custom = changes.get("custom_fields")
    if custom:
        for key, value in custom.items():
            entry.set_custom_property(key, value)

    logger.info("Updated entry '%s'", entry.title)
    return entry


def delete_entry(db: PyKeePass, entry: object) -> None:
    """Delete an entry from the database."""
    title = getattr(entry, "title", "<unknown>")
    db.delete_entry(entry)
    logger.info("Deleted entry '%s'", title)


def add_group(db: PyKeePass, parent_path: list[str], name: str) -> object:
    """Create a new child group under the specified parent path.

    Raises ``ValueError`` if the parent group does not exist.
    """
    parent = _find_group(db, parent_path)
    if parent is None:
        raise ValueError(
            f"Parent group not found: {'/'.join(parent_path) or 'root'}"
        )
    group = db.add_group(parent, name)
    logger.info("Added group '%s' under '%s'", name, parent.name)
    return group


def delete_group(
    db: PyKeePass, group_path: list[str], recursive: bool = False
) -> None:
    """Delete the group at *group_path*.

    If *recursive* is ``False`` and the group has entries or subgroups,
    a ``ValueError`` is raised.
    """
    group = _find_group(db, group_path)
    if group is None:
        raise ValueError(f"Group not found: {'/'.join(group_path)}")

    if not recursive:
        has_entries = bool(group.entries)
        has_subgroups = bool(group.subgroups)
        if has_entries or has_subgroups:
            raise ValueError("Group is not empty")

    db.delete_group(group)
    logger.info("Deleted group '%s'", "/".join(group_path))


def save(db: PyKeePass, backup: bool = True) -> None:
    """Persist changes to disk.

    When *backup* is ``True`` (the default), the current ``.kdbx`` file
    is copied to ``.kdbx.bak`` before saving.
    """
    db_path = Path(db.filename)

    if backup:
        bak_path = db_path.with_suffix(db_path.suffix + ".bak")
        shutil.copy2(str(db_path), str(bak_path))
        logger.debug("Backup written to %s", bak_path)

    db.save()
    logger.info("Database saved: %s", db_path.name)


def find_entry(
    db: PyKeePass,
    title: str,
    group_path: list[str] | None = None,
) -> object | None:
    """Find an entry by title, optionally scoped to a group.

    Returns the entry or ``None`` if not found.
    """
    if group_path is not None:
        group = _find_group(db, group_path)
        if group is None:
            return None
        return db.find_entries(title=title, group=group, first=True)

    return db.find_entries(title=title, first=True)


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------

def _find_group(db: PyKeePass, group_path: list[str]) -> object | None:
    """Walk *group_path* starting from the root group.

    Returns the final group or ``None`` if any segment is missing.
    """
    if not group_path:
        return db.root_group

    current = db.root_group
    for segment in group_path:
        child = next(
            (g for g in (current.subgroups or []) if g.name == segment),
            None,
        )
        if child is None:
            return None
        current = child
    return current
