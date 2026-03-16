"""Unit tests for user-facing error wording."""

import pytest

from py_moodle.auth import LoginError, MoodleAuth
from py_moodle.course import MoodleCourseError, list_courses
from py_moodle.session import MoodleSession, MoodleSessionError
from py_moodle.settings import Settings


class StubResponse:
    """Minimal HTTP response object for error-message tests."""

    def __init__(self, *, text="", url="https://moodle.example.test/", json_data=None):
        self.text = text
        self.url = url
        self.json_data = json_data
        self.status_code = 200

    def json(self):
        """Return the configured JSON payload."""
        return self.json_data

    def raise_for_status(self):
        """Mirror the requests.Response API for successful responses."""
        return None


class StubSession:
    """Minimal session object for deterministic unit tests."""

    def __init__(self, *, get_response=None, post_response=None):
        self.get_response = get_response or StubResponse()
        self.post_response = post_response or StubResponse(json_data={})
        self.sesskey = None
        self.webservice_token = None

    def get(self, url, **kwargs):
        """Return the canned GET response."""
        return self.get_response

    def post(self, url, **kwargs):
        """Return the canned POST response."""
        return self.post_response


class StubCompatibility:
    """Minimal compatibility helper that never finds a sesskey."""

    @staticmethod
    def extract_sesskey(text):
        """Return no sesskey for the provided HTML payload."""
        return None


def build_settings():
    """Create a minimal settings object for session tests."""
    return Settings(
        env_name="local",
        url="https://moodle.example.test",
        username="user",
        password="secret",
        use_cas=False,
        cas_url=None,
        webservice_token=None,
    )


def test_standard_login_error_mentions_credentials_and_cas():
    """Invalid login errors should point users to credentials and CAS settings."""
    auth = MoodleAuth(
        base_url="https://moodle.example.test",
        username="user",
        password="wrong",
    )
    auth.compatibility = type(
        "Compat",
        (),
        {"extract_login_token": staticmethod(lambda text: "token")},
    )()
    auth.session = StubSession(
        get_response=StubResponse(text="<input name='logintoken' value='token'>"),
        post_response=StubResponse(
            text="Invalid login",
            url="https://moodle.example.test/login/index.php",
        ),
    )

    with pytest.raises(LoginError) as excinfo:
        auth._standard_login()

    message = str(excinfo.value)
    assert "invalid username or password" in message
    assert "MOODLE_USERNAME" in message
    assert "CAS" in message


def test_session_login_error_mentions_webservice_and_cas(monkeypatch):
    """Missing token and sesskey errors should point to the likely fixes."""
    stub_session = StubSession(get_response=StubResponse(text="<html></html>"))
    monkeypatch.setattr("py_moodle.session.login", lambda *args, **kwargs: stub_session)
    monkeypatch.setattr(
        "py_moodle.session.get_session_compatibility",
        lambda session: StubCompatibility(),
    )

    moodle_session = MoodleSession(build_settings())

    with pytest.raises(MoodleSessionError) as excinfo:
        moodle_session._login()

    message = str(excinfo.value)
    assert "no webservice token or sesskey was available" in message
    assert "Moodle mobile web service" in message
    assert "CAS/session configuration" in message


def test_session_call_without_token_mentions_wsfunction():
    """Missing-token errors should explain how to restore webservice access."""
    moodle_session = MoodleSession(build_settings())
    moodle_session._session = StubSession()

    with pytest.raises(LoginError) as excinfo:
        moodle_session.call("core_webservice_get_site_info")

    message = str(excinfo.value)
    assert "core_webservice_get_site_info" in message
    assert "pre-configured token" in message
    assert "Moodle mobile web service" in message


def test_session_call_api_error_mentions_wsfunction():
    """API errors should include the failing Moodle webservice function name."""
    moodle_session = MoodleSession(build_settings())
    moodle_session._session = StubSession(
        post_response=StubResponse(
            json_data={
                "message": "Access control exception",
                "errorcode": "accessexception",
                "exception": "required_capability_exception",
            }
        )
    )
    moodle_session._token = "token"

    with pytest.raises(MoodleSessionError) as excinfo:
        moodle_session.call("core_course_get_courses")

    message = str(excinfo.value)
    assert "core_course_get_courses" in message
    assert "Access control exception" in message
    assert "accessexception" in message


def test_list_courses_error_mentions_token_or_sesskey():
    """Course-listing errors should explain which session credentials are missing."""
    with pytest.raises(MoodleCourseError) as excinfo:
        list_courses(object(), "https://moodle.example.test")

    message = str(excinfo.value)
    assert "valid webservice token or sesskey" in message
    assert "Moodle mobile web service" in message
