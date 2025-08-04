# tests/test_module.py
import random
import time

import pytest

from py_moodle.label import add_label
from py_moodle.module import (
    MoodleModuleError,
    delete_module,
    get_module_info,
    get_module_types,
    rename_module_name,
)

# --- Fixtures ---


@pytest.fixture
def base_url(request):
    """Base URL of the Moodle instance, from conftest.py."""
    return request.config.moodle_target.url


@pytest.fixture
def sesskey(moodle):
    """Session key extracted by the 'moodle' fixture."""
    if not moodle.sesskey:
        pytest.skip("No sesskey available for module tests.")
    return moodle.sesskey


@pytest.fixture
def temporary_module(moodle, request, temporary_course_for_labels, first_section_id):
    """
    Fixture that creates a temporary module (a label) for testing and cleans it up.
    Yields the cmid of the created module.
    temporary_course_for_labels and first_section_id fixtures are defined on conftest.py
    """
    base_url = request.config.moodle_target.url
    sesskey = moodle.sesskey

    initial_html = "<p>Initial content for module test</p>"
    initial_name = f"Initial Name {random.randint(1000, 9999)}"

    cmid = add_label(
        session=moodle,
        base_url=base_url,
        sesskey=sesskey,
        course_id=temporary_course_for_labels["id"],
        section_id=first_section_id,
        html=initial_html,
        name=initial_name,
    )

    yield cmid, initial_name

    # Teardown: delete the module
    try:
        delete_module(moodle, base_url, sesskey, cmid)
    except MoodleModuleError:
        # Ignore if it's already deleted or fails
        pass


# --- Tests ---


def test_get_module_types_success(moodle, base_url, sesskey):
    """
    Tests if we can successfully fetch the list of available module types.
    """
    try:
        module_types = get_module_types(
            session=moodle, base_url=base_url, sesskey=sesskey, course_id=1
        )
    except MoodleModuleError as e:
        pytest.fail(f"get_module_types failed with an unexpected exception: {e}")

    # 1. Check the structure of the response
    assert isinstance(module_types, list), "The function should return a list."
    assert len(module_types) > 0, "The list of module types should not be empty."

    # 2. Check the structure of a single item in the list
    first_module = module_types[0]
    assert isinstance(
        first_module, dict
    ), "Each item in the list should be a dictionary."
    assert "id" in first_module, "Each module must have an 'id' key."
    assert "name" in first_module, "Each module must have a 'name' key (modname)."
    assert (
        "title" in first_module
    ), "Each module must have a 'title' key (translated name)."

    # 3. Verify that common modules exist in the list
    module_names = {m["name"] for m in module_types}
    assert "label" in module_names, "The 'label' module type should be available."
    assert "scorm" in module_names, "The 'scorm' module type should be available."
    assert "folder" in module_names, "The 'folder' module type should be available."

    # 4. Verify that IDs are integers
    assert all(
        isinstance(m["id"], int) for m in module_types
    ), "All module IDs should be integers."


def test_rename_module_name(moodle, request, temporary_module):
    """
    Tests the generic rename_module_name function.
    """
    base_url = request.config.moodle_target.url
    sesskey = moodle.sesskey
    cmid, initial_name = temporary_module

    # 1. Verify initial name
    module_info_before = get_module_info(moodle, base_url, sesskey, cmid)
    assert module_info_before.get("cm", {}).get("name") == initial_name

    # 2. Rename the module
    new_name = f"Renamed Module {random.randint(1000, 9999)}"
    success = rename_module_name(moodle, base_url, sesskey, cmid, name=new_name)
    assert success is True, "rename_module_name should return True on success."

    # 3. Verify the change was applied
    time.sleep(1)  # Give Moodle a moment to process the update
    module_info_after = get_module_info(moodle, base_url, sesskey, cmid)
    assert (
        module_info_after.get("cm", {}).get("name") == new_name
    ), "The module name was not updated correctly."
