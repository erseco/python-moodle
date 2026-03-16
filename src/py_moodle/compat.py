"""Compatibility helpers for Moodle version-specific HTML parsing."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Optional

import requests
from bs4 import BeautifulSoup, Tag

from .config import DEFAULT_REQUEST_TIMEOUT


@dataclass(frozen=True)
class MoodleVersion:
    """Normalized Moodle version information."""

    raw: str
    major: Optional[int] = None
    minor: Optional[int] = None
    patch: Optional[int] = None
    source: str = "unknown"


@dataclass(frozen=True)
class MoodleCompatibilityContext:
    """Detected Moodle compatibility information."""

    version: MoodleVersion
    strategy: "BaseCompatibilityStrategy"


class BaseCompatibilityStrategy:
    """Base strategy for Moodle HTML compatibility helpers."""

    version_range = "generic"
    login_token_selectors = (
        'input[name="logintoken"]',
        'input[name="login_token"]',
    )
    sesskey_patterns = (
        r'"sesskey":"([^"]+)"',
        r"M\.cfg\.sesskey\s*=\s*[\"']([^\"']+)[\"']",
        r'["\']sesskey["\']\s*:\s*["\']([^"\']+)["\']',
    )
    error_selectors = (
        ".error",
        ".errormessage",
        ".alert-danger",
        'div[data-fieldtype="error"]',
        ".notifyproblem",
    )
    modedit_form_selectors = (
        'form[action*="modedit.php"]',
        "form#mform1",
        'form[id^="mform"]',
    )
    user_fullname_selectors = (
        ".usermenu .usertext",
        '[data-region="usermenu"] .usertext',
        '[data-region="usermenu"] .logininfo',
        ".logininfo a:last-of-type",
    )
    folder_file_selectors = (
        '.folder_tree a[href*="/pluginfile.php/"]',
        '.foldertree a[href*="/pluginfile.php/"]',
        'a[href*="/pluginfile.php/"]',
    )

    def extract_login_token(self, html: str) -> str:
        """Extract the login token from a Moodle login page."""
        soup = BeautifulSoup(html, "lxml")
        for selector in self.login_token_selectors:
            token_input = soup.select_one(selector)
            if token_input and token_input.get("value"):
                return token_input["value"]
        return ""

    def extract_sesskey(self, html: str) -> Optional[str]:
        """Extract a sesskey from Moodle HTML or embedded JavaScript."""
        for pattern in self.sesskey_patterns:
            match = re.search(pattern, html)
            if match:
                return match.group(1)
        return None

    def extract_error_message(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract a visible Moodle error message from a response page."""
        for selector in self.error_selectors:
            error_node = soup.select_one(selector)
            if error_node:
                message = error_node.get_text(strip=True)
                if message:
                    return message
        return None

    def find_modedit_form(self, soup: BeautifulSoup) -> Optional[Tag]:
        """Locate the module edit form in a Moodle page."""
        for selector in self.modedit_form_selectors:
            form = soup.select_one(selector)
            if form is not None:
                return form
        return None

    def extract_user_fullname(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract the current user's visible fullname from the dashboard."""
        for selector in self.user_fullname_selectors:
            node = soup.select_one(selector)
            if node:
                fullname = node.get_text(" ", strip=True)
                if fullname:
                    return fullname
        return None

    def extract_folder_filenames(self, soup: BeautifulSoup) -> list[str]:
        """Extract filenames from a folder activity page."""
        filenames: list[str] = []
        for selector in self.folder_file_selectors:
            for link in soup.select(selector):
                href = link.get("href", "")
                if "pluginfile.php" not in href:
                    continue
                filename = link.get_text(strip=True)
                if filename:
                    filenames.append(filename)
            if filenames:
                break
        return sorted(set(filenames))


class LegacyCompatibilityStrategy(BaseCompatibilityStrategy):
    """Compatibility strategy for older Moodle 3.x layouts."""

    version_range = "3.x"
    user_fullname_selectors = (
        ".logininfo a:last-of-type",
        '[data-region="usermenu"] .logininfo',
        ".usermenu .usertext",
    )
    folder_file_selectors = (
        '.foldertree a[href*="/pluginfile.php/"]',
        '.folder_tree a[href*="/pluginfile.php/"]',
        'a[href*="/pluginfile.php/"]',
    )


class ModernCompatibilityStrategy(BaseCompatibilityStrategy):
    """Compatibility strategy for Moodle 4.x and newer layouts."""

    version_range = "4.x+"
    user_fullname_selectors = (
        '[data-region="usermenu"] .usertext',
        ".usermenu .usertext",
        '[data-region="usermenu"] .logininfo',
        ".logininfo a:last-of-type",
    )


DEFAULT_COMPATIBILITY = ModernCompatibilityStrategy()
LEGACY_COMPATIBILITY = LegacyCompatibilityStrategy()


def parse_moodle_version(
    raw_version: Optional[str], source: str = "unknown"
) -> MoodleVersion:
    """Parse Moodle version text into a normalized structure.

    Args:
        raw_version: Moodle release text, such as
            ``"4.5.2+ (Build: 20241001)"``.
        source: Human-readable description of where the version was found.

    Returns:
        MoodleVersion: Parsed version information. When no numeric version can
        be extracted, the returned object keeps the raw text and leaves the
        numeric fields unset.
    """
    cleaned = (raw_version or "").strip()
    match = re.search(r"(\d+)(?:\.(\d+))?(?:\.(\d+))?", cleaned)
    if not match:
        return MoodleVersion(raw=cleaned or "unknown", source=source)
    major, minor, patch = match.groups()
    return MoodleVersion(
        raw=cleaned,
        major=int(major),
        minor=int(minor) if minor is not None else None,
        patch=int(patch) if patch is not None else None,
        source=source,
    )


def extract_version_from_dashboard(html: str) -> MoodleVersion:
    """Extract Moodle version information from dashboard HTML.

    Args:
        html: Rendered Moodle dashboard HTML.

    Returns:
        MoodleVersion: Version parsed from dashboard metadata or embedded
        JavaScript configuration. If no version marker is found, returns an
        ``unknown`` version placeholder.
    """
    soup = BeautifulSoup(html, "lxml")
    generator = soup.find("meta", attrs={"name": re.compile("^generator$", re.I)})
    if generator and generator.get("content"):
        version = parse_moodle_version(generator["content"], source="html-meta")
        if version.major is not None:
            return version

    patterns = (
        (r'"release"\s*:\s*"([^"]+)"', "html-js"),
        (r"M\.cfg\.release\s*=\s*[\"']([^\"']+)[\"']", "html-js"),
    )
    for pattern, source in patterns:
        match = re.search(pattern, html)
        if match:
            version = parse_moodle_version(match.group(1), source=source)
            if version.major is not None:
                return version

    return MoodleVersion(raw="unknown", source="html")


def get_strategy_for_version(version: MoodleVersion) -> BaseCompatibilityStrategy:
    """Return the selector strategy matching a Moodle version.

    Args:
        version: Detected Moodle version information.

    Returns:
        BaseCompatibilityStrategy: Legacy selectors for Moodle 3.x and modern
        selectors for Moodle 4.x and newer releases.
    """
    if version.major is not None and version.major < 4:
        return LEGACY_COMPATIBILITY
    return DEFAULT_COMPATIBILITY


def detect_moodle_compatibility(
    session: requests.Session, base_url: str, token: Optional[str] = None
) -> MoodleCompatibilityContext:
    """Detect the Moodle version and return the matching strategy.

    Args:
        session: Authenticated Moodle session.
        base_url: Base URL of the Moodle instance.
        token: Optional webservice token. When available, detection first tries
            ``core_webservice_get_site_info`` before falling back to dashboard
            HTML probing.

    Returns:
        MoodleCompatibilityContext: Detected version metadata together with the
        strategy that should be used for selector and parsing fallbacks.
    """
    if token is None:
        token = getattr(session, "webservice_token", None)

    version = MoodleVersion(raw="unknown")
    if token:
        request_params = {
            "moodlewsrestformat": "json",
            "wsfunction": "core_webservice_get_site_info",
            "wstoken": token,
        }
        try:
            response = session.post(
                f"{base_url}/webservice/rest/server.php",
                params=request_params,
                timeout=DEFAULT_REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            data = response.json()
            if isinstance(data, dict) and "exception" not in data:
                release = data.get("release") or data.get("version")
                version = parse_moodle_version(release, source="webservice")
        except (requests.RequestException, ValueError, TypeError, json.JSONDecodeError):
            pass

    if version.major is None:
        try:
            response = session.get(
                f"{base_url}/my/",
                timeout=DEFAULT_REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            version = extract_version_from_dashboard(response.text)
        except requests.RequestException:
            pass

    return MoodleCompatibilityContext(
        version=version,
        strategy=get_strategy_for_version(version),
    )


def get_session_compatibility(session: requests.Session) -> BaseCompatibilityStrategy:
    """Return the compatibility strategy attached to a session.

    Args:
        session: Requests session that may carry compatibility metadata.

    Returns:
        BaseCompatibilityStrategy: Strategy attached during login when present,
        otherwise a version-derived fallback, or the default modern strategy
        when no metadata is available.
    """
    compatibility = getattr(session, "moodle_compat", None)
    if compatibility is not None:
        return compatibility
    version = getattr(session, "moodle_version", None)
    if isinstance(version, MoodleVersion):
        return get_strategy_for_version(version)
    return DEFAULT_COMPATIBILITY


__all__ = [
    "BaseCompatibilityStrategy",
    "DEFAULT_COMPATIBILITY",
    "LegacyCompatibilityStrategy",
    "ModernCompatibilityStrategy",
    "MoodleCompatibilityContext",
    "MoodleVersion",
    "detect_moodle_compatibility",
    "extract_version_from_dashboard",
    "get_session_compatibility",
    "get_strategy_for_version",
    "parse_moodle_version",
]
