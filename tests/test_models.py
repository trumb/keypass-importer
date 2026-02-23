"""Tests for data models."""

import pytest
from keypass_importer.models import (
    KeePassEntry,
    CyberArkAccount,
    ImportResult,
    ImportSummary,
    MappingMode,
)


class TestKeePassEntry:
    def test_basic_entry(self):
        entry = KeePassEntry(
            title="My Server",
            username="admin",
            password="s3cret",
            url="ssh://10.0.0.1:22",
            group_path=["Infrastructure", "Linux"],
            notes="Production server",
        )
        assert entry.title == "My Server"
        assert entry.username == "admin"
        assert entry.password == "s3cret"
        assert entry.url == "ssh://10.0.0.1:22"
        assert entry.group_path == ["Infrastructure", "Linux"]
        assert entry.notes == "Production server"
        assert entry.custom_fields == {}

    def test_entry_with_custom_fields(self):
        entry = KeePassEntry(
            title="DB",
            username="root",
            password="pw",
            custom_fields={"platform": "MySQL", "port": "3306"},
        )
        assert entry.custom_fields["platform"] == "MySQL"

    def test_entry_minimal(self):
        entry = KeePassEntry(title="Bare", username="u", password="p")
        assert entry.url is None
        assert entry.group_path == []
        assert entry.notes is None
        assert entry.custom_fields == {}

    def test_group_path_string(self):
        entry = KeePassEntry(
            title="T",
            username="u",
            password="p",
            group_path=["Root", "Web", "Production"],
        )
        assert entry.group_path_str == "Root/Web/Production"

    def test_group_path_string_empty(self):
        entry = KeePassEntry(title="T", username="u", password="p")
        assert entry.group_path_str == ""


class TestCyberArkAccount:
    def test_basic_account(self):
        account = CyberArkAccount(
            safe_name="Linux-Safe",
            platform_id="UnixSSH",
            address="10.0.0.1",
            username="admin",
            secret="s3cret",
            name="Linux-Safe-10.0.0.1-admin",
        )
        assert account.safe_name == "Linux-Safe"
        assert account.platform_id == "UnixSSH"
        assert account.secret_type == "password"

    def test_to_api_payload(self):
        account = CyberArkAccount(
            safe_name="MySafe",
            platform_id="UnixSSH",
            address="server.local",
            username="root",
            secret="pw",
            name="MySafe-server.local-root",
        )
        payload = account.to_api_payload()
        assert payload["safeName"] == "MySafe"
        assert payload["platformId"] == "UnixSSH"
        assert payload["address"] == "server.local"
        assert payload["userName"] == "root"
        assert payload["secret"] == "pw"
        assert payload["secretType"] == "password"
        assert payload["name"] == "MySafe-server.local-root"

    def test_to_api_payload_with_properties(self):
        account = CyberArkAccount(
            safe_name="S",
            platform_id="MySQL",
            address="db.local",
            username="root",
            secret="pw",
            name="S-db.local-root",
            platform_properties={"Port": "3306", "Database": "mydb"},
        )
        payload = account.to_api_payload()
        assert payload["platformAccountProperties"]["Port"] == "3306"


class TestImportResult:
    def test_success_result(self):
        result = ImportResult(
            entry_title="My Server",
            entry_group="Infra/Linux",
            status="imported",
            safe_name="Linux-Safe",
            account_id="123_456",
        )
        assert result.status == "imported"
        assert result.error is None

    def test_duplicate_result(self):
        result = ImportResult(
            entry_title="My Server",
            entry_group="Infra/Linux",
            status="duplicate",
            safe_name="Linux-Safe",
            account_id="existing_789",
        )
        assert result.status == "duplicate"

    def test_failed_result(self):
        result = ImportResult(
            entry_title="Bad Entry",
            entry_group="Root",
            status="failed",
            error="Safe not found",
        )
        assert result.status == "failed"
        assert result.error == "Safe not found"


class TestImportSummary:
    def test_summary_from_results(self):
        results = [
            ImportResult(entry_title="A", entry_group="G", status="imported", safe_name="S", account_id="1"),
            ImportResult(entry_title="B", entry_group="G", status="imported", safe_name="S", account_id="2"),
            ImportResult(entry_title="C", entry_group="G", status="duplicate", safe_name="S", account_id="3"),
            ImportResult(entry_title="D", entry_group="G", status="failed", error="err"),
        ]
        summary = ImportSummary.from_results(results)
        assert summary.total == 4
        assert summary.imported == 2
        assert summary.duplicates == 1
        assert summary.failed == 1


class TestMappingMode:
    def test_enum_values(self):
        assert MappingMode.SINGLE == "single"
        assert MappingMode.GROUP == "group"
        assert MappingMode.CONFIG == "config"
