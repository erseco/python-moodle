"""Unit tests for the ``doctor`` diagnostics module and CLI command."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import requests
import yaml
from typer.testing import CliRunner

from py_moodle.session import MoodleSession, MoodleSessionError
from py_moodle.settings import Settings

FAKE_PASSWORD = "s3cr3t-pw-fake"
FAKE_TOKEN = "tok3n-fake-value"
FAKE_SESSKEY = "sesskey-fake-abc123"


def _make_settings(**overrides) -> Settings:
    """Build a fake Settings instance for tests.

    Args:
        **overrides: Fields to override on top of the sane defaults.

    Returns:
        Settings: A fully populated fake settings object.
    """
    defaults = dict(
        env_name="test",
        url="https://moodle.example.test",
        username="doctor-user",
        password=FAKE_PASSWORD,
        use_cas=False,
        cas_url=None,
        webservice_token=FAKE_TOKEN,
    )
    defaults.update(overrides)
    return Settings(**defaults)


def _make_site_info_payload(**overrides) -> dict:
    """Build a canned ``core_webservice_get_site_info`` response.

    Args:
        **overrides: Fields to override on top of the sane defaults.

    Returns:
        dict: Payload shaped like the real Moodle webservice response.
    """
    payload = dict(
        sitename="Test Site",
        username="doctor-user",
        firstname="Doc",
        lastname="Tor",
        fullname="Doc Tor",
        lang="en",
        userid=2,
        siteurl="https://moodle.example.test",
        userpictureurl="https://moodle.example.test/pic.jpg",
        functions=[{"name": "core_webservice_get_site_info", "version": "1.0"}],
        downloadfiles=1,
        uploadfiles=1,
        release="4.3.2+ (Build: 20231201)",
        version="2023100901",
        mobilecssurl="",
        advancedfeatures=[],
        usercanmanageownfiles=True,
        userquota=100000000,
        usermaxuploadfilesize=20971520,
        userhomepage=0,
        userprivateaccesskey="private-access-key-fake",
        siteid=1,
        sitecalendartype="gregorian",
        usercalendartype="gregorian",
        userissiteadmin=True,
        theme="boost",
        limitconcurrentlogins=0,
        policyagreed=1,
    )
    payload.update(overrides)
    return payload


def _make_mocked_session(**overrides) -> MagicMock:
    """Build a MagicMock standing in for a successfully logged-in MoodleSession.

    Args:
        **overrides: ``sesskey``, ``token``, ``moodle_version``, or
            ``site_info_payload`` to override the defaults.

    Returns:
        MagicMock: A mock exposing the same surface as ``MoodleSession``.
    """
    session = MagicMock(spec=MoodleSession)
    session.session = MagicMock()
    session.sesskey = overrides.get("sesskey", FAKE_SESSKEY)
    session.token = overrides.get("token", FAKE_TOKEN)
    session.moodle_version = overrides.get(
        "moodle_version",
        SimpleNamespace(raw="4.3.2", major=4, minor=3, patch=2, source="webservice"),
    )
    session.call.return_value = overrides.get(
        "site_info_payload", _make_site_info_payload()
    )
    return session


@pytest.fixture
def fake_settings():
    """Return a fake Settings instance with a fake password and token."""
    return _make_settings()


@pytest.fixture
def mocked_session():
    """Return a MagicMock standing in for a successfully logged-in session."""
    return _make_mocked_session()


@pytest.fixture
def patch_probes(monkeypatch):
    """Patch requests.Session.get/.head to return a canned 200 response."""

    def _apply(get_response=None, head_response=None, get_error=None, head_error=None):
        fake_response = MagicMock(status_code=200)

        def fake_get(self, *args, **kwargs):
            if get_error is not None:
                raise get_error
            return get_response or fake_response

        def fake_head(self, *args, **kwargs):
            if head_error is not None:
                raise head_error
            return head_response or fake_response

        monkeypatch.setattr(requests.Session, "get", fake_get)
        monkeypatch.setattr(requests.Session, "head", fake_head)

    return _apply


# ---------------------------------------------------------------------------
# run_diagnostics() library-level tests
# ---------------------------------------------------------------------------


def test_run_diagnostics_all_pass(
    monkeypatch, fake_settings, mocked_session, patch_probes
):
    """All checks should pass when every dependency behaves correctly."""
    monkeypatch.setattr("py_moodle.doctor.load_settings", lambda env: fake_settings)
    monkeypatch.setattr(MoodleSession, "get", MagicMock(return_value=mocked_session))
    patch_probes()

    from py_moodle.doctor import CheckStatus, run_diagnostics

    report = run_diagnostics("test")

    assert report.exit_code == 0
    assert report.checks, "Expected at least one check to have run."
    assert not any(c.status == CheckStatus.FAIL for c in report.checks)


def test_run_diagnostics_warnings_only(monkeypatch, patch_probes):
    """Missing token and an unreachable upload probe should degrade to WARN only."""
    settings = _make_settings(webservice_token=None)
    session = _make_mocked_session(token=None)

    monkeypatch.setattr("py_moodle.doctor.load_settings", lambda env: settings)
    monkeypatch.setattr(MoodleSession, "get", MagicMock(return_value=session))
    patch_probes(head_error=requests.RequestException("upload probe unreachable"))

    from py_moodle.doctor import CheckStatus, run_diagnostics

    report = run_diagnostics("test")

    assert report.exit_code == 0
    assert not any(c.status == CheckStatus.FAIL for c in report.checks)

    warn_names = {c.name for c in report.checks if c.status == CheckStatus.WARN}
    assert "webservice_token" in warn_names
    assert "upload_endpoint" in warn_names


def test_run_diagnostics_login_failure(monkeypatch, fake_settings, patch_probes):
    """A login failure must be a critical FAIL without blocking other checks."""
    monkeypatch.setattr("py_moodle.doctor.load_settings", lambda env: fake_settings)
    monkeypatch.setattr(
        MoodleSession,
        "get",
        MagicMock(side_effect=MoodleSessionError("bad credentials")),
    )
    patch_probes()

    from py_moodle.doctor import CheckStatus, run_diagnostics

    report = run_diagnostics("test")

    assert report.exit_code == 1

    login_checks = [c for c in report.checks if c.name == "login"]
    assert len(login_checks) == 1
    assert login_checks[0].status == CheckStatus.FAIL

    base_url_checks = [c for c in report.checks if c.name == "base_url"]
    assert len(base_url_checks) == 1
    assert base_url_checks[0].status == CheckStatus.PASS


def test_run_diagnostics_unknown_env_raises():
    """An unresolvable environment should raise ValueError, not be swallowed."""
    from py_moodle.doctor import run_diagnostics

    with pytest.raises(ValueError):
        run_diagnostics("does-not-exist")


# ---------------------------------------------------------------------------
# CLI-level tests
# ---------------------------------------------------------------------------


def test_cli_doctor_unknown_env_exit_code_2():
    """The CLI should map a load_settings ValueError to exit code 2."""
    from py_moodle.cli.app import app

    runner = CliRunner()
    result = runner.invoke(app, ["--env", "does-not-exist-env", "doctor", "run"])

    assert result.exit_code == 2


def test_cli_doctor_json_output_shape(monkeypatch):
    """--output json should produce a list of {name, status, message} dicts."""
    import py_moodle.cli.doctor as doctor_cli
    from py_moodle.cli.app import app
    from py_moodle.doctor import CheckResult, CheckStatus, DoctorReport

    fake_report = DoctorReport(
        env="test",
        checks=[
            CheckResult(name="base_url", status=CheckStatus.PASS, message="ok"),
            CheckResult(name="login", status=CheckStatus.PASS, message="ok"),
        ],
    )
    monkeypatch.setattr(doctor_cli, "run_diagnostics", lambda env: fake_report)

    runner = CliRunner()
    result = runner.invoke(app, ["--env", "test", "doctor", "run", "--output", "json"])

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert isinstance(data, list)
    assert data
    for item in data:
        assert set(item.keys()) == {"name", "status", "message"}


def test_cli_doctor_yaml_output_shape(monkeypatch):
    """--output yaml should also produce a list of check dicts."""
    import py_moodle.cli.doctor as doctor_cli
    from py_moodle.cli.app import app
    from py_moodle.doctor import CheckResult, CheckStatus, DoctorReport

    fake_report = DoctorReport(
        env="test",
        checks=[CheckResult(name="base_url", status=CheckStatus.PASS, message="ok")],
    )
    monkeypatch.setattr(doctor_cli, "run_diagnostics", lambda env: fake_report)

    runner = CliRunner()
    result = runner.invoke(app, ["--env", "test", "doctor", "run", "--output", "yaml"])

    assert result.exit_code == 0
    data = yaml.safe_load(result.output)
    assert data == [{"name": "base_url", "status": "pass", "message": "ok"}]


def test_cli_doctor_exit_code_1_on_failure(monkeypatch):
    """The CLI should exit with code 1 when the report contains a FAIL."""
    import py_moodle.cli.doctor as doctor_cli
    from py_moodle.cli.app import app
    from py_moodle.doctor import CheckResult, CheckStatus, DoctorReport

    fake_report = DoctorReport(
        env="test",
        checks=[CheckResult(name="login", status=CheckStatus.FAIL, message="nope")],
    )
    monkeypatch.setattr(doctor_cli, "run_diagnostics", lambda env: fake_report)

    runner = CliRunner()
    result = runner.invoke(app, ["--env", "test", "doctor", "run"])

    assert result.exit_code == 1


def test_doctor_registered_in_help():
    """The doctor command group should appear in `py-moodle --help`."""
    from py_moodle.cli.app import app

    runner = CliRunner()
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "doctor" in result.output


# ---------------------------------------------------------------------------
# Secret redaction
# ---------------------------------------------------------------------------


def test_doctor_never_prints_secrets(monkeypatch, patch_probes):
    """Neither the fake password nor the fake token may ever appear in output."""
    settings = _make_settings()
    session = _make_mocked_session()

    monkeypatch.setattr("py_moodle.doctor.load_settings", lambda env: settings)
    monkeypatch.setattr(MoodleSession, "get", MagicMock(return_value=session))
    patch_probes()

    from py_moodle.doctor import run_diagnostics

    report = run_diagnostics("test")

    for check in report.checks:
        assert FAKE_PASSWORD not in check.message
        assert FAKE_TOKEN not in check.message

    import py_moodle.cli.doctor as doctor_cli
    from py_moodle.cli.app import app

    monkeypatch.setattr(doctor_cli, "run_diagnostics", lambda env: report)

    runner = CliRunner()
    table_result = runner.invoke(app, ["--env", "test", "doctor", "run"])
    json_result = runner.invoke(
        app, ["--env", "test", "doctor", "run", "--output", "json"]
    )
    yaml_result = runner.invoke(
        app, ["--env", "test", "doctor", "run", "--output", "yaml"]
    )

    for result in (table_result, json_result, yaml_result):
        assert FAKE_PASSWORD not in result.output
        assert FAKE_TOKEN not in result.output
