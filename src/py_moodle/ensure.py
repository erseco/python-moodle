"""Idempotent ensure-style provisioning helpers for Moodle content.

This module extends the ``ensure_course`` pattern (see
:mod:`py_moodle.course`) to sections and content modules. Every helper is
*idempotent*: it first looks up an existing object by its human-readable
natural key and only creates a new one when nothing matches, mirroring how
``ensure_course`` keys on ``shortname``.

The idempotency keys are:

* :func:`ensure_module` (and its wrappers): ``(name, modname)`` within the
  course.
* :func:`ensure_section`: the section ``name`` within the course.

These helpers only ever *create or reuse*; they never delete or reconcile
away extra objects. The heavy lookup
(``get_course_with_sections_and_modules``) and the mutating primitives
(``add_label``/``add_resource``/``add_folder``/``create_section``) are imported
lazily inside the functions to avoid import cycles and to keep the module easy
to test with monkeypatching.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Dict, Literal, Optional

import requests

from .section import MoodleSectionError

EnsureModuleStatus = Literal["created", "reused"]
EnsureSectionStatus = Literal["created", "reused"]


@dataclass
class EnsureModuleResult:
    """Outcome of an :func:`ensure_module` call.

    Attributes:
        status: ``"created"`` when a new module was created, ``"reused"``
            when an existing module matched the ``(name, modname)`` key.
        cmid: The course module ID of the resulting module.
        module: The matched module dictionary when ``status == "reused"``,
            or ``None`` when a new module was created.
    """

    status: EnsureModuleStatus
    cmid: int
    module: Optional[Dict[str, Any]] = None


@dataclass
class EnsureSectionResult:
    """Outcome of an :func:`ensure_section` call.

    Attributes:
        status: ``"created"`` when a new section was created and renamed,
            ``"reused"`` when an existing section matched by ``name``.
        section: The resulting section dictionary. When ``status ==
            "reused"`` this is the section as returned by
            ``get_course_with_sections_and_modules``; when ``status ==
            "created"`` it is a minimal ``{"id": ..., "name": ...}`` mapping.
    """

    status: EnsureSectionStatus
    section: Dict[str, Any]


def ensure_module(
    session: requests.Session,
    base_url: str,
    sesskey: str,
    course_id: int,
    section_id: int,
    *,
    name: str,
    modname: str,
    create_fn: Callable[[], int],
    token: Optional[str] = None,
) -> EnsureModuleResult:
    """Ensure a module with the given name and type exists in the course.

    Scans every section of the course for a module whose ``name`` and
    ``modname`` both match. If found, the module is reused and ``create_fn``
    is never called. Otherwise ``create_fn`` is invoked exactly once (it must
    create the module and return its ``cmid``) and the result is ``created``.

    Args:
        session: Authenticated requests session.
        base_url: Base URL of the Moodle instance.
        sesskey: Session key for AJAX/form calls.
        course_id: ID of the course to search within.
        section_id: ID of the section the module belongs to (passed by the
            wrappers to their ``create_fn``; not used for the lookup, which is
            course-wide, mirroring ``ensure_course``).
        name: Human-readable module name used as part of the idempotency key.
        modname: Moodle module type (e.g. ``"label"``) used as part of the
            idempotency key.
        create_fn: Zero-argument callable that creates the module and returns
            its ``cmid``. Only called when no existing module matches.
        token: Optional webservice token forwarded to the course lookup.

    Returns:
        EnsureModuleResult: Typed result with ``status`` of ``"created"`` or
        ``"reused"``.
    """
    from py_moodle.course import get_course_with_sections_and_modules

    course = get_course_with_sections_and_modules(
        session, base_url, sesskey, course_id, token=token
    )
    for section in course.get("sections", []):
        for module in section.get("modules", []):
            if module.get("name") == name and module.get("modname") == modname:
                return EnsureModuleResult(
                    status="reused", cmid=module.get("id"), module=module
                )

    cmid = create_fn()
    return EnsureModuleResult(status="created", cmid=cmid, module=None)


def ensure_label(
    session: requests.Session,
    base_url: str,
    sesskey: str,
    course_id: int,
    section_id: int,
    *,
    name: str,
    html: str,
    visible: int = 1,
    token: Optional[str] = None,
) -> EnsureModuleResult:
    """Ensure a ``label`` module with the given name exists.

    Thin wrapper over :func:`ensure_module` binding ``modname="label"`` and
    delegating creation to :func:`py_moodle.label.add_label`.

    Args:
        session: Authenticated requests session.
        base_url: Base URL of the Moodle instance.
        sesskey: Session key for AJAX/form calls.
        course_id: ID of the course.
        section_id: ID of the section to create the label in when missing.
        name: Label name (idempotency key together with the module type).
        html: HTML content of the label.
        visible: Whether the label is visible (``1``) or hidden (``0``).
        token: Optional webservice token forwarded to the course lookup.

    Returns:
        EnsureModuleResult: Result of the create-or-reuse operation.
    """

    def create_fn() -> int:
        from py_moodle.label import add_label

        return add_label(
            session,
            base_url,
            sesskey,
            course_id,
            section_id,
            html,
            name=name,
            visible=visible,
        )

    return ensure_module(
        session,
        base_url,
        sesskey,
        course_id,
        section_id,
        name=name,
        modname="label",
        create_fn=create_fn,
        token=token,
    )


def ensure_resource(
    session: requests.Session,
    base_url: str,
    sesskey: str,
    course_id: int,
    section_id: int,
    *,
    name: str,
    file_path: str,
    intro: str = "",
    visible: int = 1,
    token: Optional[str] = None,
) -> EnsureModuleResult:
    """Ensure a ``resource`` (single-file) module with the given name exists.

    Thin wrapper over :func:`ensure_module` binding ``modname="resource"`` and
    delegating creation to :func:`py_moodle.resource.add_resource`.

    Args:
        session: Authenticated requests session.
        base_url: Base URL of the Moodle instance.
        sesskey: Session key for AJAX/form calls.
        course_id: ID of the course.
        section_id: ID of the section to create the resource in when missing.
        name: Resource name (idempotency key together with the module type).
        file_path: Local path to the file to upload when creating.
        intro: Optional HTML introduction for the resource.
        visible: Whether the resource is visible (``1``) or hidden (``0``).
        token: Optional webservice token forwarded to the course lookup.

    Returns:
        EnsureModuleResult: Result of the create-or-reuse operation.
    """

    def create_fn() -> int:
        from py_moodle.resource import add_resource

        return add_resource(
            session,
            base_url,
            sesskey,
            course_id,
            section_id,
            name,
            file_path,
            intro=intro,
            visible=visible,
        )

    return ensure_module(
        session,
        base_url,
        sesskey,
        course_id,
        section_id,
        name=name,
        modname="resource",
        create_fn=create_fn,
        token=token,
    )


def ensure_folder(
    session: requests.Session,
    base_url: str,
    sesskey: str,
    course_id: int,
    section_id: int,
    *,
    name: str,
    files_itemid: int,
    intro_html: str = "",
    visible: int = 1,
    token: Optional[str] = None,
) -> EnsureModuleResult:
    """Ensure a ``folder`` module with the given name exists.

    Thin wrapper over :func:`ensure_module` binding ``modname="folder"`` and
    delegating creation to :func:`py_moodle.folder.add_folder`.

    Args:
        session: Authenticated requests session.
        base_url: Base URL of the Moodle instance.
        sesskey: Session key for AJAX/form calls.
        course_id: ID of the course.
        section_id: ID of the section to create the folder in when missing.
        name: Folder name (idempotency key together with the module type).
        files_itemid: Draft-area itemid holding the folder's files.
        intro_html: Optional HTML introduction for the folder.
        visible: Whether the folder is visible (``1``) or hidden (``0``).
        token: Optional webservice token forwarded to the course lookup.

    Returns:
        EnsureModuleResult: Result of the create-or-reuse operation.
    """

    def create_fn() -> int:
        from py_moodle.folder import add_folder

        return add_folder(
            session,
            base_url,
            sesskey,
            course_id,
            section_id,
            name,
            files_itemid,
            intro_html=intro_html,
            visible=visible,
        )

    return ensure_module(
        session,
        base_url,
        sesskey,
        course_id,
        section_id,
        name=name,
        modname="folder",
        create_fn=create_fn,
        token=token,
    )


def _rename_section(
    session: requests.Session,
    base_url: str,
    sesskey: str,
    section_id: int,
    name: str,
) -> bool:
    """Rename a course section via the ``inplace_editable`` AJAX endpoint.

    Args:
        session: Authenticated requests session.
        base_url: Base URL of the Moodle instance.
        sesskey: Session key for the AJAX call.
        section_id: ID of the section to rename.
        name: New name for the section.

    Returns:
        bool: ``True`` when Moodle confirms the rename.

    Raises:
        MoodleSectionError: If the AJAX call fails or returns an error.

    Note:
        Section renaming is served by the active course format's
        ``inplace_editable`` handler. This helper targets the standard
        ``sectionname`` item type provided by Moodle's built-in
        topics/weeks formats (the default for courses created through this
        library); custom course formats that do not implement it are not
        supported.
    """
    ajax_url = (
        f"{base_url}/lib/ajax/service.php?sesskey={sesskey}"
        "&info=core_update_inplace_editable"
    )
    payload = [
        {
            "index": 0,
            "methodname": "core_update_inplace_editable",
            "args": {
                "component": "format_topics",
                "itemtype": "sectionname",
                "itemid": str(section_id),
                "value": name,
            },
        }
    ]
    try:
        resp = session.post(
            ajax_url,
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload),
        )
        resp.raise_for_status()
        result = resp.json()
    except requests.RequestException as exc:
        raise MoodleSectionError(
            f"Failed to communicate with Moodle to rename section: {exc}"
        )

    if result and isinstance(result, list) and result[0].get("error") is False:
        return True

    error_details = "Unknown AJAX error"
    if result and isinstance(result, list):
        error_details = result[0].get("exception", {}).get("message", error_details)
    raise MoodleSectionError(f"Error renaming section: {error_details}")


def ensure_section(
    session: requests.Session,
    base_url: str,
    sesskey: str,
    course_id: int,
    *,
    name: str,
    token: Optional[str] = None,
) -> EnsureSectionResult:
    """Ensure a section with the given name exists in the course.

    Looks up an existing section by ``name`` via
    ``get_course_with_sections_and_modules``. If found, it is reused. Otherwise
    a new section is created with ``create_section`` and then renamed to
    ``name`` (see :func:`_rename_section` for the renaming mechanism and its
    limitations).

    Args:
        session: Authenticated requests session.
        base_url: Base URL of the Moodle instance.
        sesskey: Session key for AJAX/form calls.
        course_id: ID of the course.
        name: Section name used as the idempotency key.
        token: Optional webservice token forwarded to the course lookup.

    Returns:
        EnsureSectionResult: Typed result with ``status`` of ``"created"`` or
        ``"reused"``.
    """
    from py_moodle.course import get_course_with_sections_and_modules
    from py_moodle.section import create_section

    course = get_course_with_sections_and_modules(
        session, base_url, sesskey, course_id, token=token
    )
    for section in course.get("sections", []):
        if section.get("name") == name:
            return EnsureSectionResult(status="reused", section=section)

    created = create_section(session, base_url, sesskey, course_id)
    section_id = created.get("fields", {}).get("id")
    _rename_section(session, base_url, sesskey, section_id, name)
    return EnsureSectionResult(
        status="created", section={"id": section_id, "name": name}
    )


__all__ = [
    "EnsureModuleResult",
    "EnsureSectionResult",
    "ensure_module",
    "ensure_label",
    "ensure_resource",
    "ensure_folder",
    "ensure_section",
]
