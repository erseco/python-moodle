"""Unit tests for the ``MoodleClient`` high-level facade."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

import py_moodle
from py_moodle.session import MoodleSession
from py_moodle.settings import Settings


class StubResponse:
    """Minimal HTTP response object used by :class:`StubSession`."""

    def __init__(self, *, text="", json_data=None, status_code=200):
        self.text = text
        self.json_data = json_data
        self.status_code = status_code

    def json(self):
        """Return the configured JSON payload."""
        return self.json_data

    def raise_for_status(self):
        """Mirror the requests.Response API for successful responses."""
        return None


class StubSession:
    """Minimal stand-in for ``requests.Session`` used in login stubs."""

    def __init__(self, *, sesskey="sesskey-abc", webservice_token="token-abc"):
        self.sesskey = sesskey
        self.webservice_token = webservice_token
        self.closed = False

    def get(self, url, **kwargs):
        """Return a canned GET response."""
        return StubResponse(text="<html></html>")

    def post(self, url, **kwargs):
        """Return a canned POST response."""
        return StubResponse(json_data={})

    def close(self):
        """Record that the session was closed."""
        self.closed = True


def build_settings(env_name="local"):
    """Build minimal Settings for client construction tests."""
    return Settings(
        env_name=env_name,
        url="https://moodle.example.test",
        username="user",
        password="secret",
        use_cas=False,
        cas_url=None,
        webservice_token=None,
    )


@pytest.fixture(autouse=True)
def clear_moodle_session_cache():
    """Ensure MoodleSession's per-environment cache does not leak between tests."""
    MoodleSession._cache.clear()
    yield
    MoodleSession._cache.clear()


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


def test_client_construction_explicit_settings(monkeypatch):
    """MoodleClient(settings) derives session/base_url/token/sesskey lazily."""
    from py_moodle.client import MoodleClient

    stub_session = StubSession()
    monkeypatch.setattr("py_moodle.session.login", lambda *a, **k: stub_session)

    client = MoodleClient(build_settings())

    assert client.base_url == "https://moodle.example.test"
    assert client.token == "token-abc"
    assert client.sesskey == "sesskey-abc"
    assert client.session is stub_session


def test_client_construction_explicit_connection():
    """MoodleClient(session=..., base_url=..., ...) works without Settings."""
    from py_moodle.client import MoodleClient

    stub_session = StubSession()

    client = MoodleClient(
        session=stub_session,
        base_url="https://moodle.example.test",
        token="token-xyz",
        sesskey="sesskey-xyz",
    )

    assert client.session is stub_session
    assert client.base_url == "https://moodle.example.test"
    assert client.token == "token-xyz"
    assert client.sesskey == "sesskey-xyz"


def test_client_requires_settings_or_explicit_connection():
    """Constructing with neither settings nor session/base_url must fail clearly."""
    from py_moodle.client import MoodleClient

    with pytest.raises(ValueError):
        MoodleClient()


def test_client_from_env(monkeypatch):
    """from_env() loads settings for the profile and wires a cached MoodleSession."""
    from py_moodle.client import MoodleClient

    monkeypatch.setenv("MOODLE_TEST_URL", "https://moodle.example.test")
    monkeypatch.setenv("MOODLE_TEST_USERNAME", "user")
    monkeypatch.setenv("MOODLE_TEST_PASSWORD", "secret")
    stub_session = StubSession()
    monkeypatch.setattr("py_moodle.session.login", lambda *a, **k: stub_session)

    client = MoodleClient.from_env("test")

    assert client.base_url == "https://moodle.example.test"
    assert client.token == "token-abc"
    assert client.sesskey == "sesskey-abc"
    assert client.session is stub_session
    # Confirm it reused MoodleSession's caching for the "test" environment.
    assert MoodleSession.get("test").session is stub_session


# ---------------------------------------------------------------------------
# Context manager
# ---------------------------------------------------------------------------


def test_client_context_manager_enter_returns_self():
    """__enter__ returns the same client instance."""
    from py_moodle.client import MoodleClient

    client = MoodleClient(
        session=StubSession(),
        base_url="https://moodle.example.test",
        token="t",
        sesskey="s",
    )

    with client as moodle:
        assert moodle is client


def test_client_context_manager_exit_closes_session():
    """__exit__ closes the underlying requests.Session exactly once, safely."""
    from py_moodle.client import MoodleClient

    stub_session = StubSession()
    client = MoodleClient(
        session=stub_session,
        base_url="https://moodle.example.test",
        token="t",
        sesskey="s",
    )

    with client:
        pass

    assert stub_session.closed is True

    # Calling __exit__ again must not raise.
    client.__exit__(None, None, None)

    # Nor must it raise when invoked after an exception inside the block.
    with pytest.raises(RuntimeError):
        with client:
            raise RuntimeError("boom")


def test_client_context_manager_exit_without_open_session_is_safe(monkeypatch):
    """__exit__ must not raise or force a login when the session was never used."""
    from py_moodle.client import MoodleClient

    def _fail_login(*args, **kwargs):
        raise AssertionError("close() must not trigger a lazy login")

    monkeypatch.setattr("py_moodle.session.login", _fail_login)

    client = MoodleClient(build_settings())

    with client:
        pass  # Never touch client.session/.token/.sesskey.


# ---------------------------------------------------------------------------
# Resource namespaces
# ---------------------------------------------------------------------------


def test_client_exposes_resource_namespaces():
    """Each resource namespace is a distinct, non-None object bound to the client."""
    from py_moodle.client import (
        AssignmentsResource,
        CoursesResource,
        FoldersResource,
        LabelsResource,
        MoodleClient,
        ScormResource,
        SectionsResource,
        UsersResource,
    )

    client = MoodleClient(
        session=StubSession(),
        base_url="https://moodle.example.test",
        token="t",
        sesskey="s",
    )

    expected_types = {
        "courses": CoursesResource,
        "sections": SectionsResource,
        "users": UsersResource,
        "folders": FoldersResource,
        "labels": LabelsResource,
        "assignments": AssignmentsResource,
        "scorm": ScormResource,
    }

    seen_ids = set()
    for attr_name, expected_type in expected_types.items():
        resource = getattr(client, attr_name)
        assert resource is not None
        assert resource is not client
        assert isinstance(resource, expected_type)
        seen_ids.add(id(resource))

    assert len(seen_ids) == len(expected_types)


# ---------------------------------------------------------------------------
# Delegation
# ---------------------------------------------------------------------------


def test_courses_list_delegates_to_list_courses(monkeypatch):
    """moodle.courses.list() delegates to course.list_courses with client wiring."""
    from py_moodle.client import MoodleClient

    mock_list_courses = MagicMock(return_value=[{"id": 1}])
    monkeypatch.setattr("py_moodle.course.list_courses", mock_list_courses)

    client = MoodleClient(
        session=StubSession(),
        base_url="https://moodle.example.test",
        token="tok",
        sesskey="sess",
    )

    result = client.courses.list()

    mock_list_courses.assert_called_once_with(
        client.session, client.base_url, token="tok", sesskey="sess"
    )
    assert result == [{"id": 1}]


def test_courses_create_delegates_with_kwargs(monkeypatch):
    """moodle.courses.create(**kwargs) forwards kwargs to course.create_course."""
    from py_moodle.client import MoodleClient

    mock_create_course = MagicMock(return_value={"id": 42})
    monkeypatch.setattr("py_moodle.course.create_course", mock_create_course)

    client = MoodleClient(
        session=StubSession(),
        base_url="https://moodle.example.test",
        token="tok",
        sesskey="sess",
    )

    result = client.courses.create(
        fullname="My course", shortname="my-course", categoryid=1
    )

    mock_create_course.assert_called_once_with(
        client.session,
        client.base_url,
        "sess",
        fullname="My course",
        shortname="my-course",
        categoryid=1,
    )
    assert result == {"id": 42}


def test_scorm_add_delegates_to_add_scorm(monkeypatch):
    """moodle.scorm.add(**kwargs) forwards kwargs to scorm.add_scorm."""
    from py_moodle.client import MoodleClient

    mock_add_scorm = MagicMock(return_value=99)
    monkeypatch.setattr("py_moodle.scorm.add_scorm", mock_add_scorm)

    client = MoodleClient(
        session=StubSession(),
        base_url="https://moodle.example.test",
        token="tok",
        sesskey="sess",
    )

    result = client.scorm.add(
        course_id=1, section_id=1, name="SCORM 1", file_path="package.zip"
    )

    mock_add_scorm.assert_called_once_with(
        client.session,
        client.base_url,
        "sess",
        course_id=1,
        section_id=1,
        name="SCORM 1",
        file_path="package.zip",
    )
    assert result == 99


# ---------------------------------------------------------------------------
# Public API surface / backward compatibility
# ---------------------------------------------------------------------------


def test_public_api_exports_moodle_client():
    """Confirm MoodleClient is importable from the top-level package."""
    from py_moodle import MoodleClient
    from py_moodle.client import MoodleClient as ClientModuleMoodleClient

    assert MoodleClient is ClientModuleMoodleClient
    assert "MoodleClient" in py_moodle.__all__


def test_existing_function_imports_unaffected():
    """Direct low-level imports keep working unchanged (regression guard)."""
    from py_moodle.course import list_courses

    assert callable(list_courses)
