"""Tests for CLI group add/delete commands."""

from __future__ import annotations

import pytest
from pathlib import Path
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
    parent = kp.add_group(kp.root_group, "Servers")
    kp.add_group(parent, "Linux")
    kp.save()
    return db_path


def _reopen(path: Path) -> PyKeePass:
    return PyKeePass(str(path), password="testpass")


class TestGroupAdd:
    def test_add_creates_group(self, runner, sample_kdbx):
        result = runner.invoke(
            cli,
            [
                "group", "add", str(sample_kdbx),
                "--name", "Databases",
            ],
            input="testpass\n",
        )
        assert result.exit_code == 0
        assert "Added group 'Databases'" in result.output

        kp = _reopen(sample_kdbx)
        names = [g.name for g in kp.root_group.subgroups]
        assert "Databases" in names

    def test_add_nested_group(self, runner, sample_kdbx):
        result = runner.invoke(
            cli,
            [
                "group", "add", str(sample_kdbx),
                "--name", "Web",
                "--parent", "Servers/Linux",
            ],
            input="testpass\n",
        )
        assert result.exit_code == 0

        kp = _reopen(sample_kdbx)
        # Navigate to Servers -> Linux -> Web
        servers = next(g for g in kp.root_group.subgroups if g.name == "Servers")
        linux = next(g for g in servers.subgroups if g.name == "Linux")
        names = [g.name for g in linux.subgroups]
        assert "Web" in names

    def test_add_parent_not_found(self, runner, sample_kdbx):
        result = runner.invoke(
            cli,
            [
                "group", "add", str(sample_kdbx),
                "--name", "Orphan",
                "--parent", "NonExistent",
            ],
            input="testpass\n",
        )
        assert result.exit_code != 0
        assert "Parent group not found" in result.output

    def test_add_bad_password(self, runner, sample_kdbx):
        result = runner.invoke(
            cli,
            [
                "group", "add", str(sample_kdbx),
                "--name", "X",
            ],
            input="wrong\n",
        )
        assert result.exit_code != 0


class TestGroupDelete:
    def test_delete_empty_group(self, runner, sample_kdbx):
        # Linux is empty (no entries, no sub-subgroups)
        result = runner.invoke(
            cli,
            [
                "group", "delete", str(sample_kdbx),
                "--name", "Servers/Linux", "--yes",
            ],
            input="testpass\n",
        )
        assert result.exit_code == 0
        assert "Deleted group" in result.output

        kp = _reopen(sample_kdbx)
        servers = next(g for g in kp.root_group.subgroups if g.name == "Servers")
        names = [g.name for g in servers.subgroups]
        assert "Linux" not in names

    def test_delete_non_recursive_with_children_fails(self, runner, tmp_path):
        """Non-recursive delete of a group with subgroups should fail."""
        db_path = tmp_path / "test2.kdbx"
        kp = create_database(str(db_path), password="testpass")
        parent = kp.add_group(kp.root_group, "HasChild")
        kp.add_group(parent, "Child")
        kp.save()

        result = runner.invoke(
            cli,
            [
                "group", "delete", str(db_path),
                "--name", "HasChild", "--yes",
            ],
            input="testpass\n",
        )
        assert result.exit_code != 0
        assert "not empty" in result.output

    def test_delete_recursive(self, runner, sample_kdbx):
        result = runner.invoke(
            cli,
            [
                "group", "delete", str(sample_kdbx),
                "--name", "Servers",
                "--recursive", "--yes",
            ],
            input="testpass\n",
        )
        assert result.exit_code == 0

        kp = _reopen(sample_kdbx)
        names = [g.name for g in kp.root_group.subgroups]
        assert "Servers" not in names

    def test_delete_group_not_found(self, runner, sample_kdbx):
        result = runner.invoke(
            cli,
            [
                "group", "delete", str(sample_kdbx),
                "--name", "Ghost", "--yes",
            ],
            input="testpass\n",
        )
        assert result.exit_code != 0
        assert "Group not found" in result.output

    def test_delete_bad_password(self, runner, sample_kdbx):
        result = runner.invoke(
            cli,
            [
                "group", "delete", str(sample_kdbx),
                "--name", "Servers", "--yes",
            ],
            input="wrong\n",
        )
        assert result.exit_code != 0

    def test_delete_aborted_by_user(self, runner, sample_kdbx):
        """Declining the confirmation prompt aborts without deleting."""
        result = runner.invoke(
            cli,
            [
                "group", "delete", str(sample_kdbx),
                "--name", "Servers/Linux",
            ],
            input="n\n",
        )
        assert result.exit_code == 0
        assert "Aborted" in result.output
        kp = _reopen(sample_kdbx)
        servers = next(g for g in kp.root_group.subgroups if g.name == "Servers")
        names = [g.name for g in servers.subgroups]
        assert "Linux" in names
