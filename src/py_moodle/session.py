# src/moodle/session.py
"""Reusable, thread-safe Moodle session.

Lazy login on first access and cache sessions per environment.
"""

import threading
from typing import TYPE_CHECKING

import requests

if TYPE_CHECKING:
    from .settings import Settings

from .auth import login


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

            # Fallback extraction if sesskey was not attached by login()
            if not self._sesskey:
                import re

                resp = session.get(f"{self.settings.url}/my/")
                m = re.search(r'"sesskey":"([a-zA-Z0-9]+)"', resp.text)
                if not m:
                    m = re.search(
                        r"M\.cfg\.sesskey\s*=\s*['\"]([a-zA-Z0-9]+)['\"]", resp.text
                    )
                self._sesskey = m.group(1) if m else None

            # Validate we have at least one usable token
            if not self._token and not self._sesskey:
                raise MoodleSessionError(
                    "Could not obtain webservice token nor sesskey. "
                    "Check REST protocol permissions or CAS config."
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
