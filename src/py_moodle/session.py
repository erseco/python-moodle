"""Reusable, thread-safe Moodle session.

Lazy login on first access and cache sessions per environment.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

import requests

if TYPE_CHECKING:
    from .settings import Settings

from typing import Any, Dict, Optional

from .auth import LoginError, login
from .compat import DEFAULT_COMPATIBILITY, get_session_compatibility
from .config import DEFAULT_REQUEST_TIMEOUT
from .http import MoodleHttpError, MoodleWebserviceError, request_webservice


class MoodleSessionError(RuntimeError):
    """Raised when we cannot obtain token or sesskey."""


class MoodleSession:
    """Reusable and thread-safe Moodle session manager."""

    _lock = threading.Lock()
    _cache: dict[str, "MoodleSession"] = {}

    def __init__(self, settings: "Settings") -> None:
        """Initialize a session wrapper for the given settings."""
        self.settings = settings
        self._session: requests.Session | None = None
        self._sesskey: str | None = None
        self._token: str | None = None
        self._compatibility = DEFAULT_COMPATIBILITY
        self._moodle_version = None

    # ------------- internal helpers -------------
    def _login(self) -> None:
        """Perform the actual login once."""
        if self._session is not None:
            return  # already logged in

        with self._lock:
            if self._session is not None:
                return  # another thread won the race

            session = login(
                self.settings.url,
                self.settings.username,
                self.settings.password,
                use_cas=self.settings.use_cas,
                cas_url=self.settings.cas_url,
                pre_configured_token=self.settings.webservice_token,
                debug=False,
            )
            self._token = getattr(session, "webservice_token", None)
            self._sesskey = getattr(session, "sesskey", None)
            self._compatibility = get_session_compatibility(session)
            self._moodle_version = getattr(session, "moodle_version", None)

            # Fallback extraction if sesskey was not attached by login()
            if not self._sesskey:
                resp = session.get(
                    f"{self.settings.url}/my/",
                    timeout=DEFAULT_REQUEST_TIMEOUT,
                )
                self._sesskey = self._compatibility.extract_sesskey(resp.text)

            # Validate we have at least one usable token
            if not self._token and not self._sesskey:
                raise MoodleSessionError(
                    "Authenticated to Moodle, but no webservice token or sesskey "
                    "was available. Confirm the Moodle mobile web service is "
                    "enabled for this user, or review CAS/session configuration."
                )

            self._session = session

    # ------------- public API -------------
    @property
    def session(self) -> requests.Session:
        """Return the authenticated requests.Session (login once)."""
        if self._session is None:
            self._login()
        return self._session

    @property
    def sesskey(self) -> str:
        """Return the session key (guaranteed to exist)."""
        self._login()
        assert self._sesskey is not None  # ensured by _login
        return self._sesskey

    @property
    def token(self) -> str | None:
        """Return the webservice token, or None if not available."""
        self._login()
        return self._token

    @property
    def compatibility(self):
        """Return the compatibility strategy selected for the current session."""
        self._login()
        return self._compatibility

    @property
    def moodle_version(self):
        """Return detected Moodle version information when available."""
        self._login()
        return self._moodle_version

    def call(
        self,
        wsfunction: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Makes a call to the Moodle webservice API."""
        if not self.token:
            raise LoginError(
                "Cannot call Moodle webservice "
                f"{wsfunction!r} without a webservice token. Use a pre-configured "
                "token or log in with a user allowed to access the Moodle mobile "
                "web service."
            )

        if params is None:
            params = {}

        try:
            return request_webservice(
                self.session,
                self.settings.url,
                wsfunction,
                params,
                token=self.token,
                timeout=DEFAULT_REQUEST_TIMEOUT,
            )
        except MoodleWebserviceError as exc:
            raise MoodleSessionError(
                f"Moodle API call {wsfunction!r} failed: "
                f"{exc.args[0] if exc.args else 'Unknown error'} "
                f"(errorcode: {exc.errorcode or 'N/A'}, "
                f"exception: {exc.moodle_exception or 'N/A'})"
            ) from exc
        except MoodleHttpError as exc:
            raise MoodleSessionError(
                f"Moodle API call {wsfunction!r} failed: {exc}"
            ) from exc

    # ------------- factory -------------
    @classmethod
    def get(cls, env: str | None = None) -> "MoodleSession":
        """Return or create a cached session for the given environment.

        Args:
            env: Environment key (e.g., ``"local"`` or ``"staging"``).

        Returns:
            MoodleSession: Cached session instance.
        """
        from .settings import load_settings

        env_key = (env or "local").lower()
        if env_key not in cls._cache:
            cls._cache[env_key] = cls(load_settings(env_key))
        return cls._cache[env_key]


__all__ = ["MoodleSessionError", "MoodleSession"]
