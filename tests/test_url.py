import random

import pytest

from py_moodle.course import (
    create_course,
    delete_course,
    get_course_with_sections_and_modules,
)
from py_moodle.module import delete_module
from py_moodle.url import MoodleUrlError, add_url


@pytest.fixture(scope="module")
def temporary_course_for_urls(request):
    """Create a temporary course for URL tests and delete it afterwards."""
    target = request.config.moodle_target
    from py_moodle.auth import login

    moodle_session = login(
        url=target.url, username=target.username, password=target.password
    )
    if not moodle_session.sesskey:
        pytest.skip("Could not get sesskey to create a temporary course.")

    base_url = target.url
    sesskey = moodle_session.sesskey

    fullname = f"Test Course For URLs {random.randint(1000, 9999)}"
    shortname = f"TCU{random.randint(1000, 9999)}"

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
def first_section_id_for_urls(moodle, request, temporary_course_for_urls) -> int:
    """Get the ID of the first thematic section of the temporary course."""
    base_url = request.config.moodle_target.url
    course_id = temporary_course_for_urls["id"]
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
        "Could not find the first thematic section in the temporary course for URLs."
    )


def test_add_url(
    moodle,
    request,
    temporary_course_for_urls,
    first_section_id_for_urls,
):
    """Test creating a URL module linking to an external resource."""
    base_url = request.config.moodle_target.url
    course_id = temporary_course_for_urls["id"]
    section_id = first_section_id_for_urls
    sesskey = moodle.sesskey

    external_url = "https://www.example.com/"
    url_name = f"Test URL {random.randint(1000, 9999)}"

    new_cmid = None
    try:
        new_cmid = add_url(
            session=moodle,
            base_url=base_url,
            sesskey=sesskey,
            course_id=course_id,
            section_id=section_id,
            name=url_name,
            external_url=external_url,
        )
    except MoodleUrlError as e:
        pytest.fail(f"add_url failed with an exception: {e}")

    assert isinstance(new_cmid, int), "add_url should return the new course module ID."

    token = getattr(moodle, "webservice_token", None)
    course_data = get_course_with_sections_and_modules(
        moodle, base_url, sesskey, course_id, token
    )
    section = next((s for s in course_data["sections"] if s["id"] == section_id), {})
    new_module = next(
        (m for m in section.get("modules", []) if m["id"] == new_cmid), None
    )

    assert new_module is not None, "Newly created URL module was not found."
    assert new_module.get("name") == url_name
    assert new_module.get("modname") == "url"

    deleted = delete_module(moodle, base_url, sesskey, new_cmid)
    assert deleted is True, "Failed to clean up the created URL module."
