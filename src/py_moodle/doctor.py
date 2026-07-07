"""End-to-end diagnostics for a configured Moodle environment.

Composes the existing configuration, session, compatibility, and site-info
building blocks into a single, read-only health report for a Moodle
environment. Never mutates remote state and never surfaces raw secret
values (password, webservice token, sesskey) in any check message.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

import requests

from py_moodle.config import DEFAULT_SCRAPE_TIMEOUT
from py_moodle.session import MoodleSession
from py_moodle.settings import Settings, load_settings
from py_moodle.site import SiteInfo, get_site_info

#: Names of checks that are allowed to produce CheckStatus.FAIL. Every other
#: check can only ever result in PASS or WARN.
CRITICAL_CHECKS = frozenset({"base_url", "login", "sesskey"})


class CheckStatus(str, Enum):
    """Outcome of a single diagnostic check."""

    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"


@dataclass
class CheckResult:
    """Result of a single diagnostic check.

    Attributes:
        name: Short machine-friendly identifier (e.g. "login").
        status: One of CheckStatus.PASS/WARN/FAIL.
        message: Human-readable detail. MUST NOT contain raw secret
            values (password, webservice token, sesskey).
    """

    name: str
    status: CheckStatus
    message: str


@dataclass
class DoctorReport:
    """Aggregate result of running all doctor checks for one environment."""

    env: str
    checks: List[CheckResult] = field(default_factory=list)

    @property
    def exit_code(self) -> int:
        """Return 1 if any check FAILed, else 0."""
        return 1 if any(c.status == CheckStatus.FAIL for c in self.checks) else 0

    def as_dicts(self) -> List[dict]:
        """Return checks as plain dicts for JSON/YAML rendering."""
        return [
            {"name": c.name, "status": c.status.value, "message": c.message}
            for c in self.checks
        ]


def _add(report: DoctorReport, name: str, status: CheckStatus, message: str) -> None:
    """Append a CheckResult to the report, enforcing the critical-check rule."""
    if status == CheckStatus.FAIL and name not in CRITICAL_CHECKS:
        # Defensive guard: only the checks listed in CRITICAL_CHECKS may FAIL.
        status = CheckStatus.WARN
    report.checks.append(CheckResult(name=name, status=status, message=message))


def _check_base_url(report: DoctorReport, settings: Settings) -> None:
    """Check that the configured base URL is reachable (critical)."""
    probe = requests.Session()
    try:
        response = probe.get(settings.url, timeout=DEFAULT_SCRAPE_TIMEOUT)
        if response.status_code < 500:
            _add(
                report,
                "base_url",
                CheckStatus.PASS,
                f"Base URL reachable (HTTP {response.status_code}).",
            )
        else:
            _add(
                report,
                "base_url",
                CheckStatus.FAIL,
                f"Base URL returned a server error (HTTP {response.status_code}).",
            )
    except requests.RequestException as exc:
        _add(
            report,
            "base_url",
            CheckStatus.FAIL,
            f"Base URL unreachable: {type(exc).__name__}.",
        )


def _redact_secrets(text: str, settings: Settings) -> str:
    """Scrub known secret values for ``settings`` out of ``text``.

    Defensive measure for check messages that embed an arbitrary
    exception's ``str()``: even though today's login/auth exceptions do not
    happen to include the raw password or token, nothing guarantees a
    future change in the login flow won't. This ensures the module's own
    "never surfaces raw secret values" guarantee holds regardless.

    Args:
        text: Message text that may contain a secret value verbatim.
        settings: Settings whose password/webservice_token must never
            appear in ``text``.

    Returns:
        str: ``text`` with any known secret value replaced by a marker.
    """
    for secret in (settings.password, settings.webservice_token):
        if secret:
            text = text.replace(secret, "***REDACTED***")
    return text


def _check_login(
    report: DoctorReport, env: str, settings: Settings
) -> Optional[MoodleSession]:
    """Check that login succeeds (critical). Returns the session on success."""
    try:
        session = MoodleSession.get(env)
        session.session  # Trigger (or validate) the lazy login.
        _add(report, "login", CheckStatus.PASS, "Login succeeded.")
        return session
    except Exception as exc:
        message = _redact_secrets(
            f"Login failed: {type(exc).__name__}: {exc}", settings
        )
        _add(report, "login", CheckStatus.FAIL, message)
        return None


def _check_cas(report: DoctorReport, settings: Settings) -> None:
    """Report whether CAS/SSO is configured for this environment (informational)."""
    if settings.use_cas:
        _add(
            report,
            "cas",
            CheckStatus.PASS,
            "CAS/SSO login is configured for this environment.",
        )
    else:
        _add(
            report,
            "cas",
            CheckStatus.PASS,
            "Standard Moodle login is configured (no CAS/SSO).",
        )


def _check_moodle_version(
    report: DoctorReport, session: Optional[MoodleSession]
) -> None:
    """Check that the Moodle version could be detected (optional)."""
    if session is None:
        _add(
            report,
            "moodle_version",
            CheckStatus.WARN,
            "Skipped: login did not succeed.",
        )
        return
    try:
        version = session.moodle_version
    except Exception as exc:
        _add(
            report,
            "moodle_version",
            CheckStatus.WARN,
            f"Moodle version undetectable: {type(exc).__name__}.",
        )
        return

    raw = getattr(version, "raw", None)
    if raw and raw != "unknown":
        _add(
            report,
            "moodle_version",
            CheckStatus.PASS,
            f"Moodle version detected: {raw}.",
        )
    else:
        _add(
            report,
            "moodle_version",
            CheckStatus.WARN,
            "Moodle version could not be determined.",
        )


def _check_sesskey(report: DoctorReport, session: Optional[MoodleSession]) -> None:
    """Check that a sesskey is available (critical)."""
    if session is None:
        _add(
            report,
            "sesskey",
            CheckStatus.WARN,
            "Skipped: login did not succeed.",
        )
        return
    try:
        sesskey = session.sesskey
        if sesskey:
            _add(
                report,
                "sesskey",
                CheckStatus.PASS,
                f"sesskey available (length {len(sesskey)}).",
            )
        else:
            _add(
                report,
                "sesskey",
                CheckStatus.FAIL,
                "sesskey unavailable after a successful login.",
            )
    except Exception as exc:
        _add(
            report,
            "sesskey",
            CheckStatus.FAIL,
            f"sesskey unavailable: {type(exc).__name__}.",
        )


def _check_webservice_token(
    report: DoctorReport, settings: Settings, session: Optional[MoodleSession]
) -> None:
    """Check that a webservice token is available (optional)."""
    token = None
    if session is not None:
        try:
            token = session.token
        except Exception:
            token = None
    if not token:
        token = settings.webservice_token

    if token:
        _add(
            report,
            "webservice_token",
            CheckStatus.PASS,
            f"Webservice token available (length {len(token)}).",
        )
    else:
        _add(
            report,
            "webservice_token",
            CheckStatus.WARN,
            "No webservice token available; webservice-dependent checks "
            "will be limited.",
        )


def _check_webservice(
    report: DoctorReport, session: Optional[MoodleSession]
) -> Optional[SiteInfo]:
    """Check that the webservice is reachable (optional). Returns SiteInfo."""
    if session is None:
        _add(
            report,
            "webservice",
            CheckStatus.WARN,
            "Skipped: login did not succeed.",
        )
        return None

    try:
        token = session.token
    except Exception:
        token = None

    if not token:
        _add(
            report,
            "webservice",
            CheckStatus.WARN,
            "Skipped: no webservice token available.",
        )
        return None

    try:
        site_info = get_site_info(session)
        _add(
            report,
            "webservice",
            CheckStatus.PASS,
            f"Webservice reachable (Moodle release {site_info.release}).",
        )
        return site_info
    except Exception as exc:
        _add(
            report,
            "webservice",
            CheckStatus.WARN,
            f"Webservice call failed: {type(exc).__name__}.",
        )
        return None


def _check_upload_endpoint(report: DoctorReport, settings: Settings) -> None:
    """Check that the upload endpoint responds (optional)."""
    probe = requests.Session()
    upload_url = f"{settings.url.rstrip('/')}/webservice/upload.php"
    try:
        response = probe.head(upload_url, timeout=DEFAULT_SCRAPE_TIMEOUT)
        _add(
            report,
            "upload_endpoint",
            CheckStatus.PASS,
            f"Upload endpoint responded (HTTP {response.status_code}).",
        )
    except requests.RequestException as exc:
        _add(
            report,
            "upload_endpoint",
            CheckStatus.WARN,
            f"Upload endpoint unreachable: {type(exc).__name__}.",
        )


def _check_user_identity(report: DoctorReport, site_info: Optional[SiteInfo]) -> None:
    """Check that the current user's identity is derivable (optional)."""
    if site_info is None:
        _add(
            report,
            "user_identity",
            CheckStatus.WARN,
            "Skipped: site info unavailable.",
        )
        return
    if site_info.fullname and site_info.userid:
        _add(
            report,
            "user_identity",
            CheckStatus.PASS,
            f"Current user: {site_info.fullname} (id={site_info.userid}).",
        )
    else:
        _add(
            report,
            "user_identity",
            CheckStatus.WARN,
            "Current user identity not derivable from site info.",
        )


def _check_capabilities(report: DoctorReport, site_info: Optional[SiteInfo]) -> None:
    """Check that relevant capabilities are derivable (optional)."""
    if site_info is None:
        _add(
            report,
            "capabilities",
            CheckStatus.WARN,
            "Skipped: site info unavailable.",
        )
        return
    role = "site administrator" if site_info.userissiteadmin else "standard user"
    _add(
        report,
        "capabilities",
        CheckStatus.PASS,
        f"Current user capability level: {role}.",
    )


def _check_max_upload_size(report: DoctorReport, site_info: Optional[SiteInfo]) -> None:
    """Check that the max upload size is derivable (optional)."""
    if site_info is None:
        _add(
            report,
            "max_upload_size",
            CheckStatus.WARN,
            "Skipped: site info unavailable.",
        )
        return
    size = site_info.usermaxuploadfilesize
    if isinstance(size, int):
        _add(
            report,
            "max_upload_size",
            CheckStatus.PASS,
            f"Max upload size: {size} bytes.",
        )
    else:
        _add(
            report,
            "max_upload_size",
            CheckStatus.WARN,
            "Max upload size not derivable from site info.",
        )


def _check_mobile_webservice(
    report: DoctorReport, site_info: Optional[SiteInfo]
) -> None:
    """Check that the mobile web service appears enabled (optional)."""
    if site_info is None:
        _add(
            report,
            "mobile_webservice",
            CheckStatus.WARN,
            "Skipped: site info unavailable.",
        )
        return
    if site_info.functions:
        _add(
            report,
            "mobile_webservice",
            CheckStatus.PASS,
            "Mobile web service appears enabled "
            f"({len(site_info.functions)} functions available).",
        )
    else:
        _add(
            report,
            "mobile_webservice",
            CheckStatus.WARN,
            "No web service functions detected; the mobile web service may "
            "be disabled. Run 'py-moodle admin enable-webservice' if you "
            "have administrator rights.",
        )


def run_diagnostics(env: str) -> DoctorReport:
    """Run all doctor checks for a Moodle environment.

    Args:
        env: Environment key passed to load_settings/MoodleSession.get.

    Returns:
        DoctorReport: Aggregate report. Individual checks never raise;
        each failure is captured as a CheckResult with status FAIL/WARN.

    Raises:
        ValueError: If load_settings(env) cannot resolve required
            configuration (propagated so the CLI can map it to exit
            code 2, distinct from a failed check).
    """
    settings = load_settings(env)
    report = DoctorReport(env=settings.env_name)

    _check_base_url(report, settings)
    session = _check_login(report, env, settings)
    _check_cas(report, settings)
    _check_moodle_version(report, session)
    _check_sesskey(report, session)
    _check_webservice_token(report, settings, session)
    site_info = _check_webservice(report, session)
    _check_upload_endpoint(report, settings)
    _check_user_identity(report, site_info)
    _check_capabilities(report, site_info)
    _check_max_upload_size(report, site_info)
    _check_mobile_webservice(report, site_info)

    return report


__all__ = [
    "CheckStatus",
    "CheckResult",
    "DoctorReport",
    "CRITICAL_CHECKS",
    "run_diagnostics",
]
