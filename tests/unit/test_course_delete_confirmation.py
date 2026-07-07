"""Unit tests for the ``ConfirmationRequired`` behavior of ``delete_course()``."""

import pytest

from py_moodle.course import ConfirmationRequired, MoodleCourseError, delete_course

CONFIRM_PAGE_HTML = (
    "<title>Test Course</title>"
    '<form method="post" action="delete.php">'
    '<input type="hidden" name="sesskey" value="abc123">'
    '<input type="hidden" name="delete" value="delete-token-xyz">'
    "</form>"
)


class FakeResponse:
    """Minimal HTTP response stub for ``delete_course`` tests."""

    def __init__(self, *, text="", status_code=200):
        """Store the canned text and status code."""
        self.text = text
        self.status_code = status_code

    def raise_for_status(self):
        """Mirror the requests.Response API for successful responses."""
        return None


class FakeSession:
    """Fake ``requests.Session`` that records POST calls for assertions."""

    def __init__(self, get_text=CONFIRM_PAGE_HTML, post_response=None):
        """Configure the canned GET text and POST response."""
        self.get_text = get_text
        self.post_response = post_response or FakeResponse(text="<html>ok</html>")
        self.post_calls = []

    def get(self, url, **kwargs):
        """Return the canned confirmation-page response."""
        return FakeResponse(text=self.get_text)

    def post(self, url, **kwargs):
        """Record the POST call and return the canned response."""
        self.post_calls.append((url, kwargs))
        return self.post_response


def test_delete_course_without_force_raises_confirmation_required(monkeypatch, capsys):
    """delete_course(force=False) must raise instead of blocking on input()."""

    def _fail_if_called(*args, **kwargs):
        raise AssertionError("input() must not be called")

    monkeypatch.setattr("builtins.input", _fail_if_called)

    session = FakeSession()

    with pytest.raises(ConfirmationRequired) as excinfo:
        delete_course(
            session, "https://moodle.example.test", "sesskey123", 42, force=False
        )

    assert excinfo.value.course_id == 42
    assert excinfo.value.course_title == "Test Course"
    assert session.post_calls == []

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_delete_course_with_force_proceeds_without_raising(monkeypatch):
    """delete_course(force=True) should submit the deletion form directly."""

    def _fail_if_called(*args, **kwargs):
        raise AssertionError("input() must not be called")

    monkeypatch.setattr("builtins.input", _fail_if_called)

    session = FakeSession()

    delete_course(session, "https://moodle.example.test", "sesskey123", 42, force=True)

    assert len(session.post_calls) == 1
    url, kwargs = session.post_calls[0]
    assert url == "https://moodle.example.test/course/delete.php"
    assert kwargs["data"]["id"] == "42"
    assert kwargs["data"]["delete"] == "delete-token-xyz"
    assert kwargs["data"]["confirm"] == "1"


def test_confirmation_required_is_a_moodle_course_error():
    """The new exception should subclass MoodleCourseError for compatibility."""
    assert issubclass(ConfirmationRequired, MoodleCourseError)
