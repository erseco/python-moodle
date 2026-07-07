"""Unit tests for the transport strategy modules in ``py_moodle.transport``."""

import pytest

from py_moodle.course import MoodleCourseError, list_courses
from py_moodle.transport import TransportError, TransportUnavailableError
from py_moodle.transport import ajax as ajax_transport
from py_moodle.transport import webservice as webservice_transport

FAKE_TOKEN = "fake-wstoken-abcdef0123456789"
FAKE_SESSKEY = "fake-sesskey-9f8e7d6c"
BASE_URL = "https://moodle.example.test"


class StubResponse:
    """Minimal ``requests.Response``-like object for deterministic tests."""

    def __init__(self, *, status_code=200, text="", json_data=None):
        self.status_code = status_code
        self.text = text
        self._json_data = json_data

    def json(self):
        """Return the configured JSON payload."""
        return self._json_data


class StubSession:
    """Records GET/POST calls and dispatches canned responses by URL."""

    def __init__(self, *, get_result=None, post_result=None, post_dispatch=None):
        self.get_result = get_result
        self.post_result = post_result
        self.post_dispatch = post_dispatch or {}
        self.get_calls = []
        self.post_calls = []

    def get(self, url, **kwargs):
        """Record a GET call and return the configured result."""
        self.get_calls.append({"url": url, "kwargs": kwargs})
        return self.get_result

    def post(self, url, **kwargs):
        """Record a POST call and return a result dispatched by URL prefix."""
        self.post_calls.append({"url": url, "kwargs": kwargs})
        for prefix, result in self.post_dispatch.items():
            if url.startswith(prefix):
                return result
        return self.post_result


# ---------------------------------------------------------------------------
# Webservice transport
# ---------------------------------------------------------------------------


def test_webservice_call_returns_parsed_response_on_success():
    """A successful webservice call returns the parsed JSON payload."""
    session = StubSession(post_result=StubResponse(json_data=[{"id": 2}, {"id": 1}]))

    result = webservice_transport.call(
        session, BASE_URL, "core_course_get_courses", FAKE_TOKEN
    )

    assert result == [{"id": 2}, {"id": 1}]


def test_webservice_call_raises_transport_unavailable_on_invalid_token():
    """An 'Invalid token' Moodle response signals a transport fallback."""
    session = StubSession(
        post_result=StubResponse(
            json_data={
                "exception": "moodle_exception",
                "errorcode": "invalidtoken",
                "message": "Invalid token - token not found",
            }
        )
    )

    with pytest.raises(TransportUnavailableError):
        webservice_transport.call(
            session, BASE_URL, "core_course_get_courses", FAKE_TOKEN
        )


def test_webservice_call_raises_transport_error_on_other_moodle_exception():
    """A non-token Moodle exception raises a plain TransportError."""
    session = StubSession(
        post_result=StubResponse(
            json_data={
                "exception": "required_capability_exception",
                "errorcode": "nopermissions",
                "message": "Access control exception",
            }
        )
    )

    with pytest.raises(TransportError) as excinfo:
        webservice_transport.call(
            session, BASE_URL, "core_course_get_courses", FAKE_TOKEN
        )

    assert not isinstance(excinfo.value, TransportUnavailableError)
    assert "Access control exception" in str(excinfo.value)


# ---------------------------------------------------------------------------
# AJAX transport
# ---------------------------------------------------------------------------


def test_ajax_call_returns_unwrapped_data_on_success():
    """A successful AJAX call returns the unwrapped data payload."""
    session = StubSession(
        get_result=StubResponse(text="<html></html>"),
        post_result=StubResponse(
            json_data=[{"error": False, "data": [{"id": 1}, {"id": 2}]}]
        ),
    )

    result = ajax_transport.call(
        session, BASE_URL, "core_course_get_courses", FAKE_SESSKEY
    )

    assert result == [{"id": 1}, {"id": 2}]
    # The pre-flight session refresh must happen before the AJAX call.
    assert session.get_calls
    assert session.get_calls[0]["url"] == f"{BASE_URL}/my/"


def test_ajax_call_without_sesskey_raises_transport_unavailable_without_http():
    """Without a sesskey the AJAX transport fails fast, with no HTTP call."""
    session = StubSession()

    with pytest.raises(TransportUnavailableError):
        ajax_transport.call(session, BASE_URL, "core_course_get_courses", None)

    assert session.get_calls == []
    assert session.post_calls == []


# ---------------------------------------------------------------------------
# list_courses(): migrated to use the transport strategies
# ---------------------------------------------------------------------------


def test_list_courses_uses_webservice_when_token_succeeds():
    """list_courses() returns sorted courses via webservice, without AJAX."""
    session = StubSession(post_result=StubResponse(json_data=[{"id": 2}, {"id": 1}]))

    result = list_courses(session, BASE_URL, token=FAKE_TOKEN)

    assert result == [{"id": 1}, {"id": 2}]
    assert all("lib/ajax/service.php" not in call["url"] for call in session.post_calls)


def test_list_courses_falls_back_to_ajax_on_invalid_token():
    """list_courses() falls back to AJAX when the webservice token is invalid."""
    session = StubSession(
        get_result=StubResponse(text="<html></html>"),
        post_dispatch={
            f"{BASE_URL}/webservice/rest/server.php": StubResponse(
                json_data={
                    "exception": "moodle_exception",
                    "errorcode": "invalidtoken",
                    "message": "Invalid token - token not found",
                }
            ),
            f"{BASE_URL}/lib/ajax/service.php": StubResponse(
                json_data=[{"error": False, "data": [{"id": 2}, {"id": 1}]}]
            ),
        },
    )

    result = list_courses(session, BASE_URL, token="bad-token", sesskey=FAKE_SESSKEY)

    assert result == [{"id": 1}, {"id": 2}]


def test_list_courses_raises_when_neither_transport_usable():
    """list_courses() raises a clear error with no token and no sesskey."""
    session = StubSession()

    with pytest.raises(MoodleCourseError) as excinfo:
        list_courses(session, BASE_URL)

    assert "token or sesskey" in str(excinfo.value)
    assert session.post_calls == []
    assert session.get_calls == []
