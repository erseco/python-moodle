import random

import pytest

from py_moodle.course import (
    create_course,
    delete_course,
    get_course_with_sections_and_modules,
)
from py_moodle.module import delete_module
from py_moodle.page import MoodlePageError, add_page


@pytest.fixture(scope="module")
def temporary_course_for_pages(request):
    """Create a temporary course for page tests and delete it afterwards."""
    target = request.config.moodle_target
    from py_moodle.auth import login

    moodle_session = login(
        url=target.url, username=target.username, password=target.password
    )
    if not moodle_session.sesskey:
        pytest.skip("Could not get sesskey to create a temporary course.")

    base_url = target.url
    sesskey = moodle_session.sesskey

    fullname = f"Test Course For Pages {random.randint(1000, 9999)}"
    shortname = f"TCP{random.randint(1000, 9999)}"

    course = create_course(
        session=moodle_session,
        base_url=base_url,
        sesskey=sesskey,
        fullname=fullname,
        shortname=shortname,
        categoryid=1,
        numsections=1,
    )

    yield course

    delete_course(moodle_session, base_url, sesskey, course["id"], force=True)


@pytest.fixture
def first_section_id_for_pages(moodle, request, temporary_course_for_pages) -> int:
    """Get the ID of the first thematic section of the temporary course."""
    base_url = request.config.moodle_target.url
    course_id = temporary_course_for_pages["id"]
    token = getattr(moodle, "webservice_token", None)

    data = get_course_with_sections_and_modules(
        moodle, base_url, moodle.sesskey, course_id, token=token
    )
    target_section = next(
        (s for s in data.get("sections", []) if s.get("section") == 1), None
    )
    if target_section and "id" in target_section:
        return int(target_section["id"])

    pytest.fail(
        "Could not find the first thematic section in the temporary course for pages."
    )


def test_add_page(
    moodle,
    request,
    temporary_course_for_pages,
    first_section_id_for_pages,
):
    """Test creating a page module with HTML content."""
    base_url = request.config.moodle_target.url
    course_id = temporary_course_for_pages["id"]
    section_id = first_section_id_for_pages
    sesskey = moodle.sesskey

    page_name = f"Test Page {random.randint(1000, 9999)}"
    content = "<p>Hello from automated test page.</p>"

    new_cmid = None
    try:
        new_cmid = add_page(
            session=moodle,
            base_url=base_url,
            sesskey=sesskey,
            course_id=course_id,
            section_id=section_id,
            name=page_name,
            content=content,
        )
    except MoodlePageError as e:
        pytest.fail(f"add_page failed with an exception: {e}")

    assert isinstance(
        new_cmid, int
    ), "add_page should return the new course module ID (cmid)."

    token = getattr(moodle, "webservice_token", None)
    course_data = get_course_with_sections_and_modules(
        moodle, base_url, sesskey, course_id, token
    )
    section = next((s for s in course_data["sections"] if s["id"] == section_id), {})
    new_module = next(
        (m for m in section.get("modules", []) if m["id"] == new_cmid), None
    )

    assert new_module is not None, "Newly created page module was not found."
    assert new_module.get("name") == page_name
    assert new_module.get("modname") == "page"

    deleted = delete_module(moodle, base_url, sesskey, new_cmid)
    assert deleted is True, "Failed to clean up the created page module."
