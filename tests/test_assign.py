# tests/test_assign.py
import random

import pytest

# Import the new assign functionality
from py_moodle.assign import MoodleAssignError, add_assign
from py_moodle.course import (
    create_course,
    delete_course,
    get_course_with_sections_and_modules,
)

# Import helpers needed for testing
from py_moodle.module import delete_module


# --- Fixtures ---
@pytest.fixture(scope="module")
def temporary_course_for_assign(request):
    """Creates a temporary course for the assign tests and deletes it afterwards."""
    target = request.config.moodle_target
    from py_moodle.auth import login

    moodle_session = login(
        url=target.url, username=target.username, password=target.password
    )
    if not moodle_session.sesskey:
        pytest.skip("Could not get sesskey to create a temporary course.")

    base_url = target.url
    sesskey = moodle_session.sesskey

    fullname = f"Test Course For Assigns {random.randint(1000, 9999)}"
    shortname = f"TCA{random.randint(1000, 9999)}"

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

    # Teardown: delete the course
    delete_course(moodle_session, base_url, sesskey, course["id"], force=True)


@pytest.fixture
def first_section_id_for_assign(moodle, request, temporary_course_for_assign) -> int:
    """Gets the ID of the first thematic section of the temporary course."""
    base_url = request.config.moodle_target.url
    course_id = temporary_course_for_assign["id"]
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
        "Could not find the first thematic section in the temporary course for assign."
    )


# --- Tests ---


def test_add_assign(
    moodle, request, temporary_course_for_assign, first_section_id_for_assign
):
    """
    Tests the creation of a simple assign within a temporary course and section.
    """
    base_url = request.config.moodle_target.url
    course_id = temporary_course_for_assign["id"]
    section_id = first_section_id_for_assign
    sesskey = moodle.sesskey
    token = getattr(moodle, "webservice_token", None)

    # Define assign details
    assign_name = f"Test Assign {random.randint(1000, 9999)}"
    intro_text = "Please submit your work here."

    # 1. Get the list of modules in the section *before* adding the new one
    course_data_before = get_course_with_sections_and_modules(
        moodle, base_url, sesskey, course_id, token=token
    )
    section_before = next(
        (s for s in course_data_before["sections"] if s["id"] == section_id), {}
    )
    cmids_before = {module["id"] for module in section_before.get("modules", [])}

    # 2. Create the assign
    try:
        new_cmid = add_assign(
            session=moodle,
            base_url=base_url,
            sesskey=sesskey,
            course_id=course_id,
            section_id=section_id,
            name=assign_name,
            intro=intro_text,
        )
    except MoodleAssignError as e:
        pytest.fail(f"add_assign failed with an exception: {e}")

    assert isinstance(
        new_cmid, int
    ), "add_assign should return the new course module ID (cmid)."

    # 3. Verify the assign was created by checking the section contents again
    course_data_after = get_course_with_sections_and_modules(
        moodle, base_url, sesskey, course_id, token=token
    )
    section_after = next(
        (s for s in course_data_after["sections"] if s["id"] == section_id), {}
    )
    modules_after = section_after.get("modules", [])

    # Find the newly created module
    new_module = next((m for m in modules_after if m["id"] == new_cmid), None)

    assert (
        new_module is not None
    ), f"Module with new cmid {new_cmid} was not found in the section."
    assert new_module.get("name") == assign_name
    assert new_module.get("modname") == "assign"
    assert new_cmid not in cmids_before, "The new cmid should not have existed before."

    # 4. Clean up the created module
    deleted = delete_module(moodle, base_url, sesskey, new_cmid)
    assert deleted is True, "Failed to clean up the created assign module."
