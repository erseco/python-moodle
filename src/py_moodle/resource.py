# src/moodle/resource.py
"""Resource module management for Moodle CLI.

Provides functions to create and delete 'resource' modules (single files)
using Moodle's web forms and AJAX endpoints.
All code and comments are in English.
"""

from __future__ import annotations

import time
from typing import Callable, Optional

import requests

from .course import get_course_context_id
from .draftfile import MoodleDraftFileError, upload_file_to_draft_area
from .module import MoodleModuleError, add_generic_module, delete_module

MODULE_NAME = "resource"


class MoodleResourceError(Exception):
    """Exception raised for errors in resource operations."""


def add_resource(
    session: requests.Session,
    base_url: str,
    sesskey: str,
    course_id: int,
    section_id: int,
    name: str,
    file_path: str,
    intro: str = "",
    visible: int = 1,
    progress_callback: Optional[Callable[[int], None]] = None,
) -> int:
    """Create a new resource module by uploading a single file.

    Args:
        session: Authenticated ``requests.Session`` object.
        base_url: Base URL of the Moodle instance.
        sesskey: Session key for form submissions.
        course_id: ID of the course to add the resource to.
        section_id: ID of the section within the course.
        name: Name of the resource module.
        file_path: Local path to the file to upload.
        intro: Optional HTML introduction for the resource.
        visible: Whether the module is visible (1) or hidden (0).
        progress_callback: Optional callback for upload progress.

    Returns:
        The new course module ID (cmid).
    """
    try:
        course_context_id = get_course_context_id(session, base_url, course_id)
    except Exception as e:
        raise MoodleResourceError(f"Failed to determine course context ID: {e}")

    try:
        files_itemid, _ = upload_file_to_draft_area(
            session=session,
            base_url=base_url,
            sesskey=sesskey,
            course_id=course_id,
            course_context_id=course_context_id,
            file_path=file_path,
            progress_callback=progress_callback,
        )
    except MoodleDraftFileError as e:
        raise MoodleResourceError(f"Failed to upload file for resource: {e}")

    intro_itemid = int(time.time() * 1000)
    specific_payload = {
        "_qf__mod_resource_mod_form": "1",
        "name": name,
        "introeditor[text]": f"<p>{intro}</p>",
        "introeditor[format]": "1",
        "introeditor[itemid]": str(intro_itemid),
        "showdescription": "0",
        "files": str(files_itemid),
        "display": "0",
        "visible": str(visible),
        "submitbutton": "Save and return to course",
    }

    try:
        return add_generic_module(
            session=session,
            base_url=base_url,
            sesskey=sesskey,
            module_name=MODULE_NAME,
            course_id=course_id,
            section_id=section_id,
            specific_payload=specific_payload,
        )
    except MoodleModuleError as e:
        raise MoodleResourceError(f"Failed to add resource: {e}")


def delete_resource(
    session: requests.Session, base_url: str, sesskey: str, cmid: int
) -> bool:
    """Delete a resource module by its course module ID."""
    try:
        return delete_module(session, base_url, sesskey, cmid)
    except MoodleModuleError as e:
        raise MoodleResourceError(f"Failed to delete resource: {e}")


__all__ = ["MoodleResourceError", "add_resource", "delete_resource"]
