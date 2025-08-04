# src/moodle/url.py
"""URL module management for Moodle CLI.

Provides functions to create and delete "url" modules linking to external resources.
All code and comments are in English.
"""
from __future__ import annotations

import time

import requests

from .module import MoodleModuleError, add_generic_module, delete_module

MODULE_NAME = "url"


class MoodleUrlError(Exception):
    """Exception raised for errors in URL module operations."""


def add_url(
    session: requests.Session,
    base_url: str,
    sesskey: str,
    course_id: int,
    section_id: int,
    name: str,
    external_url: str,
    intro: str = "",
    visible: int = 1,
) -> int:
    """Create a new URL module in a course section.

    Args:
        session: Authenticated ``requests.Session`` object.
        base_url: Base URL of the Moodle instance.
        sesskey: Session key for form submissions.
        course_id: ID of the course to add the URL to.
        section_id: ID of the section within the course.
        name: Name of the URL module.
        external_url: The external URL to be linked.
        intro: Optional introduction or description for the URL.
        visible: Visibility flag (1 for visible, 0 for hidden).

    Returns:
        The new course module ID (cmid).
    """
    intro_itemid = int(time.time() * 1000)
    specific_payload = {
        "_qf__mod_url_mod_form": "1",
        "name": name,
        "introeditor[text]": f"<p>{intro}</p>",
        "introeditor[format]": "1",
        "introeditor[itemid]": str(intro_itemid),
        "externalurl": external_url,
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
        raise MoodleUrlError(f"Failed to add URL: {e}")


def delete_url(
    session: requests.Session, base_url: str, sesskey: str, cmid: int
) -> bool:
    """Delete a URL module by its course module ID."""
    try:
        return delete_module(session, base_url, sesskey, cmid)
    except MoodleModuleError as e:
        raise MoodleUrlError(f"Failed to delete URL: {e}")


__all__ = ["MoodleUrlError", "add_url", "delete_url"]
