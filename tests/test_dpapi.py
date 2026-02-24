"""Tests for Windows DPAPI decryption module.

All tests mock DPAPI internals so they run on any OS.
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from keypass_importer.keepass._dpapi import dpapi_decrypt_user_key, _get_user_key_path


class TestDpapiDecryptUserKey:
    """Successful DPAPI decryption."""

    @patch("keypass_importer.keepass._dpapi._crypt_unprotect_data")
    @patch("keypass_importer.keepass._dpapi._get_user_key_path")
    def test_reads_and_decrypts_key(self, mock_get_path, mock_decrypt, tmp_path):
        key_file = tmp_path / "ProtectedUserKey.bin"
        key_file.write_bytes(b"\xde\xad\xbe\xef" * 8)
        mock_get_path.return_value = key_file
        mock_decrypt.return_value = b"\x00" * 32

        result = dpapi_decrypt_user_key()

        assert result == b"\x00" * 32
        mock_decrypt.assert_called_once_with(b"\xde\xad\xbe\xef" * 8)

    @patch("keypass_importer.keepass._dpapi._crypt_unprotect_data")
    @patch("keypass_importer.keepass._dpapi._get_user_key_path")
    def test_returns_correct_byte_length(self, mock_get_path, mock_decrypt, tmp_path):
        key_file = tmp_path / "ProtectedUserKey.bin"
        key_file.write_bytes(b"\xff" * 64)
        mock_get_path.return_value = key_file
        mock_decrypt.return_value = b"\xab" * 32

        result = dpapi_decrypt_user_key()

        assert len(result) == 32


class TestDpapiMissingKeyFile:
    """Missing ProtectedUserKey.bin."""

    @patch("keypass_importer.keepass._dpapi._get_user_key_path")
    def test_missing_key_file_raises(self, mock_get_path, tmp_path):
        mock_get_path.return_value = tmp_path / "nonexistent" / "ProtectedUserKey.bin"

        with pytest.raises(FileNotFoundError, match="ProtectedUserKey.bin not found"):
            dpapi_decrypt_user_key()


class TestDpapiDecryptFailure:
    """DPAPI decryption failure."""

    @patch("keypass_importer.keepass._dpapi._crypt_unprotect_data")
    @patch("keypass_importer.keepass._dpapi._get_user_key_path")
    def test_decrypt_failure_propagates(self, mock_get_path, mock_decrypt, tmp_path):
        key_file = tmp_path / "ProtectedUserKey.bin"
        key_file.write_bytes(b"\xde\xad" * 16)
        mock_get_path.return_value = key_file
        mock_decrypt.side_effect = OSError("CryptUnprotectData failed (wrong user account?)")

        with pytest.raises(OSError, match="CryptUnprotectData failed"):
            dpapi_decrypt_user_key()


class TestGetUserKeyPath:
    """Path construction from APPDATA."""

    @patch("keypass_importer.keepass._dpapi.os.environ.get")
    def test_constructs_path_from_appdata(self, mock_env_get):
        mock_env_get.return_value = r"C:\Users\testuser\AppData\Roaming"

        result = _get_user_key_path()

        assert result == Path(r"C:\Users\testuser\AppData\Roaming\KeePass\ProtectedUserKey.bin")
        mock_env_get.assert_called_once_with("APPDATA", "")

    @patch("keypass_importer.keepass._dpapi.os.environ.get")
    def test_empty_appdata_returns_relative_path(self, mock_env_get):
        mock_env_get.return_value = ""

        result = _get_user_key_path()

        assert result == Path("KeePass/ProtectedUserKey.bin")
