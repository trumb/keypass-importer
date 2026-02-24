"""Shared exception hierarchy for keypass-importer."""

from __future__ import annotations


class KeyPassImporterError(Exception):
    """Base exception for all keypass-importer errors."""


class DatabaseError(KeyPassImporterError):
    """Error opening or reading a KeePass database."""


class AuthenticationError(KeyPassImporterError):
    """Error during CyberArk authentication."""


class ApiError(KeyPassImporterError):
    """Error communicating with CyberArk REST API."""


class ConfigError(KeyPassImporterError):
    """Error loading or validating configuration."""


class SyncError(KeyPassImporterError):
    """Error during bidirectional sync."""
