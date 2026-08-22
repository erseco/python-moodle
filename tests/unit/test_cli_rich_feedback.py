"""Unit tests for Rich CLI feedback and upload progress."""

from __future__ import annotations

import io
from unittest.mock import MagicMock

import typer
from rich.console import Console

from py_moodle.cli.feedback import error, status, success, upload_progress, warning
from py_moodle.cli.output import OutputFormat


def _ctx(*, quiet: bool = False, no_color: bool = True) -> typer.Context:
    """Build a minimal Typer context for feedback helper tests."""
    ctx = MagicMock(spec=typer.Context)
    ctx.obj = {"quiet": quiet, "no_color": no_color}
    return ctx


def test_success_and_warning_respect_quiet(monkeypatch):
    """Incidental success and warning messages are suppressed by --quiet."""
    buffer = io.StringIO()
    console = Console(file=buffer, force_terminal=False, no_color=True)
    monkeypatch.setattr("py_moodle.cli.feedback.get_console", lambda ctx=None: console)

    ctx = _ctx(quiet=True)
    success(ctx, "Created")
    warning(ctx, "Skipped")

    assert buffer.getvalue() == ""


def test_error_is_never_suppressed(monkeypatch, capsys):
    """Errors remain visible on stderr even when --quiet is active."""
    console = Console(force_terminal=False, no_color=True)
    monkeypatch.setattr("py_moodle.cli.feedback.get_console", lambda ctx=None: console)

    error(_ctx(quiet=True), "Upload failed")

    captured = capsys.readouterr()
    assert "Upload failed" in captured.err
    assert captured.out == ""


def test_status_is_noop_for_machine_readable_output(monkeypatch):
    """JSON/YAML/CSV paths never render Rich status output."""
    buffer = io.StringIO()
    console = Console(file=buffer, force_terminal=True, no_color=True)
    monkeypatch.setattr("py_moodle.cli.feedback.get_console", lambda ctx=None: console)

    for output_format in (OutputFormat.JSON, OutputFormat.YAML, OutputFormat.CSV):
        with status(_ctx(), "Fetching...", output_format):
            pass

    assert buffer.getvalue() == ""


def test_upload_progress_is_noop_for_machine_readable_output(monkeypatch):
    """Machine-readable output receives a safe callback without terminal output."""
    buffer = io.StringIO()
    console = Console(file=buffer, force_terminal=True, no_color=True)
    monkeypatch.setattr("py_moodle.cli.feedback.get_console", lambda ctx=None: console)

    with upload_progress(
        _ctx(),
        "/path/does/not/need/to/exist.zip",
        output_format=OutputFormat.JSON,
    ) as callback:
        callback(1024)

    assert buffer.getvalue() == ""


def test_upload_progress_renders_byte_progress(monkeypatch, tmp_path):
    """Interactive table output renders a byte-based Rich progress bar."""
    upload = tmp_path / "package.zip"
    upload.write_bytes(b"x" * 2048)

    buffer = io.StringIO()
    console = Console(
        file=buffer,
        force_terminal=True,
        no_color=True,
        width=120,
    )
    monkeypatch.setattr("py_moodle.cli.feedback.get_console", lambda ctx=None: console)

    with upload_progress(_ctx(), str(upload)) as callback:
        callback(1024)
        callback(1024)

    rendered = buffer.getvalue()
    assert "Uploading package.zip" in rendered
    assert "100%" in rendered
