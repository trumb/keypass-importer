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
    def test_dry_run_no_api_calls(self, runner, sample_kdbx, tmp_path):
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
    def test_import_from_csv_dry_run(self, runner, tmp_path):
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


class TestConfigPathBranch:
    """Tests for --config loading (lines 152-160)."""

    def test_config_file_populates_options(self, runner, sample_kdbx, tmp_path):
        """A YAML config file fills in safe, mapping_mode, default_platform, and output_dir."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            "tenant_url: https://t.cyberark.cloud\n"
            "client_id: app\n"
            "safe: ConfigSafe\n"
            "mapping_mode: single\n"
            "default_platform: UnixSSH\n"
            "output_dir: " + str(tmp_path / "reports") + "\n",
            encoding="utf-8",
        )

        result = runner.invoke(
            cli,
            [
                "import",
                str(sample_kdbx),
                "--tenant-url", "https://t.cyberark.cloud",
                "--client-id", "app",
                "--config", str(config_file),
                "--dry-run",
            ],
            input="testpass\n",
        )
        assert result.exit_code == 0
        assert "Found 1 entries" in result.output

    def test_config_with_mapping_rules(self, runner, sample_kdbx, tmp_path):
        """Config with mapping_rules is loaded without error."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            "tenant_url: https://t.cyberark.cloud\n"
            "client_id: app\n"
            "safe: MySafe\n"
            "mapping_mode: single\n"
            "mapping_rules:\n"
            "  - group: Servers\n"
            "    safe: ServerSafe\n"
            "    platform: UnixSSH\n",
            encoding="utf-8",
        )

        result = runner.invoke(
            cli,
            [
                "import",
                str(sample_kdbx),
                "--tenant-url", "https://t.cyberark.cloud",
                "--client-id", "app",
                "--config", str(config_file),
                "--dry-run",
            ],
            input="testpass\n",
        )
        assert result.exit_code == 0


class TestMapFileBranch:
    """Tests for --map-file loading (lines 163-166)."""

    def test_map_file_loads_mapping_rules(self, runner, sample_kdbx, tmp_path):
        """--map-file loads mapping_rules from a separate YAML file."""
        map_file = tmp_path / "map.yaml"
        map_file.write_text(
            "tenant_url: https://t.cyberark.cloud\n"
            "client_id: app\n"
            "mapping_rules:\n"
            "  - group: Servers\n"
            "    safe: ServerSafe\n"
            "    platform: UnixSSH\n",
            encoding="utf-8",
        )

        result = runner.invoke(
            cli,
            [
                "import",
                str(sample_kdbx),
                "--tenant-url", "https://t.cyberark.cloud",
                "--client-id", "app",
                "--safe", "TestSafe",
                "--map-file", str(map_file),
                "--dry-run",
                "--output-dir", str(tmp_path),
            ],
            input="testpass\n",
        )
        assert result.exit_code == 0


class TestMissingSafe:
    """Tests for missing --safe in single mode (lines 172-173)."""

    def test_single_mode_without_safe_fails(self, runner, sample_kdbx, tmp_path):
        """Single mapping mode without --safe produces an error."""
        result = runner.invoke(
            cli,
            [
                "import",
                str(sample_kdbx),
                "--tenant-url", "https://t.cyberark.cloud",
                "--client-id", "app",
                "--mapping-mode", "single",
            ],
            input="testpass\n",
        )
        assert result.exit_code != 0
        assert "--safe is required" in result.output or "--safe is required" in (result.output + (result.stderr or ""))


class TestCsvReadError:
    """Tests for CSV read error path (lines 181-183)."""

    def test_import_from_csv_read_error(self, runner, tmp_path):
        """A malformed CSV (missing required columns) produces an error."""
        bad_csv = tmp_path / "bad.csv"
        bad_csv.write_text("col_a,col_b\nval1,val2\n", encoding="utf-8")

        result = runner.invoke(
            cli,
            [
                "import",
                "--from-csv", str(bad_csv),
                "--tenant-url", "https://t.cyberark.cloud",
                "--client-id", "app",
                "--safe", "TestSafe",
            ],
        )
        assert result.exit_code != 0
        assert "Error" in result.output or "error" in result.output.lower()


class TestKdbxReadError:
    """Tests for kdbx read error in the else branch (lines 189-191)."""

    def test_import_kdbx_wrong_password(self, runner, sample_kdbx, tmp_path):
        """A wrong kdbx password triggers the error path."""
        result = runner.invoke(
            cli,
            [
                "import",
                str(sample_kdbx),
                "--tenant-url", "https://t.cyberark.cloud",
                "--client-id", "app",
                "--safe", "TestSafe",
            ],
            input="wrongpass\n",
        )
        assert result.exit_code != 0
        assert "Error" in result.output or "error" in result.output.lower()


class TestRealImportLoop:
    """Tests for the non-dry-run import loop (lines 239-273)."""

    @patch("keypass_importer.cli.CyberArkClient")
    @patch("keypass_importer.cli.authenticate")
    def test_successful_account_creation(self, mock_auth, mock_client_cls, runner, sample_kdbx, tmp_path):
        """Account created successfully when no duplicate exists."""
        mock_token = MagicMock()
        mock_token.access_token = "fake_token"
        mock_auth.return_value = mock_token

        mock_client = MagicMock()
        mock_client.find_existing_account.return_value = None
        mock_client.create_account.return_value = "acct-12345"
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
        mock_client.create_account.assert_called_once()
        mock_client.find_existing_account.assert_called_once()
        # Verify results CSV was written
        assert (tmp_path / "results.csv").exists()

    @patch("keypass_importer.cli.CyberArkClient")
    @patch("keypass_importer.cli.authenticate")
    def test_duplicate_account_detected(self, mock_auth, mock_client_cls, runner, sample_kdbx, tmp_path):
        """Duplicate is detected and skipped without creating."""
        mock_token = MagicMock()
        mock_token.access_token = "fake_token"
        mock_auth.return_value = mock_token

        mock_client = MagicMock()
        mock_client.find_existing_account.return_value = "existing-id-999"
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
        mock_client.find_existing_account.assert_called_once()
        mock_client.create_account.assert_not_called()
        # Verify duplicates CSV was written
        assert (tmp_path / "duplicates.csv").exists()

    @patch("keypass_importer.cli.CyberArkClient")
    @patch("keypass_importer.cli.authenticate")
    def test_import_error_during_create(self, mock_auth, mock_client_cls, runner, sample_kdbx, tmp_path):
        """An exception during create_account results in a 'failed' entry."""
        mock_token = MagicMock()
        mock_token.access_token = "fake_token"
        mock_auth.return_value = mock_token

        mock_client = MagicMock()
        mock_client.find_existing_account.return_value = None
        mock_client.create_account.side_effect = ValueError("API error: 403 Forbidden")
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
        # Verify failed CSV was written
        assert (tmp_path / "failed.csv").exists()

    @patch("keypass_importer.cli.CyberArkClient")
    @patch("keypass_importer.cli.authenticate")
    def test_real_import_from_csv_creates_account(self, mock_auth, mock_client_cls, runner, tmp_path):
        """Non-dry-run import from CSV creates accounts successfully."""
        mock_token = MagicMock()
        mock_token.access_token = "fake_token"
        mock_auth.return_value = mock_token

        mock_client = MagicMock()
        mock_client.find_existing_account.return_value = None
        mock_client.create_account.return_value = "csv-acct-001"
        mock_client_cls.return_value = mock_client

        csv_file = tmp_path / "entries.csv"
        csv_file.write_text(
            "title,username,password,url,group,notes\n"
            "WebApp,admin,s3cret,https://app.example.com,Servers/Web,some notes\n",
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
                "--output-dir", str(tmp_path),
            ],
        )
        assert result.exit_code == 0
        mock_client.create_account.assert_called_once()
        assert (tmp_path / "results.csv").exists()


class TestDryRunErrorPath:
    """Test that dry-run handles mapping errors gracefully."""

    def test_dry_run_mapping_error_produces_failed_result(self, runner, tmp_path):
        """When map_entry raises during dry-run, entry is marked failed."""
        # CSV with a group that won't match any rules + config mode + no fallback safe
        csv_file = tmp_path / "input.csv"
        csv_file.write_text(
            "title,username,password,url,group\n"
            "Server,admin,pw,ssh://10.0.0.1,NoMatch/Group\n",
            encoding="utf-8",
        )
        result = runner.invoke(
            cli,
            [
                "import",
                "--from-csv", str(csv_file),
                "--tenant-url", "https://t.cyberark.cloud",
                "--client-id", "app",
                "--mapping-mode", "config",
                # No --safe fallback and no rules = map_entry will raise
                "--dry-run",
                "--output-dir", str(tmp_path),
            ],
        )
        # Should still exit 0 — errors are captured in results, not fatal
        assert result.exit_code == 0
        assert (tmp_path / "failed.csv").exists()


class TestClientClose:
    """Verify CyberArkClient.close() is exercised."""

    @patch("keypass_importer.cli.CyberArkClient")
    @patch("keypass_importer.cli.authenticate")
    def test_client_close_called(self, mock_auth, mock_client_cls, runner, sample_kdbx, tmp_path):
        mock_token = MagicMock()
        mock_token.access_token = "fake_token"
        mock_auth.return_value = mock_token

        mock_client = MagicMock()
        mock_client.find_existing_account.return_value = None
        mock_client.create_account.return_value = "id-1"
        mock_client_cls.return_value = mock_client

        runner.invoke(
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
        mock_client.close.assert_called_once()
