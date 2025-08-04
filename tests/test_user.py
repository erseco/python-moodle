# tests/test_user.py
import random

import pytest

from py_moodle.user import MoodleUserError, create_user, delete_user, list_course_users


@pytest.fixture
def base_url(request):
    """Base URL of the Moodle instance, from conftest.py."""
    return request.config.moodle_target.url


@pytest.fixture
def token(moodle):
    """Webservice token extracted by the 'moodle' fixture."""
    if not moodle.webservice_token:
        pytest.skip("No webservice token available for user tests.")
    return moodle.webservice_token


@pytest.fixture
def sesskey(moodle):
    """Session key."""
    if not moodle.sesskey:
        pytest.skip("No sesskey available for form-based user tests.")
    return moodle.sesskey


def test_list_course_users(moodle, base_url, token):
    """Test that users from a course can be listed (e.g. the 'site' course)."""
    try:
        # Course with ID 1 is "Site home", usually has the admin.
        users = list_course_users(moodle, base_url, token, course_id=1)
    except MoodleUserError as e:
        pytest.skip(f"Skipping list users test: {e}")

    assert isinstance(users, list)
    assert len(users) > 0
    assert "id" in users[0]
    assert "fullname" in users[0]


def test_create_and_delete_user(moodle, base_url, token, sesskey):
    """
    Test the complete lifecycle: create a user and ensure it gets deleted.
    This test will use the webservice if available, otherwise it will fall back to the form method.
    """
    rand_id = random.randint(10000, 99999)
    new_user_data = {
        "username": f"testuser{rand_id}",
        "password": f"TestPassword{rand_id}!",  # Fulfills complexity policies
        "firstname": "Pytest",
        "lastname": f"User{rand_id}",
        "email": f"testuser{rand_id}@example.com",
    }
    created_user = None

    try:
        # 1. Create the user
        # Pass both token and sesskey to allow the function to choose the method.
        created_user = create_user(
            moodle, base_url, token, sesskey=sesskey, **new_user_data
        )
        assert "id" in created_user and created_user["id"] is not None
        assert created_user["username"] == new_user_data["username"]

    except MoodleUserError as e:
        pytest.fail(f"User creation failed with both webservice and form methods: {e}")

    finally:
        # 2. Delete the user (cleanup)
        if created_user and "id" in created_user:
            try:
                # Pass both token and sesskey for deletion fallback
                deleted = delete_user(
                    moodle, base_url, token, created_user["id"], sesskey=sesskey
                )
                assert (
                    deleted is True
                ), "The user deletion function did not return True."
            except MoodleUserError as e:
                pytest.fail(
                    f"CLEANUP FAILED: Could not delete test user {created_user['id']}: {e}"
                )
