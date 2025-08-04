# src/moodle/settings.py
"""Single source of truth for configuration.

Reads environment variables following the pattern
``MOODLE_<ENV>_URL`` / ``USERNAME`` / ``PASSWORD`` and supports
environment-specific CAS URLs and predefined webservice tokens.
"""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Settings:
    """Holds all configuration for a specific Moodle environment."""

    env_name: str
    url: str
    username: str
    password: str
    use_cas: bool
    cas_url: Optional[str]
    webservice_token: Optional[str]


def load_settings(env: Optional[str] = None) -> Settings:
    """Load settings for the requested environment.

    Args:
        env: Environment key (``"local"``, ``"staging"``, ``"prod"``, etc.).
            Falls back to the ``MOODLE_ENV`` variable if omitted.

    Returns:
        Settings: Configuration object populated for the selected environment.

    Raises:
        ValueError: If any required core variable (URL, USERNAME, PASSWORD) is missing.
    """
    env_name = (env or os.getenv("MOODLE_ENV", "local")).lower()
    prefix = f"MOODLE_{env_name.upper()}"

    # --- Load core credentials ---
    required_vars = ("URL", "USERNAME", "PASSWORD")
    values = {}
    for suffix in required_vars:
        key = f"{prefix}_{suffix}"
        value = os.getenv(key)
        if not value:
            raise ValueError(f"Missing required environment variable: {key}")
        values[suffix.lower()] = value

    # --- Load environment-specific CAS URL ---
    cas_url_key = f"{prefix}_CAS_URL"
    cas_url = os.getenv(cas_url_key)
    use_cas = bool(cas_url)

    # --- Load environment-specific pre-defined Webservice Token ---
    ws_token_key = f"{prefix}_WS_TOKEN"
    ws_token = os.getenv(ws_token_key)

    return Settings(
        env_name=env_name,
        url=values["url"],
        username=values["username"],
        password=values["password"],
        use_cas=use_cas,
        cas_url=cas_url,
        webservice_token=ws_token,
    )


__all__ = ["Settings", "load_settings"]
