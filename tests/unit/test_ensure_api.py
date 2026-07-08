"""Unit tests for the idempotent ensure-style content provisioning API.

All Moodle interactions are fully mocked: no network access is performed.
The tests patch ``get_course_with_sections_and_modules`` (the lookup) and the
``add_*``/``create_section`` primitives (the mutations) so behaviour can be
asserted purely from Python.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from py_moodle import course as course_module
from py_moodle import ensure as ensure_pkg
from py_moodle.ensure import (
    EnsureModuleResult,
    EnsureSectionResult,
    ensure_folder,
    ensure_label,
    ensure_module,
    ensure_resource,
    ensure_section,
)

SESSION = object()
BASE_URL = "https://moodle.example.test"
SESSKEY = "sesskey123"
COURSE_ID = 42
SECTION_ID = 7


def _patch_course(monkeypatch, course_data):
    """Patch the course lookup to return ``course_data``."""
    monkeypatch.setattr(
        course_module,
        "get_course_with_sections_and_modules",
        lambda *a, **k: course_data,
    )


# ---------------------------------------------------------------------------
# ensure_module()
# ---------------------------------------------------------------------------


def test_ensure_module_reuses_existing_without_calling_create_fn(monkeypatch):
    """A module with matching (name, modname) is reused; create_fn is not run."""
    course_data = {
        "sections": [
            {"modules": [{"id": 3, "name": "Other", "modname": "resource"}]},
            {"modules": [{"id": 101, "name": "Intro", "modname": "label"}]},
        ]
    }
    _patch_course(monkeypatch, course_data)

    create_fn = MagicMock(return_value=999)
    result = ensure_module(
        SESSION,
        BASE_URL,
        SESSKEY,
        COURSE_ID,
        SECTION_ID,
        name="Intro",
        modname="label",
        create_fn=create_fn,
    )

    assert isinstance(result, EnsureModuleResult)
    assert result.status == "reused"
    assert result.cmid == 101
    assert result.module == {"id": 101, "name": "Intro", "modname": "label"}
    create_fn.assert_not_called()


def test_ensure_module_creates_when_absent(monkeypatch):
    """When no module matches, create_fn is called exactly once."""
    _patch_course(monkeypatch, {"sections": []})

    create_fn = MagicMock(return_value=555)
    result = ensure_module(
        SESSION,
        BASE_URL,
        SESSKEY,
        COURSE_ID,
        SECTION_ID,
        name="New",
        modname="label",
        create_fn=create_fn,
    )

    assert result.status == "created"
    assert result.cmid == 555
    assert result.module is None
    create_fn.assert_called_once_with()


def test_ensure_module_discriminates_by_modname(monkeypatch):
    """A same-name module with a different modname is treated as absent."""
    course_data = {
        "sections": [
            {"modules": [{"id": 9, "name": "Shared", "modname": "resource"}]},
        ]
    }
    _patch_course(monkeypatch, course_data)

    create_fn = MagicMock(return_value=12)
    result = ensure_module(
        SESSION,
        BASE_URL,
        SESSKEY,
        COURSE_ID,
        SECTION_ID,
        name="Shared",
        modname="label",
        create_fn=create_fn,
    )

    assert result.status == "created"
    assert result.cmid == 12
    create_fn.assert_called_once_with()


# ---------------------------------------------------------------------------
# ensure_label / ensure_resource / ensure_folder delegation
# ---------------------------------------------------------------------------


def test_ensure_label_delegates_with_correct_modname_and_kwargs(monkeypatch):
    """ensure_label forwards html/name/visible to add_label and binds modname."""
    _patch_course(monkeypatch, {"sections": []})

    import py_moodle.label as label_module

    captured = {}

    def fake_add_label(
        session, base_url, sesskey, course_id, section_id, html, name="x", visible=1
    ):
        captured.update(
            session=session,
            base_url=base_url,
            sesskey=sesskey,
            course_id=course_id,
            section_id=section_id,
            html=html,
            name=name,
            visible=visible,
        )
        return 777

    monkeypatch.setattr(label_module, "add_label", fake_add_label)

    result = ensure_label(
        SESSION,
        BASE_URL,
        SESSKEY,
        COURSE_ID,
        SECTION_ID,
        name="MyLabel",
        html="<p>hi</p>",
        visible=0,
    )

    assert result.status == "created"
    assert result.cmid == 777
    assert captured["name"] == "MyLabel"
    assert captured["html"] == "<p>hi</p>"
    assert captured["visible"] == 0
    assert captured["course_id"] == COURSE_ID
    assert captured["section_id"] == SECTION_ID


def test_ensure_label_reuses_existing_label(monkeypatch):
    """A pre-existing label with the same name is reused without add_label."""
    course_data = {
        "sections": [{"modules": [{"id": 3, "name": "MyLabel", "modname": "label"}]}]
    }
    _patch_course(monkeypatch, course_data)

    import py_moodle.label as label_module

    add_label_spy = MagicMock()
    monkeypatch.setattr(label_module, "add_label", add_label_spy)

    result = ensure_label(
        SESSION,
        BASE_URL,
        SESSKEY,
        COURSE_ID,
        SECTION_ID,
        name="MyLabel",
        html="<p>hi</p>",
    )

    assert result.status == "reused"
    assert result.cmid == 3
    add_label_spy.assert_not_called()


def test_ensure_resource_delegates_with_correct_modname_and_kwargs(monkeypatch):
    """ensure_resource forwards name/file_path/intro/visible to add_resource."""
    _patch_course(monkeypatch, {"sections": []})

    import py_moodle.resource as resource_module

    captured = {}

    def fake_add_resource(
        session,
        base_url,
        sesskey,
        course_id,
        section_id,
        name,
        file_path,
        intro="",
        visible=1,
        progress_callback=None,
    ):
        captured.update(name=name, file_path=file_path, intro=intro, visible=visible)
        return 888

    monkeypatch.setattr(resource_module, "add_resource", fake_add_resource)

    result = ensure_resource(
        SESSION,
        BASE_URL,
        SESSKEY,
        COURSE_ID,
        SECTION_ID,
        name="Notes",
        file_path="/tmp/a.pdf",
        intro="hi",
        visible=1,
    )

    assert result.status == "created"
    assert result.cmid == 888
    assert captured["name"] == "Notes"
    assert captured["file_path"] == "/tmp/a.pdf"
    assert captured["intro"] == "hi"


def test_ensure_folder_delegates_with_correct_modname_and_kwargs(monkeypatch):
    """ensure_folder forwards name/files_itemid/intro_html/visible to add_folder."""
    _patch_course(monkeypatch, {"sections": []})

    import py_moodle.folder as folder_module

    captured = {}

    def fake_add_folder(
        session,
        base_url,
        sesskey,
        course_id,
        section_id,
        name,
        files_itemid,
        intro_html="",
        visible=1,
    ):
        captured.update(
            name=name,
            files_itemid=files_itemid,
            intro_html=intro_html,
            visible=visible,
        )
        return 999

    monkeypatch.setattr(folder_module, "add_folder", fake_add_folder)

    result = ensure_folder(
        SESSION,
        BASE_URL,
        SESSKEY,
        COURSE_ID,
        SECTION_ID,
        name="Docs",
        files_itemid=123,
        intro_html="desc",
        visible=1,
    )

    assert result.status == "created"
    assert result.cmid == 999
    assert captured["name"] == "Docs"
    assert captured["files_itemid"] == 123
    assert captured["intro_html"] == "desc"


# ---------------------------------------------------------------------------
# ensure_section()
# ---------------------------------------------------------------------------


def test_ensure_section_reuses_same_named_section(monkeypatch):
    """A section whose name already matches is reused, no creation/rename."""
    course_data = {"sections": [{"id": 5, "name": "Week 1", "modules": []}]}
    _patch_course(monkeypatch, course_data)

    import py_moodle.section as section_module

    create_spy = MagicMock()
    monkeypatch.setattr(section_module, "create_section", create_spy)
    rename_spy = MagicMock()
    monkeypatch.setattr(ensure_pkg, "_rename_section", rename_spy)

    result = ensure_section(SESSION, BASE_URL, SESSKEY, COURSE_ID, name="Week 1")

    assert isinstance(result, EnsureSectionResult)
    assert result.status == "reused"
    assert result.section == {"id": 5, "name": "Week 1", "modules": []}
    create_spy.assert_not_called()
    rename_spy.assert_not_called()


def test_ensure_section_creates_and_renames_when_absent(monkeypatch):
    """When no section matches, a section is created and then renamed."""
    _patch_course(monkeypatch, {"sections": [{"id": 1, "name": "General"}]})

    import py_moodle.section as section_module

    created_event = {"name": "section", "fields": {"id": 77, "number": 3}}
    create_spy = MagicMock(return_value=created_event)
    monkeypatch.setattr(section_module, "create_section", create_spy)
    rename_spy = MagicMock()
    monkeypatch.setattr(ensure_pkg, "_rename_section", rename_spy)

    result = ensure_section(SESSION, BASE_URL, SESSKEY, COURSE_ID, name="New Week")

    assert result.status == "created"
    assert result.section == {"id": 77, "name": "New Week"}
    create_spy.assert_called_once()
    rename_spy.assert_called_once_with(SESSION, BASE_URL, SESSKEY, 77, "New Week")


# ---------------------------------------------------------------------------
# create_or_update_course()
# ---------------------------------------------------------------------------


def test_create_or_update_course_delegates_with_update_true(monkeypatch):
    """create_or_update_course calls ensure_course with update=True."""
    captured = {}

    def fake_ensure_course(
        session,
        base_url,
        sesskey,
        *,
        shortname,
        fullname,
        category_id,
        token=None,
        update=False,
        **create_kwargs,
    ):
        captured.update(
            shortname=shortname,
            fullname=fullname,
            category_id=category_id,
            token=token,
            update=update,
            create_kwargs=create_kwargs,
        )
        return course_module.EnsureCourseResult(status="updated", course={"id": 1})

    monkeypatch.setattr(course_module, "ensure_course", fake_ensure_course)

    result = course_module.create_or_update_course(
        SESSION,
        BASE_URL,
        SESSKEY,
        shortname="CS101",
        fullname="Intro CS",
        category_id=2,
        numsections=6,
    )

    assert result.status == "updated"
    assert captured["update"] is True
    assert captured["shortname"] == "CS101"
    assert captured["fullname"] == "Intro CS"
    assert captured["category_id"] == 2
    assert captured["create_kwargs"] == {"numsections": 6}
