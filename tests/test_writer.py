"""Tests for keepass.writer CRUD operations.

Uses real pykeepass databases (not mocks) to verify behaviour.
"""

from __future__ import annotations

import pytest
from pathlib import Path
from pykeepass import create_database

from keypass_importer.keepass.writer import (
    add_entry,
    add_group,
    delete_entry,
    delete_group,
    find_entry,
    find_or_create_group,
    save,
    update_entry,
)


@pytest.fixture
def db(tmp_path: Path):
    """Create a temporary KeePass database for testing."""
    db_path = tmp_path / "test.kdbx"
    kp = create_database(str(db_path), password="testpass")
    kp.save()
    return kp


# ------------------------------------------------------------------
# find_or_create_group
# ------------------------------------------------------------------


class TestFindOrCreateGroup:
    def test_empty_path_returns_root(self, db):
        result = find_or_create_group(db, [])
        assert result.name == db.root_group.name

    def test_creates_single_group(self, db):
        group = find_or_create_group(db, ["Servers"])
        assert group.name == "Servers"
        assert group.parentgroup.name == db.root_group.name

    def test_creates_nested_groups(self, db):
        group = find_or_create_group(db, ["Servers", "Linux", "Web"])
        assert group.name == "Web"
        # Walk back
        assert group.parentgroup.name == "Linux"
        assert group.parentgroup.parentgroup.name == "Servers"

    def test_finds_existing_group(self, db):
        db.add_group(db.root_group, "Existing")
        group = find_or_create_group(db, ["Existing"])
        assert group.name == "Existing"
        # Should not have created a duplicate
        root_children = [g.name for g in db.root_group.subgroups]
        assert root_children.count("Existing") == 1

    def test_partial_path_exists(self, db):
        """First segment exists, second is created."""
        db.add_group(db.root_group, "A")
        group = find_or_create_group(db, ["A", "B"])
        assert group.name == "B"
        assert group.parentgroup.name == "A"


# ------------------------------------------------------------------
# add_entry
# ------------------------------------------------------------------


class TestAddEntry:
    def test_add_to_root(self, db):
        entry = add_entry(db, [], "Root Entry", "user1", "pw1")
        assert entry.title == "Root Entry"
        assert entry.username == "user1"
        assert entry.password == "pw1"
        assert entry.group.name == db.root_group.name

    def test_add_to_nested_group(self, db):
        entry = add_entry(db, ["Servers", "Linux"], "Web Server", "admin", "s3cret")
        assert entry.title == "Web Server"
        assert entry.group.name == "Linux"

    def test_add_with_url_and_notes(self, db):
        entry = add_entry(
            db, [], "Site", "u", "p",
            url="https://example.com",
            notes="Some notes",
        )
        assert entry.url == "https://example.com"
        assert entry.notes == "Some notes"

    def test_add_with_custom_fields(self, db):
        entry = add_entry(
            db, [], "Custom", "u", "p",
            custom_fields={"env": "prod", "region": "us-east-1"},
        )
        assert entry.get_custom_property("env") == "prod"
        assert entry.get_custom_property("region") == "us-east-1"

    def test_add_with_no_custom_fields(self, db):
        entry = add_entry(db, [], "Plain", "u", "p")
        # Should not raise; custom_properties should be empty or None-ish
        assert entry.title == "Plain"

    def test_add_auto_creates_group(self, db):
        """Adding entry to non-existent group auto-creates the group."""
        add_entry(db, ["NewGroup"], "Entry", "u", "p")
        groups = [g.name for g in db.root_group.subgroups]
        assert "NewGroup" in groups


# ------------------------------------------------------------------
# update_entry
# ------------------------------------------------------------------


class TestUpdateEntry:
    def test_update_title(self, db):
        entry = add_entry(db, [], "Old", "u", "p")
        update_entry(db, entry, title="New")
        assert entry.title == "New"

    def test_update_username(self, db):
        entry = add_entry(db, [], "E", "old_user", "p")
        update_entry(db, entry, username="new_user")
        assert entry.username == "new_user"

    def test_update_password(self, db):
        entry = add_entry(db, [], "E", "u", "old_pw")
        update_entry(db, entry, password="new_pw")
        assert entry.password == "new_pw"

    def test_update_url(self, db):
        entry = add_entry(db, [], "E", "u", "p", url="https://old.com")
        update_entry(db, entry, url="https://new.com")
        assert entry.url == "https://new.com"

    def test_update_notes(self, db):
        entry = add_entry(db, [], "E", "u", "p", notes="old")
        update_entry(db, entry, notes="new notes")
        assert entry.notes == "new notes"

    def test_update_custom_fields(self, db):
        entry = add_entry(db, [], "E", "u", "p", custom_fields={"a": "1"})
        update_entry(db, entry, custom_fields={"a": "2", "b": "3"})
        assert entry.get_custom_property("a") == "2"
        assert entry.get_custom_property("b") == "3"

    def test_update_multiple_fields(self, db):
        entry = add_entry(db, [], "E", "u", "p")
        update_entry(db, entry, title="T2", username="u2", password="p2")
        assert entry.title == "T2"
        assert entry.username == "u2"
        assert entry.password == "p2"

    def test_update_returns_entry(self, db):
        entry = add_entry(db, [], "E", "u", "p")
        result = update_entry(db, entry, title="Changed")
        assert result is entry

    def test_update_unknown_field_raises(self, db):
        """Passing an unrecognised keyword raises ValueError."""
        entry = add_entry(db, [], "E", "u", "p")
        with pytest.raises(ValueError, match="Unknown fields"):
            update_entry(db, entry, titl="typo")

    def test_update_unknown_and_valid_fields_raises(self, db):
        """Mixing valid and unknown keywords still raises."""
        entry = add_entry(db, [], "E", "u", "p")
        with pytest.raises(ValueError, match="Unknown fields"):
            update_entry(db, entry, title="ok", bad_field="nope")


# ------------------------------------------------------------------
# delete_entry
# ------------------------------------------------------------------


class TestDeleteEntry:
    def test_delete_entry_removes_it(self, db):
        entry = add_entry(db, [], "ToDelete", "u", "p")
        delete_entry(db, entry)
        assert find_entry(db, "ToDelete") is None

    def test_delete_from_group(self, db):
        entry = add_entry(db, ["G"], "ToDelete", "u", "p")
        delete_entry(db, entry)
        assert find_entry(db, "ToDelete", group_path=["G"]) is None


# ------------------------------------------------------------------
# add_group
# ------------------------------------------------------------------


class TestAddGroup:
    def test_add_to_root(self, db):
        group = add_group(db, [], "NewGroup")
        assert group.name == "NewGroup"
        assert group.parentgroup.name == db.root_group.name

    def test_add_nested(self, db):
        db.add_group(db.root_group, "Parent")
        group = add_group(db, ["Parent"], "Child")
        assert group.name == "Child"
        assert group.parentgroup.name == "Parent"

    def test_parent_not_found_raises(self, db):
        with pytest.raises(ValueError, match="Parent group not found"):
            add_group(db, ["NonExistent"], "Child")


# ------------------------------------------------------------------
# delete_group
# ------------------------------------------------------------------


class TestDeleteGroup:
    def test_delete_empty_group(self, db):
        db.add_group(db.root_group, "Empty")
        delete_group(db, ["Empty"])
        names = [g.name for g in db.root_group.subgroups]
        assert "Empty" not in names

    def test_non_recursive_with_entries_raises(self, db):
        grp = db.add_group(db.root_group, "HasEntries")
        db.add_entry(grp, "E", "u", "p")
        with pytest.raises(ValueError, match="Group is not empty"):
            delete_group(db, ["HasEntries"], recursive=False)

    def test_non_recursive_with_subgroups_raises(self, db):
        parent = db.add_group(db.root_group, "HasSub")
        db.add_group(parent, "Child")
        with pytest.raises(ValueError, match="Group is not empty"):
            delete_group(db, ["HasSub"], recursive=False)

    def test_recursive_deletes_all(self, db):
        parent = db.add_group(db.root_group, "Big")
        child = db.add_group(parent, "Sub")
        db.add_entry(child, "Deep Entry", "u", "p")
        delete_group(db, ["Big"], recursive=True)
        names = [g.name for g in db.root_group.subgroups]
        assert "Big" not in names

    def test_group_not_found_raises(self, db):
        with pytest.raises(ValueError, match="Group not found"):
            delete_group(db, ["Ghost"])


# ------------------------------------------------------------------
# save
# ------------------------------------------------------------------


class TestSave:
    def test_save_to_disk(self, db, tmp_path):
        add_entry(db, [], "Persisted", "u", "p")
        save(db, backup=False)
        # Re-open and verify
        from pykeepass import PyKeePass

        kp2 = PyKeePass(str(tmp_path / "test.kdbx"), password="testpass")
        found = kp2.find_entries(title="Persisted", first=True)
        assert found is not None

    def test_backup_creates_bak_file(self, db, tmp_path):
        save(db, backup=True)
        bak = tmp_path / "test.kdbx.bak"
        assert bak.exists()

    def test_backup_false_no_bak(self, db, tmp_path):
        save(db, backup=False)
        bak = tmp_path / "test.kdbx.bak"
        assert not bak.exists()


# ------------------------------------------------------------------
# find_entry
# ------------------------------------------------------------------


class TestFindEntry:
    def test_find_by_title(self, db):
        add_entry(db, [], "Findable", "u", "p")
        result = find_entry(db, "Findable")
        assert result is not None
        assert result.title == "Findable"

    def test_find_scoped_to_group(self, db):
        add_entry(db, ["A"], "InA", "u", "p")
        add_entry(db, ["B"], "InB", "u", "p")
        assert find_entry(db, "InA", group_path=["A"]) is not None
        assert find_entry(db, "InB", group_path=["A"]) is None

    def test_returns_none_when_not_found(self, db):
        assert find_entry(db, "Nonexistent") is None

    def test_returns_none_when_group_not_found(self, db):
        assert find_entry(db, "X", group_path=["NoSuchGroup"]) is None
