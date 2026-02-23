"""Tests for entry-to-account mapper with platform detection."""

import pytest

from keypass_importer.models import KeePassEntry, CyberArkAccount, MappingMode
from keypass_importer.config import MappingRule
from keypass_importer.mapper import (
    detect_platform,
    map_entry,
    map_entries,
    generate_account_name,
)


class TestDetectPlatform:
    def test_ssh_url(self):
        assert detect_platform("ssh://10.0.0.1") == "UnixSSH"

    def test_ssh_port(self):
        assert detect_platform("10.0.0.1:22") == "UnixSSH"

    def test_mysql_port(self):
        assert detect_platform("db.local:3306") == "MySQL"

    def test_postgres_port(self):
        assert detect_platform("db.local:5432") == "PostgreSQL"

    def test_mssql_port(self):
        assert detect_platform("db.local:1433") == "MSSql"

    def test_rdp_url(self):
        assert detect_platform("rdp://win-server") == "WinServerLocal"

    def test_rdp_port(self):
        assert detect_platform("win-server:3389") == "WinServerLocal"

    def test_http_url(self):
        assert detect_platform("https://admin.example.com") == "WinDesktopApplications"

    def test_http_plain(self):
        assert detect_platform("http://app.local") == "WinDesktopApplications"

    def test_no_url(self):
        assert detect_platform(None) == "WinDesktopApplications"

    def test_empty_url(self):
        assert detect_platform("") == "WinDesktopApplications"

    def test_generic_url(self):
        assert detect_platform("server.local") == "WinDesktopApplications"


class TestGenerateAccountName:
    def test_basic_name(self):
        name = generate_account_name("MySafe", "10.0.0.1", "admin")
        assert name == "MySafe-10.0.0.1-admin"

    def test_sanitizes_special_chars(self):
        name = generate_account_name("My Safe", "server@domain", "user/name")
        assert " " not in name
        assert "/" not in name


class TestMapEntry:
    def test_single_mode(self):
        entry = KeePassEntry(
            title="Server",
            username="admin",
            password="pw",
            url="ssh://10.0.0.1:22",
            group_path=["Infra", "Linux"],
        )
        account = map_entry(
            entry,
            mode=MappingMode.SINGLE,
            safe_name="Linux-Safe",
        )
        assert account.safe_name == "Linux-Safe"
        assert account.platform_id == "UnixSSH"
        assert account.address == "10.0.0.1"
        assert account.username == "admin"
        assert account.secret == "pw"

    def test_group_mode(self):
        entry = KeePassEntry(
            title="Server",
            username="admin",
            password="pw",
            group_path=["Infrastructure", "Linux"],
        )
        account = map_entry(entry, mode=MappingMode.GROUP)
        assert account.safe_name == "Infrastructure-Linux"

    def test_group_mode_root_entry(self):
        entry = KeePassEntry(
            title="Server",
            username="admin",
            password="pw",
            group_path=[],
        )
        account = map_entry(
            entry,
            mode=MappingMode.GROUP,
            safe_name="Fallback-Safe",
        )
        assert account.safe_name == "Fallback-Safe"

    def test_config_mode_matching_rule(self):
        entry = KeePassEntry(
            title="Server",
            username="admin",
            password="pw",
            group_path=["Infrastructure", "Linux"],
        )
        rules = [
            MappingRule(group="Infrastructure/Linux", safe="Linux-Safe", platform="UnixSSH"),
            MappingRule(group="Infrastructure/Windows", safe="Win-Safe"),
        ]
        account = map_entry(
            entry,
            mode=MappingMode.CONFIG,
            mapping_rules=rules,
        )
        assert account.safe_name == "Linux-Safe"
        assert account.platform_id == "UnixSSH"

    def test_config_mode_no_match_uses_fallback(self):
        entry = KeePassEntry(
            title="Server",
            username="admin",
            password="pw",
            group_path=["Unknown"],
        )
        rules = [MappingRule(group="Other", safe="Other-Safe")]
        account = map_entry(
            entry,
            mode=MappingMode.CONFIG,
            mapping_rules=rules,
            safe_name="Fallback",
        )
        assert account.safe_name == "Fallback"

    def test_custom_field_platform_override(self):
        entry = KeePassEntry(
            title="Server",
            username="admin",
            password="pw",
            url="ssh://server:22",
            custom_fields={"platform": "CustomPlatform"},
        )
        account = map_entry(entry, mode=MappingMode.SINGLE, safe_name="S")
        assert account.platform_id == "CustomPlatform"

    def test_default_platform_override(self):
        entry = KeePassEntry(
            title="Server",
            username="admin",
            password="pw",
            url="ssh://server:22",
        )
        account = map_entry(
            entry,
            mode=MappingMode.SINGLE,
            safe_name="S",
            default_platform="ForcedPlatform",
        )
        assert account.platform_id == "ForcedPlatform"

    def test_extracts_address_from_url(self):
        entry = KeePassEntry(
            title="T", username="u", password="p",
            url="ssh://myhost.example.com:22",
        )
        account = map_entry(entry, mode=MappingMode.SINGLE, safe_name="S")
        assert account.address == "myhost.example.com"

    def test_address_from_plain_host(self):
        entry = KeePassEntry(
            title="T", username="u", password="p",
            url="10.0.0.5:3306",
        )
        account = map_entry(entry, mode=MappingMode.SINGLE, safe_name="S")
        assert account.address == "10.0.0.5"

    def test_address_fallback_to_title(self):
        entry = KeePassEntry(
            title="my-server", username="u", password="p",
        )
        account = map_entry(entry, mode=MappingMode.SINGLE, safe_name="S")
        assert account.address == "my-server"


class TestMapEntries:
    def test_maps_all_entries(self):
        entries = [
            KeePassEntry(title="A", username="u1", password="p1", group_path=["G"]),
            KeePassEntry(title="B", username="u2", password="p2", group_path=["G"]),
        ]
        accounts = map_entries(entries, mode=MappingMode.SINGLE, safe_name="S")
        assert len(accounts) == 2
        assert all(isinstance(a, CyberArkAccount) for a in accounts)
