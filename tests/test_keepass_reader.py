"""Tests for KeePass .kdbx reader."""

import pytest
from pathlib import Path
from pykeepass import create_database

from keypass_importer.keepass_reader import read_keepass
from keypass_importer.models import KeePassEntry


@pytest.fixture
def sample_kdbx(tmp_path: Path) -> Path:
    """Create a sample .kdbx file with test entries."""
    db_path = tmp_path / "test.kdbx"
    kp = create_database(str(db_path), password="testpass")

    # Create groups
    infra = kp.add_group(kp.root_group, "Infrastructure")
    linux = kp.add_group(infra, "Linux")
    web = kp.add_group(kp.root_group, "Web")

    # Add entries
    entry1 = kp.add_entry(linux, "prod-server", "admin", "s3cret")
    entry1.url = "ssh://10.0.0.1:22"
    entry1.notes = "Production box"

    entry2 = kp.add_entry(linux, "db-server", "root", "dbpass")
    entry2.url = "10.0.0.2:5432"

    entry3 = kp.add_entry(web, "company-site", "webadmin", "webpass")
    entry3.url = "https://admin.example.com"

    # Entry with custom field
    entry4 = kp.add_entry(kp.root_group, "custom-entry", "user", "pass")
    entry4.set_custom_property("platform", "MySQL")
    entry4.set_custom_property("Database", "mydb")

    kp.save()
    return db_path


@pytest.fixture
def empty_kdbx(tmp_path: Path) -> Path:
    """Create an empty .kdbx file."""
    db_path = tmp_path / "empty.kdbx"
    kp = create_database(str(db_path), password="testpass")
    kp.save()
    return db_path


class TestReadKeepass:
    def test_reads_all_entries(self, sample_kdbx: Path):
        entries = read_keepass(sample_kdbx, password="testpass")
        assert len(entries) == 4

    def test_entry_fields(self, sample_kdbx: Path):
        entries = read_keepass(sample_kdbx, password="testpass")
        prod = next(e for e in entries if e.title == "prod-server")
        assert prod.username == "admin"
        assert prod.password == "s3cret"
        assert prod.url == "ssh://10.0.0.1:22"
        assert prod.notes == "Production box"

    def test_group_hierarchy(self, sample_kdbx: Path):
        entries = read_keepass(sample_kdbx, password="testpass")
        prod = next(e for e in entries if e.title == "prod-server")
        assert prod.group_path == ["Infrastructure", "Linux"]

        web = next(e for e in entries if e.title == "company-site")
        assert web.group_path == ["Web"]

    def test_custom_fields(self, sample_kdbx: Path):
        entries = read_keepass(sample_kdbx, password="testpass")
        custom = next(e for e in entries if e.title == "custom-entry")
        assert custom.custom_fields["platform"] == "MySQL"
        assert custom.custom_fields["Database"] == "mydb"

    def test_root_entry_group_path(self, sample_kdbx: Path):
        entries = read_keepass(sample_kdbx, password="testpass")
        custom = next(e for e in entries if e.title == "custom-entry")
        assert custom.group_path == []

    def test_empty_database(self, empty_kdbx: Path):
        entries = read_keepass(empty_kdbx, password="testpass")
        assert entries == []

    def test_wrong_password_raises(self, sample_kdbx: Path):
        with pytest.raises(ValueError, match="[Ff]ailed to open|[Ii]nvalid"):
            read_keepass(sample_kdbx, password="wrongpass")

    def test_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            read_keepass(Path("/nonexistent/db.kdbx"), password="x")

    def test_returns_keepass_entry_models(self, sample_kdbx: Path):
        entries = read_keepass(sample_kdbx, password="testpass")
        for entry in entries:
            assert isinstance(entry, KeePassEntry)

    def test_skips_entries_without_username(self, tmp_path: Path):
        """Entries with no username are skipped (can't create CyberArk account)."""
        db_path = tmp_path / "nousername.kdbx"
        kp = create_database(str(db_path), password="testpass")
        kp.add_entry(kp.root_group, "has-user", "admin", "pw")
        entry_no_user = kp.add_entry(kp.root_group, "no-user", "", "pw", force_creation=True)
        kp.save()

        entries = read_keepass(db_path, password="testpass")
        titles = [e.title for e in entries]
        assert "has-user" in titles
        assert "no-user" not in titles

    def test_skips_recycle_bin(self, tmp_path: Path):
        """Line 49-50: Entries in the 'Recycle Bin' group are skipped."""
        db_path = tmp_path / "recyclebin.kdbx"
        kp = create_database(str(db_path), password="testpass")

        # Create a Recycle Bin group with an entry
        recycle_bin = kp.add_group(kp.root_group, "Recycle Bin")
        kp.add_entry(recycle_bin, "deleted-entry", "trashed_user", "pw")

        # Create a normal entry
        kp.add_entry(kp.root_group, "normal-entry", "good_user", "pw")

        kp.save()

        entries = read_keepass(db_path, password="testpass")
        titles = [e.title for e in entries]
        assert "normal-entry" in titles
        assert "deleted-entry" not in titles
