"""Unit tests for generic module creation helpers."""

from __future__ import annotations

from urllib.parse import parse_qs

import pytest

from py_moodle.module import MoodleModuleError, add_generic_module


class _FakeResponse:
    """Minimal response object for module unit tests."""

    def __init__(self, status_code: int, text: str = ""):
        self.status_code = status_code
        self.text = text

    def raise_for_status(self) -> None:
        """Mimic ``requests.Response.raise_for_status``."""
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class _FakeSession:
    """Minimal session object that records add-module requests."""

    def __init__(self, post_response: _FakeResponse):
        self.post_response = post_response
        self.get_calls: list[str] = []
        self.post_calls: list[dict[str, object]] = []

    def get(self, url: str):
        """Return a fixed add-form HTML page."""
        self.get_calls.append(url)
        return _FakeResponse(
            200,
            text="""
            <form id="mform1" action="/course/modedit.php">
                <input type="hidden" name="_qf__mod_assign_mod_form" value="1">
                <input type="hidden" name="gradecat" value="7">
                <input type="text" name="name" value="Old name">
                <textarea name="activityeditor[text]">Old instructions</textarea>
                <input
                    type="checkbox"
                    name="assignsubmission_file_enabled"
                    value="1"
                    checked
                >
                <select name="grade[modgrade_type]">
                    <option value="point" selected>Point</option>
                </select>
            </form>
            """,
        )

    def post(self, url: str, data=None, headers=None, allow_redirects=False):
        """Record the outgoing POST request."""
        self.post_calls.append(
            {
                "url": url,
                "data": data,
                "headers": headers,
                "allow_redirects": allow_redirects,
            }
        )
        return self.post_response


def test_add_generic_module_preserves_form_defaults(monkeypatch):
    """Module creation should submit the fetched add form defaults."""
    session = _FakeSession(_FakeResponse(303))
    course_states = iter(
        [
            {"sections": [{"id": 10, "section": 1, "modules": []}]},
            {"sections": [{"id": 10, "section": 1, "modules": [{"id": 98}]}]},
        ]
    )

    monkeypatch.setattr(
        "py_moodle.module._get_module_id_from_name",
        lambda *args, **kwargs: 123,
    )
    monkeypatch.setattr(
        "py_moodle.module.get_course_with_sections_and_modules",
        lambda *args, **kwargs: next(course_states),
    )
    monkeypatch.setattr("py_moodle.module.time.sleep", lambda *_args: None)

    new_cmid = add_generic_module(
        session=session,
        base_url="https://moodle.example.test",
        sesskey="sesskey123",
        module_name="assign",
        course_id=5,
        section_id=10,
        specific_payload={
            "name": "Essay 1",
            "activityeditor[text]": "<p>Write an essay.</p>",
        },
    )

    assert new_cmid == 98
    assert session.get_calls == [
        "https://moodle.example.test/course/modedit.php?add=assign&type=&course=5&section=1&return=0&sr=-1"
    ]

    posted_data = parse_qs(session.post_calls[0]["data"])
    assert posted_data["gradecat"] == ["7"]
    assert posted_data["assignsubmission_file_enabled"] == ["1"]
    assert posted_data["name"] == ["Essay 1"]
    assert posted_data["activityeditor[text]"] == ["<p>Write an essay.</p>"]


def test_add_generic_module_rejects_non_redirect_responses(monkeypatch):
    """A 200 response should be treated as a failed module creation."""
    session = _FakeSession(
        _FakeResponse(200, '<div class="alert-danger">Validation failed</div>')
    )

    monkeypatch.setattr(
        "py_moodle.module._get_module_id_from_name",
        lambda *args, **kwargs: 123,
    )
    monkeypatch.setattr(
        "py_moodle.module.get_course_with_sections_and_modules",
        lambda *args, **kwargs: {"sections": [{"id": 10, "section": 1, "modules": []}]},
    )

    with pytest.raises(MoodleModuleError, match="Validation failed"):
        add_generic_module(
            session=session,
            base_url="https://moodle.example.test",
            sesskey="sesskey123",
            module_name="assign",
            course_id=5,
            section_id=10,
            specific_payload={"name": "Essay 1"},
        )
