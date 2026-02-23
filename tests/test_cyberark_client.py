"""Tests for CyberArk Privilege Cloud REST API client."""

import pytest

from keypass_importer.cyberark_client import CyberArkClient
from keypass_importer.models import CyberArkAccount


@pytest.fixture
def client():
    return CyberArkClient(
        base_url="https://mytenant.privilegecloud.cyberark.cloud",
        access_token="test_token_abc",
    )


@pytest.fixture
def sample_account():
    return CyberArkAccount(
        safe_name="Linux-Safe",
        platform_id="UnixSSH",
        address="10.0.0.1",
        username="admin",
        secret="s3cret",
        name="Linux-Safe-10.0.0.1-admin",
    )


class TestListSafes:
    def test_returns_safe_names(self, client, httpx_mock):
        httpx_mock.add_response(
            url="https://mytenant.privilegecloud.cyberark.cloud/PasswordVault/API/Safes",
            json={
                "value": [
                    {"safeName": "Linux-Safe", "safeNumber": 1},
                    {"safeName": "Windows-Safe", "safeNumber": 2},
                ],
                "count": 2,
            },
        )
        safes = client.list_safes()
        assert safes == ["Linux-Safe", "Windows-Safe"]

    def test_auth_header_sent(self, client, httpx_mock):
        httpx_mock.add_response(
            url="https://mytenant.privilegecloud.cyberark.cloud/PasswordVault/API/Safes",
            json={"value": [], "count": 0},
        )
        client.list_safes()
        request = httpx_mock.get_request()
        assert request.headers["Authorization"] == "Bearer test_token_abc"


class TestFindExistingAccount:
    def test_finds_duplicate(self, client, httpx_mock):
        httpx_mock.add_response(
            url="https://mytenant.privilegecloud.cyberark.cloud/PasswordVault/API/Accounts?search=10.0.0.1+admin&filter=safeName+eq+Linux-Safe",
            json={
                "value": [
                    {"id": "acc_existing_123", "userName": "admin", "address": "10.0.0.1"},
                ],
                "count": 1,
            },
        )
        account_id = client.find_existing_account("Linux-Safe", "10.0.0.1", "admin")
        assert account_id == "acc_existing_123"

    def test_no_duplicate(self, client, httpx_mock):
        httpx_mock.add_response(
            url="https://mytenant.privilegecloud.cyberark.cloud/PasswordVault/API/Accounts?search=10.0.0.1+admin&filter=safeName+eq+Linux-Safe",
            json={"value": [], "count": 0},
        )
        account_id = client.find_existing_account("Linux-Safe", "10.0.0.1", "admin")
        assert account_id is None


class TestCreateAccount:
    def test_creates_account(self, client, httpx_mock, sample_account):
        httpx_mock.add_response(
            url="https://mytenant.privilegecloud.cyberark.cloud/PasswordVault/API/Accounts",
            method="POST",
            json={"id": "new_acc_456", "name": sample_account.name},
            status_code=201,
        )
        account_id = client.create_account(sample_account)
        assert account_id == "new_acc_456"

    def test_sends_correct_payload(self, client, httpx_mock, sample_account):
        httpx_mock.add_response(
            url="https://mytenant.privilegecloud.cyberark.cloud/PasswordVault/API/Accounts",
            method="POST",
            json={"id": "new_acc_456"},
            status_code=201,
        )
        client.create_account(sample_account)
        request = httpx_mock.get_request()
        import json
        body = json.loads(request.content)
        assert body["safeName"] == "Linux-Safe"
        assert body["platformId"] == "UnixSSH"
        assert body["userName"] == "admin"
        assert body["secret"] == "s3cret"

    def test_api_error_raises(self, client, httpx_mock, sample_account):
        httpx_mock.add_response(
            url="https://mytenant.privilegecloud.cyberark.cloud/PasswordVault/API/Accounts",
            method="POST",
            json={"ErrorCode": "PASWS027E", "ErrorMessage": "Safe not found"},
            status_code=404,
        )
        with pytest.raises(ValueError, match="Safe not found"):
            client.create_account(sample_account)


class TestClose:
    def test_close_shuts_down_http_client(self, client):
        """Verify close() calls through to the httpx client."""
        client.close()
        # After close, further requests should fail
        with pytest.raises(Exception):
            client.list_safes()
