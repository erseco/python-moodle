# tests/test_label.py
import random

import pytest

from py_moodle.label import MoodleLabelError, add_label, delete_label, update_label
from py_moodle.module import get_module_info


def test_add_and_delete_label(
    moodle, request, temporary_course_for_labels, first_section_id
):
    """
    Tests the full lifecycle of a label (create and delete)
    within a temporary course and section.
    temporary_course_for_labels and first_section_id fixtures are defined on conftest.py
    """
    base_url = request.config.moodle_target.url
    course_id = temporary_course_for_labels["id"]
    sesskey = moodle.sesskey

    html = f"<p>Test label from pytest {random.randint(1000, 9999)}</p>"
    name = "pytest label"

    cmid = add_label(
        session=moodle,
        base_url=base_url,
        sesskey=sesskey,
        course_id=course_id,
        section_id=first_section_id,
        html=html,
        name=name,
        visible=1,
    )

    assert cmid is not None, "add_label should return a cmid."

    deleted = delete_label(
        session=moodle,
        base_url=base_url,
        sesskey=sesskey,
        cmid=cmid,
    )

    assert deleted is True, "delete_label should return True."


@pytest.fixture
def temporary_label(moodle, request, temporary_course_for_labels, first_section_id):
    """
    Fixture that creates a label for a test and cleans it up afterwards.
    temporary_course_for_labels and first_section_id fixtures are defined on conftest.py
    """
    base_url = request.config.moodle_target.url
    sesskey = moodle.sesskey

    initial_html = f"<p>Initial content for edit test {random.randint(1000, 9999)}</p>"
    cmid = add_label(
        session=moodle,
        base_url=base_url,
        sesskey=sesskey,
        course_id=temporary_course_for_labels["id"],
        section_id=first_section_id,
        html=initial_html,
    )

    yield cmid, initial_html

    # Teardown
    try:
        delete_label(moodle, base_url, sesskey, cmid)
    except MoodleLabelError:
        # Ignore if it's already deleted or fails, the course cleanup will handle it.
        pass


def test_edit_label_all_fields(moodle, request, temporary_label):
    """
    Tests editing all available fields of a label at once: name, content, and visibility.
    """
    base_url = request.config.moodle_target.url
    sesskey = moodle.sesskey
    cmid, initial_html = temporary_label

    # 1. Verify initial state
    module_info_before = get_module_info(moodle, base_url, sesskey, cmid)
    assert module_info_before.get("intro") == initial_html
    assert module_info_before.get("cm", {}).get("name") == "Label (via CLI)"
    assert module_info_before.get("cm", {}).get("visible") == 1  # Default is visible

    # 2. Edit the label with new content, a new name, and set to hidden
    updated_html = (
        f"<h2>Updated Title</h2><p>Updated content {random.randint(1000, 9999)}</p>"
    )
    updated_name = "Updated Test Label"

    success = update_label(
        session=moodle,
        base_url=base_url,
        cmid=cmid,
        html=updated_html,
        name=updated_name,
        visible=0,
    )
    assert success is True, "update_label should return True on success."

    # 3. Verify the changes were applied
    import time

    time.sleep(1)  # Give Moodle a moment to process the update

    module_info_after = get_module_info(moodle, base_url, sesskey, cmid)
    assert module_info_after.get("cm", {}).get("name") == updated_name
    assert module_info_after.get("cm", {}).get("visible") == 0
    assert module_info_after.get("intro") == updated_html


def test_edit_label_with_complex_html(moodle, request, temporary_label):
    """
    Tests updating a label with more complex HTML to ensure formatting is preserved.
    """
    base_url = request.config.moodle_target.url
    cmid, _ = temporary_label

    lorem_ipsum = "Lorem ipsum dolor sit amet, consectetur adipiscing elit."
    complex_html = (
        f"<h1>Main Title</h1>"
        f"<ul><li><b>Item 1:</b> {lorem_ipsum}</li><li><i>Item 2:</i> Plain text.</li></ul>"
        f"<p>A final paragraph with a <a href='#'>link</a>.</p>"
    )

    success = update_label(moodle, base_url, cmid, html=complex_html)
    assert success is True

    module_info = get_module_info(moodle, base_url, moodle.sesskey, cmid)
    assert module_info.get("intro") == complex_html


def test_edit_label_only_name(moodle, request, temporary_label):
    """
    Tests that updating only the name of a label does not change its content.
    """
    base_url = request.config.moodle_target.url
    cmid, initial_html = temporary_label
    new_name = f"Name Only Update - {random.randint(1000, 9999)}"

    success = update_label(moodle, base_url, cmid, name=new_name)
    assert success is True

    module_info = get_module_info(moodle, base_url, moodle.sesskey, cmid)
    assert module_info.get("cm", {}).get("name") == new_name
    assert module_info.get("intro") == initial_html  # Verify content is unchanged


def test_edit_label_only_visibility(moodle, request, temporary_label):
    """
    Tests toggling the visibility of a label.
    """
    base_url = request.config.moodle_target.url
    cmid, initial_html = temporary_label

    # 1. Hide the label
    success_hide = update_label(moodle, base_url, cmid, visible=0)
    assert success_hide is True

    module_info_hidden = get_module_info(moodle, base_url, moodle.sesskey, cmid)
    assert module_info_hidden.get("cm", {}).get("visible") == 0
    assert (
        module_info_hidden.get("intro") == initial_html
    )  # Verify content is unchanged

    # 2. Show the label again
    success_show = update_label(moodle, base_url, cmid, visible=1)
    assert success_show is True

    module_info_visible = get_module_info(moodle, base_url, moodle.sesskey, cmid)
    assert module_info_visible.get("cm", {}).get("visible") == 1
