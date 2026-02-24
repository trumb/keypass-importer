"""Tests for KeePass composite key unlock module."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from keypass_importer.keepass.unlock import open_database


class TestOpenDatabasePasswordOnly:
    """Password-only unlock scenarios."""

    @patch("keypass_importer.keepass.unlock.PyKeePass")
    def test_opens_with_password(self, mock_pykeepass, tmp_path):
        db_file = tmp_path / "test.kdbx"
        db_file.write_bytes(b"fake-kdbx")
        mock_kp = MagicMock()
        mock_pykeepass.return_value = mock_kp

        result = open_database(db_file, password="secret")

        assert result is mock_kp
        mock_pykeepass.assert_called_once_with(
            str(db_file),
            password="secret",
            keyfile=None,
            transformed_key=None,
        )

    def test_missing_file_raises(self):
        with pytest.raises(FileNotFoundError, match="KeePass file not found"):
            open_database(Path("/nonexistent/db.kdbx"), password="x")

    @patch("keypass_importer.keepass.unlock.PyKeePass")
    def test_bad_credentials_raises(self, mock_pykeepass, tmp_path):
        from pykeepass.exceptions import CredentialsError

        db_file = tmp_path / "test.kdbx"
        db_file.write_bytes(b"fake-kdbx")
        mock_pykeepass.side_effect = CredentialsError("Invalid credentials")

        with pytest.raises(ValueError, match="Failed to open KeePass database"):
            open_database(db_file, password="wrong")


class TestOpenDatabaseKeyFile:
    """Key file unlock scenarios."""

    @patch("keypass_importer.keepass.unlock.PyKeePass")
    def test_opens_with_keyfile_only(self, mock_pykeepass, tmp_path):
        db_file = tmp_path / "test.kdbx"
        db_file.write_bytes(b"fake-kdbx")
        key_file = tmp_path / "key.keyx"
        key_file.write_bytes(b"fake-key")
        mock_kp = MagicMock()
        mock_pykeepass.return_value = mock_kp

        result = open_database(db_file, keyfile=key_file)

        assert result is mock_kp
        mock_pykeepass.assert_called_once_with(
            str(db_file),
            password=None,
            keyfile=str(key_file),
            transformed_key=None,
        )

    @patch("keypass_importer.keepass.unlock.PyKeePass")
    def test_opens_with_password_and_keyfile(self, mock_pykeepass, tmp_path):
        db_file = tmp_path / "test.kdbx"
        db_file.write_bytes(b"fake-kdbx")
        key_file = tmp_path / "key.keyx"
        key_file.write_bytes(b"fake-key")
        mock_kp = MagicMock()
        mock_pykeepass.return_value = mock_kp

        result = open_database(db_file, password="pw", keyfile=key_file)

        assert result is mock_kp
        mock_pykeepass.assert_called_once_with(
            str(db_file),
            password="pw",
            keyfile=str(key_file),
            transformed_key=None,
        )

    def test_keyfile_not_found_raises(self, tmp_path):
        db_file = tmp_path / "test.kdbx"
        db_file.write_bytes(b"fake-kdbx")

        with pytest.raises(FileNotFoundError, match="Key file not found"):
            open_database(db_file, keyfile=Path("/nonexistent/key.keyx"))


class TestOpenDatabaseWindowsCredential:
    """DPAPI (Windows credential) unlock scenarios."""

    @patch("keypass_importer.keepass.unlock.PyKeePass")
    @patch("keypass_importer.keepass._dpapi.dpapi_decrypt_user_key")
    def test_opens_with_dpapi(self, mock_dpapi, mock_pykeepass, tmp_path):
        db_file = tmp_path / "test.kdbx"
        db_file.write_bytes(b"fake-kdbx")
        mock_dpapi.return_value = b"\x00" * 32
        mock_kp = MagicMock()
        mock_pykeepass.return_value = mock_kp

        result = open_database(db_file, use_windows_credential=True)

        assert result is mock_kp
        mock_dpapi.assert_called_once()
        mock_pykeepass.assert_called_once_with(
            str(db_file),
            password=None,
            keyfile=None,
            transformed_key=b"\x00" * 32,
        )

    @patch("keypass_importer.keepass.unlock.PyKeePass")
    @patch("keypass_importer.keepass._dpapi.dpapi_decrypt_user_key")
    def test_opens_with_all_three_methods(self, mock_dpapi, mock_pykeepass, tmp_path):
        db_file = tmp_path / "test.kdbx"
        db_file.write_bytes(b"fake-kdbx")
        key_file = tmp_path / "key.keyx"
        key_file.write_bytes(b"fake-key")
        mock_dpapi.return_value = b"\xaa" * 32
        mock_kp = MagicMock()
        mock_pykeepass.return_value = mock_kp

        result = open_database(
            db_file, password="pw", keyfile=key_file, use_windows_credential=True
        )

        assert result is mock_kp
        mock_dpapi.assert_called_once()
        mock_pykeepass.assert_called_once_with(
            str(db_file),
            password="pw",
            keyfile=str(key_file),
            transformed_key=b"\xaa" * 32,
        )

    @patch("keypass_importer.keepass.unlock.PyKeePass")
    @patch("keypass_importer.keepass._dpapi.dpapi_decrypt_user_key")
    def test_opens_with_dpapi_and_password(self, mock_dpapi, mock_pykeepass, tmp_path):
        db_file = tmp_path / "test.kdbx"
        db_file.write_bytes(b"fake-kdbx")
        mock_dpapi.return_value = b"\xbb" * 32
        mock_kp = MagicMock()
        mock_pykeepass.return_value = mock_kp

        result = open_database(db_file, password="pw", use_windows_credential=True)

        assert result is mock_kp
        mock_pykeepass.assert_called_once_with(
            str(db_file),
            password="pw",
            keyfile=None,
            transformed_key=b"\xbb" * 32,
        )


class TestOpenDatabaseNoCredentials:
    """No credentials provided."""

    def test_no_credentials_raises(self, tmp_path):
        db_file = tmp_path / "test.kdbx"
        db_file.write_bytes(b"fake-kdbx")

        with pytest.raises(ValueError, match="At least one credential required"):
            open_database(db_file)

    def test_none_password_no_keyfile_no_dpapi_raises(self, tmp_path):
        db_file = tmp_path / "test.kdbx"
        db_file.write_bytes(b"fake-kdbx")

        with pytest.raises(ValueError, match="At least one credential required"):
            open_database(db_file, password=None, keyfile=None, use_windows_credential=False)
