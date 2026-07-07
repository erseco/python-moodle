"""Unit tests for issue #66: ``--fields`` machine-readable field selection.

These tests cover the reusable ``select_fields``/``parse_fields`` helpers in
``py_moodle.cli.output`` and the ``--fields`` option wired into the four
migrated ``list`` commands (courses, categories, sections, users). All tests
run without any network access, Docker, or a live Moodle instance, mirroring
the mocking style of ``tests/unit/test_cli_output_formats.py``.
"""

from __future__ import annotations

import csv
import io
import json

import pytest
from typer.testing import CliRunner

from py_moodle.cli.output import (
    UnknownFieldError,
    parse_fields,
    select_fields,
)


def _cli_runner_with_separate_stderr() -> CliRunner:
    """Build a CliRunner with stdout/stderr captured separately.

    Click <8.2 requires ``mix_stderr=False`` for this; Click >=8.2 removed
    that argument and always captures stderr separately. Support both.
    """
    try:
        return CliRunner(mix_stderr=False)
    except TypeError:
        return CliRunner()


# Per-command invocation config for the parametrized CLI tests. Each entry
# describes how to mock the command's dependencies and what data it returns.
_COMMAND_CONFIGS = {
    "courses": {
        "module": "py_moodle.cli.courses",
        "list_attr": "list_courses",
        "base_args": ["courses", "list"],
        "rows": [
            {
                "id": 1,
                "shortname": "cs101",
                "fullname": "Intro to CS",
                "categoryid": 3,
                "visible": 1,
            },
            {
                "id": 2,
                "shortname": "cs102",
                "fullname": "Data Structures",
                "categoryid": 3,
                "visible": 0,
            },
        ],
    },
    "categories": {
        "module": "py_moodle.cli.categories",
        "list_attr": "list_categories",
        "base_args": ["categories", "list"],
        "rows": [
            {"id": 1, "name": "Science", "parent": 0, "coursecount": 5},
            {"id": 2, "name": "Maths", "parent": 1, "coursecount": 2},
        ],
    },
    "users": {
        "module": "py_moodle.cli.users",
        "list_attr": "list_course_users",
        "base_args": ["users", "list", "--course-id", "1"],
        "rows": [
            {"id": 1, "fullname": "Ada Lovelace", "email": "ada@example.test"},
            {"id": 2, "fullname": "Alan Turing", "email": "alan@example.test"},
        ],
    },
    "sections": {
        "module": "py_moodle.cli.sections",
        "list_attr": None,  # sections list uses get_course_with_sections_and_modules
        "base_args": ["sections", "list", "--course-id", "1"],
        "rows": [
            {"id": 10, "section": 0, "name": "General", "modules": [], "visible": 1},
            {"id": 11, "section": 1, "name": "Week 1", "modules": [], "visible": 1},
        ],
    },
}


def _patch_command(monkeypatch, key):
    """Monkeypatch the session and data source for one list command.

    Args:
        monkeypatch: The pytest ``monkeypatch`` fixture.
        key: The command key in :data:`_COMMAND_CONFIGS`.

    Returns:
        The base CLI argument list for invoking that command.
    """
    from unittest.mock import MagicMock

    config = _COMMAND_CONFIGS[key]
    module = config["module"]
    rows = config["rows"]

    monkeypatch.setattr(f"{module}.MoodleSession.get", lambda env=None: MagicMock())

    if key == "sections":
        monkeypatch.setattr(
            f"{module}.get_course_with_sections_and_modules",
            lambda *a, **k: {"fullname": "Course", "sections": rows},
        )
    else:
        monkeypatch.setattr(f"{module}.{config['list_attr']}", lambda *a, **k: rows)

    return list(config["base_args"])


# ---------------------------------------------------------------------------
# Unit tests: select_fields / parse_fields
# ---------------------------------------------------------------------------


def test_select_fields_returns_requested_keys_in_order():
    """select_fields projects each row to exactly the requested keys, in order."""
    rows = [
        {"id": 1, "shortname": "cs101", "fullname": "A"},
        {"id": 2, "shortname": "cs102", "fullname": "B"},
    ]

    result = select_fields(rows, ["shortname", "id"])

    assert result == [
        {"shortname": "cs101", "id": 1},
        {"shortname": "cs102", "id": 2},
    ]
    # Key order must follow the user-provided field order.
    assert [list(row.keys()) for row in result] == [["shortname", "id"]] * 2


def test_select_fields_unknown_field_raises_typed_error():
    """select_fields raises UnknownFieldError naming the offending field(s)."""
    rows = [{"id": 1, "shortname": "cs101"}]

    with pytest.raises(UnknownFieldError) as excinfo:
        select_fields(rows, ["id", "bogus"])

    assert "bogus" in str(excinfo.value)
    assert excinfo.value.unknown == ["bogus"]
    # The available fields are surfaced to help the user recover.
    assert "shortname" in str(excinfo.value)


def test_select_fields_empty_rows_returns_empty_without_validation():
    """An empty input yields an empty result and no unknown-field error."""
    assert select_fields([], ["anything"]) == []


def test_select_fields_fills_missing_key_with_none_when_present_elsewhere():
    """A field present in some rows is kept for all rows (None when absent)."""
    rows = [{"id": 1, "email": "a@b.test"}, {"id": 2}]

    result = select_fields(rows, ["id", "email"])

    assert result == [{"id": 1, "email": "a@b.test"}, {"id": 2, "email": None}]


def test_parse_fields_splits_and_strips():
    """parse_fields splits on commas and strips surrounding whitespace."""
    assert parse_fields("id, shortname ,fullname") == ["id", "shortname", "fullname"]


def test_parse_fields_empty_is_treated_as_no_filtering():
    """Empty / whitespace-only --fields values mean 'no filtering' (None)."""
    assert parse_fields(None) is None
    assert parse_fields("") is None
    assert parse_fields("   ") is None
    assert parse_fields(",, ,") is None


# ---------------------------------------------------------------------------
# CLI tests: --fields on the list commands
# ---------------------------------------------------------------------------


def test_courses_list_json_fields_selects_keys_in_order(monkeypatch):
    """`courses list --output json --fields shortname,id` selects those keys, ordered."""
    from py_moodle.cli.app import app

    args = _patch_command(monkeypatch, "courses")

    runner = CliRunner()
    result = runner.invoke(app, args + ["--output", "json", "--fields", "shortname,id"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload == [
        {"shortname": "cs101", "id": 1},
        {"shortname": "cs102", "id": 2},
    ]
    assert [list(obj.keys()) for obj in payload] == [["shortname", "id"]] * 2


def test_courses_list_csv_fields_emits_selected_columns_in_order(monkeypatch):
    """`courses list --output csv --fields id,shortname` emits those columns, ordered."""
    from py_moodle.cli.app import app

    args = _patch_command(monkeypatch, "courses")

    runner = CliRunner()
    result = runner.invoke(app, args + ["--output", "csv", "--fields", "id,shortname"])

    assert result.exit_code == 0
    rows = list(csv.reader(io.StringIO(result.output)))
    assert rows[0] == ["id", "shortname"]
    assert rows[1] == ["1", "cs101"]
    assert rows[2] == ["2", "cs102"]


def test_courses_list_unknown_field_fails_with_stderr_message(monkeypatch):
    """An unknown --fields value exits non-zero and names the field on stderr."""
    from py_moodle.cli.app import app

    args = _patch_command(monkeypatch, "courses")

    runner = _cli_runner_with_separate_stderr()
    result = runner.invoke(app, args + ["--output", "json", "--fields", "id,bogus"])

    assert result.exit_code != 0
    assert result.stdout == ""
    assert "bogus" in result.stderr


def test_courses_list_empty_fields_leaves_output_unchanged(monkeypatch):
    """An empty --fields value behaves exactly like omitting the flag."""
    from py_moodle.cli.app import app

    args = _patch_command(monkeypatch, "courses")
    rows = _COMMAND_CONFIGS["courses"]["rows"]

    runner = CliRunner()
    with_flag = runner.invoke(app, args + ["--output", "json", "--fields", ""])
    without_flag = runner.invoke(app, args + ["--output", "json"])

    assert with_flag.exit_code == 0
    assert without_flag.exit_code == 0
    assert json.loads(with_flag.output) == rows
    assert json.loads(without_flag.output) == rows


def test_courses_list_table_ignores_fields(monkeypatch):
    """For --output table, --fields is accepted but ignored (best-effort)."""
    from py_moodle.cli.app import app

    args = _patch_command(monkeypatch, "courses")

    runner = CliRunner()
    result = runner.invoke(app, args + ["--fields", "id"])

    assert result.exit_code == 0
    # The full table is rendered regardless of --fields; unselected columns
    # such as "Fullname" are still present.
    assert "Fullname" in result.output


@pytest.mark.parametrize("key", ["courses", "categories", "sections", "users"])
def test_each_list_command_applies_fields_for_json(monkeypatch, key):
    """Every migrated list command honors --fields for json output."""
    from py_moodle.cli.app import app

    args = _patch_command(monkeypatch, key)

    runner = CliRunner()
    result = runner.invoke(app, args + ["--output", "json", "--fields", "id"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload
    assert all(list(obj.keys()) == ["id"] for obj in payload)


@pytest.mark.parametrize(
    "subcmd",
    [
        ["courses", "list", "--help"],
        ["categories", "list", "--help"],
        ["sections", "list", "--help"],
        ["users", "list", "--help"],
    ],
)
def test_each_list_command_advertises_fields_option(subcmd):
    """Each migrated list command advertises --fields in its --help output."""
    from py_moodle.cli.app import app

    runner = CliRunner()
    result = runner.invoke(app, subcmd)

    assert result.exit_code == 0
    assert "--fields" in result.output
