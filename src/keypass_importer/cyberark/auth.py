"""OAuth2 Authorization Code + PKCE flow for CyberArk Identity."""

from __future__ import annotations

import base64
import hashlib
import logging
import secrets
import threading
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlencode, urlparse, parse_qs

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class TokenResponse(BaseModel):
    """OAuth2 token response."""

    access_token: str
    token_type: str = "Bearer"
    expires_in: int = 3600
    refresh_token: str | None = None


def generate_pkce_pair() -> tuple[str, str]:
    """Generate a PKCE code_verifier and code_challenge (S256)."""
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


def build_authorize_url(
    tenant_url: str,
    client_id: str,
    redirect_uri: str,
    code_challenge: str,
    scope: str = "openid",
) -> str:
    """Build the CyberArk Identity authorization URL."""
    base = f"{tenant_url.rstrip('/')}/oauth2/authorize/{client_id}"
    params = urlencode({
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scope,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    })
    return f"{base}?{params}"


class _CallbackHandler(BaseHTTPRequestHandler):
    """HTTP handler that captures the OAuth2 callback."""

    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        if "error" in params:
            self.server._auth_code = None
            self.server._error = params["error"][0]
            self._respond("Authentication failed. You can close this window.")
        elif "code" in params:
            self.server._auth_code = params["code"][0]
            self.server._error = None
            self._respond("Authentication successful! You can close this window.")
        else:
            self._respond("Unexpected callback. Missing 'code' parameter.", 400)

        # Signal that we got the response
        self.server._got_response.set()

    def _respond(self, message: str, status: int = 200):
        self.send_response(status)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        html = f"<html><body><h2>{message}</h2></body></html>"
        self.wfile.write(html.encode())

    def log_message(self, format, *args):
        """Suppress default access log."""
        logger.debug(format, *args)


class PKCECallbackServer:
    """Local HTTP server to receive the OAuth2 authorization code redirect."""

    def __init__(self, port: int = 8443):
        self._server = HTTPServer(("localhost", port), _CallbackHandler)
        self._server._auth_code = None
        self._server._error = None
        self._server._got_response = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def port(self) -> int:
        return self._server.server_address[1]

    @property
    def auth_code(self) -> str | None:
        return self._server._auth_code

    @property
    def error(self) -> str | None:
        return self._server._error

    def start(self):
        """Start the callback server in a background thread."""
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        logger.info("Callback server listening on port %d", self.port)

    def wait_for_code(self, timeout: float = 120.0) -> str | None:
        """Block until the auth code is received or timeout expires."""
        self._server._got_response.wait(timeout=timeout)
        return self.auth_code

    def stop(self):
        """Shut down the callback server."""
        self._server.shutdown()
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Callback server stopped")


def exchange_code_for_token(
    tenant_url: str,
    client_id: str,
    auth_code: str,
    code_verifier: str,
    redirect_uri: str,
) -> TokenResponse:
    """Exchange an authorization code for an access token."""
    token_url = f"{tenant_url.rstrip('/')}/oauth2/token/{client_id}"

    resp = httpx.post(
        token_url,
        data={
            "grant_type": "authorization_code",
            "code": auth_code,
            "redirect_uri": redirect_uri,
            "client_id": client_id,
            "code_verifier": code_verifier,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    if resp.status_code != 200:
        detail = resp.json().get("error", resp.text)
        raise ValueError(f"OAuth2 token exchange failed: {detail}")

    return TokenResponse(**resp.json())


def authenticate(
    tenant_url: str,
    client_id: str,
    callback_port: int = 8443,
    timeout: float = 120.0,
) -> TokenResponse:
    """Run the full PKCE auth flow: start server, open browser, wait for code, exchange.

    This is the main entry point for CLI authentication.
    """
    verifier, challenge = generate_pkce_pair()
    redirect_uri = f"http://localhost:{callback_port}/callback"

    server = PKCECallbackServer(port=callback_port)
    server.start()

    try:
        auth_url = build_authorize_url(tenant_url, client_id, redirect_uri, challenge)
        logger.info("Opening browser for authentication...")
        webbrowser.open(auth_url)

        code = server.wait_for_code(timeout=timeout)
        if not code:
            error = server.error or "Timed out waiting for authentication"
            raise ValueError(f"Authentication failed: {error}")

        return exchange_code_for_token(
            tenant_url, client_id, code, verifier, redirect_uri
        )
    finally:
        server.stop()
