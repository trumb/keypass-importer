"""Tests for CLI helpers module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from keypass_importer.cli.helpers import prompt_password


class TestPromptPassword:
    @patch("keypass_importer.cli.helpers.click.prompt", return_value="secret")
    def test_required_password_no_alternatives(self, mock_prompt):
        result = prompt_password(keyfile=None, windows_credential=False)
        assert result == "secret"
        mock_prompt.assert_called_once_with("KeePass master password", hide_input=True)

    @patch("keypass_importer.cli.helpers.click.prompt", return_value="mypass")
    def test_optional_with_keyfile(self, mock_prompt):
        result = prompt_password(keyfile=Path("key.keyx"), windows_credential=False)
        assert result == "mypass"
        mock_prompt.assert_called_once_with(
            "KeePass master password (press Enter to skip)",
            hide_input=True,
            default="",
            show_default=False,
        )

    @patch("keypass_importer.cli.helpers.click.prompt", return_value="")
    def test_optional_skipped_returns_none(self, mock_prompt):
        result = prompt_password(keyfile=Path("key.keyx"), windows_credential=False)
        assert result is None

    @patch("keypass_importer.cli.helpers.click.prompt", return_value="pw")
    def test_optional_with_windows_credential(self, mock_prompt):
        result = prompt_password(keyfile=None, windows_credential=True)
        assert result == "pw"

    @patch("keypass_importer.cli.helpers.click.prompt", return_value="")
    def test_optional_both_alternatives_skipped(self, mock_prompt):
        result = prompt_password(keyfile=Path("k"), windows_credential=True)
        assert result is None
