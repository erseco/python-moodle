"""Unit tests for shared HTTP timeout defaults."""

from py_moodle.compat import detect_moodle_compatibility
from py_moodle.config import (
    DEFAULT_LARGE_UPLOAD_TIMEOUT,
    DEFAULT_REQUEST_TIMEOUT,
    DEFAULT_UPLOAD_TIMEOUT,
)
from py_moodle.draftfile import upload_file_to_draft_area
from py_moodle.session import MoodleSession
from py_moodle.settings import Settings
from py_moodle.upload import upload_file_webservice


class FakeResponse:
    """Minimal response object for timeout tests."""

    def __init__(self, text="", json_data=None, status_code=200):
        self.text = text
        self._json_data = json_data
        self.status_code = status_code

    def raise_for_status(self):
        """Raise for failing HTTP statuses."""
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        """Return the configured JSON payload."""
        return self._json_data


class RecordingSession:
    """Minimal session that records GET and POST calls."""

    def __init__(self, get_response=None, post_response=None):
        self.get_response = get_response or FakeResponse()
        self.post_response = post_response or FakeResponse(json_data={})
        self.get_calls = []
        self.post_calls = []

    def get(self, url, **kwargs):
        """Record a GET request."""
        self.get_calls.append({"url": url, "kwargs": kwargs})
        return self.get_response

    def post(self, url, **kwargs):
        """Record a POST request."""
        self.post_calls.append({"url": url, "kwargs": kwargs})
        return self.post_response


def test_session_call_uses_shared_default_request_timeout():
    """Webservice calls should use the centralized request timeout."""
    settings = Settings(
        env_name="local",
        url="https://moodle.example.test",
        username="user",
        password="secret",
        use_cas=False,
        cas_url=None,
        webservice_token=None,
    )
    session = RecordingSession(post_response=FakeResponse(json_data={"ok": True}))
    moodle_session = MoodleSession(settings)
    moodle_session._session = session
    moodle_session._token = "token"

    response = moodle_session.call("core_webservice_get_site_info")

    assert response == {"ok": True}
    assert session.post_calls[0]["kwargs"]["timeout"] == DEFAULT_REQUEST_TIMEOUT


def test_detect_moodle_compatibility_uses_shared_default_request_timeout():
    """Compatibility detection should use the shared timeout for HTTP probes."""
    session = RecordingSession(
        get_response=FakeResponse(
            text='<meta name="generator" content="Moodle 4.5.2+ (Build: 20241001)">'
        ),
        post_response=FakeResponse(json_data={"exception": "disabled"}),
    )

    compatibility = detect_moodle_compatibility(
        session, "https://moodle.example.test", token="token"
    )

    assert compatibility.version.major == 4
    assert session.post_calls[0]["kwargs"]["timeout"] == DEFAULT_REQUEST_TIMEOUT
    assert session.get_calls[0]["kwargs"]["timeout"] == DEFAULT_REQUEST_TIMEOUT


def test_upload_helpers_use_shared_default_timeouts(tmp_path, monkeypatch):
    """Upload helpers should default to the shared upload timeout constants."""
    file_path = tmp_path / "demo.txt"
    file_path.write_text("demo content", encoding="utf-8")

    upload_calls = []

    def fake_requests_post(url, **kwargs):
        upload_calls.append({"url": url, "kwargs": kwargs})
        return FakeResponse(json_data=[{"itemid": 7}])

    monkeypatch.setattr("py_moodle.upload.requests.post", fake_requests_post)

    itemid = upload_file_webservice(
        "https://moodle.example.test", "token", str(file_path)
    )

    assert itemid == 7
    assert upload_calls[0]["kwargs"]["timeout"] == DEFAULT_UPLOAD_TIMEOUT

    monkeypatch.setattr("py_moodle.draftfile.detect_upload_repo", lambda *args: 9)
    draft_session = RecordingSession(
        post_response=FakeResponse(json_data={"id": 99, "filename": "demo.txt"})
    )

    draft_itemid, filename = upload_file_to_draft_area(
        session=draft_session,
        base_url="https://moodle.example.test",
        sesskey="sesskey",
        course_id=12,
        course_context_id=34,
        file_path=str(file_path),
    )

    assert draft_itemid == 99
    assert filename == "demo.txt"
    assert (
        draft_session.post_calls[0]["kwargs"]["timeout"] == DEFAULT_LARGE_UPLOAD_TIMEOUT
    )
