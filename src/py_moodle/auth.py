# src/moodle/auth.py
"""
Authentication module for Moodle.

Handles session-based login (including support for CAS) and retrieves the session key required for further AJAX requests.
"""

import re
from typing import Optional

import requests
from bs4 import BeautifulSoup


class LoginError(Exception):
    """Exception raised when authentication fails."""


class MoodleAuth:
    """Authenticate a user against a Moodle site."""

    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        use_cas: bool = False,
        cas_url: Optional[str] = None,
        pre_configured_token: Optional[str] = None,
        debug: bool = False,
    ):
        """Initialize the authenticator.

        Args:
            base_url: Base URL of the Moodle instance.
            username: Username to authenticate with.
            password: Password for the user.
            use_cas: Whether to use CAS authentication.
            cas_url: URL of the CAS server (if ``use_cas`` is ``True``).
            pre_configured_token: Pre-created webservice token, if available.
            debug: Enable verbose debugging output.
        """
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.sesskey = None
        self.use_cas = use_cas
        self.cas_url = cas_url
        self.pre_configured_token = pre_configured_token
        self.debug = debug
        self.webservice_token = None

    def login(self) -> requests.Session:
        """Authenticate the user and return a Moodle session.

        Returns:
            requests.Session: Authenticated session with cookies.

        Raises:
            LoginError: If authentication fails.
        """
        if self.debug:
            print(
                f"[DEBUG] Login: base_url={self.base_url} username={self.username} use_cas={self.use_cas} cas_url={self.cas_url}"
            )
        if self.use_cas and self.cas_url:
            self._cas_login()
        else:
            self._standard_login()
        # Try to get the sesskey, but don't fail if it's not possible (for pure AJAX)
        try:
            self.sesskey = self._get_sesskey()
            if self.debug:
                print(f"[DEBUG] sesskey obtained: {self.sesskey}")
        except Exception as e:
            if self.debug:
                print(f"[DEBUG] Could not obtain sesskey: {e}")
            self.sesskey = None
        # Try to get webservice token
        try:
            self.webservice_token = self._get_webservice_token()
            if self.debug:
                print(f"[DEBUG] webservice_token obtained: {self.webservice_token}")
        except Exception as e:
            if self.debug:
                print(f"[DEBUG] Could not obtain webservice token: {e}")
            self.webservice_token = None
        return self.session

    def _standard_login(self):
        """Perform standard Moodle login and set session cookies."""
        login_url = f"{self.base_url}/login/index.php"
        if self.debug:
            print(f"[DEBUG] GET {login_url}")
        resp = self.session.get(login_url)
        if self.debug:
            print(f"[DEBUG] Response {resp.status_code} {resp.url}")
        soup = BeautifulSoup(resp.text, "lxml")
        logintoken_input = soup.find("input", {"name": "logintoken"})
        logintoken = logintoken_input["value"] if logintoken_input else ""

        payload = {
            "username": self.username,
            "password": self.password,
            "logintoken": logintoken,
            "anchor": "",
        }
        if self.debug:
            print(f"[DEBUG] POST {login_url} payload={payload}")
        resp = self.session.post(login_url, data=payload, allow_redirects=True)
        if self.debug:
            print(f"[DEBUG] Response {resp.status_code} {resp.url}")
        # Authentication failed if redirected back to login page
        if "/login/index.php" in resp.url or "Invalid login" in resp.text:
            raise LoginError("Invalid Moodle username or password.")

    def _cas_login(self):
        """
        Perform CAS login flow programmatically (no browser interaction).
        Maintains cookies and follows the CAS ticket flow.
        """
        import re

        # Step 1: Get CAS login page to extract execution token
        service_url = f"{self.base_url}/login/index.php"
        from urllib.parse import quote

        cas_login_url = f"{self.cas_url.rstrip('/')}/login?service={quote(service_url)}"
        if self.debug:
            print(f"[DEBUG] GET {cas_login_url}")
        resp = self.session.get(cas_login_url)
        if self.debug:
            print(f"[DEBUG] Response {resp.status_code} {resp.url}")
            print(f"[DEBUG] Response text (first 500 chars): {resp.text[:500]}")
        if resp.status_code != 200:
            raise LoginError(f"Failed to load CAS login page: {resp.status_code}")
        # Try to match both single and double quotes for value
        cas_id_match = re.search(
            r'name=["\']execution["\']\s+value=["\']([^"\']+)["\']', resp.text
        )
        if not cas_id_match:
            # Fallback: try to match execution value anywhere
            cas_id_match = re.search(
                r'execution[\'"]?\s*value=["\']([^"\']+)["\']', resp.text
            )
        if not cas_id_match:
            if self.debug:
                print("[DEBUG] Could not find execution value in CAS login page.")
            raise LoginError("CAS login ticket not found (no execution value).")
        cas_id = cas_id_match.group(1)
        if self.debug:
            print(f"[DEBUG] CAS execution value: {cas_id}")

        # Step 2: Submit login form with username, password, execution
        payload = {
            "username": self.username,
            "password": self.password,
            "execution": cas_id,
            "_eventId": "submit",
        }
        if self.debug:
            print(f"[DEBUG] POST {cas_login_url} payload={payload}")
        # Keep session cookies in self.session
        resp = self.session.post(cas_login_url, data=payload, allow_redirects=False)
        if self.debug:
            print(f"[DEBUG] Response {resp.status_code} {resp.url}")
            print(f"[DEBUG] Response headers: {resp.headers}")
        if resp.status_code not in (302, 303):
            raise LoginError(
                f"CAS login POST did not redirect. Status: {resp.status_code}"
            )
        location = resp.headers.get("Location")
        if not location:
            if self.debug:
                print("[DEBUG] No Location header after CAS POST.")
            raise LoginError("CAS login failed. No redirect to service with ticket.")
        if self.debug:
            print(f"[DEBUG] Following redirect to {location}")
        # Step 3: Follow redirect to Moodle with CAS ticket (keeping cookies)
        resp2 = self.session.get(location, allow_redirects=True)
        if self.debug:
            print(f"[DEBUG] Response {resp2.status_code} {resp2.url}")
        # Optionally, check if login was successful
        dashboard_url = f"{self.base_url}/my/"
        if self.debug:
            print(f"[DEBUG] GET {dashboard_url}")
        resp3 = self.session.get(dashboard_url)
        if self.debug:
            print(f"[DEBUG] Dashboard response {resp3.status_code} {resp3.url}")
            print(
                f"[DEBUG] Dashboard response text (first 500 chars): {resp3.text[:500]}"
            )
        # Relaxed check: if we get a 200 and the page is not the login form, consider it successful
        if resp3.status_code != 200:
            raise LoginError("CAS login failed: dashboard did not return HTTP 200.")
        # Check for typical login form markers
        if (
            "<form" in resp3.text.lower()
            and ("login" in resp3.text.lower() or "username" in resp3.text.lower())
            and ("password" in resp3.text.lower())
        ):
            raise LoginError(
                "CAS login failed or session not established (login form detected). Please check credentials or CAS configuration."
            )
        # If we get here, the login was successful
        return

    def _get_sesskey(self) -> str:
        """
        Retrieve the Moodle session key (sesskey) for AJAX operations.
        Returns the sesskey as a string.
        """
        dashboard_url = f"{self.base_url}/my/"
        resp = self.session.get(dashboard_url)
        match = re.search(r'"sesskey":"([^"]+)"', resp.text)
        if not match:
            match = re.search(r"M\.cfg\.sesskey\s*=\s*[\"']([^\"']+)[\"']", resp.text)
        if not match:
            raise LoginError("Could not extract sesskey after login.")
        return match.group(1)

    def _get_webservice_token(self) -> Optional[str]:
        """
        Try to obtain a webservice token. It prefers a pre-configured token if available,
        otherwise it attempts to fetch one from the server.

        Returns:
            The token as a string, or None if not available.
        """

        # Prefer a pre-configured token when provided.
        if self.pre_configured_token:
            if self.debug:
                print("[DEBUG] Using pre-configured webservice token.")
            return self.pre_configured_token

        # This will only work if the user has a valid webservice enabled for 'moodle_mobile_app'
        login_data = {
            "username": self.username,
            "password": self.password,
            "service": "moodle_mobile_app",
        }
        url = f"{self.base_url}/login/token.php"
        resp = self.session.post(url, data=login_data)
        if resp.status_code == 200:
            try:
                data = resp.json()
                if "token" in data:
                    return data["token"]
            except Exception:
                pass
        return None


def enable_webservice(
    session: requests.Session,
    base_url: str,
    sesskey: str,
    service_id: int = 1,
    debug: bool = True,
) -> bool:
    """
    Enables a webservice if it exists but is disabled (USE WITH CAUTION).

    Args:
        session: An authenticated requests.Session object.
        base_url: The base URL of the Moodle instance.
        sesskey: The session key for form submissions.
        service_id: The ID of the webservice to enable (default is 1 for 'Moodle mobile web service').
        debug: If True, print debug information.

    Returns:
        True if the operation seems successful.

    Raises:
        LoginError: If the operation fails.
    """
    url = f"{base_url}/admin/webservice/service.php"
    data = {
        "id": service_id,
        "sesskey": sesskey,
        "_qf__external_service_form": 1,
        "enabled": 1,
        "downloadfiles": 1,
        "uploadfiles": 1,
        "submitbutton": "Save changes",
    }
    resp = session.post(url, data=data)

    if debug:
        print(f"[DEBUG] POST {url} -> {resp.status_code}")
        if resp.status_code != 200:
            print(f"[DEBUG] Response text (first 500 chars): {resp.text[:500]}")

    # print(resp.text)

    if resp.status_code != 200:
        raise LoginError(
            "Failed to enable the webservice. Check user permissions and if you are logged in as admin."
        )

    return True


def login(
    url: str,
    username: str,
    password: str,
    use_cas: bool = False,
    cas_url: Optional[str] = None,
    pre_configured_token: Optional[str] = None,
    debug: bool = False,
) -> requests.Session:
    """Authenticate a user and return an active session.

    Args:
        url: Base URL of the Moodle instance.
        username: Username to authenticate.
        password: Password for the user.
        use_cas: Whether to use CAS authentication.
        cas_url: URL of the CAS server.
        pre_configured_token: Optional pre-created webservice token.
        debug: Enable verbose debugging output.

    Returns:
        An authenticated ``requests.Session`` instance.
    """
    auth = MoodleAuth(
        base_url=url,
        username=username,
        password=password,
        use_cas=use_cas,
        cas_url=cas_url,
        pre_configured_token=pre_configured_token,
        debug=debug,
    )
    session = auth.login()
    # Attach tokens to session for convenience
    session.sesskey = getattr(auth, "sesskey", None)
    session.webservice_token = getattr(auth, "webservice_token", None)
    return session


__all__ = ["LoginError", "MoodleAuth", "enable_webservice", "login"]
