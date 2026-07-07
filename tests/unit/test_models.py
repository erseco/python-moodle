"""Unit tests for the typed domain models in ``py_moodle.models``.

Every entity is exercised with four scenarios, per the issue's testing
requirements:

1. A full realistic payload (all fields populated).
2. A minimal payload with only the required field(s) (optional fields
   default to ``None`` or the documented empty-collection default).
3. A payload missing the required field(s) (raises ``ModelValidationError``).
4. A payload with unknown/extra keys (ignored silently).

These tests require no network access, no Docker, and no live Moodle
instance -- pure in-memory dict fixtures.
"""

from __future__ import annotations

import pytest

from py_moodle.models import (
    Assignment,
    Course,
    CourseModule,
    CourseSection,
    DeleteResult,
    Folder,
    Label,
    ModelValidationError,
    ScormPackage,
    UploadResult,
    User,
)

# ---------------------------------------------------------------------------
# Course
# ---------------------------------------------------------------------------


def test_course_from_full_payload():
    """A full course payload populates every field correctly."""
    payload = {
        "id": 2,
        "shortname": "CS101",
        "fullname": "Intro to CS",
        "categoryid": 1,
        "summary": "An introductory course",
        "format": "topics",
        "startdate": 1690000000,
        "enddate": 1700000000,
        "visible": 1,
    }

    course = Course.from_moodle(payload)

    assert course.id == 2
    assert course.shortname == "CS101"
    assert course.fullname == "Intro to CS"
    assert course.categoryid == 1
    assert course.summary == "An introductory course"
    assert course.format == "topics"
    assert course.startdate == 1690000000
    assert course.enddate == 1700000000
    assert course.visible == 1


def test_course_from_minimal_payload_defaults_optional_fields_to_none():
    """A payload with only the required field defaults optional fields to None."""
    course = Course.from_moodle({"id": 1})

    assert course.id == 1
    assert course.shortname is None
    assert course.fullname is None
    assert course.categoryid is None
    assert course.summary is None
    assert course.format is None
    assert course.startdate is None
    assert course.enddate is None
    assert course.visible is None


def test_course_missing_required_id_raises():
    """A payload missing the required 'id' key raises ModelValidationError."""
    with pytest.raises(ModelValidationError, match="Course"):
        Course.from_moodle({"shortname": "CS101"})


def test_course_ignores_unknown_fields():
    """Unknown/extra keys are silently ignored and do not appear on the model."""
    course = Course.from_moodle({"id": 1, "totally_unknown_field": "x"})

    assert course.id == 1
    assert not hasattr(course, "totally_unknown_field")


# ---------------------------------------------------------------------------
# CourseSection
# ---------------------------------------------------------------------------


def test_course_section_from_full_payload():
    """A full section payload (as in core_courseformat_get_state) is parsed."""
    payload = {
        "id": 10,
        "name": "Section 1",
        "section": 1,
        "visible": 1,
        "summary": "Intro material",
        "cmlist": [101, 102],
    }

    section = CourseSection.from_moodle(payload)

    assert section.id == 10
    assert section.name == "Section 1"
    assert section.section == 1
    assert section.visible == 1
    assert section.summary == "Intro material"
    assert section.cmlist == [101, 102]


def test_course_section_from_minimal_payload_defaults_optional_fields_to_none():
    """A minimal section payload defaults optional fields to None."""
    section = CourseSection.from_moodle({"id": 10})

    assert section.id == 10
    assert section.name is None
    assert section.section is None
    assert section.visible is None
    assert section.summary is None
    assert section.cmlist is None


def test_course_section_missing_required_id_raises():
    """A payload missing 'id' raises ModelValidationError."""
    with pytest.raises(ModelValidationError, match="CourseSection"):
        CourseSection.from_moodle({"name": "Section 1"})


def test_course_section_ignores_unknown_fields():
    """Unknown keys are ignored for CourseSection."""
    section = CourseSection.from_moodle({"id": 10, "totally_unknown_field": "x"})

    assert section.id == 10
    assert not hasattr(section, "totally_unknown_field")


# ---------------------------------------------------------------------------
# CourseModule
# ---------------------------------------------------------------------------


def test_course_module_from_full_payload():
    """A full module payload (as in core_courseformat_get_state's 'cm' entries)."""
    payload = {
        "id": 101,
        "name": "Assignment 1",
        "modname": "assign",
        "sectionid": 10,
        "visible": 1,
        "uservisible": 1,
    }

    module = CourseModule.from_moodle(payload)

    assert module.id == 101
    assert module.name == "Assignment 1"
    assert module.modname == "assign"
    assert module.sectionid == 10
    assert module.visible == 1
    assert module.uservisible == 1


def test_course_module_from_minimal_payload_defaults_optional_fields_to_none():
    """A minimal module payload defaults optional fields to None."""
    module = CourseModule.from_moodle({"id": 101})

    assert module.id == 101
    assert module.name is None
    assert module.modname is None
    assert module.sectionid is None
    assert module.visible is None
    assert module.uservisible is None


def test_course_module_missing_required_id_raises():
    """A payload missing 'id' raises ModelValidationError."""
    with pytest.raises(ModelValidationError, match="CourseModule"):
        CourseModule.from_moodle({"name": "Assignment 1"})


def test_course_module_ignores_unknown_fields():
    """Unknown keys are ignored for CourseModule."""
    module = CourseModule.from_moodle({"id": 101, "totally_unknown_field": "x"})

    assert module.id == 101
    assert not hasattr(module, "totally_unknown_field")


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------


def test_user_from_full_payload():
    """A full user payload (as in core_enrol_get_enrolled_users) is parsed."""
    payload = {
        "id": 5,
        "username": "jdoe",
        "firstname": "Jane",
        "lastname": "Doe",
        "fullname": "Jane Doe",
        "email": "jane.doe@example.com",
    }

    user = User.from_moodle(payload)

    assert user.id == 5
    assert user.username == "jdoe"
    assert user.firstname == "Jane"
    assert user.lastname == "Doe"
    assert user.fullname == "Jane Doe"
    assert user.email == "jane.doe@example.com"


def test_user_from_minimal_payload_defaults_optional_fields_to_none():
    """A minimal user payload defaults optional fields to None."""
    user = User.from_moodle({"id": 5})

    assert user.id == 5
    assert user.username is None
    assert user.firstname is None
    assert user.lastname is None
    assert user.fullname is None
    assert user.email is None


def test_user_missing_required_id_raises():
    """A payload missing 'id' raises ModelValidationError."""
    with pytest.raises(ModelValidationError, match="User"):
        User.from_moodle({"username": "jdoe"})


def test_user_ignores_unknown_fields():
    """Unknown keys are ignored for User."""
    user = User.from_moodle({"id": 5, "totally_unknown_field": "x"})

    assert user.id == 5
    assert not hasattr(user, "totally_unknown_field")


# ---------------------------------------------------------------------------
# Folder
# ---------------------------------------------------------------------------


def test_folder_from_full_payload():
    """A full folder payload (files derived from list_folder_content) is parsed."""
    payload = {
        "cmid": 55,
        "name": "Course Materials",
        "files": ["syllabus.pdf", "notes.docx"],
    }

    folder = Folder.from_moodle(payload)

    assert folder.cmid == 55
    assert folder.name == "Course Materials"
    assert folder.files == ["syllabus.pdf", "notes.docx"]


def test_folder_from_minimal_payload_defaults_files_to_empty_list():
    """A minimal folder payload defaults 'name' to None and 'files' to []."""
    folder = Folder.from_moodle({"cmid": 55})

    assert folder.cmid == 55
    assert folder.name is None
    assert folder.files == []


def test_folder_missing_required_cmid_raises():
    """A payload missing 'cmid' raises ModelValidationError."""
    with pytest.raises(ModelValidationError, match="Folder"):
        Folder.from_moodle({"name": "Course Materials"})


def test_folder_ignores_unknown_fields():
    """Unknown keys are ignored for Folder."""
    folder = Folder.from_moodle({"cmid": 55, "totally_unknown_field": "x"})

    assert folder.cmid == 55
    assert not hasattr(folder, "totally_unknown_field")


# ---------------------------------------------------------------------------
# Label
# ---------------------------------------------------------------------------


def test_label_from_full_payload():
    """A full label payload is parsed."""
    payload = {"cmid": 60, "name": "Welcome", "text": "<p>Welcome to the course</p>"}

    label = Label.from_moodle(payload)

    assert label.cmid == 60
    assert label.name == "Welcome"
    assert label.text == "<p>Welcome to the course</p>"


def test_label_from_minimal_payload_defaults_optional_fields_to_none():
    """A minimal label payload defaults optional fields to None."""
    label = Label.from_moodle({"cmid": 60})

    assert label.cmid == 60
    assert label.name is None
    assert label.text is None


def test_label_missing_required_cmid_raises():
    """A payload missing 'cmid' raises ModelValidationError."""
    with pytest.raises(ModelValidationError, match="Label"):
        Label.from_moodle({"name": "Welcome"})


def test_label_ignores_unknown_fields():
    """Unknown keys are ignored for Label."""
    label = Label.from_moodle({"cmid": 60, "totally_unknown_field": "x"})

    assert label.cmid == 60
    assert not hasattr(label, "totally_unknown_field")


# ---------------------------------------------------------------------------
# Assignment
# ---------------------------------------------------------------------------


def test_assignment_from_full_payload():
    """A full assignment payload is parsed."""
    payload = {
        "cmid": 70,
        "name": "Homework 1",
        "duedate": 1700000000,
        "allowsubmissionsfromdate": 1690000000,
    }

    assignment = Assignment.from_moodle(payload)

    assert assignment.cmid == 70
    assert assignment.name == "Homework 1"
    assert assignment.duedate == 1700000000
    assert assignment.allowsubmissionsfromdate == 1690000000


def test_assignment_from_minimal_payload_defaults_optional_fields_to_none():
    """A minimal assignment payload defaults optional fields to None."""
    assignment = Assignment.from_moodle({"cmid": 70})

    assert assignment.cmid == 70
    assert assignment.name is None
    assert assignment.duedate is None
    assert assignment.allowsubmissionsfromdate is None


def test_assignment_missing_required_cmid_raises():
    """A payload missing 'cmid' raises ModelValidationError."""
    with pytest.raises(ModelValidationError, match="Assignment"):
        Assignment.from_moodle({"name": "Homework 1"})


def test_assignment_ignores_unknown_fields():
    """Unknown keys are ignored for Assignment."""
    assignment = Assignment.from_moodle({"cmid": 70, "totally_unknown_field": "x"})

    assert assignment.cmid == 70
    assert not hasattr(assignment, "totally_unknown_field")


# ---------------------------------------------------------------------------
# ScormPackage
# ---------------------------------------------------------------------------


def test_scorm_package_from_full_payload():
    """A full SCORM package payload is parsed."""
    payload = {"cmid": 80, "name": "Module 1 SCORM", "reference": "scormpackage.zip"}

    scorm = ScormPackage.from_moodle(payload)

    assert scorm.cmid == 80
    assert scorm.name == "Module 1 SCORM"
    assert scorm.reference == "scormpackage.zip"


def test_scorm_package_from_minimal_payload_defaults_optional_fields_to_none():
    """A minimal SCORM package payload defaults optional fields to None."""
    scorm = ScormPackage.from_moodle({"cmid": 80})

    assert scorm.cmid == 80
    assert scorm.name is None
    assert scorm.reference is None


def test_scorm_package_missing_required_cmid_raises():
    """A payload missing 'cmid' raises ModelValidationError."""
    with pytest.raises(ModelValidationError, match="ScormPackage"):
        ScormPackage.from_moodle({"name": "Module 1 SCORM"})


def test_scorm_package_ignores_unknown_fields():
    """Unknown keys are ignored for ScormPackage."""
    scorm = ScormPackage.from_moodle({"cmid": 80, "totally_unknown_field": "x"})

    assert scorm.cmid == 80
    assert not hasattr(scorm, "totally_unknown_field")


# ---------------------------------------------------------------------------
# UploadResult
# ---------------------------------------------------------------------------


def test_upload_result_from_full_payload():
    """A full upload result payload is parsed."""
    payload = {"itemid": 123456, "filename": "document.pdf", "filepath": "/"}

    result = UploadResult.from_moodle(payload)

    assert result.itemid == 123456
    assert result.filename == "document.pdf"
    assert result.filepath == "/"


def test_upload_result_from_minimal_payload_defaults_optional_fields_to_none():
    """A minimal upload result payload defaults optional fields to None."""
    result = UploadResult.from_moodle({"itemid": 123456})

    assert result.itemid == 123456
    assert result.filename is None
    assert result.filepath is None


def test_upload_result_missing_required_itemid_raises():
    """A payload missing 'itemid' raises ModelValidationError."""
    with pytest.raises(ModelValidationError, match="UploadResult"):
        UploadResult.from_moodle({"filename": "document.pdf"})


def test_upload_result_ignores_unknown_fields():
    """Unknown keys are ignored for UploadResult."""
    result = UploadResult.from_moodle({"itemid": 123456, "totally_unknown_field": "x"})

    assert result.itemid == 123456
    assert not hasattr(result, "totally_unknown_field")


# ---------------------------------------------------------------------------
# DeleteResult
# ---------------------------------------------------------------------------


def test_delete_result_from_full_payload():
    """A full delete result payload is parsed."""
    payload = {"success": True, "message": "Course deleted successfully"}

    result = DeleteResult.from_moodle(payload)

    assert result.success is True
    assert result.message == "Course deleted successfully"


def test_delete_result_from_minimal_payload_defaults_optional_fields_to_none():
    """A minimal delete result payload defaults optional fields to None."""
    result = DeleteResult.from_moodle({"success": False})

    assert result.success is False
    assert result.message is None


def test_delete_result_missing_required_success_raises():
    """A payload missing 'success' raises ModelValidationError."""
    with pytest.raises(ModelValidationError, match="DeleteResult"):
        DeleteResult.from_moodle({"message": "Deleted"})


def test_delete_result_ignores_unknown_fields():
    """Unknown keys are ignored for DeleteResult."""
    result = DeleteResult.from_moodle({"success": True, "totally_unknown_field": "x"})

    assert result.success is True
    assert not hasattr(result, "totally_unknown_field")
