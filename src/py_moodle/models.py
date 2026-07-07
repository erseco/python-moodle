"""Typed domain models for common Moodle entities.

This module provides lightweight, dependency-free dataclasses that give a
typed, self-documenting shape to the raw ``dict``/``list[dict]`` payloads
returned by the rest of :mod:`py_moodle` (e.g. ``course.list_courses()``,
``user.list_course_users()``, ``folder.list_folder_content()``).

Each model exposes a ``from_moodle(data: dict)`` classmethod that:

- Raises :class:`ModelValidationError` when a required field is missing.
- Defaults missing optional fields to ``None`` (or an explicit
  empty-collection default, e.g. ``Folder.files``).
- Silently ignores unknown/extra keys, since real-world Moodle payloads
  routinely carry version- or plugin-specific extra fields.

This module is purely additive: it does not change the return type or
signature of any existing public function in the library.

Note on ``slots``:
    ``dataclasses.dataclass`` only accepts the ``slots`` keyword argument on
    Python 3.10+. Since this project supports Python 3.9 as its minimum
    version, ``slots=True`` is applied conditionally (Python 3.10+ only);
    on Python 3.9 the models remain ``frozen`` but without ``__slots__``.
    This is the documented exception referenced by the issue's acceptance
    criteria.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field, fields
from typing import Any, Dict, List, Optional, Type, TypeVar

T = TypeVar("T")

_SLOTS_SUPPORTED = sys.version_info >= (3, 10)


def _frozen_model(cls: Type[T]) -> Type[T]:
    """Apply frozen (and, where supported, slotted) dataclass semantics.

    Args:
        cls: The plain class to turn into a dataclass.

    Returns:
        Type[T]: The class decorated with ``@dataclass(frozen=True)``, plus
        ``slots=True`` on Python 3.10+ where the ``dataclass`` decorator
        supports that keyword argument.
    """
    if _SLOTS_SUPPORTED:
        return dataclass(frozen=True, slots=True)(cls)
    return dataclass(frozen=True)(cls)


class ModelValidationError(Exception):
    """Raised when a Moodle response dict is missing a required field."""


def _build_from_moodle(
    cls: Type[T], data: Dict[str, Any], required: tuple, entity_name: str
) -> T:
    """Build a model instance from a raw Moodle dict.

    Shared helper used by every model's ``from_moodle`` classmethod. It
    validates that all required keys are present, then constructs the
    instance using only the keys that match a known dataclass field,
    silently dropping any unknown/extra keys.

    Args:
        cls: The dataclass type to instantiate.
        data: Raw dict as returned by a Moodle webservice/AJAX/HTML scraper.
        required: Names of the fields that must be present in ``data``.
        entity_name: Human-readable entity name used in the error message.

    Returns:
        T: The constructed, typed instance.

    Raises:
        ModelValidationError: If one or more ``required`` keys are missing
            from ``data``.
    """
    missing = [key for key in required if key not in data]
    if missing:
        raise ModelValidationError(
            f"{entity_name} is missing required field(s): {', '.join(missing)}"
        )
    known_fields = {f.name for f in fields(cls)}
    kwargs = {key: value for key, value in data.items() if key in known_fields}
    return cls(**kwargs)


@_frozen_model
class Course:
    """Typed representation of a Moodle course.

    Attributes:
        id: Unique course identifier (required).
        shortname: Course short name, if present.
        fullname: Course full name, if present.
        categoryid: Category identifier, if present.
        summary: Course summary HTML, if present.
        format: Course format (e.g. "topics"), if present.
        startdate: Unix timestamp of the course start date, if present.
        enddate: Unix timestamp of the course end date, if present.
        visible: Whether the course is visible, if present.
    """

    id: int
    shortname: Optional[str] = None
    fullname: Optional[str] = None
    categoryid: Optional[int] = None
    summary: Optional[str] = None
    format: Optional[str] = None
    startdate: Optional[int] = None
    enddate: Optional[int] = None
    visible: Optional[bool] = None

    @classmethod
    def from_moodle(cls, data: Dict[str, Any]) -> "Course":
        """Build a Course from a raw Moodle dict.

        Args:
            data: Raw dict as returned by e.g. list_courses()/get_course().

        Returns:
            Course: The parsed, typed course.

        Raises:
            ModelValidationError: If the required "id" key is missing.
        """
        return _build_from_moodle(cls, data, required=("id",), entity_name="Course")


@_frozen_model
class CourseSection:
    """Typed representation of a Moodle course section.

    Modeled after the ``section`` entries inside
    ``core_courseformat_get_state``'s response.

    Attributes:
        id: Unique section identifier (required).
        name: Section name, if present.
        section: Section number, if present.
        visible: Whether the section is visible, if present.
        summary: Section summary HTML, if present.
        cmlist: List of module ids contained in the section, if present.
    """

    id: int
    name: Optional[str] = None
    section: Optional[int] = None
    visible: Optional[bool] = None
    summary: Optional[str] = None
    cmlist: Optional[List[int]] = None

    @classmethod
    def from_moodle(cls, data: Dict[str, Any]) -> "CourseSection":
        """Build a CourseSection from a raw Moodle dict.

        Args:
            data: Raw dict as returned by e.g. the ``section`` entries of
                ``core_courseformat_get_state``.

        Returns:
            CourseSection: The parsed, typed section.

        Raises:
            ModelValidationError: If the required "id" key is missing.
        """
        return _build_from_moodle(
            cls, data, required=("id",), entity_name="CourseSection"
        )


@_frozen_model
class CourseModule:
    """Typed representation of a Moodle course module.

    Modeled after the ``cm`` entries inside
    ``core_courseformat_get_state``'s response. This acts as the common
    shape shared by module-specific entities such as :class:`Folder`,
    :class:`Label`, :class:`Assignment` and :class:`ScormPackage`.

    Attributes:
        id: Unique course-module identifier (required).
        name: Module name, if present.
        modname: Module type (e.g. "folder", "assign"), if present.
        sectionid: Identifier of the section containing the module, if present.
        visible: Whether the module is visible, if present.
        uservisible: Whether the module is visible to the current user, if present.
    """

    id: int
    name: Optional[str] = None
    modname: Optional[str] = None
    sectionid: Optional[int] = None
    visible: Optional[bool] = None
    uservisible: Optional[bool] = None

    @classmethod
    def from_moodle(cls, data: Dict[str, Any]) -> "CourseModule":
        """Build a CourseModule from a raw Moodle dict.

        Args:
            data: Raw dict as returned by e.g. the ``cm`` entries of
                ``core_courseformat_get_state``.

        Returns:
            CourseModule: The parsed, typed module.

        Raises:
            ModelValidationError: If the required "id" key is missing.
        """
        return _build_from_moodle(
            cls, data, required=("id",), entity_name="CourseModule"
        )


@_frozen_model
class User:
    """Typed representation of a Moodle user.

    Modeled after ``core_enrol_get_enrolled_users`` entries.

    Attributes:
        id: Unique user identifier (required).
        username: User's login name, if present.
        firstname: User's first name, if present.
        lastname: User's last name, if present.
        fullname: User's full display name, if present.
        email: User's email address, if present.
    """

    id: int
    username: Optional[str] = None
    firstname: Optional[str] = None
    lastname: Optional[str] = None
    fullname: Optional[str] = None
    email: Optional[str] = None

    @classmethod
    def from_moodle(cls, data: Dict[str, Any]) -> "User":
        """Build a User from a raw Moodle dict.

        Args:
            data: Raw dict as returned by e.g. list_course_users().

        Returns:
            User: The parsed, typed user.

        Raises:
            ModelValidationError: If the required "id" key is missing.
        """
        return _build_from_moodle(cls, data, required=("id",), entity_name="User")


@_frozen_model
class Folder:
    """Typed representation of a Moodle folder module.

    Attributes:
        cmid: Unique course-module identifier of the folder (required).
        name: Folder name, if present.
        files: List of filenames contained in the folder. Defaults to an
            empty list when not present, mirroring the shape returned by
            ``list_folder_content()``.
    """

    cmid: int
    name: Optional[str] = None
    files: List[str] = field(default_factory=list)

    @classmethod
    def from_moodle(cls, data: Dict[str, Any]) -> "Folder":
        """Build a Folder from a raw Moodle dict.

        Args:
            data: Raw dict with at least a "cmid" key, plus optionally
                "name" and "files" (e.g. the filenames from
                ``list_folder_content()``).

        Returns:
            Folder: The parsed, typed folder.

        Raises:
            ModelValidationError: If the required "cmid" key is missing.
        """
        return _build_from_moodle(cls, data, required=("cmid",), entity_name="Folder")


@_frozen_model
class Label:
    """Typed representation of a Moodle label module.

    Attributes:
        cmid: Unique course-module identifier of the label (required).
        name: Label name, if present.
        text: Label HTML content, if present.
    """

    cmid: int
    name: Optional[str] = None
    text: Optional[str] = None

    @classmethod
    def from_moodle(cls, data: Dict[str, Any]) -> "Label":
        """Build a Label from a raw Moodle dict.

        Args:
            data: Raw dict with at least a "cmid" key.

        Returns:
            Label: The parsed, typed label.

        Raises:
            ModelValidationError: If the required "cmid" key is missing.
        """
        return _build_from_moodle(cls, data, required=("cmid",), entity_name="Label")


@_frozen_model
class Assignment:
    """Typed representation of a Moodle assignment module.

    Attributes:
        cmid: Unique course-module identifier of the assignment (required).
        name: Assignment name, if present.
        duedate: Unix timestamp of the submission due date, if present.
        allowsubmissionsfromdate: Unix timestamp from which submissions are
            allowed, if present.
    """

    cmid: int
    name: Optional[str] = None
    duedate: Optional[int] = None
    allowsubmissionsfromdate: Optional[int] = None

    @classmethod
    def from_moodle(cls, data: Dict[str, Any]) -> "Assignment":
        """Build an Assignment from a raw Moodle dict.

        Args:
            data: Raw dict with at least a "cmid" key.

        Returns:
            Assignment: The parsed, typed assignment.

        Raises:
            ModelValidationError: If the required "cmid" key is missing.
        """
        return _build_from_moodle(
            cls, data, required=("cmid",), entity_name="Assignment"
        )


@_frozen_model
class ScormPackage:
    """Typed representation of a Moodle SCORM package module.

    Attributes:
        cmid: Unique course-module identifier of the SCORM package (required).
        name: SCORM package name, if present.
        reference: Package file path or URL, if present.
    """

    cmid: int
    name: Optional[str] = None
    reference: Optional[str] = None

    @classmethod
    def from_moodle(cls, data: Dict[str, Any]) -> "ScormPackage":
        """Build a ScormPackage from a raw Moodle dict.

        Args:
            data: Raw dict with at least a "cmid" key.

        Returns:
            ScormPackage: The parsed, typed SCORM package.

        Raises:
            ModelValidationError: If the required "cmid" key is missing.
        """
        return _build_from_moodle(
            cls, data, required=("cmid",), entity_name="ScormPackage"
        )


@_frozen_model
class UploadResult:
    """Typed, enriched representation of a file upload result.

    ``upload_file_webservice()`` currently returns a bare ``int`` (the
    ``itemid``); this model exists so future code *can* build a richer
    result without requiring any existing function to change today.

    Attributes:
        itemid: Draft area item identifier of the uploaded file (required).
        filename: Name of the uploaded file, if present.
        filepath: Path of the uploaded file within the draft area, if present.
    """

    itemid: int
    filename: Optional[str] = None
    filepath: Optional[str] = None

    @classmethod
    def from_moodle(cls, data: Dict[str, Any]) -> "UploadResult":
        """Build an UploadResult from a raw dict.

        Args:
            data: Raw dict with at least an "itemid" key.

        Returns:
            UploadResult: The parsed, typed upload result.

        Raises:
            ModelValidationError: If the required "itemid" key is missing.
        """
        return _build_from_moodle(
            cls, data, required=("itemid",), entity_name="UploadResult"
        )


@_frozen_model
class DeleteResult:
    """Typed, enriched representation of a delete operation's outcome.

    ``delete_course()`` currently returns ``None`` on success (or raises);
    this model exists so future code *can* build a richer result without
    requiring any existing function to change today.

    Attributes:
        success: Whether the delete operation succeeded (required).
        message: Human-readable outcome message, if present.
    """

    success: bool
    message: Optional[str] = None

    @classmethod
    def from_moodle(cls, data: Dict[str, Any]) -> "DeleteResult":
        """Build a DeleteResult from a raw dict.

        Args:
            data: Raw dict with at least a "success" key.

        Returns:
            DeleteResult: The parsed, typed delete result.

        Raises:
            ModelValidationError: If the required "success" key is missing.
        """
        return _build_from_moodle(
            cls, data, required=("success",), entity_name="DeleteResult"
        )


__all__ = [
    "ModelValidationError",
    "Course",
    "CourseSection",
    "CourseModule",
    "User",
    "Folder",
    "Label",
    "Assignment",
    "ScormPackage",
    "UploadResult",
    "DeleteResult",
]
