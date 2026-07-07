"""Unit tests for the centralized HTTP layer in ``py_moodle.http``."""

import json

import pytest
import requests

from py_moodle.config import DEFAULT_REQUEST_TIMEOUT, DEFAULT_SCRAPE_TIMEOUT
from py_moodle.http import (
    MoodleHttpError,
    MoodleTimeoutError,
    MoodleWebserviceError,
    request_ajax,
    request_form_post,
    request_html_get,
    request_webservice,
    upload_file,
)

FAKE_TOKEN = "fake-wstoken-abcdef0123456789"
FAKE_SESSKEY = "fake-sesskey-9f8e7d6c"
FAKE_PASSWORD = "fake-Sup3rSecret!"
FAKE_AUTH_HEADER = "Bearer fake-auth-token-zzzz9999"
FAKE_COOKIE = "MoodleSession=fake-cookie-value-1234"


class StubResponse:
    """Minimal ``requests.Response``-like object for deterministic tests."""

    def __init__(self, *, status_code=200, text="", json_data=None, json_error=None):
        self.status_code = status_code
        self.text = text
        self._json_data = json_data
        self._json_error = json_error

    def json(self):
        """Return the configured JSON payload or raise the configured error."""
        if self._json_error is not None:
            raise self._json_error
        return self._json_data


class StubSession:
    """Records GET/POST calls and returns canned or raised results."""

    def __init__(self, *, get_result=None, post_result=None):
        self.get_result = get_result
        self.post_result = post_result
        self.get_calls = []
        self.post_calls = []

    def get(self, url, **kwargs):
        """Record a GET call and return or raise the configured result."""
        self.get_calls.append({"url": url, "kwargs": kwargs})
        return self._resolve(self.get_result)

    def post(self, url, **kwargs):
        """Record a POST call and return or raise the configured result."""
        self.post_calls.append({"url": url, "kwargs": kwargs})
        return self._resolve(self.post_result)

    @staticmethod
    def _resolve(result):
        if isinstance(result, BaseException):
            raise result
        return result


class AlwaysRaisingSession:
    """Session whose GET/POST always raise the given exception, forever."""

    def __init__(self, exc_factory):
        self.exc_factory = exc_factory
        self.get_calls = 0
        self.post_calls = 0

    def get(self, url, **kwargs):
        """Record the call and always raise."""
        self.get_calls += 1
        raise self.exc_factory()

    def post(self, url, **kwargs):
        """Record the call and always raise."""
        self.post_calls += 1
        raise self.exc_factory()


# ---------------------------------------------------------------------------
# Success path
# ---------------------------------------------------------------------------


def test_request_webservice_success_returns_json_with_default_timeout():
    """A successful webservice call returns the parsed JSON body unchanged."""
    session = StubSession(
        post_result=StubResponse(json_data={"id": 1, "fullname": "Course"})
    )

    result = request_webservice(
        session,
        "https://moodle.example.test",
        "core_course_get_courses",
        token="tok",
    )

    assert result == {"id": 1, "fullname": "Course"}
    assert session.post_calls[0]["kwargs"]["timeout"] == DEFAULT_REQUEST_TIMEOUT


def test_request_webservice_uses_timeout_override():
    """An explicit timeout override takes precedence over the default."""
    session = StubSession(post_result=StubResponse(json_data={"ok": True}))

    request_webservice(
        session,
        "https://moodle.example.test",
        "core_course_get_courses",
        token="tok",
        timeout=5,
    )

    assert session.post_calls[0]["kwargs"]["timeout"] == 5


# ---------------------------------------------------------------------------
# Retry behavior
# ---------------------------------------------------------------------------


def test_request_html_get_retries_on_timeout_then_raises_moodle_timeout_error():
    """GET-style requests retry on transient timeouts before failing."""
    session = AlwaysRaisingSession(requests.exceptions.Timeout)

    with pytest.raises(MoodleTimeoutError):
        request_html_get(session, "https://moodle.example.test/course/view.php?id=1")

    assert session.get_calls > 1  # retried at least once
    assert session.get_calls == session.get_calls  # sanity, count is bounded
    assert session.get_calls <= 5  # small, bounded number of attempts


def test_request_html_get_retries_on_connection_error_then_raises():
    """GET-style requests also retry on connection errors."""
    session = AlwaysRaisingSession(requests.exceptions.ConnectionError)

    with pytest.raises(MoodleHttpError):
        request_html_get(session, "https://moodle.example.test/course/view.php?id=1")

    assert session.get_calls > 1


def test_request_form_post_network_error_raises_immediately_without_retry():
    """POST-style (mutating) requests are never retried automatically."""
    session = AlwaysRaisingSession(requests.exceptions.ConnectionError)

    with pytest.raises(MoodleHttpError):
        request_form_post(session, "https://moodle.example.test/course/edit.php")

    assert session.post_calls == 1


def test_request_webservice_post_timeout_raises_immediately_without_retry():
    """A webservice call sent as POST is never retried on timeout."""
    session = AlwaysRaisingSession(requests.exceptions.Timeout)

    with pytest.raises(MoodleTimeoutError):
        request_webservice(
            session, "https://moodle.example.test", "core_course_get_courses"
        )

    assert session.post_calls == 1


# ---------------------------------------------------------------------------
# HTTP status codes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("status_code", [404, 500])
def test_request_webservice_http_error_status_raises_with_status_code(status_code):
    """4xx/5xx responses raise MoodleHttpError carrying the status code."""
    session = StubSession(
        post_result=StubResponse(status_code=status_code, text="Server error")
    )

    with pytest.raises(MoodleHttpError) as excinfo:
        request_webservice(
            session, "https://moodle.example.test", "core_course_get_courses"
        )

    assert excinfo.value.status_code == status_code


# ---------------------------------------------------------------------------
# Non-JSON body
# ---------------------------------------------------------------------------


def test_request_webservice_invalid_json_raises_typed_error_not_json_decode_error():
    """A non-JSON 200 body raises a typed exception instead of JSONDecodeError."""
    session = StubSession(
        post_result=StubResponse(
            json_error=json.JSONDecodeError("Expecting value", "<html>oops</html>", 0)
        )
    )

    with pytest.raises(MoodleHttpError):
        request_webservice(
            session, "https://moodle.example.test", "core_course_get_courses"
        )


# ---------------------------------------------------------------------------
# Moodle webservice error payload
# ---------------------------------------------------------------------------


def test_request_webservice_moodle_error_payload_raises_typed_error():
    """A Moodle webservice error body raises MoodleWebserviceError with fields."""
    session = StubSession(
        post_result=StubResponse(
            json_data={
                "exception": "moodle_exception",
                "errorcode": "invalidtoken",
                "message": "Invalid token - token not found",
            }
        )
    )

    with pytest.raises(MoodleWebserviceError) as excinfo:
        request_webservice(
            session, "https://moodle.example.test", "core_course_get_courses"
        )

    assert excinfo.value.errorcode == "invalidtoken"
    assert "Invalid token" in str(excinfo.value)


# ---------------------------------------------------------------------------
# Secret redaction
# ---------------------------------------------------------------------------


def test_redacts_wstoken_from_params_on_failure():
    """A webservice token passed as a request param never leaks into errors."""
    session = StubSession(
        post_result=StubResponse(
            status_code=500, text=f"Server error for token {FAKE_TOKEN}"
        )
    )

    with pytest.raises(MoodleHttpError) as excinfo:
        request_webservice(
            session,
            "https://moodle.example.test",
            "core_course_get_courses",
            token=FAKE_TOKEN,
        )

    exc = excinfo.value
    assert FAKE_TOKEN not in str(exc)
    assert FAKE_TOKEN not in repr(exc)
    assert all(FAKE_TOKEN not in str(a) for a in exc.args)


def test_redacts_sesskey_embedded_in_url_on_failure():
    """A sesskey embedded directly in the URL never leaks into errors."""
    session = AlwaysRaisingSession(requests.exceptions.ConnectionError)
    url = f"https://moodle.example.test/lib/ajax/service.php?sesskey={FAKE_SESSKEY}"

    with pytest.raises(MoodleHttpError) as excinfo:
        request_ajax(session, url, [{"index": 0, "methodname": "x", "args": {}}])

    exc = excinfo.value
    assert FAKE_SESSKEY not in str(exc)
    assert FAKE_SESSKEY not in repr(exc)
    assert all(FAKE_SESSKEY not in str(a) for a in exc.args)
    if exc.url:
        assert FAKE_SESSKEY not in exc.url


def test_redacts_password_from_form_post_data_on_failure():
    """A password passed as form data never leaks into raised errors."""
    session = StubSession(
        post_result=StubResponse(
            status_code=403, text=f"Forbidden, password={FAKE_PASSWORD} rejected"
        )
    )

    with pytest.raises(MoodleHttpError) as excinfo:
        request_form_post(
            session,
            "https://moodle.example.test/login/index.php",
            data={"username": "user", "password": FAKE_PASSWORD},
        )

    exc = excinfo.value
    assert FAKE_PASSWORD not in str(exc)
    assert FAKE_PASSWORD not in repr(exc)
    assert all(FAKE_PASSWORD not in str(a) for a in exc.args)


def test_redacts_authorization_header_on_failure():
    """An Authorization header value never leaks into raised errors."""
    session = StubSession(
        post_result=StubResponse(
            status_code=401, text=f"Rejected header Authorization: {FAKE_AUTH_HEADER}"
        )
    )

    with pytest.raises(MoodleHttpError) as excinfo:
        request_form_post(
            session,
            "https://moodle.example.test/webservice/rest/server.php",
            headers={"Authorization": FAKE_AUTH_HEADER},
        )

    exc = excinfo.value
    assert FAKE_AUTH_HEADER not in str(exc)
    assert FAKE_AUTH_HEADER not in repr(exc)
    assert all(FAKE_AUTH_HEADER not in str(a) for a in exc.args)


def test_redacts_cookie_header_on_failure():
    """A Cookie header value never leaks into raised errors."""
    session = StubSession(
        post_result=StubResponse(
            status_code=403, text=f"Rejected cookie: {FAKE_COOKIE}"
        )
    )

    with pytest.raises(MoodleHttpError) as excinfo:
        request_form_post(
            session,
            "https://moodle.example.test/course/edit.php",
            headers={"Cookie": FAKE_COOKIE},
        )

    exc = excinfo.value
    assert FAKE_COOKIE not in str(exc)
    assert FAKE_COOKIE not in repr(exc)
    assert all(FAKE_COOKIE not in str(a) for a in exc.args)


# ---------------------------------------------------------------------------
# request_ajax and upload_file smoke coverage
# ---------------------------------------------------------------------------


def test_request_ajax_returns_data_on_success():
    """A successful AJAX call returns the parsed JSON payload."""
    session = StubSession(
        post_result=StubResponse(json_data=[{"error": False, "data": "[]"}])
    )

    result = request_ajax(
        session,
        "https://moodle.example.test/lib/ajax/service.php?sesskey=abc",
        [{"index": 0, "methodname": "core_course_get_courses", "args": {}}],
    )

    assert result == [{"error": False, "data": "[]"}]


def test_request_ajax_raises_on_ajax_error_shape():
    """An AJAX error entry raises a typed exception with the error message."""
    session = StubSession(
        post_result=StubResponse(
            json_data=[{"error": True, "exception": {"message": "Access denied"}}]
        )
    )

    with pytest.raises(MoodleHttpError) as excinfo:
        request_ajax(
            session,
            "https://moodle.example.test/lib/ajax/service.php?sesskey=abc",
            [{"index": 0, "methodname": "core_course_get_courses", "args": {}}],
        )

    assert "Access denied" in str(excinfo.value)


def test_upload_file_uses_default_upload_timeout(monkeypatch):
    """upload_file applies the shared upload timeout by default."""
    calls = []

    def fake_post(url, **kwargs):
        calls.append({"url": url, "kwargs": kwargs})
        return StubResponse(json_data=[{"itemid": 42}])

    monkeypatch.setattr("py_moodle.http.requests.post", fake_post)

    from py_moodle.config import DEFAULT_UPLOAD_TIMEOUT

    response = upload_file(
        "https://moodle.example.test/webservice/upload.php",
        params={"token": "tok"},
        files={"file": ("demo.txt", b"data", "text/plain")},
    )

    assert response.json() == [{"itemid": 42}]
    assert calls[0]["kwargs"]["timeout"] == DEFAULT_UPLOAD_TIMEOUT


def test_request_html_get_uses_scrape_timeout_by_default():
    """request_html_get defaults to the shared scrape timeout."""
    session = StubSession(get_result=StubResponse(text="<html></html>"))

    request_html_get(session, "https://moodle.example.test/course/view.php?id=1")

    assert session.get_calls[0]["kwargs"]["timeout"] == DEFAULT_SCRAPE_TIMEOUT
