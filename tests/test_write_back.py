"""Tests for the --write-back flag on the import command."""

from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from click.testing import CliRunner
from pykeepass import create_database, PyKeePass

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


def _reopen(path: Path) -> PyKeePass:
    return PyKeePass(str(path), password="testpass")


class TestWriteBack:
    @patch("keypass_importer.cli.import_cmd.CyberArkClient")
    @patch("keypass_importer.cli.import_cmd.authenticate")
    def test_write_back_sets_custom_fields(
        self, mock_auth, mock_client_cls, runner, sample_kdbx, tmp_path
    ):
        """After successful import with --write-back, custom fields are set."""
        mock_token = MagicMock()
        mock_token.access_token = "fake_token"
        mock_auth.return_value = mock_token

        mock_client = MagicMock()
        mock_client.find_existing_account.return_value = None
        mock_client.create_account.return_value = "acct-42"
        mock_client_cls.return_value = mock_client

        result = runner.invoke(
            cli,
            [
                "import",
                str(sample_kdbx),
                "--tenant-url", "https://t.cyberark.cloud",
                "--client-id", "app",
                "--safe", "TestSafe",
                "--write-back",
                "--output-dir", str(tmp_path),
            ],
            input="testpass\n",
        )
        assert result.exit_code == 0
        assert "KeePass database updated with CyberArk metadata" in result.output

        # Verify the custom properties were actually saved
        kp = _reopen(sample_kdbx)
        entry = kp.find_entries(title="web-server", first=True)
        assert entry is not None
        assert entry.get_custom_property("cyberark_account_id") == "acct-42"
        assert entry.get_custom_property("cyberark_safe") == "TestSafe"
        assert entry.get_custom_property("cyberark_imported_at") is not None

    @patch("keypass_importer.cli.import_cmd.CyberArkClient")
    @patch("keypass_importer.cli.import_cmd.authenticate")
    def test_write_back_creates_bak_file(
        self, mock_auth, mock_client_cls, runner, sample_kdbx, tmp_path
    ):
        """Write-back save creates a .bak file."""
        mock_token = MagicMock()
        mock_token.access_token = "fake_token"
        mock_auth.return_value = mock_token

        mock_client = MagicMock()
        mock_client.find_existing_account.return_value = None
        mock_client.create_account.return_value = "acct-99"
        mock_client_cls.return_value = mock_client

        result = runner.invoke(
            cli,
            [
                "import",
                str(sample_kdbx),
                "--tenant-url", "https://t.cyberark.cloud",
                "--client-id", "app",
                "--safe", "TestSafe",
                "--write-back",
                "--output-dir", str(tmp_path),
            ],
            input="testpass\n",
        )
        assert result.exit_code == 0
        bak = sample_kdbx.with_suffix(".kdbx.bak")
        assert bak.exists()

    def test_write_back_with_from_csv_warns(self, runner, tmp_path):
        """--write-back with --from-csv produces a warning and is ignored."""
        csv_file = tmp_path / "entries.csv"
        csv_file.write_text(
            "title,username,password,url,group\n"
            "Web,admin,pw,https://a.com,Servers\n",
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
                "--write-back",
                "--dry-run",
                "--output-dir", str(tmp_path),
            ],
        )
        assert result.exit_code == 0
        assert "--write-back is not supported with --from-csv" in result.output

    def test_write_back_with_dry_run_is_ignored(self, runner, sample_kdbx, tmp_path):
        """--write-back + --dry-run does not write back."""
        result = runner.invoke(
            cli,
            [
                "import",
                str(sample_kdbx),
                "--tenant-url", "https://t.cyberark.cloud",
                "--client-id", "app",
                "--safe", "TestSafe",
                "--write-back",
                "--dry-run",
                "--output-dir", str(tmp_path),
            ],
            input="testpass\n",
        )
        assert result.exit_code == 0
        # No write-back message should appear
        assert "KeePass database updated" not in result.output
        # No .bak file should be created
        bak = sample_kdbx.with_suffix(".kdbx.bak")
        assert not bak.exists()

    @patch("keypass_importer.cli.import_cmd.CyberArkClient")
    @patch("keypass_importer.cli.import_cmd.authenticate")
    def test_write_back_without_flag_no_metadata(
        self, mock_auth, mock_client_cls, runner, sample_kdbx, tmp_path
    ):
        """Without --write-back, no custom fields are set."""
        mock_token = MagicMock()
        mock_token.access_token = "fake_token"
        mock_auth.return_value = mock_token

        mock_client = MagicMock()
        mock_client.find_existing_account.return_value = None
        mock_client.create_account.return_value = "acct-7"
        mock_client_cls.return_value = mock_client

        result = runner.invoke(
            cli,
            [
                "import",
                str(sample_kdbx),
                "--tenant-url", "https://t.cyberark.cloud",
                "--client-id", "app",
                "--safe", "TestSafe",
                "--output-dir", str(tmp_path),
            ],
            input="testpass\n",
        )
        assert result.exit_code == 0
        assert "KeePass database updated" not in result.output

        kp = _reopen(sample_kdbx)
        entry = kp.find_entries(title="web-server", first=True)
        assert entry.get_custom_property("cyberark_account_id") is None

    @patch("keypass_importer.cli.import_cmd.CyberArkClient")
    @patch("keypass_importer.cli.import_cmd.authenticate")
    def test_write_back_duplicate_not_tagged(
        self, mock_auth, mock_client_cls, runner, sample_kdbx, tmp_path
    ):
        """Duplicate entries are not tagged with write-back metadata."""
        mock_token = MagicMock()
        mock_token.access_token = "fake_token"
        mock_auth.return_value = mock_token

        mock_client = MagicMock()
        mock_client.find_existing_account.return_value = "existing-id"
        mock_client_cls.return_value = mock_client

        result = runner.invoke(
            cli,
            [
                "import",
                str(sample_kdbx),
                "--tenant-url", "https://t.cyberark.cloud",
                "--client-id", "app",
                "--safe", "TestSafe",
                "--write-back",
                "--output-dir", str(tmp_path),
            ],
            input="testpass\n",
        )
        assert result.exit_code == 0

        kp = _reopen(sample_kdbx)
        entry = kp.find_entries(title="web-server", first=True)
        # Duplicate entries don't get tagged
        assert entry.get_custom_property("cyberark_account_id") is None
