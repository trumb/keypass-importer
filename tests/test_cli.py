"""Tests for CLI commands."""

import csv
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from click.testing import CliRunner
from pykeepass import create_database

from keypass_importer.cli import cli


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def sample_kdbx(tmp_path: Path) -> Path:
    db_path = tmp_path / "test.kdbx"
    kp = create_database(str(db_path), password="testpass")
    group = kp.add_group(kp.root_group, "Servers")
    kp.add_entry(group, "web-server", "admin", "password123")
    kp.save()
    return db_path


class TestValidateCommand:
    def test_validate_success(self, runner, sample_kdbx):
        result = runner.invoke(cli, ["validate", str(sample_kdbx)], input="testpass\n")
        assert result.exit_code == 0
        assert "1" in result.output  # 1 entry found

    def test_validate_bad_password(self, runner, sample_kdbx):
        result = runner.invoke(cli, ["validate", str(sample_kdbx)], input="wrongpass\n")
        assert result.exit_code != 0

    def test_validate_missing_file(self, runner):
        result = runner.invoke(cli, ["validate", "/nonexistent.kdbx"], input="pw\n")
        assert result.exit_code != 0


class TestImportDryRun:
    @patch("keypass_importer.cli.authenticate")
    def test_dry_run_no_api_calls(self, mock_auth, runner, sample_kdbx, tmp_path):
        mock_token = MagicMock()
        mock_token.access_token = "fake_token"
        mock_auth.return_value = mock_token

        result = runner.invoke(
            cli,
            [
                "import",
                str(sample_kdbx),
                "--tenant-url", "https://t.cyberark.cloud",
                "--client-id", "app",
                "--safe", "TestSafe",
                "--dry-run",
                "--output-dir", str(tmp_path),
            ],
            input="testpass\n",
        )
        assert result.exit_code == 0
        assert "dry run" in result.output.lower() or "Dry" in result.output


class TestListSafesCommand:
    @patch("keypass_importer.cli.authenticate")
    @patch("keypass_importer.cli.CyberArkClient")
    def test_list_safes(self, mock_client_cls, mock_auth, runner):
        mock_token = MagicMock()
        mock_token.access_token = "fake_token"
        mock_auth.return_value = mock_token

        mock_client = MagicMock()
        mock_client.list_safes.return_value = ["Safe-A", "Safe-B"]
        mock_client_cls.return_value = mock_client

        result = runner.invoke(
            cli,
            [
                "list-safes",
                "--tenant-url", "https://t.cyberark.cloud",
                "--client-id", "app",
            ],
        )
        assert result.exit_code == 0
        assert "Safe-A" in result.output
        assert "Safe-B" in result.output


class TestExportCommand:
    def test_export_creates_csv(self, runner, sample_kdbx, tmp_path):
        out = tmp_path / "export.csv"
        result = runner.invoke(
            cli,
            ["export", str(sample_kdbx), "--output", str(out)],
            input="testpass\n",
        )
        assert result.exit_code == 0
        assert out.exists()
        assert "Exported 1 entries" in result.output

    def test_export_csv_no_passwords(self, runner, sample_kdbx, tmp_path):
        out = tmp_path / "export.csv"
        runner.invoke(
            cli,
            ["export", str(sample_kdbx), "--output", str(out)],
            input="testpass\n",
        )
        content = out.read_text(encoding="utf-8")
        assert "password123" not in content
        with open(out, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            assert "password" not in reader.fieldnames

    def test_export_bad_password(self, runner, sample_kdbx, tmp_path):
        out = tmp_path / "export.csv"
        result = runner.invoke(
            cli,
            ["export", str(sample_kdbx), "--output", str(out)],
            input="wrong\n",
        )
        assert result.exit_code != 0

    def test_export_no_notes(self, runner, sample_kdbx, tmp_path):
        out = tmp_path / "export.csv"
        result = runner.invoke(
            cli,
            ["export", str(sample_kdbx), "--output", str(out), "--no-notes"],
            input="testpass\n",
        )
        assert result.exit_code == 0
        with open(out, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        for row in rows:
            assert row["notes"] == ""


class TestImportFromCsv:
    @patch("keypass_importer.cli.authenticate")
    def test_import_from_csv_dry_run(self, mock_auth, runner, tmp_path):
        mock_token = MagicMock()
        mock_token.access_token = "fake_token"
        mock_auth.return_value = mock_token

        csv_file = tmp_path / "input.csv"
        csv_file.write_text(
            "title,username,password,url,group\n"
            "Web Server,admin,s3cret,https://web.example.com,Servers/Linux\n",
            encoding="utf-8",
        )

        result = runner.invoke(
            cli,
            [
                "import",
                "--from-csv", str(csv_file),
                "--tenant-url", "https://t.cyberark.cloud",
                "--client-id", "app",
                "--safe", "TestSafe",
                "--dry-run",
                "--output-dir", str(tmp_path),
            ],
        )
        assert result.exit_code == 0
        assert "Found 1 entries" in result.output
        assert "Dry run" in result.output

    def test_import_no_source_fails(self, runner, tmp_path):
        """Neither kdbx_file nor --from-csv produces an error."""
        result = runner.invoke(
            cli,
            [
                "import",
                "--tenant-url", "https://t.cyberark.cloud",
                "--client-id", "app",
                "--safe", "TestSafe",
            ],
        )
        assert result.exit_code != 0
