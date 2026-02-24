"""REST API client for CyberArk Privilege Cloud."""

from __future__ import annotations

import logging

import httpx

from keypass_importer.core.models import CyberArkAccount

logger = logging.getLogger(__name__)


class CyberArkClient:
    """Wrapper around CyberArk Privilege Cloud REST API."""

    def __init__(self, base_url: str, access_token: str):
        self._base = f"{base_url.rstrip('/')}/PasswordVault/API"
        self._http = httpx.Client(
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

    def close(self):
        self._http.close()

    def list_safes(self) -> list[str]:
        """List all safes the authenticated user can see."""
        resp = self._http.get(f"{self._base}/Safes")
        resp.raise_for_status()
        data = resp.json()
        return [s["safeName"] for s in data.get("value", [])]

    def find_existing_account(
        self, safe_name: str, address: str, username: str
    ) -> str | None:
        """Check if an account already exists. Returns account ID or None."""
        resp = self._http.get(
            f"{self._base}/Accounts",
            params={
                "search": f"{address} {username}",
                "filter": f"safeName eq {safe_name}",
            },
        )
        resp.raise_for_status()
        accounts = resp.json().get("value", [])

        for acc in accounts:
            if acc.get("userName") == username and acc.get("address") == address:
                return acc["id"]

        return None

    def create_account(self, account: CyberArkAccount) -> str:
        """Create a new account in CyberArk. Returns the account ID."""
        payload = account.to_api_payload()
        resp = self._http.post(f"{self._base}/Accounts", json=payload)

        if resp.status_code not in (200, 201):
            body = resp.json()
            msg = body.get("ErrorMessage", resp.text)
            raise ValueError(f"Failed to create account: {msg}")

        return resp.json()["id"]
