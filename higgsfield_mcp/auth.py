"""
Clerk-based authentication for Higgsfield AI consumer API
Email/password login flow with JWT refresh and session persistence
"""
import json
import os
import time
from pathlib import Path
from typing import Optional, Dict, Any

from curl_cffi import requests

CLERK_BASE = "https://clerk.higgsfield.ai"
WARMUP_URL = "https://higgsfield.ai"
CONFIG_DIR = Path.home() / ".config" / "claude-higgsfield-mcp"
SESSION_FILE = CONFIG_DIR / "session.json"
IMPERSONATE = "chrome131"


class ClerkSession:
    """Manages Clerk authentication for Higgsfield consumer API"""

    def __init__(self):
        self._session = requests.Session(impersonate=IMPERSONATE)
        self.jwt: Optional[str] = None
        self.session_id: Optional[str] = None
        self.user_id: Optional[str] = None
        self.email: Optional[str] = None

    def login(self, email: str, password: str) -> bool:
        """Full Clerk email/password login flow with optional device verification."""
        self._warmup_cloudflare()
        self._clerk_init()

        try:
            # Step 1: Create sign-in (identify with email)
            resp = self._session.post(
                f"{CLERK_BASE}/v1/client/sign_ins",
                data={"identifier": email},
                timeout=10,
            )
            if resp.status_code != 200:
                return False

            data = resp.json()
            sign_in_id = data["response"]["id"]

            # Step 2: Attempt password first factor
            if data["response"]["status"] == "needs_first_factor":
                supported = [
                    f.get("strategy")
                    for f in (data["response"].get("supported_first_factors") or [])
                ]
                if "password" not in supported:
                    return False

                resp = self._session.post(
                    f"{CLERK_BASE}/v1/client/sign_ins/{sign_in_id}/attempt_first_factor",
                    data={"strategy": "password", "password": password},
                    timeout=10,
                )
                if resp.status_code != 200:
                    return False
                data = resp.json()

            # Step 3: Handle second factor (email verification code)
            if data["response"]["status"] == "needs_second_factor":
                email_address_id = None
                for factor in (data["response"].get("supported_second_factors") or []):
                    if isinstance(factor, dict) and factor.get("strategy") == "email_code":
                        email_address_id = factor.get("email_address_id")
                        break
                if not email_address_id:
                    for factor in (data["response"].get("supported_first_factors") or []):
                        if isinstance(factor, dict) and factor.get("strategy") == "email_code":
                            email_address_id = factor.get("email_address_id")
                            break

                payload = {"strategy": "email_code"}
                if email_address_id:
                    payload["email_address_id"] = email_address_id

                resp = self._session.post(
                    f"{CLERK_BASE}/v1/client/sign_ins/{sign_in_id}/prepare_second_factor",
                    data=payload,
                    timeout=10,
                )
                if resp.status_code != 200:
                    return False

                return False  # caller must retry with code

            # Step 4: Extract session and JWT
            if data["response"]["status"] == "complete":
                client_data = data["client"]
                session = client_data["sessions"][0]
                self.session_id = session["id"]
                self.user_id = session["user"]["id"]
                self.email = email

                if not self._refresh_jwt():
                    return False

                self._save_session()
                return True

            return False

        except Exception:
            return False

    def complete_verification(self, code: str) -> bool:
        """Complete second-factor email verification."""
        try:
            resp = self._session.post(
                f"{CLERK_BASE}/v1/client/sign_ins/{self.session_id}/attempt_second_factor",
                data={"strategy": "email_code", "code": code},
                timeout=10,
            )
            if resp.status_code != 200:
                return False

            data = resp.json()
            if data["response"]["status"] == "complete":
                client_data = data["client"]
                session = client_data["sessions"][0]
                self.session_id = session["id"]
                self.user_id = session["user"]["id"]

                if not self._refresh_jwt():
                    return False

                self._save_session()
                return True

            return False
        except Exception:
            return False

    def ensure_auth(self) -> bool:
        """Ensure a valid JWT is available, refreshing if needed."""
        if not self.session_id:
            # Try loading saved session
            if not self._load_session():
                return False
        return self._refresh_jwt()

    def get_auth_header(self) -> dict:
        """Return Authorization header with current JWT."""
        return {"Authorization": f"Bearer {self.jwt}"}

    def _refresh_jwt(self) -> bool:
        """Refresh JWT from Clerk (JWTs expire in ~60s)."""
        if not self.session_id:
            return False
        try:
            resp = self._session.post(
                f"{CLERK_BASE}/v1/client/sessions/{self.session_id}/tokens",
                timeout=10,
            )
            if resp.status_code == 200:
                self.jwt = resp.json().get("jwt")
                return bool(self.jwt)
            return False
        except Exception:
            return False

    def _warmup_cloudflare(self):
        """Hit the main site to establish a Cloudflare session."""
        try:
            self._session.get(WARMUP_URL, timeout=10)
        except Exception:
            pass

    def _clerk_init(self):
        """Initialize Clerk client state."""
        try:
            self._session.get(f"{CLERK_BASE}/v1/client", timeout=10)
        except Exception:
            pass

    def _load_session(self) -> bool:
        """Load saved session from disk."""
        if not SESSION_FILE.exists():
            return False
        try:
            with open(SESSION_FILE) as f:
                data = json.load(f)
            self.session_id = data.get("sessionId")
            self.user_id = data.get("userId")
            self.email = data.get("email")
            self.jwt = data.get("jwt")

            # Restore cookies
            for c in data.get("allCookies", []):
                kwargs = {}
                if c.get("domain"):
                    kwargs["domain"] = c["domain"]
                if c.get("path"):
                    kwargs["path"] = c["path"]
                self._session.cookies.set(c["name"], c["value"], **kwargs)

            client_cookie = data.get("clientCookie")
            if client_cookie:
                self._session.cookies.set(
                    "__client", client_cookie, domain=".clerk.higgsfield.ai"
                )

            return bool(self.session_id)
        except Exception:
            return False

    def _save_session(self):
        """Save session to disk for future runs."""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        cookie_data = []
        cookie_jar = getattr(self._session.cookies, "jar", None) or self._session.cookies
        for cookie in cookie_jar:
            if not hasattr(cookie, "name"):
                continue
            cookie_data.append({
                "name": cookie.name,
                "value": cookie.value,
                "domain": getattr(cookie, "domain", None),
                "path": getattr(cookie, "path", None),
            })

        client_cookie = (
            self._session.cookies.get("__client", domain=".clerk.higgsfield.ai")
            or self._session.cookies.get("__client")
        )

        session_data = {
            "sessionId": self.session_id,
            "userId": self.user_id,
            "email": self.email,
            "jwt": self.jwt,
            "savedAt": time.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "allCookies": cookie_data,
            "clientCookie": client_cookie,
        }

        with open(SESSION_FILE, "w") as f:
            json.dump(session_data, f, indent=2)
