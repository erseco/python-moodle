"""Unit tests for the interactive confirmation flow of ``courses delete``."""

from unittest.mock import MagicMock, call, patch

from typer.testing import CliRunner

from py_moodle.cli.app import app
from py_moodle.course import ConfirmationRequired

runner = CliRunner()


def _fake_moodle_session():
    """Build a MagicMock standing in for a MoodleSession instance."""
    ms = MagicMock()
    ms.session = MagicMock()
    ms.settings.url = "https://moodle.example.test"
    ms.sesskey = "sesskey123"
    return ms


def test_delete_course_confirmation_declined_aborts_without_deleting():
    """Declining the confirmation prompt aborts without a second delete call."""
    fake_ms = _fake_moodle_session()
    with (
        patch("py_moodle.cli.courses.MoodleSession.get", return_value=fake_ms),
        patch("py_moodle.cli.courses.delete_course") as mock_delete,
    ):
        mock_delete.side_effect = ConfirmationRequired(42, "Test Course")

        result = runner.invoke(app, ["courses", "delete", "42"], input="n\n")

    assert result.exit_code == 0
    assert "Aborted." in result.output
    assert "deleted successfully" not in result.output
    mock_delete.assert_called_once_with(
        fake_ms.session, fake_ms.settings.url, fake_ms.sesskey, 42, force=False
    )


def test_delete_course_confirmation_accepted_deletes():
    """Accepting the confirmation prompt re-invokes delete_course(force=True)."""
    fake_ms = _fake_moodle_session()
    with (
        patch("py_moodle.cli.courses.MoodleSession.get", return_value=fake_ms),
        patch("py_moodle.cli.courses.delete_course") as mock_delete,
    ):
        mock_delete.side_effect = [ConfirmationRequired(42, "Test Course"), None]

        result = runner.invoke(app, ["courses", "delete", "42"], input="y\n")

    assert result.exit_code == 0
    assert "Course 42 deleted successfully." in result.output
    assert mock_delete.call_count == 2
    mock_delete.assert_has_calls(
        [
            call(
                fake_ms.session,
                fake_ms.settings.url,
                fake_ms.sesskey,
                42,
                force=False,
            ),
            call(
                fake_ms.session,
                fake_ms.settings.url,
                fake_ms.sesskey,
                42,
                force=True,
            ),
        ]
    )


def test_delete_course_force_skips_confirmation():
    """--force deletes directly, without any confirmation prompt."""
    fake_ms = _fake_moodle_session()
    with (
        patch("py_moodle.cli.courses.MoodleSession.get", return_value=fake_ms),
        patch("py_moodle.cli.courses.delete_course") as mock_delete,
    ):
        mock_delete.return_value = None

        result = runner.invoke(app, ["courses", "delete", "42", "--force"])

    assert result.exit_code == 0
    assert "Course 42 deleted successfully." in result.output
    mock_delete.assert_called_once_with(
        fake_ms.session, fake_ms.settings.url, fake_ms.sesskey, 42, force=True
    )
