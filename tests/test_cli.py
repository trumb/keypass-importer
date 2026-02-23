"""Tests for CLI commands."""

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
