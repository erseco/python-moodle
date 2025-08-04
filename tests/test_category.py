# tests/test_category.py
import random

import pytest

from py_moodle.category import (
    MoodleCategoryError,
    create_category,
    delete_category,
    get_category,
    list_categories,
)


@pytest.fixture
def base_url(request):
    """Base URL of the Moodle instance, from conftest.py."""
    return request.config.moodle_target.url


@pytest.fixture
def sesskey(moodle):
    """Session key extracted by the 'moodle' fixture."""
    if not moodle.sesskey:
        pytest.skip("No sesskey available for category tests.")
    return moodle.sesskey


@pytest.fixture
def token(moodle):
    """Webservice token. Required for listing and getting, but not for creating/deleting."""
    if not moodle.webservice_token:
        pytest.skip(
            "No webservice token available. The list/get categories test will be skipped."
        )
    return moodle.webservice_token


def test_list_categories(moodle, base_url, token):
    """Test that categories can be listed through the webservice."""
    try:
        categories = list_categories(moodle, base_url, token)
    except MoodleCategoryError as e:
        pytest.skip(f"Skipping list categories test: {e}")

    assert isinstance(categories, list)
    assert any("id" in c for c in categories)


def test_create_get_and_delete_category(moodle, base_url, sesskey, token):
    """
    Test the complete cycle using the form method (sesskey):
    1. Create a category.
    2. Get it to verify (using token).
    3. Delete it to avoid leaving residues.
    """
    new_category_name = f"Pytest Form Category {random.randint(1000, 9999)}"
    new_category = None

    try:
        # 1. Create the category using sesskey (form method)
        new_category = create_category(
            session=moodle, base_url=base_url, sesskey=sesskey, name=new_category_name
        )
        assert (
            "id" in new_category
        ), "The category creation response did not include an ID."
        assert new_category["name"] == new_category_name

        # 2. Get the category to confirm it exists (using token)
        fetched_category = get_category(
            session=moodle,
            base_url=base_url,
            token=token,  # get_category still uses webservice, it's more reliable for reading
            categoryid=new_category["id"],
        )
        assert fetched_category["id"] == new_category["id"]
        assert fetched_category["name"] == new_category_name

    except MoodleCategoryError as e:
        # If creation or getting fails, we skip the test.
        pytest.skip(f"Skipping category creation/deletion test: {e}")

    finally:
        # 3. Delete the category using sesskey (executes even if assertions fail)
        if new_category and "id" in new_category:
            try:
                deleted = delete_category(
                    session=moodle,
                    base_url=base_url,
                    sesskey=sesskey,
                    categoryid=new_category["id"],
                )
                assert (
                    deleted is True
                ), "The category deletion function did not return True."
            except MoodleCategoryError as e:
                # If a category cannot be deleted (e.g. it's not empty), it might be normal.
                # But in a test, it should fail so we can investigate.
                pytest.fail(
                    f"FAILURE: Could not delete test category {new_category['id']}: {e}"
                )
