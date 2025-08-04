# tests/test_course.py
import datetime
import random

import pytest

from py_moodle.course import (
    MoodleCourseError,
    create_course,
    delete_course,
    get_course,
    get_course_context_id,
    list_courses,
)

# ... (fixtures unchanged) ...


@pytest.fixture(scope="module")
def temporary_course_for_context(request):
    """Create a temporary course for the context test and delete it afterwards."""
    target = request.config.moodle_target
    from py_moodle.auth import login

    moodle_session = login(
        url=target.url, username=target.username, password=target.password
    )
    if not moodle_session.sesskey:
        pytest.skip("No sesskey to create temporary course.")

    base_url = target.url
    sesskey = moodle_session.sesskey
    fullname = f"Test Course For Context ID {random.randint(1000, 9999)}"
    shortname = f"TCCID{random.randint(1000, 9999)}"

    try:
        course = create_course(moodle_session, base_url, sesskey, fullname, shortname)
        yield course
        delete_course(moodle_session, base_url, sesskey, course["id"], force=True)
    except MoodleCourseError as e:
        pytest.skip(f"Could not manage temporary course for context test: {e}")


@pytest.fixture
def base_url(request):
    return request.config.moodle_target.url


@pytest.fixture
def sesskey(moodle):
    if not hasattr(moodle, "sesskey"):
        pytest.skip("No sesskey available")
    return moodle.sesskey


@pytest.fixture
def token(moodle):
    if not moodle.webservice_token:
        pytest.skip("No webservice token available")
    return moodle.webservice_token


def test_list_courses(moodle, base_url, token):
    courses = list_courses(moodle, base_url, token=token)
    assert isinstance(courses, list)
    # A Moodle instance should have at least the site home course
    assert len(courses) > 0
    assert any("fullname" in c for c in courses)


def test_create_and_delete_course(moodle, base_url, sesskey, token):
    """
    Tests the full lifecycle of a course: creation, verification, and deletion.
    """
    fullname = f"pytest-course-{random.randint(1000, 9999)}"
    shortname = f"pyt-c-{random.randint(1000, 9999)}"
    now = datetime.datetime.now()

    # 1. Create the course
    course = create_course(
        session=moodle,
        base_url=base_url,
        sesskey=sesskey,
        fullname=fullname,
        shortname=shortname,
        categoryid=1,
        summary="Created by test_create_and_delete_course",
        # startdate={"day": now.day, "month": now.month, "year": now.year},
        startdate={
            "day": now.day,
            "month": now.month,
            "year": now.year,
            "hour": 0,
            "minute": 0,
        },
        # enddate={"enabled": 0} # Disable end date for simplicity
        enddate={
            "enabled": 0,
            "day": now.day,
            "month": now.month,
            "year": now.year + 1,
            "hour": 0,
            "minute": 0,
        },
    )

    # Assert that create_course returns a dictionary with the expected keys
    assert isinstance(course, dict)
    assert isinstance(course["id"], int)
    assert "id" in course
    assert course["fullname"] == fullname
    assert course["shortname"] == shortname

    course_id = course["id"]

    # 2. Delete the course
    delete_course(moodle, base_url, sesskey, course_id, force=True)

    # 3. Verify the course is gone
    # get_course will call core_course_get_contents which raises an exception
    # if the course ID is invalid. This is the expected behavior.

    with pytest.raises(
        MoodleCourseError,
        match=r"(Invalid value for courseid|The course with id .* was not found|Can't find data record in database table course|Failed to parse course state from AJAX: Can't find data record in database.)",
    ):
        get_course(moodle, base_url, sesskey, course_id, token=token)


def test_get_course_context_id(moodle, base_url, temporary_course_for_context):
    """
    Verify that get_course_context_id extracts a valid numeric context ID from a course page.
    """
    course_id = temporary_course_for_context["id"]

    try:
        # 1. Call the function to test
        context_id = get_course_context_id(
            session=moodle, base_url=base_url, course_id=course_id
        )

        # 2. Verify the result
        assert isinstance(context_id, int), "The context ID should be an integer."
        assert context_id > 0, "The context ID should be a positive number."

    except MoodleCourseError as e:
        pytest.fail(f"get_course_context_id failed with an unexpected exception: {e}")
