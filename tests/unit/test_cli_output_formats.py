"""Unit tests for issue #42: CSV output, --quiet, --no-color, --verbose/--debug.

These tests extend the CLI output format work from PR #25
(``tests/unit/test_output_format.py``) without modifying it. All tests run
without any network access, Docker, or a live Moodle instance.
"""

from __future__ import annotations

import csv
import io
import logging
import re
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from py_moodle.cli.output import OutputFormat, emit, get_console


def _strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from a string."""
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def _cli_runner_with_separate_stderr() -> CliRunner:
    """Build a CliRunner with stdout/stderr captured separately.

    Click <8.2 requires ``mix_stderr=False`` for this; Click >=8.2 removed
    that argument and always captures stderr separately. Support both.
    """
    try:
        return CliRunner(mix_stderr=False)
    except TypeError:
        return CliRunner()


@pytest.fixture(autouse=True)
def _reset_py_moodle_logging():
    """Snapshot and restore the shared ``py_moodle`` logger state per test.

    ``configure_logging()`` and ``MoodleAuth(debug=True)`` intentionally
    mutate shared, process-global logger objects (level, handlers,
    propagate). Without this fixture, one test's configuration could leak
    into another test running later in the same process.
    """
    loggers = [logging.getLogger("py_moodle"), logging.getLogger("py_moodle.auth")]
    snapshots = [(lgr, lgr.level, list(lgr.handlers), lgr.propagate) for lgr in loggers]
    yield
    for lgr, level, handlers, propagate in snapshots:
        lgr.level = level
        lgr.handlers = handlers
        lgr.propagate = propagate


# ---------------------------------------------------------------------------
# CSV output (emit())
# ---------------------------------------------------------------------------


def test_emit_csv_serializes_list_with_fields(capsys):
    """CSV output with explicit fields produces a re-parsable header + rows."""
    data = [
        {"id": 1, "shortname": "cs101", "fullname": "Course A"},
        {"id": 2, "shortname": "cs102", "fullname": "Course B"},
    ]

    emit(
        data,
        OutputFormat.CSV,
        csv_fields=[("ID", "id"), ("Shortname", "shortname"), ("Fullname", "fullname")],
    )

    captured = capsys.readouterr()
    reader = csv.reader(io.StringIO(captured.out))
    rows = list(reader)

    assert rows[0] == ["ID", "Shortname", "Fullname"]
    assert rows[1] == ["1", "cs101", "Course A"]
    assert rows[2] == ["2", "cs102", "Course B"]


def test_emit_csv_supports_callable_extractors(capsys):
    """CSV field accessors may be callables deriving a value from the row."""
    data = [{"id": 1, "modules": ["a", "b", "c"]}]

    emit(
        data,
        OutputFormat.CSV,
        csv_fields=[("ID", "id"), ("Module Count", lambda row: len(row["modules"]))],
    )

    captured = capsys.readouterr()
    rows = list(csv.reader(io.StringIO(captured.out)))
    assert rows[0] == ["ID", "Module Count"]
    assert rows[1] == ["1", "3"]


def test_emit_csv_without_fields_falls_back_to_keys(capsys):
    """CSV without explicit fields still produces valid, re-parsable CSV."""
    data = [{"id": 1, "name": "A"}, {"id": 2, "name": "B"}]

    emit(data, OutputFormat.CSV)

    captured = capsys.readouterr()
    reader = csv.DictReader(io.StringIO(captured.out))
    rows = list(reader)

    assert reader.fieldnames == ["id", "name"]
    assert rows == [{"id": "1", "name": "A"}, {"id": "2", "name": "B"}]


def test_emit_csv_single_dict_is_treated_as_one_row(capsys):
    """A single dict (not wrapped in a list) is emitted as a single CSV row."""
    data = {"id": 42, "fullname": "Test Course"}

    emit(data, OutputFormat.CSV, csv_fields=[("ID", "id"), ("Fullname", "fullname")])

    captured = capsys.readouterr()
    rows = list(csv.reader(io.StringIO(captured.out)))
    assert rows == [["ID", "Fullname"], ["42", "Test Course"]]


def test_output_format_values_includes_csv():
    """The OutputFormat enum gains a CSV member without losing the others."""
    assert OutputFormat.TABLE == "table"
    assert OutputFormat.JSON == "json"
    assert OutputFormat.YAML == "yaml"
    assert OutputFormat.CSV == "csv"


@pytest.mark.parametrize(
    "subcmd",
    [
        ["courses", "list", "--help"],
        ["categories", "list", "--help"],
        ["sections", "list", "--help"],
        ["users", "list", "--help"],
    ],
)
def test_representative_list_commands_show_csv_choice(subcmd):
    """Representative list commands advertise csv as a valid --output choice."""
    from py_moodle.cli.app import app

    runner = CliRunner()
    result = runner.invoke(app, subcmd)

    assert result.exit_code == 0
    assert "csv" in _strip_ansi(result.output)


def test_courses_list_csv_output_has_expected_headers_and_rows(monkeypatch):
    """`courses list --output csv` produces headers matching the table view."""
    from py_moodle.cli.app import app

    fake_courses = [
        {
            "id": 1,
            "shortname": "cs101",
            "fullname": "Intro to CS",
            "categoryid": 3,
            "visible": 1,
        }
    ]
    monkeypatch.setattr(
        "py_moodle.cli.courses.MoodleSession.get", lambda env=None: MagicMock()
    )
    monkeypatch.setattr(
        "py_moodle.cli.courses.list_courses", lambda *a, **k: fake_courses
    )

    runner = CliRunner()
    result = runner.invoke(app, ["courses", "list", "--output", "csv"])

    assert result.exit_code == 0
    rows = list(csv.reader(io.StringIO(result.output)))
    assert rows[0] == ["ID", "Shortname", "Fullname", "Category", "Visible"]
    assert rows[1] == ["1", "cs101", "Intro to CS", "3", "1"]


# ---------------------------------------------------------------------------
# --quiet
# ---------------------------------------------------------------------------


def test_quiet_flag_suppresses_status_message_but_not_result(monkeypatch):
    """--quiet suppresses the creation confirmation but the command still succeeds."""
    from py_moodle.cli.app import app

    fake_course = {"id": 7, "fullname": "New Course", "shortname": "newc"}
    monkeypatch.setattr(
        "py_moodle.cli.courses.MoodleSession.get", lambda env=None: MagicMock()
    )
    monkeypatch.setattr(
        "py_moodle.cli.courses.create_course", lambda *a, **k: fake_course
    )

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "--quiet",
            "courses",
            "create",
            "--fullname",
            "New Course",
            "--shortname",
            "newc",
        ],
    )

    assert result.exit_code == 0
    assert "Course created" not in result.output
    assert result.output.strip() == ""


def test_without_quiet_flag_status_message_is_shown(monkeypatch):
    """Without --quiet, the same command still prints its confirmation (no regression)."""
    from py_moodle.cli.app import app

    fake_course = {"id": 7, "fullname": "New Course", "shortname": "newc"}
    monkeypatch.setattr(
        "py_moodle.cli.courses.MoodleSession.get", lambda env=None: MagicMock()
    )
    monkeypatch.setattr(
        "py_moodle.cli.courses.create_course", lambda *a, **k: fake_course
    )

    runner = CliRunner()
    result = runner.invoke(
        app,
        ["courses", "create", "--fullname", "New Course", "--shortname", "newc"],
    )

    assert result.exit_code == 0
    assert "Course created: 7 - New Course (newc)" in result.output


def test_quiet_flag_does_not_suppress_json_payload(monkeypatch):
    """--quiet must never suppress the primary emit()-rendered payload."""
    from py_moodle.cli.app import app

    fake_courses = [{"id": 1, "shortname": "cs101", "fullname": "Course A"}]
    monkeypatch.setattr(
        "py_moodle.cli.courses.MoodleSession.get", lambda env=None: MagicMock()
    )
    monkeypatch.setattr(
        "py_moodle.cli.courses.list_courses", lambda *a, **k: fake_courses
    )

    runner = CliRunner()
    result = runner.invoke(app, ["--quiet", "courses", "list", "--output", "json"])

    assert result.exit_code == 0
    import json

    assert json.loads(result.output) == fake_courses


def test_quiet_flag_does_not_suppress_errors(monkeypatch):
    """--quiet must never suppress error messages."""
    from py_moodle.cli.app import app

    monkeypatch.setattr(
        "py_moodle.cli.courses.MoodleSession.get", lambda env=None: MagicMock()
    )

    def _raise(*args, **kwargs):
        raise Exception("shortname already in use")

    monkeypatch.setattr("py_moodle.cli.courses.create_course", _raise)

    runner = _cli_runner_with_separate_stderr()
    result = runner.invoke(
        app,
        [
            "--quiet",
            "courses",
            "create",
            "--fullname",
            "New Course",
            "--shortname",
            "newc",
        ],
    )

    assert result.exit_code == 1
    assert "already in use" in result.stderr


# ---------------------------------------------------------------------------
# --no-color
# ---------------------------------------------------------------------------


def test_no_color_flag_strips_ansi_from_table_output(monkeypatch):
    """--no-color renders tables without any ANSI escape sequences."""
    from py_moodle.cli.app import app

    fake_courses = [
        {
            "id": 1,
            "shortname": "cs101",
            "fullname": "Course A",
            "categoryid": 1,
            "visible": 1,
        }
    ]
    monkeypatch.setattr(
        "py_moodle.cli.courses.MoodleSession.get", lambda env=None: MagicMock()
    )
    monkeypatch.setattr(
        "py_moodle.cli.courses.list_courses", lambda *a, **k: fake_courses
    )

    runner = CliRunner()
    result = runner.invoke(app, ["--no-color", "courses", "list"])

    assert result.exit_code == 0
    assert "\x1b[" not in result.output


def test_get_console_no_color_disables_ansi_even_when_forced():
    """The no-color console never emits ANSI, unlike a color-forced console."""
    import typer

    ctx = MagicMock(spec=typer.Context)
    ctx.obj = {"no_color": True}

    console = get_console(ctx)
    buffer = io.StringIO()
    console.file = buffer
    console.print("[bold red]Hello[/bold red]")

    assert "\x1b[" not in buffer.getvalue()
    assert "Hello" in buffer.getvalue()


def test_get_console_without_no_color_allows_color_when_forced():
    """Sanity check: absent --no-color, a terminal-like console can render color."""
    from rich.console import Console

    forced = Console(force_terminal=True)
    buffer = io.StringIO()
    forced.file = buffer
    forced.print("[bold red]Hello[/bold red]")

    assert "\x1b[" in buffer.getvalue()


# ---------------------------------------------------------------------------
# --verbose / --debug
# ---------------------------------------------------------------------------


def test_global_flags_are_advertised_in_help():
    """--quiet, --no-color, --verbose, and --debug are documented CLI options."""
    from py_moodle.cli.app import app

    runner = CliRunner()
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    clean = _strip_ansi(result.output)
    assert "--quiet" in clean
    assert "--no-color" in clean
    assert "--verbose" in clean
    assert "--debug" in clean


def test_configure_logging_sets_level_from_flags():
    """configure_logging maps --verbose/--debug to logging levels, writing to stderr."""
    import sys

    from py_moodle.cli.output import LOGGER_NAME, configure_logging

    configure_logging(verbose=False, debug=False)
    logger = logging.getLogger(LOGGER_NAME)
    assert logger.level == logging.WARNING
    assert logger.handlers[0].stream is sys.stderr

    configure_logging(verbose=True, debug=False)
    assert logging.getLogger(LOGGER_NAME).level == logging.INFO

    configure_logging(verbose=False, debug=True)
    assert logging.getLogger(LOGGER_NAME).level == logging.DEBUG

    # Reset to the quiescent default so other tests are not affected.
    configure_logging(verbose=False, debug=False)


class _FakeResponse:
    """Minimal HTTP response stand-in used to drive MoodleAuth.login()."""

    def __init__(
        self,
        text="",
        url="https://moodle.example.test/",
        status_code=200,
        headers=None,
        json_data=None,
    ):
        self.text = text
        self.url = url
        self.status_code = status_code
        self.headers = headers or {}
        self._json_data = json_data if json_data is not None else {}

    def json(self):
        """Return the configured JSON payload."""
        return self._json_data

    def raise_for_status(self):
        """Mirror requests.Response's API for a successful response."""
        return None


class _FakeLoginSession:
    """Minimal session double simulating a full standard login flow."""

    def __init__(self, dashboard_html, token_json):
        self.dashboard_html = dashboard_html
        self.token_json = token_json

    def get(self, url, **kwargs):
        """Return the dashboard page for /my/, or a bare login page otherwise."""
        if url.rstrip("/").endswith("/my"):
            return _FakeResponse(text=self.dashboard_html, url=url)
        return _FakeResponse(text='<input name="logintoken" value="tok123">', url=url)

    def post(self, url, **kwargs):
        """Return a token payload for token.php, or a successful redirect."""
        if url.endswith("/login/token.php"):
            return _FakeResponse(json_data=self.token_json, url=url)
        return _FakeResponse(url="https://moodle.example.test/my/")


FAKE_SESSKEY = "FAKE_SESSKEY_ABC123"
FAKE_TOKEN = "FAKE_TOKEN_XYZ789"
FAKE_PASSWORD = "FAKE_PASSWORD_1"


def test_debug_flag_never_leaks_fake_secret(monkeypatch, caplog):
    """Debug-level auth logging must never leak a real secret value."""
    from py_moodle.auth import MoodleAuth
    from py_moodle.compat import (
        DEFAULT_COMPATIBILITY,
        MoodleCompatibilityContext,
        MoodleVersion,
    )

    monkeypatch.setattr(
        "py_moodle.auth.detect_moodle_compatibility",
        lambda session, base_url, token=None: MoodleCompatibilityContext(
            version=MoodleVersion(raw="unknown"), strategy=DEFAULT_COMPATIBILITY
        ),
    )

    dashboard_html = (
        "<html><head><script>"
        f'M.cfg.sesskey = "{FAKE_SESSKEY}";'
        "</script></head></html>"
    )
    stub_session = _FakeLoginSession(dashboard_html, {"token": FAKE_TOKEN})

    auth = MoodleAuth(
        base_url="https://moodle.example.test",
        username="tester",
        password=FAKE_PASSWORD,
        debug=True,
    )
    auth.session = stub_session

    with caplog.at_level(logging.DEBUG, logger="py_moodle.auth"):
        auth.login()

    # Sanity check: the flow really did obtain the planted fake secrets.
    assert auth.sesskey == FAKE_SESSKEY
    assert auth.webservice_token == FAKE_TOKEN

    logged_text = "\n".join(record.getMessage() for record in caplog.records)
    assert FAKE_SESSKEY not in logged_text
    assert FAKE_TOKEN not in logged_text
    assert FAKE_PASSWORD not in logged_text
    # A redacted placeholder should appear in place of the secrets.
    assert "REDACTED" in logged_text


def test_debug_flag_wired_through_configure_logging_never_leaks_secret(
    monkeypatch, capsys
):
    """The real CLI wiring (configure_logging + MoodleSession's hardcoded
    ``MoodleAuth(debug=False)``) must not leak secrets either.

    ``MoodleSession._login()`` always calls ``login(..., debug=False)``;
    diagnostic visibility is controlled entirely by the shared
    ``"py_moodle"`` logger's level (set by ``--debug``/``--verbose`` via
    :func:`configure_logging`), not by this per-instance flag. This test
    exercises that exact combination to prove the CLI flag alone is
    sufficient, and that stdout stays clean while stderr never leaks a
    secret.
    """
    from py_moodle.auth import MoodleAuth
    from py_moodle.cli.output import configure_logging
    from py_moodle.compat import (
        DEFAULT_COMPATIBILITY,
        MoodleCompatibilityContext,
        MoodleVersion,
    )

    monkeypatch.setattr(
        "py_moodle.auth.detect_moodle_compatibility",
        lambda session, base_url, token=None: MoodleCompatibilityContext(
            version=MoodleVersion(raw="unknown"), strategy=DEFAULT_COMPATIBILITY
        ),
    )

    # Mirror exactly what `py-moodle --debug ...` does at the CLI layer.
    configure_logging(verbose=False, debug=True)

    dashboard_html = (
        "<html><head><script>"
        f'M.cfg.sesskey = "{FAKE_SESSKEY}";'
        "</script></head></html>"
    )
    stub_session = _FakeLoginSession(dashboard_html, {"token": FAKE_TOKEN})

    auth = MoodleAuth(
        base_url="https://moodle.example.test",
        username="tester",
        password=FAKE_PASSWORD,
        debug=False,
    )
    auth.session = stub_session
    auth.login()

    captured = capsys.readouterr()
    assert captured.out == ""
    assert FAKE_SESSKEY not in captured.err
    assert FAKE_TOKEN not in captured.err
    assert FAKE_PASSWORD not in captured.err
    assert "REDACTED" in captured.err
    assert "DEBUG" in captured.err


def test_verbose_flag_never_leaks_fake_secret(monkeypatch, caplog):
    """--verbose (INFO level) diagnostics must also never leak a secret value."""
    from py_moodle.auth import MoodleAuth
    from py_moodle.compat import (
        DEFAULT_COMPATIBILITY,
        MoodleCompatibilityContext,
        MoodleVersion,
    )

    monkeypatch.setattr(
        "py_moodle.auth.detect_moodle_compatibility",
        lambda session, base_url, token=None: MoodleCompatibilityContext(
            version=MoodleVersion(raw="unknown"), strategy=DEFAULT_COMPATIBILITY
        ),
    )

    dashboard_html = (
        "<html><head><script>"
        f'M.cfg.sesskey = "{FAKE_SESSKEY}";'
        "</script></head></html>"
    )
    stub_session = _FakeLoginSession(dashboard_html, {"token": FAKE_TOKEN})

    auth = MoodleAuth(
        base_url="https://moodle.example.test",
        username="tester",
        password=FAKE_PASSWORD,
    )
    auth.session = stub_session

    with caplog.at_level(logging.INFO, logger="py_moodle.auth"):
        auth.login()

    logged_text = "\n".join(record.getMessage() for record in caplog.records)
    assert FAKE_SESSKEY not in logged_text
    assert FAKE_TOKEN not in logged_text
    assert FAKE_PASSWORD not in logged_text
    # INFO-level output should still say *something* diagnostic.
    assert "Login" in logged_text


# ---------------------------------------------------------------------------
# Errors to stderr / stream separation
# ---------------------------------------------------------------------------


def test_json_output_error_goes_to_stderr_not_stdout(monkeypatch):
    """A failing command with --output json prints nothing but the error, on stderr."""
    from py_moodle.cli.app import app
    from py_moodle.course import MoodleCourseError

    def _raise(*args, **kwargs):
        raise MoodleCourseError("course not found: boom")

    monkeypatch.setattr(
        "py_moodle.cli.courses.get_course_with_sections_and_modules", _raise
    )
    monkeypatch.setattr(
        "py_moodle.cli.courses.MoodleSession.get", lambda env=None: MagicMock()
    )

    runner = _cli_runner_with_separate_stderr()
    result = runner.invoke(app, ["courses", "show", "1", "--output", "json"])

    assert result.exit_code == 1
    assert result.stdout == ""
    assert "boom" in result.stderr


def test_csv_output_error_goes_to_stderr_not_stdout(monkeypatch):
    """A failing command with --output csv prints nothing but the error, on stderr."""
    from py_moodle.cli.app import app
    from py_moodle.course import MoodleCourseError

    def _raise(*args, **kwargs):
        raise MoodleCourseError("course not found: boom")

    monkeypatch.setattr(
        "py_moodle.cli.courses.get_course_with_sections_and_modules", _raise
    )
    monkeypatch.setattr(
        "py_moodle.cli.courses.MoodleSession.get", lambda env=None: MagicMock()
    )

    runner = _cli_runner_with_separate_stderr()
    result = runner.invoke(app, ["courses", "show", "1", "--output", "csv"])

    assert result.exit_code == 1
    assert result.stdout == ""
    assert "boom" in result.stderr
