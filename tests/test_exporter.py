"""Tests for CSV export functionality (KeePass entries for auditing)."""

import csv
import pytest
from pathlib import Path

from keypass_importer.models import KeePassEntry


@pytest.fixture
def sample_entries() -> list[KeePassEntry]:
    return [
        KeePassEntry(
            title="Web Server",
            username="admin",
            password="s3cret!",
            url="ssh://web01.example.com:22",
            group_path=["Servers", "Linux"],
            notes="Primary web server",
            custom_fields={"env": "production", "region": "us-east-1"},
        ),
        KeePassEntry(
            title="Database",
            username="dbadmin",
            password="dbp@ss",
            url="db.example.com:5432",
            group_path=["Servers", "Databases"],
            notes="PostgreSQL primary",
            custom_fields={},
        ),
        KeePassEntry(
            title="Windows RDP",
            username="administrator",
            password="winP@ss",
            url="rdp://win01.example.com",
            group_path=[],
            notes=None,
            custom_fields={},
        ),
    ]


class TestExportEntriesCsv:
    def test_export_basic(self, tmp_path: Path, sample_entries):
        """Exports entries, verify CSV has correct columns and data."""
        from keypass_importer.exporter import export_entries_csv

        out = tmp_path / "export.csv"
        export_entries_csv(sample_entries, out)

        with open(out, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 3
        assert rows[0]["title"] == "Web Server"
        assert rows[0]["username"] == "admin"
        assert rows[0]["group"] == "Servers/Linux"

    def test_export_no_passwords(self, tmp_path: Path, sample_entries):
        """Verify password field is NEVER in the CSV output."""
        from keypass_importer.exporter import export_entries_csv

        out = tmp_path / "export.csv"
        export_entries_csv(sample_entries, out)

        content = out.read_text(encoding="utf-8")
        # Check that none of the actual password values appear
        assert "s3cret!" not in content
        assert "dbp@ss" not in content
        assert "winP@ss" not in content

        # Check that 'password' is not a CSV column header
        with open(out, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            assert "password" not in reader.fieldnames

    def test_export_with_notes_disabled(self, tmp_path: Path, sample_entries):
        """include_notes=False produces empty notes column."""
        from keypass_importer.exporter import export_entries_csv

        out = tmp_path / "export.csv"
        export_entries_csv(sample_entries, out, include_notes=False)

        with open(out, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        for row in rows:
            assert row["notes"] == ""

    def test_export_empty_entries(self, tmp_path: Path):
        """Empty list creates CSV with just headers."""
        from keypass_importer.exporter import export_entries_csv

        out = tmp_path / "export.csv"
        count = export_entries_csv([], out)

        assert count == 0
        with open(out, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 0
        # Headers should still exist
        assert "title" in reader.fieldnames
        assert "group" in reader.fieldnames

    def test_export_platform_detection(self, tmp_path: Path, sample_entries):
        """Verify detected_platform column has correct values."""
        from keypass_importer.exporter import export_entries_csv

        out = tmp_path / "export.csv"
        export_entries_csv(sample_entries, out)

        with open(out, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        # ssh://web01.example.com:22 -> UnixSSH
        assert rows[0]["detected_platform"] == "UnixSSH"
        # db.example.com:5432 -> PostgreSQL
        assert rows[1]["detected_platform"] == "PostgreSQL"
        # rdp://win01.example.com -> WinServerLocal
        assert rows[2]["detected_platform"] == "WinServerLocal"

    def test_export_custom_fields_formatting(self, tmp_path: Path, sample_entries):
        """Custom fields formatted as 'key=value; key2=value2'."""
        from keypass_importer.exporter import export_entries_csv

        out = tmp_path / "export.csv"
        export_entries_csv(sample_entries, out)

        with open(out, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        # First entry has custom_fields: {"env": "production", "region": "us-east-1"}
        cf = rows[0]["custom_fields"]
        assert "env=production" in cf
        assert "region=us-east-1" in cf

        # Second entry has no custom fields
        assert rows[1]["custom_fields"] == ""

    def test_export_returns_count(self, tmp_path: Path, sample_entries):
        """Verify return value matches entry count."""
        from keypass_importer.exporter import export_entries_csv

        out = tmp_path / "export.csv"
        count = export_entries_csv(sample_entries, out)
        assert count == 3

    def test_export_root_group_label(self, tmp_path: Path):
        """Entry with empty group_path shows '(root)'."""
        from keypass_importer.exporter import export_entries_csv

        entries = [
            KeePassEntry(
                title="Root Entry",
                username="user",
                password="pw",
                group_path=[],
            ),
        ]
        out = tmp_path / "export.csv"
        export_entries_csv(entries, out)

        with open(out, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            row = next(reader)
        assert row["group"] == "(root)"
