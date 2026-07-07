# src/moodle/auth.py
"""
Authentication module for Moodle.

Handles session-based login (including support for CAS) and retrieves the session key required for further AJAX requests.
"""

import logging
import re
from typing import Any, Dict, Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests

from .compat import DEFAULT_COMPATIBILITY, detect_moodle_compatibility

#: Logger for authentication diagnostics. The CLI configures this logger's
#: level and stderr handler via ``py_moodle.cli.output.configure_logging``
#: based on the ``--verbose``/``--debug`` flags, keeping diagnostic output
#: on stderr, separate from any machine-readable payload on stdout.
logger = logging.getLogger(__name__)

#: Placeholder used instead of any secret-bearing value in debug logs.
_REDACTED = "***REDACTED***"

#: Query string parameter names that may carry a secret (webservice token,
#: session key, password, or single sign-on ticket) and must be redacted
#: before a URL is logged.
_SECRET_QUERY_PARAMS = {"token", "wstoken", "sesskey", "password", "ticket"}

#: Header names that may carry session/authentication secrets (cookies,
#: bearer tokens) and must be redacted before headers are logged.
_SECRET_HEADER_NAMES = {"set-cookie", "cookie", "authorization"}


def _redact_url(url: Optional[str]) -> Optional[str]:
    """Redact secret-bearing query parameters from a URL before logging.

    Args:
        url: The URL to sanitize, or ``None``.

    Returns:
        The URL with any secret-bearing query parameter value (token,
        wstoken, sesskey, password, ticket) replaced by a redacted
        placeholder. Returns the input unchanged when it has no query
        string, and ``None`` when ``url`` is ``None``.
    """
    if not url or "?" not in url:
        return url
    parsed = urlsplit(url)
    query_pairs = parse_qsl(parsed.query, keep_blank_values=True)
    redacted_pairs = [
        (key, _REDACTED if key.lower() in _SECRET_QUERY_PARAMS else value)
        for key, value in query_pairs
    ]
    redacted_query = urlencode(redacted_pairs)
    return urlunsplit(parsed._replace(query=redacted_query))


def _redact_headers(headers: Any) -> Dict[str, Any]:
    """Return a copy of response/request headers with secrets redacted.

    Args:
        headers: A mapping of header name to value.

    Returns:
        dict: A new dict with sensitive header values (cookies,
        authorization) replaced by a redacted placeholder.
    """
    return {
        key: (_REDACTED if key.lower() in _SECRET_HEADER_NAMES else value)
        for key, value in dict(headers).items()
    }


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
            debug: Retained for backward compatibility with earlier releases
                that printed directly to stdout when this flag was set. All
                diagnostics now go through the stdlib ``logging`` module
                (see the module-level ``logger``), so visibility is
                controlled by the caller's logging configuration instead of
                this flag: the ``py-moodle`` CLI's ``--verbose``/``--debug``
                options configure it automatically (see
                :func:`py_moodle.cli.output.configure_logging`); direct
                (non-CLI) callers should call
                ``logging.basicConfig(level=logging.DEBUG)`` (or configure a
                handler on the ``"py_moodle"`` logger) to see this output.
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
        self.compatibility = DEFAULT_COMPATIBILITY
        self.moodle_version = None

    def login(self) -> requests.Session:
        """Authenticate the user and return a Moodle session.

        Returns:
            requests.Session: Authenticated session with cookies.

        Raises:
            LoginError: If authentication fails.
        """
        logger.info(
            "Logging in to %s (username=%s, use_cas=%s)",
            self.base_url,
            self.username,
            self.use_cas,
        )
        logger.debug(
            "Login: base_url=%s username=%s use_cas=%s cas_url=%s",
            self.base_url,
            self.username,
            self.use_cas,
            self.cas_url,
        )
        if self.use_cas and self.cas_url:
            self._cas_login()
        else:
            self._standard_login()
        # Try to get the sesskey, but don't fail if it's not possible (for pure AJAX)
        try:
            self.sesskey = self._get_sesskey()
            logger.debug("sesskey obtained: %s", _REDACTED if self.sesskey else None)
        except Exception as e:
            logger.debug("Could not obtain sesskey: %s", e)
            self.sesskey = None
        # Try to get webservice token
        try:
            self.webservice_token = self._get_webservice_token()
            logger.debug(
                "webservice_token obtained: %s",
                _REDACTED if self.webservice_token else None,
            )
        except Exception as e:
            logger.debug("Could not obtain webservice token: %s", e)
            self.webservice_token = None
        compatibility_context = detect_moodle_compatibility(
            self.session, self.base_url, token=self.webservice_token
        )
        self.compatibility = compatibility_context.strategy
        self.moodle_version = compatibility_context.version
        logger.debug(
            "Moodle compatibility: version=%s source=%s strategy=%s",
            self.moodle_version.raw,
            self.moodle_version.source,
            self.compatibility.version_range,
        )
        logger.info(
            "Login completed: sesskey=%s webservice_token=%s",
            "yes" if self.sesskey else "no",
            "yes" if self.webservice_token else "no",
        )
        return self.session

    def _standard_login(self):
        """Perform standard Moodle login and set session cookies."""
        login_url = f"{self.base_url}/login/index.php"
        logger.debug("GET %s", login_url)
        resp = self.session.get(login_url)
        logger.debug("Response %s %s", resp.status_code, _redact_url(resp.url))
        logintoken = self.compatibility.extract_login_token(resp.text)

        payload = {
            "username": self.username,
            "password": self.password,
            "logintoken": logintoken,
            "anchor": "",
        }
        # Avoid logging sensitive information such as passwords.
        # Log only non-sensitive fields for debugging.
        logger.debug("POST %s with username=%s", login_url, self.username)
        resp = self.session.post(login_url, data=payload, allow_redirects=True)
        logger.debug("Response %s %s", resp.status_code, _redact_url(resp.url))
        # Authentication failed if redirected back to login page
        if "/login/index.php" in resp.url or "Invalid login" in resp.text:
            raise LoginError(
                "Moodle login failed: invalid username or password. "
                "Verify MOODLE_USERNAME and MOODLE_PASSWORD, and enable CAS "
                "login if your site requires single sign-on."
            )

    def _cas_login(self):
        """
        Perform CAS login flow programmatically (no browser interaction).
        Maintains cookies and follows the CAS ticket flow.
        """
        # Step 1: Get CAS login page to extract execution token
        service_url = f"{self.base_url}/login/index.php"
        from urllib.parse import quote

        cas_login_url = f"{self.cas_url.rstrip('/')}/login?service={quote(service_url)}"
        logger.debug("GET %s", cas_login_url)
        resp = self.session.get(cas_login_url)
        logger.debug("Response %s %s", resp.status_code, _redact_url(resp.url))
        logger.debug("Response length: %d bytes", len(resp.text))
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
            logger.debug("Could not find execution value in CAS login page.")
            raise LoginError("CAS login ticket not found (no execution value).")
        cas_id = cas_id_match.group(1)
        logger.debug("CAS execution value: %s", cas_id)

        # Step 2: Submit login form with username, password, execution
        payload = {
            "username": self.username,
            "password": self.password,
            "execution": cas_id,
            "_eventId": "submit",
        }
        redacted_payload = {
            "username": self.username,
            "password": _REDACTED,
            "execution": cas_id,
            "_eventId": "submit",
        }
        logger.debug("POST %s payload=%s", cas_login_url, redacted_payload)
        # Keep session cookies in self.session
        resp = self.session.post(cas_login_url, data=payload, allow_redirects=False)
        logger.debug("Response %s %s", resp.status_code, _redact_url(resp.url))
        logger.debug("Response headers: %s", _redact_headers(resp.headers))
        if resp.status_code not in (302, 303):
            raise LoginError(
                f"CAS login POST did not redirect. Status: {resp.status_code}"
            )
        location = resp.headers.get("Location")
        if not location:
            logger.debug("No Location header after CAS POST.")
            raise LoginError("CAS login failed. No redirect to service with ticket.")
        logger.debug("Following redirect to %s", _redact_url(location))
        # Step 3: Follow redirect to Moodle with CAS ticket (keeping cookies)
        resp2 = self.session.get(location, allow_redirects=True)
        logger.debug("Response %s %s", resp2.status_code, _redact_url(resp2.url))
        # Optionally, check if login was successful
        dashboard_url = f"{self.base_url}/my/"
        logger.debug("GET %s", dashboard_url)
        resp3 = self.session.get(dashboard_url)
        logger.debug(
            "Dashboard response %s %s", resp3.status_code, _redact_url(resp3.url)
        )
        logger.debug("Dashboard response length: %d bytes", len(resp3.text))
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
        sesskey = self.compatibility.extract_sesskey(resp.text)
        if not sesskey:
            raise LoginError(
                "Moodle login succeeded, but no sesskey was found on the dashboard. "
                "Confirm the account can open the site in a browser and that the "
                "session is not being redirected back to the login page."
            )
        return sesskey

    def _get_webservice_token(self) -> Optional[str]:
        """
        Try to obtain a webservice token. It prefers a pre-configured token if available,
        otherwise it attempts to fetch one from the server.

        Returns:
            The token as a string, or None if not available.
        """

        # Prefer a pre-configured token when provided.
        if self.pre_configured_token:
            logger.debug("Using pre-configured webservice token.")
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
        debug: Retained for backward compatibility; see :class:`MoodleAuth`
            for how diagnostic visibility is now controlled via the stdlib
            ``logging`` module instead. The ``sesskey`` value is never
            logged, and response bodies are not dumped verbatim.

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

    logger.debug("POST %s -> %s", url, resp.status_code)
    if resp.status_code != 200:
        logger.debug("Response length: %d bytes", len(resp.text))

    if resp.status_code != 200:
        raise LoginError(
            "Failed to enable the Moodle webservice. Confirm the current user has "
            "site administration permissions and that the session is still logged in."
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
        debug: See :class:`MoodleAuth`; a convenience for direct (non-CLI)
            library use.

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
    session.moodle_version = getattr(auth, "moodle_version", None)
    session.moodle_compat = getattr(auth, "compatibility", DEFAULT_COMPATIBILITY)
    return session


__all__ = ["LoginError", "MoodleAuth", "enable_webservice", "login"]
