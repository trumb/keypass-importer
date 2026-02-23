"""Tests for CyberArk OAuth2 PKCE authentication."""

import hashlib
import base64
import threading
import time
import pytest
import httpx

from keypass_importer.cyberark_auth import (
    generate_pkce_pair,
    build_authorize_url,
    exchange_code_for_token,
    PKCECallbackServer,
)


class TestPKCEGeneration:
    def test_verifier_length(self):
        verifier, _ = generate_pkce_pair()
        assert 43 <= len(verifier) <= 128

    def test_challenge_is_sha256_of_verifier(self):
        verifier, challenge = generate_pkce_pair()
        expected = (
            base64.urlsafe_b64encode(
                hashlib.sha256(verifier.encode("ascii")).digest()
            )
            .rstrip(b"=")
            .decode("ascii")
        )
        assert challenge == expected

    def test_each_call_unique(self):
        pair1 = generate_pkce_pair()
        pair2 = generate_pkce_pair()
        assert pair1[0] != pair2[0]


class TestBuildAuthorizeUrl:
    def test_contains_required_params(self):
        url = build_authorize_url(
            tenant_url="https://aax1234.id.cyberark.cloud",
            client_id="my-app",
            redirect_uri="http://localhost:8443/callback",
            code_challenge="test_challenge",
        )
        assert "response_type=code" in url
        assert "client_id=my-app" in url
        assert "code_challenge=test_challenge" in url
        assert "code_challenge_method=S256" in url
        assert "redirect_uri=" in url
        assert "aax1234.id.cyberark.cloud" in url


class TestPKCECallbackServer:
    def test_captures_auth_code(self):
        server = PKCECallbackServer(port=0)  # OS picks free port
        server.start()
        actual_port = server.port

        # Simulate CyberArk redirect
        try:
            resp = httpx.get(
                f"http://localhost:{actual_port}/callback",
                params={"code": "test_auth_code_123"},
                follow_redirects=False,
            )
            assert resp.status_code == 200
            assert server.auth_code == "test_auth_code_123"
        finally:
            server.stop()

    def test_handles_error_response(self):
        server = PKCECallbackServer(port=0)
        server.start()
        actual_port = server.port

        try:
            resp = httpx.get(
                f"http://localhost:{actual_port}/callback",
                params={"error": "access_denied", "error_description": "User denied"},
                follow_redirects=False,
            )
            assert server.auth_code is None
            assert server.error == "access_denied"
        finally:
            server.stop()


class TestExchangeCodeForToken:
    def test_token_exchange(self, httpx_mock):
        httpx_mock.add_response(
            url="https://tenant.id.cyberark.cloud/oauth2/token/my-app",
            method="POST",
            json={
                "access_token": "eyJ_test_token",
                "token_type": "Bearer",
                "expires_in": 3600,
            },
        )
        token = exchange_code_for_token(
            tenant_url="https://tenant.id.cyberark.cloud",
            client_id="my-app",
            auth_code="code_abc",
            code_verifier="verifier_xyz",
            redirect_uri="http://localhost:8443/callback",
        )
        assert token.access_token == "eyJ_test_token"
        assert token.expires_in == 3600

    def test_token_exchange_error(self, httpx_mock):
        httpx_mock.add_response(
            url="https://tenant.id.cyberark.cloud/oauth2/token/my-app",
            method="POST",
            status_code=400,
            json={"error": "invalid_grant"},
        )
        with pytest.raises(ValueError, match="token exchange failed"):
            exchange_code_for_token(
                tenant_url="https://tenant.id.cyberark.cloud",
                client_id="my-app",
                auth_code="bad_code",
                code_verifier="verifier",
                redirect_uri="http://localhost:8443/callback",
            )


# ---------------------------------------------------------------------------
# Coverage gap tests: missing-code callback, wait_for_code, authenticate
# ---------------------------------------------------------------------------

import socket
import urllib.request
from unittest.mock import patch

from keypass_importer.cyberark_auth import authenticate


def _find_free_port() -> int:
    """Return an OS-assigned free TCP port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("localhost", 0))
        return s.getsockname()[1]


class TestPKCECallbackServerExtended:
    """Additional PKCECallbackServer tests for uncovered branches."""

    def test_handles_missing_code_and_error(self):
        """GET /callback with no params triggers the 400 else branch (line 73)."""
        server = PKCECallbackServer(port=0)
        server.start()
        actual_port = server.port

        try:
            resp = httpx.get(
                f"http://localhost:{actual_port}/callback",
                follow_redirects=False,
            )
            assert resp.status_code == 400
            assert server.auth_code is None
        finally:
            server.stop()

    def test_wait_for_code(self):
        """wait_for_code blocks until a code arrives, then returns it (lines 120-121)."""
        server = PKCECallbackServer(port=0)
        server.start()
        actual_port = server.port

        def _send_code():
            time.sleep(0.1)
            httpx.get(
                f"http://localhost:{actual_port}/callback",
                params={"code": "wait_test_code"},
                follow_redirects=False,
            )

        try:
            sender = threading.Thread(target=_send_code, daemon=True)
            sender.start()
            code = server.wait_for_code(timeout=5.0)
            assert code == "wait_test_code"
            sender.join(timeout=3)
        finally:
            server.stop()


class TestAuthenticate:
    """Tests for the top-level authenticate() orchestrator (lines 170-190)."""

    @patch("keypass_importer.cyberark_auth.webbrowser.open")
    def test_authenticate_success(self, mock_browser_open, httpx_mock):
        """Full happy-path: browser opens, callback arrives, token exchanged."""
        port = _find_free_port()

        httpx_mock.add_response(
            url=f"https://tenant.id.cyberark.cloud/oauth2/token/my-app",
            method="POST",
            json={
                "access_token": "eyJ_full_flow_token",
                "token_type": "Bearer",
                "expires_in": 1800,
            },
        )

        def _simulate_callback():
            """Wait for server to be ready, then send the auth code.

            Uses urllib instead of httpx to bypass httpx_mock interception.
            """
            time.sleep(0.3)
            urllib.request.urlopen(
                f"http://localhost:{port}/callback?code=test_code"
            )

        sender = threading.Thread(target=_simulate_callback, daemon=True)
        sender.start()

        token = authenticate(
            tenant_url="https://tenant.id.cyberark.cloud",
            client_id="my-app",
            callback_port=port,
            timeout=5.0,
        )

        assert token.access_token == "eyJ_full_flow_token"
        assert token.expires_in == 1800
        mock_browser_open.assert_called_once()
        sender.join(timeout=3)

    @patch("keypass_importer.cyberark_auth.webbrowser.open")
    def test_authenticate_timeout(self, mock_browser_open):
        """No code ever arrives -- authenticate raises ValueError on timeout."""
        port = _find_free_port()

        with pytest.raises(ValueError, match="Authentication failed"):
            authenticate(
                tenant_url="https://tenant.id.cyberark.cloud",
                client_id="my-app",
                callback_port=port,
                timeout=0.1,
            )

        mock_browser_open.assert_called_once()

    @patch("keypass_importer.cyberark_auth.webbrowser.open")
    def test_authenticate_error_from_idp(self, mock_browser_open):
        """IdP returns an error param -- authenticate raises ValueError."""
        port = _find_free_port()

        def _simulate_error_callback():
            """Uses urllib instead of httpx to bypass httpx_mock interception."""
            time.sleep(0.2)
            urllib.request.urlopen(
                f"http://localhost:{port}/callback?error=access_denied"
            )

        sender = threading.Thread(target=_simulate_error_callback, daemon=True)
        sender.start()

        with pytest.raises(ValueError, match="Authentication failed.*access_denied"):
            authenticate(
                tenant_url="https://tenant.id.cyberark.cloud",
                client_id="my-app",
                callback_port=port,
                timeout=5.0,
            )

        mock_browser_open.assert_called_once()
        sender.join(timeout=3)
