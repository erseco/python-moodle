"""Unit tests for the idempotent ``ensure_course`` operation."""

from __future__ import annotations

import re

import pytest
from typer.testing import CliRunner

from py_moodle import course as course_module
from py_moodle.course import EnsureCourseResult, ensure_course


def _strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from a string."""
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


# ---------------------------------------------------------------------------
# ensure_course() core function tests
# ---------------------------------------------------------------------------


def test_ensure_course_creates_when_no_existing_course(monkeypatch):
    """No course with the requested shortname exists: a new one is created."""
    monkeypatch.setattr(course_module, "list_courses", lambda *a, **k: [])

    create_calls = []

    def fake_create_course(session, base_url, sesskey, **kwargs):
        create_calls.append(kwargs)
        return {"id": 10, "shortname": "demo", "fullname": "Demo", "categoryid": 2}

    monkeypatch.setattr(course_module, "create_course", fake_create_course)
    monkeypatch.setattr(
        course_module,
        "update_course_basic",
        lambda *a, **k: pytest.fail("update_course_basic must not be called"),
    )

    result = ensure_course(
        object(),
        "https://moodle.example.test",
        "sesskey123",
        shortname="demo",
        fullname="Demo",
        category_id=2,
    )

    assert isinstance(result, EnsureCourseResult)
    assert result.status == "created"
    assert result.course["id"] == 10
    assert len(create_calls) == 1
    assert create_calls[0]["shortname"] == "demo"
    assert create_calls[0]["fullname"] == "Demo"
    assert create_calls[0]["categoryid"] == 2


def test_ensure_course_reuses_when_found_matching_and_update_false(monkeypatch):
    """An existing, matching course is left untouched and reported as reused."""
    existing_course = {
        "id": 5,
        "shortname": "demo",
        "fullname": "Demo",
        "categoryid": 2,
    }
    monkeypatch.setattr(
        course_module, "list_courses", lambda *a, **k: [existing_course]
    )

    def fail_create(*a, **k):
        pytest.fail("create_course must not be called")

    def fail_update(*a, **k):
        pytest.fail("update_course_basic must not be called")

    monkeypatch.setattr(course_module, "create_course", fail_create)
    monkeypatch.setattr(course_module, "update_course_basic", fail_update)

    result = ensure_course(
        object(),
        "https://moodle.example.test",
        "sesskey123",
        shortname="demo",
        fullname="Demo",
        category_id=2,
        update=False,
    )

    assert result.status == "reused"
    assert result.course == existing_course
    assert result.differences is None


def test_ensure_course_conflict_when_found_differs_and_update_false(monkeypatch):
    """A found course with a different fullname reports a conflict, no mutation."""
    existing_course = {
        "id": 5,
        "shortname": "demo",
        "fullname": "Old Name",
        "categoryid": 2,
    }
    monkeypatch.setattr(
        course_module, "list_courses", lambda *a, **k: [existing_course]
    )

    def fail_create(*a, **k):
        pytest.fail("create_course must not be called")

    def fail_update(*a, **k):
        pytest.fail("update_course_basic must not be called")

    monkeypatch.setattr(course_module, "create_course", fail_create)
    monkeypatch.setattr(course_module, "update_course_basic", fail_update)

    result = ensure_course(
        object(),
        "https://moodle.example.test",
        "sesskey123",
        shortname="demo",
        fullname="New Name",
        category_id=2,
        update=False,
    )

    assert result.status == "conflict"
    assert result.course == existing_course
    assert result.differences == {"fullname": ("Old Name", "New Name")}


def test_ensure_course_updates_when_found_and_update_true(monkeypatch):
    """A found course with differing fields is updated when update=True."""
    existing_course = {
        "id": 5,
        "shortname": "demo",
        "fullname": "Old Name",
        "categoryid": 2,
    }
    monkeypatch.setattr(
        course_module, "list_courses", lambda *a, **k: [existing_course]
    )

    def fail_create(*a, **k):
        pytest.fail("create_course must not be called")

    update_calls = []

    def fake_update_course_basic(session, base_url, sesskey, courseid, **kwargs):
        update_calls.append((courseid, kwargs))
        return {
            "id": courseid,
            "shortname": "demo",
            "fullname": "New Name",
            "categoryid": 3,
        }

    monkeypatch.setattr(course_module, "create_course", fail_create)
    monkeypatch.setattr(course_module, "update_course_basic", fake_update_course_basic)

    result = ensure_course(
        object(),
        "https://moodle.example.test",
        "sesskey123",
        shortname="demo",
        fullname="New Name",
        category_id=3,
        update=True,
    )

    assert result.status == "updated"
    assert len(update_calls) == 1
    courseid, kwargs = update_calls[0]
    assert courseid == 5
    assert kwargs == {"fullname": "New Name", "categoryid": 3}
    assert result.course["fullname"] == "New Name"


def test_ensure_course_shortname_lookup_is_exact_match(monkeypatch):
    """A similar-but-not-identical shortname is treated as not found."""
    monkeypatch.setattr(
        course_module,
        "list_courses",
        lambda *a, **k: [
            {"id": 1, "shortname": "demo2", "fullname": "Demo Two", "categoryid": 1}
        ],
    )

    create_calls = []

    def fake_create_course(session, base_url, sesskey, **kwargs):
        create_calls.append(kwargs)
        return {"id": 9, "shortname": "demo", "fullname": "Demo", "categoryid": 1}

    def fail_update(*a, **k):
        pytest.fail("update_course_basic must not be called")

    monkeypatch.setattr(course_module, "create_course", fake_create_course)
    monkeypatch.setattr(course_module, "update_course_basic", fail_update)

    result = ensure_course(
        object(),
        "https://moodle.example.test",
        "sesskey123",
        shortname="demo",
        fullname="Demo",
        category_id=1,
    )

    assert result.status == "created"
    assert len(create_calls) == 1


# ---------------------------------------------------------------------------
# CLI wrapper tests
# ---------------------------------------------------------------------------


class _FakeSettings:
    """Minimal settings stub exposing the ``url`` attribute used by the CLI."""

    url = "https://moodle.example.test"


class _FakeMoodleSession:
    """Minimal MoodleSession stub for CLI tests."""

    session = object()
    settings = _FakeSettings()
    sesskey = "sesskey123"
    token = "tok123"

    @classmethod
    def get(cls, env):
        """Return the fake session regardless of the requested environment."""
        return cls()


def test_cli_courses_ensure_created(monkeypatch):
    """The CLI command reports a created course and exits successfully."""
    from py_moodle.cli import courses as courses_cli
    from py_moodle.cli.app import app

    monkeypatch.setattr(courses_cli, "MoodleSession", _FakeMoodleSession)
    monkeypatch.setattr(
        courses_cli,
        "ensure_course",
        lambda *a, **k: EnsureCourseResult(
            status="created",
            course={"id": 1, "shortname": "demo", "fullname": "Demo", "categoryid": 1},
        ),
    )

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "courses",
            "ensure",
            "--shortname",
            "demo",
            "--fullname",
            "Demo",
            "--category-id",
            "1",
        ],
    )

    assert result.exit_code == 0
    assert "created" in _strip_ansi(result.output)


def test_cli_courses_ensure_conflict_exit_code(monkeypatch):
    """The CLI command exits with code 1 when the result status is conflict."""
    from py_moodle.cli import courses as courses_cli
    from py_moodle.cli.app import app

    monkeypatch.setattr(courses_cli, "MoodleSession", _FakeMoodleSession)
    monkeypatch.setattr(
        courses_cli,
        "ensure_course",
        lambda *a, **k: EnsureCourseResult(
            status="conflict",
            course={"id": 1, "shortname": "demo", "fullname": "Old", "categoryid": 1},
            differences={"fullname": ("Old", "New")},
        ),
    )

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "courses",
            "ensure",
            "--shortname",
            "demo",
            "--fullname",
            "New",
            "--category-id",
            "1",
        ],
    )

    assert result.exit_code == 1
    assert "conflict" in _strip_ansi(result.output)
