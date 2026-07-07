"""Unit tests for the logging-based repo-id fallback warning in draftfile.py."""

import logging

from py_moodle.draftfile import MoodleDraftFileError, upload_file_to_draft_area


class FakeResponse:
    """Minimal HTTP response stub for the draft-upload endpoint."""

    def __init__(self, *, json_data=None, status_code=200):
        """Store the canned JSON payload and status code."""
        self.status_code = status_code
        self._json_data = json_data or {}

    def raise_for_status(self):
        """Mirror the requests.Response API for successful responses."""
        return None

    def json(self):
        """Return the configured JSON payload."""
        return self._json_data


class FakeSession:
    """Fake ``requests.Session`` that records POST calls for assertions."""

    def __init__(self):
        """Initialize the call log."""
        self.post_calls = []

    def post(self, url, **kwargs):
        """Record the POST call and return a canned success response."""
        self.post_calls.append((url, kwargs))
        return FakeResponse(json_data={"id": 123, "filename": "test.txt"})


def test_repo_id_fallback_logs_warning_not_print(monkeypatch, tmp_path, caplog, capsys):
    """When repo-id auto-detection fails, a warning is logged, not printed."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("hello")

    def _raise(*args, **kwargs):
        raise MoodleDraftFileError("boom")

    monkeypatch.setattr("py_moodle.draftfile.detect_upload_repo", _raise)

    session = FakeSession()

    with caplog.at_level(logging.WARNING, logger="py_moodle.draftfile"):
        upload_file_to_draft_area(
            session=session,
            base_url="https://moodle.example.test",
            sesskey="sesskey123",
            course_id=1,
            course_context_id=2,
            file_path=str(test_file),
            itemid=999,
        )

    warning_records = [
        record
        for record in caplog.records
        if record.name == "py_moodle.draftfile" and record.levelno == logging.WARNING
    ]
    assert warning_records, "Expected a WARNING record on py_moodle.draftfile"
    assert any(
        "Falling back to default ID 5" in record.message for record in warning_records
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""

    # The fallback repo_id of 5 must still be used in the outgoing payload.
    _, kwargs = session.post_calls[0]
    assert kwargs["data"]["repo_id"] == "5"
