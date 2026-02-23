"""Data models for KeePass entries, CyberArk accounts, and import results."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class MappingMode(str, Enum):
    """How KeePass groups map to CyberArk safes."""

    SINGLE = "single"
    GROUP = "group"
    CONFIG = "config"


class KeePassEntry(BaseModel):
    """A single entry parsed from a KeePass .kdbx file."""

    title: str
    username: str
    password: str
    url: str | None = None
    group_path: list[str] = Field(default_factory=list)
    notes: str | None = None
    custom_fields: dict[str, str] = Field(default_factory=dict)

    @property
    def group_path_str(self) -> str:
        """Return the group path as a slash-separated string."""
        return "/".join(self.group_path)


class CyberArkAccount(BaseModel):
    """A CyberArk Privilege Cloud account ready for API submission."""

    safe_name: str
    platform_id: str
    address: str
    username: str
    secret: str
    name: str
    secret_type: str = "password"
    platform_properties: dict[str, str] = Field(default_factory=dict)

    def to_api_payload(self) -> dict[str, Any]:
        """Convert to the JSON payload expected by the CyberArk REST API."""
        payload: dict[str, Any] = {
            "name": self.name,
            "address": self.address,
            "userName": self.username,
            "platformId": self.platform_id,
            "safeName": self.safe_name,
            "secretType": self.secret_type,
            "secret": self.secret,
        }
        if self.platform_properties:
            payload["platformAccountProperties"] = dict(self.platform_properties)
        return payload


class ImportResult(BaseModel):
    """Result of importing a single entry."""

    entry_title: str
    entry_group: str
    status: str  # "imported", "duplicate", "failed"
    safe_name: str | None = None
    account_id: str | None = None
    error: str | None = None
    detected_platform: str | None = None
    url: str | None = None
    timestamp: str | None = None


class ImportSummary(BaseModel):
    """Aggregate summary of an import run."""

    total: int
    imported: int
    duplicates: int
    failed: int

    @classmethod
    def from_results(cls, results: list[ImportResult]) -> ImportSummary:
        """Build a summary by counting result statuses."""
        return cls(
            total=len(results),
            imported=sum(1 for r in results if r.status == "imported"),
            duplicates=sum(1 for r in results if r.status == "duplicate"),
            failed=sum(1 for r in results if r.status == "failed"),
        )
