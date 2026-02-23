"""Maps KeePass entries to CyberArk accounts with platform auto-detection."""

from __future__ import annotations

import logging
import re
from urllib.parse import urlparse

from keypass_importer.config import MappingRule
from keypass_importer.models import CyberArkAccount, KeePassEntry, MappingMode

logger = logging.getLogger(__name__)

# Port-based platform detection
_PORT_PLATFORMS: dict[str, str] = {
    "22": "UnixSSH",
    "3306": "MySQL",
    "5432": "PostgreSQL",
    "1433": "MSSql",
    "3389": "WinServerLocal",
}

# Scheme-based platform detection
_SCHEME_PLATFORMS: dict[str, str] = {
    "ssh": "UnixSSH",
    "rdp": "WinServerLocal",
    "http": "WinDesktopApplications",
    "https": "WinDesktopApplications",
}


def detect_platform(url: str | None) -> str:
    """Auto-detect CyberArk platform ID from a KeePass entry URL."""
    if not url:
        return "WinDesktopApplications"

    # Try parsing as a proper URL
    parsed = urlparse(url)
    if parsed.scheme and parsed.scheme in _SCHEME_PLATFORMS:
        # Check port first for scheme URLs
        port = str(parsed.port) if parsed.port else None
        if port and port in _PORT_PLATFORMS:
            return _PORT_PLATFORMS[port]
        return _SCHEME_PLATFORMS[parsed.scheme]

    # Try host:port pattern (no scheme)
    port_match = re.search(r":(\d+)$", url)
    if port_match:
        port = port_match.group(1)
        if port in _PORT_PLATFORMS:
            return _PORT_PLATFORMS[port]

    return "WinDesktopApplications"


def _extract_address(url: str | None, title: str) -> str:
    """Extract the host/address from a URL, falling back to title."""
    if not url:
        return title

    parsed = urlparse(url)
    if parsed.hostname:
        return parsed.hostname

    # host:port without scheme
    host_match = re.match(r"^([^:]+):\d+$", url)
    if host_match:
        return host_match.group(1)

    return url if url else title


def generate_account_name(safe: str, address: str, username: str) -> str:
    """Generate a CyberArk account name from components."""
    raw = f"{safe}-{address}-{username}"
    # Replace problematic characters
    return re.sub(r"[^\w.\-]", "_", raw)


def _resolve_safe(
    entry: KeePassEntry,
    mode: MappingMode,
    safe_name: str | None,
    mapping_rules: list[MappingRule] | None,
) -> str:
    """Determine the target safe for an entry based on mapping mode."""
    if mode == MappingMode.SINGLE:
        if not safe_name:
            raise ValueError("safe_name is required for single mapping mode")
        return safe_name

    if mode == MappingMode.GROUP:
        if entry.group_path:
            return "-".join(entry.group_path)
        if safe_name:
            return safe_name
        raise ValueError(
            f"Entry '{entry.title}' is in root group and no fallback safe provided"
        )

    if mode == MappingMode.CONFIG:
        group_str = entry.group_path_str
        for rule in (mapping_rules or []):
            if group_str == rule.group or group_str.startswith(rule.group + "/"):
                return rule.safe
        if safe_name:
            return safe_name
        raise ValueError(
            f"No mapping rule matches group '{group_str}' and no fallback safe"
        )

    raise ValueError(f"Unknown mapping mode: {mode}")


def _resolve_platform(
    entry: KeePassEntry,
    default_platform: str | None,
    mapping_rules: list[MappingRule] | None,
    mode: MappingMode,
) -> str:
    """Determine the platform ID, checking custom field > default > rule > auto-detect."""
    # Custom field takes priority
    if "platform" in entry.custom_fields:
        return entry.custom_fields["platform"]

    # CLI/config default override
    if default_platform:
        return default_platform

    # Config-mode rule platform
    if mode == MappingMode.CONFIG and mapping_rules:
        group_str = entry.group_path_str
        for rule in mapping_rules:
            if rule.platform and (
                group_str == rule.group or group_str.startswith(rule.group + "/")
            ):
                return rule.platform

    # Auto-detect from URL
    return detect_platform(entry.url)


def map_entry(
    entry: KeePassEntry,
    mode: MappingMode,
    safe_name: str | None = None,
    default_platform: str | None = None,
    mapping_rules: list[MappingRule] | None = None,
) -> CyberArkAccount:
    """Map a single KeePass entry to a CyberArk account."""
    safe = _resolve_safe(entry, mode, safe_name, mapping_rules)
    platform = _resolve_platform(entry, default_platform, mapping_rules, mode)
    address = _extract_address(entry.url, entry.title)
    name = generate_account_name(safe, address, entry.username)

    return CyberArkAccount(
        safe_name=safe,
        platform_id=platform,
        address=address,
        username=entry.username,
        secret=entry.password,
        name=name,
    )


def map_entries(
    entries: list[KeePassEntry],
    mode: MappingMode,
    safe_name: str | None = None,
    default_platform: str | None = None,
    mapping_rules: list[MappingRule] | None = None,
) -> list[CyberArkAccount]:
    """Map a list of KeePass entries to CyberArk accounts."""
    return [
        map_entry(entry, mode, safe_name, default_platform, mapping_rules)
        for entry in entries
    ]
