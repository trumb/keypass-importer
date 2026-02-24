"""Tests for CLI entry add/edit/delete commands."""

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


class TestEntryAdd:
    def test_add_creates_entry(self, runner, sample_kdbx):
        result = runner.invoke(
            cli,
            [
                "entry", "add", str(sample_kdbx),
                "--title", "NewEntry",
                "--username", "newuser",
                "--password", "newpw",
            ],
            input="testpass\n",
        )
        assert result.exit_code == 0
        assert "Added entry 'NewEntry'" in result.output

        kp = _reopen(sample_kdbx)
        found = kp.find_entries(title="NewEntry", first=True)
        assert found is not None
        assert found.username == "newuser"

    def test_add_with_group(self, runner, sample_kdbx):
        result = runner.invoke(
            cli,
            [
                "entry", "add", str(sample_kdbx),
                "--title", "LinuxBox",
                "--username", "root",
                "--password", "toor",
                "--group", "Servers/Linux",
            ],
            input="testpass\n",
        )
        assert result.exit_code == 0
        kp = _reopen(sample_kdbx)
        found = kp.find_entries(title="LinuxBox", first=True)
        assert found is not None
        assert found.group.name == "Linux"

    def test_add_with_url_and_notes(self, runner, sample_kdbx):
        result = runner.invoke(
            cli,
            [
                "entry", "add", str(sample_kdbx),
                "--title", "WebApp",
                "--username", "admin",
                "--password", "s3cret",
                "--url", "https://app.example.com",
                "--notes", "Production server",
            ],
            input="testpass\n",
        )
        assert result.exit_code == 0
        kp = _reopen(sample_kdbx)
        found = kp.find_entries(title="WebApp", first=True)
        assert found.url == "https://app.example.com"
        assert found.notes == "Production server"

    def test_add_bad_password(self, runner, sample_kdbx):
        result = runner.invoke(
            cli,
            [
                "entry", "add", str(sample_kdbx),
                "--title", "E",
                "--username", "u",
                "--password", "p",
            ],
            input="wrong\n",
        )
        assert result.exit_code != 0


class TestEntryEdit:
    def test_edit_modifies_entry(self, runner, sample_kdbx):
        result = runner.invoke(
            cli,
            [
                "entry", "edit", str(sample_kdbx),
                "--title", "web-server",
                "--new-title", "web-server-v2",
                "--username", "root",
            ],
            input="testpass\n",
        )
        assert result.exit_code == 0
        assert "Updated entry" in result.output

        kp = _reopen(sample_kdbx)
        found = kp.find_entries(title="web-server-v2", first=True)
        assert found is not None
        assert found.username == "root"

    def test_edit_not_found(self, runner, sample_kdbx):
        result = runner.invoke(
            cli,
            [
                "entry", "edit", str(sample_kdbx),
                "--title", "nonexistent",
                "--new-title", "new",
            ],
            input="testpass\n",
        )
        assert result.exit_code != 0
        assert "not found" in result.output

    def test_edit_no_changes(self, runner, sample_kdbx):
        result = runner.invoke(
            cli,
            [
                "entry", "edit", str(sample_kdbx),
                "--title", "web-server",
            ],
            input="testpass\n",
        )
        assert result.exit_code == 0
        assert "No changes" in result.output

    def test_edit_with_group_scope(self, runner, sample_kdbx):
        result = runner.invoke(
            cli,
            [
                "entry", "edit", str(sample_kdbx),
                "--title", "web-server",
                "--group", "Servers",
                "--password", "newpw",
            ],
            input="testpass\n",
        )
        assert result.exit_code == 0
        kp = _reopen(sample_kdbx)
        found = kp.find_entries(title="web-server", first=True)
        assert found.password == "newpw"

    def test_edit_bad_password(self, runner, sample_kdbx):
        result = runner.invoke(
            cli,
            [
                "entry", "edit", str(sample_kdbx),
                "--title", "web-server",
                "--new-title", "X",
            ],
            input="wrong\n",
        )
        assert result.exit_code != 0


class TestEntryDelete:
    def test_delete_removes_entry(self, runner, sample_kdbx):
        result = runner.invoke(
            cli,
            [
                "entry", "delete", str(sample_kdbx),
                "--title", "web-server",
            ],
            input="testpass\n",
        )
        assert result.exit_code == 0
        assert "Deleted entry" in result.output

        kp = _reopen(sample_kdbx)
        found = kp.find_entries(title="web-server", first=True)
        assert found is None

    def test_delete_not_found(self, runner, sample_kdbx):
        result = runner.invoke(
            cli,
            [
                "entry", "delete", str(sample_kdbx),
                "--title", "ghost",
            ],
            input="testpass\n",
        )
        assert result.exit_code != 0
        assert "not found" in result.output

    def test_delete_with_group_scope(self, runner, sample_kdbx):
        result = runner.invoke(
            cli,
            [
                "entry", "delete", str(sample_kdbx),
                "--title", "web-server",
                "--group", "Servers",
            ],
            input="testpass\n",
        )
        assert result.exit_code == 0
        kp = _reopen(sample_kdbx)
        found = kp.find_entries(title="web-server", first=True)
        assert found is None

    def test_delete_bad_password(self, runner, sample_kdbx):
        result = runner.invoke(
            cli,
            [
                "entry", "delete", str(sample_kdbx),
                "--title", "web-server",
            ],
            input="wrong\n",
        )
        assert result.exit_code != 0
