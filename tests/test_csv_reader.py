"""Tests for CSV input reader (alternative to .kdbx)."""

import pytest
from pathlib import Path

from keypass_importer.models import KeePassEntry


def _write_csv(path: Path, content: str) -> Path:
    """Helper to write a CSV file for testing."""
    path.write_text(content.strip() + "\n", encoding="utf-8")
    return path


class TestReadCsvEntries:
    def test_read_csv_basic(self, tmp_path: Path):
        """Read valid CSV, verify entries match."""
        from keypass_importer.csv_reader import read_csv_entries

        csv_file = _write_csv(
            tmp_path / "entries.csv",
            """\
title,username,password,url,group,notes
Web Server,admin,s3cret,https://web.example.com,Servers/Linux,Primary server
Database,dbadmin,dbp@ss,db.example.com:5432,Servers/Databases,PostgreSQL""",
        )

        entries = read_csv_entries(csv_file)
        assert len(entries) == 2
        assert entries[0].title == "Web Server"
        assert entries[0].username == "admin"
        assert entries[0].password == "s3cret"
        assert entries[0].url == "https://web.example.com"
        assert entries[1].title == "Database"

    def test_read_csv_missing_required_columns(self, tmp_path: Path):
        """Raises ValueError when required columns are missing."""
        from keypass_importer.csv_reader import read_csv_entries

        csv_file = _write_csv(
            tmp_path / "bad.csv",
            """\
title,url,notes
Web Server,https://example.com,Notes""",
        )

        with pytest.raises(ValueError, match="missing required columns"):
            read_csv_entries(csv_file)

    def test_read_csv_empty_file(self, tmp_path: Path):
        """Raises ValueError for empty CSV file."""
        from keypass_importer.csv_reader import read_csv_entries

        csv_file = tmp_path / "empty.csv"
        csv_file.write_text("", encoding="utf-8")

        with pytest.raises(ValueError, match="empty"):
            read_csv_entries(csv_file)

    def test_read_csv_file_not_found(self, tmp_path: Path):
        """Raises FileNotFoundError for missing file."""
        from keypass_importer.csv_reader import read_csv_entries

        with pytest.raises(FileNotFoundError, match="not found"):
            read_csv_entries(tmp_path / "nonexistent.csv")

    def test_read_csv_skips_empty_username(self, tmp_path: Path):
        """Rows without username are skipped."""
        from keypass_importer.csv_reader import read_csv_entries

        csv_file = _write_csv(
            tmp_path / "entries.csv",
            """\
title,username,password
Valid Entry,admin,pass1
Missing User,,pass2
Another Valid,user2,pass3""",
        )

        entries = read_csv_entries(csv_file)
        assert len(entries) == 2
        assert entries[0].username == "admin"
        assert entries[1].username == "user2"

    def test_read_csv_group_parsing(self, tmp_path: Path):
        """'Servers/Linux' -> group_path=['Servers', 'Linux']."""
        from keypass_importer.csv_reader import read_csv_entries

        csv_file = _write_csv(
            tmp_path / "entries.csv",
            """\
title,username,password,group
Server A,admin,pw,Servers/Linux
Server B,admin,pw,Servers/Windows/Domain""",
        )

        entries = read_csv_entries(csv_file)
        assert entries[0].group_path == ["Servers", "Linux"]
        assert entries[1].group_path == ["Servers", "Windows", "Domain"]

    def test_read_csv_optional_columns_missing(self, tmp_path: Path):
        """CSV without optional columns still works."""
        from keypass_importer.csv_reader import read_csv_entries

        csv_file = _write_csv(
            tmp_path / "entries.csv",
            """\
title,username,password
Server A,admin,pw123""",
        )

        entries = read_csv_entries(csv_file)
        assert len(entries) == 1
        assert entries[0].url is None
        assert entries[0].notes is None
        assert entries[0].group_path == []

    def test_read_csv_preserves_password(self, tmp_path: Path):
        """Password field is preserved (needed for import)."""
        from keypass_importer.csv_reader import read_csv_entries

        csv_file = _write_csv(
            tmp_path / "entries.csv",
            """\
title,username,password
Entry,user,My$ecretP@ss!""",
        )

        entries = read_csv_entries(csv_file)
        assert entries[0].password == "My$ecretP@ss!"

    def test_read_csv_empty_group(self, tmp_path: Path):
        """Empty group results in empty group_path list."""
        from keypass_importer.csv_reader import read_csv_entries

        csv_file = _write_csv(
            tmp_path / "entries.csv",
            """\
title,username,password,group
Root Entry,admin,pw,""",
        )

        entries = read_csv_entries(csv_file)
        assert entries[0].group_path == []

    def test_read_csv_untitled_entry(self, tmp_path: Path):
        """Entry without title gets '(untitled)' default."""
        from keypass_importer.csv_reader import read_csv_entries

        csv_file = _write_csv(
            tmp_path / "entries.csv",
            """\
title,username,password
,admin,pw""",
        )

        entries = read_csv_entries(csv_file)
        assert entries[0].title == "(untitled)"
