"""Unit tests for the CLI output format utility."""

from __future__ import annotations

import json
import re

import pytest
import yaml
from typer.testing import CliRunner

from py_moodle.cli.output import OutputFormat, emit


def _strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from a string."""
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


# ---------------------------------------------------------------------------
# emit() unit tests
# ---------------------------------------------------------------------------


def test_emit_json_serializes_list(capsys):
    """JSON format should produce valid, indented JSON output."""
    data = [{"id": 1, "name": "Course A"}, {"id": 2, "name": "Course B"}]

    emit(data, OutputFormat.JSON)

    captured = capsys.readouterr()
    parsed = json.loads(captured.out)
    assert parsed == data


def test_emit_json_serializes_dict(capsys):
    """JSON format should handle a plain dict."""
    data = {"id": 42, "fullname": "Test Course"}

    emit(data, OutputFormat.JSON)

    captured = capsys.readouterr()
    parsed = json.loads(captured.out)
    assert parsed == data


def test_emit_json_preserves_unicode(capsys):
    """JSON format should not escape non-ASCII characters."""
    data = [{"name": "Ñoño"}]

    emit(data, OutputFormat.JSON)

    captured = capsys.readouterr()
    assert "Ñoño" in captured.out


def test_emit_yaml_serializes_list(capsys):
    """YAML format should produce valid YAML output for a list."""
    data = [{"id": 1, "name": "Course A"}, {"id": 2, "name": "Course B"}]

    emit(data, OutputFormat.YAML)

    captured = capsys.readouterr()
    parsed = yaml.safe_load(captured.out)
    assert parsed == data


def test_emit_yaml_serializes_dict(capsys):
    """YAML format should handle a plain dict."""
    data = {"id": 42, "fullname": "Test Course"}

    emit(data, OutputFormat.YAML)

    captured = capsys.readouterr()
    parsed = yaml.safe_load(captured.out)
    assert parsed == data


def test_emit_yaml_preserves_unicode(capsys):
    """YAML format should not escape non-ASCII characters."""
    data = [{"name": "Ñoño"}]

    emit(data, OutputFormat.YAML)

    captured = capsys.readouterr()
    assert "Ñoño" in captured.out


def test_emit_table_calls_table_fn():
    """Table format should invoke the provided table_fn with the data."""
    data = [{"id": 1}]
    calls = []

    def fake_table_fn(d):
        calls.append(d)

    emit(data, OutputFormat.TABLE, table_fn=fake_table_fn)

    assert calls == [data]


def test_emit_table_raises_without_table_fn():
    """Table format without a table_fn should raise ValueError."""
    with pytest.raises(ValueError, match="table_fn is required"):
        emit([{"id": 1}], OutputFormat.TABLE)


# ---------------------------------------------------------------------------
# OutputFormat enum tests
# ---------------------------------------------------------------------------


def test_output_format_values():
    """The ``OutputFormat`` enum exposes the expected string values."""
    assert OutputFormat.TABLE == "table"
    assert OutputFormat.JSON == "json"
    assert OutputFormat.YAML == "yaml"


def test_output_format_is_str_enum():
    """``OutputFormat`` members are usable as plain strings."""
    fmt = OutputFormat.JSON
    assert isinstance(fmt, str)
    assert fmt == "json"


# ---------------------------------------------------------------------------
# CLI integration tests (no live Moodle required)
# ---------------------------------------------------------------------------


def test_courses_list_help_shows_output_option():
    """The courses list command should advertise --output in its help text."""
    from py_moodle.cli.app import app

    runner = CliRunner()
    result = runner.invoke(app, ["courses", "list", "--help"])

    assert result.exit_code == 0
    assert "--output" in _strip_ansi(result.output)


def test_categories_list_help_shows_output_option():
    """The categories list command should advertise --output in its help text."""
    from py_moodle.cli.app import app

    runner = CliRunner()
    result = runner.invoke(app, ["categories", "list", "--help"])

    assert result.exit_code == 0
    assert "--output" in _strip_ansi(result.output)


def test_sections_list_help_shows_output_option():
    """The sections list command should advertise --output in its help text."""
    from py_moodle.cli.app import app

    runner = CliRunner()
    result = runner.invoke(app, ["sections", "list", "--help"])

    assert result.exit_code == 0
    assert "--output" in _strip_ansi(result.output)


def test_users_list_help_shows_output_option():
    """The users list command should advertise --output in its help text."""
    from py_moodle.cli.app import app

    runner = CliRunner()
    result = runner.invoke(app, ["users", "list", "--help"])

    assert result.exit_code == 0
    assert "--output" in _strip_ansi(result.output)


def test_modules_show_help_shows_output_option():
    """The modules show command should advertise --output in its help text."""
    from py_moodle.cli.app import app

    runner = CliRunner()
    result = runner.invoke(app, ["modules", "show", "--help"])

    assert result.exit_code == 0
    assert "--output" in _strip_ansi(result.output)


def test_modules_list_types_help_shows_output_option():
    """The modules list-types command should advertise --output in its help text."""
    from py_moodle.cli.app import app

    runner = CliRunner()
    result = runner.invoke(app, ["modules", "list-types", "--help"])

    assert result.exit_code == 0
    assert "--output" in _strip_ansi(result.output)


def test_courses_show_help_shows_output_option():
    """The courses show command should advertise --output in its help text."""
    from py_moodle.cli.app import app

    runner = CliRunner()
    result = runner.invoke(app, ["courses", "show", "--help"])

    assert result.exit_code == 0
    assert "--output" in _strip_ansi(result.output)


def test_sections_show_help_shows_output_option():
    """The sections show command should advertise --output in its help text."""
    from py_moodle.cli.app import app

    runner = CliRunner()
    result = runner.invoke(app, ["sections", "show", "--help"])

    assert result.exit_code == 0
    assert "--output" in _strip_ansi(result.output)


def test_no_command_has_json_flag():
    """None of the updated commands should still expose a bare --json flag."""
    from py_moodle.cli.app import app

    runner = CliRunner()
    for subcmd in [
        ["courses", "list", "--help"],
        ["courses", "show", "--help"],
        ["categories", "list", "--help"],
        ["sections", "list", "--help"],
        ["sections", "show", "--help"],
        ["users", "list", "--help"],
        ["modules", "show", "--help"],
        ["modules", "list-types", "--help"],
    ]:
        result = runner.invoke(app, subcmd)
        assert result.exit_code == 0, f"Non-zero exit for {subcmd}: {result.output}"
        clean = _strip_ansi(result.output)
        assert "--json" not in clean, f"--json flag still present in {' '.join(subcmd)}"
