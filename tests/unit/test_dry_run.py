"""Unit tests for ``--dry-run`` support on create/delete/scorm CLI commands."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from py_moodle.cli.app import app

runner = CliRunner()


def _fake_moodle_session() -> MagicMock:
    """Build a MagicMock standing in for a ``MoodleSession.get()`` result."""
    ms = MagicMock()
    ms.session = MagicMock()
    ms.settings.url = "https://moodle.example.test"
    ms.sesskey = "sesskey123"
    ms.token = "token123"
    return ms


# ---------------------------------------------------------------------------
# courses create --dry-run
# ---------------------------------------------------------------------------


def test_courses_create_dry_run_does_not_call_create_course():
    """``courses create --dry-run`` must never call ``create_course``."""
    with (
        patch("py_moodle.cli.courses.MoodleSession") as mock_session_cls,
        patch("py_moodle.cli.courses.create_course") as mock_create,
    ):
        mock_session_cls.get.return_value = _fake_moodle_session()

        result = runner.invoke(
            app,
            [
                "courses",
                "create",
                "--fullname",
                "Test Course",
                "--shortname",
                "T1",
                "--dry-run",
            ],
        )

    assert result.exit_code == 0, result.output
    mock_create.assert_not_called()


def test_courses_create_dry_run_human_readable_output():
    """The human-readable dry-run output must identify the planned course."""
    with (
        patch("py_moodle.cli.courses.MoodleSession") as mock_session_cls,
        patch("py_moodle.cli.courses.create_course"),
    ):
        mock_session_cls.get.return_value = _fake_moodle_session()

        result = runner.invoke(
            app,
            [
                "courses",
                "create",
                "--fullname",
                "Test Course",
                "--shortname",
                "T1",
                "--dry-run",
            ],
        )

    assert result.exit_code == 0, result.output
    assert "Test Course" in result.output
    assert "T1" in result.output


def test_courses_create_dry_run_json_output():
    """JSON dry-run output must be parseable and mark the course id as estimated."""
    with (
        patch("py_moodle.cli.courses.MoodleSession") as mock_session_cls,
        patch("py_moodle.cli.courses.create_course") as mock_create,
    ):
        mock_session_cls.get.return_value = _fake_moodle_session()

        result = runner.invoke(
            app,
            [
                "courses",
                "create",
                "--fullname",
                "Test Course",
                "--shortname",
                "T1",
                "--categoryid",
                "3",
                "--output",
                "json",
                "--dry-run",
            ],
        )

    assert result.exit_code == 0, result.output
    plan = json.loads(result.output)
    assert plan["action"] == "create_course"
    assert plan["dry_run"] is True
    assert plan["parameters"]["fullname"] == "Test Course"
    assert plan["parameters"]["shortname"] == "T1"
    assert plan["parameters"]["categoryid"] == 3
    # The real course id cannot be known before contacting Moodle.
    assert plan["target"]["course_id"] != 3
    mock_create.assert_not_called()


def test_courses_create_without_dry_run_calls_create_course_once():
    """Regression: normal ``courses create`` still calls ``create_course`` once."""
    with (
        patch("py_moodle.cli.courses.MoodleSession") as mock_session_cls,
        patch("py_moodle.cli.courses.create_course") as mock_create,
    ):
        mock_session_cls.get.return_value = _fake_moodle_session()
        mock_create.return_value = {
            "id": 99,
            "fullname": "Test Course",
            "shortname": "T1",
        }

        result = runner.invoke(
            app,
            [
                "courses",
                "create",
                "--fullname",
                "Test Course",
                "--shortname",
                "T1",
            ],
        )

    assert result.exit_code == 0, result.output
    mock_create.assert_called_once()
    assert "99" in result.output


# ---------------------------------------------------------------------------
# courses delete --dry-run
# ---------------------------------------------------------------------------


def test_courses_delete_dry_run_does_not_call_delete_course():
    """``courses delete --dry-run`` must never call ``delete_course``."""
    with (
        patch("py_moodle.cli.courses.MoodleSession") as mock_session_cls,
        patch("py_moodle.cli.courses.delete_course") as mock_delete,
    ):
        mock_session_cls.get.return_value = _fake_moodle_session()

        result = runner.invoke(app, ["courses", "delete", "42", "--dry-run"])

    assert result.exit_code == 0, result.output
    mock_delete.assert_not_called()


def test_courses_delete_dry_run_skips_confirmation_prompt():
    """Dry-run must not prompt for confirmation, even without ``--force``."""
    with (
        patch("py_moodle.cli.courses.MoodleSession") as mock_session_cls,
        patch("py_moodle.cli.courses.delete_course") as mock_delete,
        patch("typer.confirm") as mock_confirm,
    ):
        mock_session_cls.get.return_value = _fake_moodle_session()

        # input="" would raise if the CLI actually reads from stdin for a
        # confirmation prompt, since CliRunner's default input stream is empty.
        result = runner.invoke(app, ["courses", "delete", "42", "--dry-run"], input="")

    assert result.exit_code == 0, result.output
    mock_delete.assert_not_called()
    mock_confirm.assert_not_called()


def test_courses_delete_dry_run_human_readable_output():
    """The human-readable dry-run output must identify the target course id."""
    with (
        patch("py_moodle.cli.courses.MoodleSession") as mock_session_cls,
        patch("py_moodle.cli.courses.delete_course"),
    ):
        mock_session_cls.get.return_value = _fake_moodle_session()

        result = runner.invoke(app, ["courses", "delete", "42", "--dry-run"])

    assert result.exit_code == 0, result.output
    assert "42" in result.output


def test_courses_delete_dry_run_json_output():
    """JSON dry-run output must contain the target course id."""
    with (
        patch("py_moodle.cli.courses.MoodleSession") as mock_session_cls,
        patch("py_moodle.cli.courses.delete_course") as mock_delete,
    ):
        mock_session_cls.get.return_value = _fake_moodle_session()

        result = runner.invoke(
            app, ["courses", "delete", "42", "--output", "json", "--dry-run"]
        )

    assert result.exit_code == 0, result.output
    plan = json.loads(result.output)
    assert plan["action"] == "delete_course"
    assert plan["dry_run"] is True
    assert plan["target"]["course_id"] == 42
    mock_delete.assert_not_called()


def test_courses_delete_without_dry_run_calls_delete_course_once():
    """Regression: normal ``courses delete --force`` still calls ``delete_course`` once."""
    with (
        patch("py_moodle.cli.courses.MoodleSession") as mock_session_cls,
        patch("py_moodle.cli.courses.delete_course") as mock_delete,
    ):
        mock_session_cls.get.return_value = _fake_moodle_session()

        result = runner.invoke(app, ["courses", "delete", "42", "--force"])

    assert result.exit_code == 0, result.output
    mock_delete.assert_called_once()
    args, kwargs = mock_delete.call_args
    assert args[3] == 42
    assert kwargs.get("force") is True


# ---------------------------------------------------------------------------
# modules add scorm --dry-run
# ---------------------------------------------------------------------------


def test_modules_add_scorm_dry_run_does_not_call_add_scorm(tmp_path):
    """``modules add scorm --dry-run`` must never call ``add_scorm``."""
    package = tmp_path / "package.zip"
    package.write_text("fake zip contents")

    with (
        patch("py_moodle.cli.modules.MoodleSession") as mock_session_cls,
        patch("py_moodle.cli.modules.add_scorm") as mock_add_scorm,
    ):
        mock_session_cls.get.return_value = _fake_moodle_session()

        result = runner.invoke(
            app,
            [
                "modules",
                "add",
                "scorm",
                "--course-id",
                "42",
                "--section-id",
                "3",
                "--name",
                "SCORM 1",
                "--file",
                str(package),
                "--dry-run",
            ],
        )

    assert result.exit_code == 0, result.output
    mock_add_scorm.assert_not_called()


def test_modules_add_scorm_dry_run_human_readable_output(tmp_path):
    """The human-readable dry-run output must identify the planned SCORM."""
    package = tmp_path / "package.zip"
    package.write_text("fake zip contents")

    with (
        patch("py_moodle.cli.modules.MoodleSession") as mock_session_cls,
        patch("py_moodle.cli.modules.add_scorm"),
    ):
        mock_session_cls.get.return_value = _fake_moodle_session()

        result = runner.invoke(
            app,
            [
                "modules",
                "add",
                "scorm",
                "--course-id",
                "42",
                "--section-id",
                "3",
                "--name",
                "SCORM 1",
                "--file",
                str(package),
                "--dry-run",
            ],
        )

    assert result.exit_code == 0, result.output
    assert "SCORM 1" in result.output
    assert "42" in result.output
    assert "3" in result.output


def test_modules_add_scorm_dry_run_json_output(tmp_path):
    """JSON dry-run output must contain the plan's action, target, and parameters."""
    package = tmp_path / "package.zip"
    package.write_text("fake zip contents")

    with (
        patch("py_moodle.cli.modules.MoodleSession") as mock_session_cls,
        patch("py_moodle.cli.modules.add_scorm") as mock_add_scorm,
    ):
        mock_session_cls.get.return_value = _fake_moodle_session()

        result = runner.invoke(
            app,
            [
                "modules",
                "add",
                "scorm",
                "--course-id",
                "42",
                "--section-id",
                "3",
                "--name",
                "SCORM 1",
                "--file",
                str(package),
                "--output",
                "json",
                "--dry-run",
            ],
        )

    assert result.exit_code == 0, result.output
    plan = json.loads(result.output)
    assert plan["action"] == "add_scorm"
    assert plan["dry_run"] is True
    assert plan["target"] == {"course_id": 42, "section_id": 3}
    assert plan["parameters"]["name"] == "SCORM 1"
    assert plan["parameters"]["file_path"] == str(package)
    mock_add_scorm.assert_not_called()


def test_modules_add_scorm_without_dry_run_calls_add_scorm_once(tmp_path):
    """Regression: normal ``modules add scorm`` still calls ``add_scorm`` once."""
    package = tmp_path / "package.zip"
    package.write_text("fake zip contents")

    with (
        patch("py_moodle.cli.modules.MoodleSession") as mock_session_cls,
        patch("py_moodle.cli.modules.add_scorm") as mock_add_scorm,
    ):
        mock_session_cls.get.return_value = _fake_moodle_session()
        mock_add_scorm.return_value = 101

        result = runner.invoke(
            app,
            [
                "modules",
                "add",
                "scorm",
                "--course-id",
                "42",
                "--section-id",
                "3",
                "--name",
                "SCORM 1",
                "--file",
                str(package),
            ],
        )

    assert result.exit_code == 0, result.output
    mock_add_scorm.assert_called_once()
    assert "101" in result.output
