import pytest

from py_moodle.auth import LoginError, login


@pytest.fixture
def moodle(request):
    target = request.config.moodle_target
    return login(url=target.url, username=target.username, password=target.password)


def test_login_success(moodle):
    """Should authenticate and return a session object when credentials are correct."""
    cookies = moodle.cookies.get_dict()
    assert any("MoodleSession" in k for k in cookies)


def test_webservice_token_obtained(moodle):
    """Should obtain a webservice token after login (if enabled for the user)."""
    assert hasattr(moodle, "webservice_token")
    if moodle.webservice_token:
        assert isinstance(moodle.webservice_token, str)
        assert len(moodle.webservice_token) > 0


def test_login_failure(request):
    """
    Attempting to log in with wrong credentials MUST raise LoginError.
    """
    target = request.config.moodle_target  # injected by conftest.py
    with pytest.raises(LoginError):
        login(url=target.url, username="notauser", password="badpass")
