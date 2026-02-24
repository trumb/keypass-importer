"""Tests for the shared exception hierarchy."""

import pytest

from keypass_importer.core.errors import (
    ApiError,
    AuthenticationError,
    ConfigError,
    DatabaseError,
    KeyPassImporterError,
    SyncError,
)


class TestExceptionHierarchy:
    """All custom exceptions inherit from KeyPassImporterError."""

    @pytest.mark.parametrize(
        "exc_cls",
        [DatabaseError, AuthenticationError, ApiError, ConfigError, SyncError],
    )
    def test_subclass_of_base(self, exc_cls):
        assert issubclass(exc_cls, KeyPassImporterError)

    @pytest.mark.parametrize(
        "exc_cls",
        [DatabaseError, AuthenticationError, ApiError, ConfigError, SyncError],
    )
    def test_subclass_of_exception(self, exc_cls):
        assert issubclass(exc_cls, Exception)

    @pytest.mark.parametrize(
        "exc_cls",
        [
            KeyPassImporterError,
            DatabaseError,
            AuthenticationError,
            ApiError,
            ConfigError,
            SyncError,
        ],
    )
    def test_raise_and_catch_by_base(self, exc_cls):
        with pytest.raises(KeyPassImporterError):
            raise exc_cls("test error")

    @pytest.mark.parametrize(
        "exc_cls",
        [
            KeyPassImporterError,
            DatabaseError,
            AuthenticationError,
            ApiError,
            ConfigError,
            SyncError,
        ],
    )
    def test_message_preserved(self, exc_cls):
        err = exc_cls("something went wrong")
        assert str(err) == "something went wrong"

    def test_catch_specific_not_sibling(self):
        """DatabaseError should not be caught by ApiError handler."""
        with pytest.raises(DatabaseError):
            try:
                raise DatabaseError("db broke")
            except ApiError:
                pytest.fail("DatabaseError should not be caught as ApiError")
