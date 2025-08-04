# src/moodle/page.py
"""Page module management for Moodle CLI.

Provides functions to create and delete 'page' modules,
allowing HTML content to be added to a course.
All code and comments are in English.
"""

from __future__ import annotations

import time

import requests

from .module import MoodleModuleError, add_generic_module, delete_module

MODULE_NAME = "page"


class MoodlePageError(Exception):
    """Exception raised for errors in page operations."""


def add_page(
    session: requests.Session,
    base_url: str,
    sesskey: str,
    course_id: int,
    section_id: int,
    name: str,
    content: str,
    intro: str = "",
    visible: int = 1,
) -> int:
    """Create a new page module with the provided HTML content.

    Args:
        session: Authenticated ``requests.Session`` object.
        base_url: Base URL of the Moodle instance.
        sesskey: Session key for form submissions.
        course_id: ID of the course to add the page to.
        section_id: ID of the section within the course.
        name: Name of the page module.
        content: HTML content of the page.
        intro: Optional introduction displayed above the content.
        visible: Whether the module is visible (1) or hidden (0).

    Returns:
        The new course module ID (cmid).
    """
    intro_itemid = int(time.time() * 1000)
    page_itemid = intro_itemid + 1
    specific_payload = {
        "_qf__mod_page_mod_form": "1",
        "name": name,
        "introeditor[text]": f"<p>{intro}</p>",
        "introeditor[format]": "1",
        "introeditor[itemid]": str(intro_itemid),
        "page[text]": content,
        "page[format]": "1",
        "page[itemid]": str(page_itemid),
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
        raise MoodlePageError(f"Failed to add page: {e}")


def delete_page(
    session: requests.Session, base_url: str, sesskey: str, cmid: int
) -> bool:
    """Delete a page module by its course module ID."""
    try:
        return delete_module(session, base_url, sesskey, cmid)
    except MoodleModuleError as e:
        raise MoodlePageError(f"Failed to delete page: {e}")


__all__ = ["MoodlePageError", "add_page", "delete_page"]
