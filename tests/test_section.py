# tests/test_section.py
import random

import pytest

# Import updated course functions
from py_moodle.course import (
    MoodleCourseError,
    create_course,
    delete_course,
    get_course_with_sections_and_modules,
)
from py_moodle.section import MoodleSectionError, create_section, delete_section


# --- Fixtures (the temporary_course fixture will now work) ---
@pytest.fixture(scope="module")
def temporary_course(request):
    """
    Creates a temporary course for all tests in this module and deletes it when finished.
    """
    target = request.config.moodle_target
    from py_moodle.auth import login

    moodle_session = login(
        url=target.url, username=target.username, password=target.password
    )

    if not moodle_session.sesskey:
        pytest.skip("Could not obtain sesskey to create the temporary course.")

    base_url = target.url
    sesskey = moodle_session.sesskey

    fullname = f"Test Course For Sections {random.randint(1000, 9999)}"
    shortname = f"TCS{random.randint(1000, 9999)}"

    try:
        # Now create_course returns a dictionary, as expected
        course = create_course(
            session=moodle_session,
            base_url=base_url,
            sesskey=sesskey,
            fullname=fullname,
            shortname=shortname,
            categoryid=1,
            numsections=1,
        )
        assert isinstance(course, dict) and "id" in course
    except MoodleCourseError as e:
        pytest.skip(f"Could not create temporary course for section tests: {e}")

    yield course  # The course (dict) is available for tests

    try:
        # The teardown will now also work
        delete_course(moodle_session, base_url, sesskey, course["id"], force=True)
    except MoodleCourseError as e:
        print(
            f"\nWARNING: Could not delete temporary course {course['id']}. Error: {e}"
        )


# ... (other fixtures like base_url and sesskey unchanged) ...
@pytest.fixture
def base_url(request):
    return request.config.moodle_target.url


@pytest.fixture
def sesskey(moodle):
    if not hasattr(moodle, "sesskey") or not moodle.sesskey:
        pytest.skip("No sesskey available for section tests.")
    return moodle.sesskey


# --- Tests ---


def test_list_sections(moodle, base_url, sesskey, temporary_course):
    """
    Test that sections can be listed using the new central function.
    """
    course_id = temporary_course["id"]
    token = getattr(moodle, "webservice_token", None)

    try:
        # Use the new canonical function
        data = get_course_with_sections_and_modules(
            moodle, base_url, sesskey, course_id, token=token
        )
    except MoodleCourseError as e:
        pytest.fail(f"Failed to list sections of temporary course: {e}")

    assert isinstance(data, dict)
    assert "sections" in data
    sections = data["sections"]
    assert isinstance(sections, list)
    # A newly created course has section 0 (General) and the one created with it (section 1).
    assert len(sections) >= 2
    assert any(
        s.get("section") == 0 for s in sections
    )  # Verify that the General section (position 0) exists
    assert any(
        s.get("section") == 1 for s in sections
    )  # Verify that the first thematic section exists


def test_create_and_delete_section(moodle, base_url, sesskey, temporary_course):
    """
    Test the creation and deletion of a section within the temporary course.
    """
    course_id = temporary_course["id"]
    token = getattr(moodle, "webservice_token", None)

    # 1. Create a new section
    try:
        new_section_event = create_section(moodle, base_url, sesskey, course_id)
        assert isinstance(
            new_section_event, dict
        ), "create_section should return a dictionary."
        new_section_id = int(new_section_event.get("fields", {}).get("id"))
        assert (
            new_section_id is not None
        ), "The creation response did not contain a section ID."
    except MoodleSectionError as e:
        pytest.skip(
            f"Could not create section (may not be supported by course format): {e}"
        )

    # 2. Verify that the section exists by listing them with the new function
    all_sections_data = get_course_with_sections_and_modules(
        moodle, base_url, sesskey, course_id, token=token
    )
    section_ids = [s["id"] for s in all_sections_data["sections"]]
    assert new_section_id in section_ids

    # 3. Delete the created section
    try:
        delete_section(moodle, base_url, sesskey, course_id, new_section_id)
    except MoodleSectionError as e:
        pytest.fail(f"Failed to delete section {new_section_id}: {e}")

    # 4. Verify that the section no longer exists
    import time

    time.sleep(1)  # Give Moodle a second to process the deletion
    sections_after_delete_data = get_course_with_sections_and_modules(
        moodle, base_url, sesskey, course_id, token=token
    )
    section_ids_after_delete = [s["id"] for s in sections_after_delete_data["sections"]]
    assert new_section_id not in section_ids_after_delete
