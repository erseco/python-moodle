# src/moodle/label.py
"""Label management module for ``py-moodle``."""

import time
from typing import Optional

import requests

# Import the new generic functions from 'module'
from .module import (
    MoodleModuleError,
    add_generic_module,
    delete_module,
    update_generic_module,
)

# Constants specific to the 'label' module
MODULE_NAME = "label"


class MoodleLabelError(Exception):
    """Exception raised for errors in label operations."""


def add_label(
    session: requests.Session,
    base_url: str,
    sesskey: str,
    course_id: int,
    section_id: int,
    html: str,
    name: str = "Label (via CLI)",
    visible: int = 1,
) -> int:
    """
    Creates a new label by calling the generic module creation function.
    """
    draft_id = int(time.time() * 1000)

    # 1. Define the payload specific to a 'label' module
    specific_payload = {
        "name": name,
        "introeditor[text]": html,
        "introeditor[format]": "1",  # 1 = HTML format
        "introeditor[itemid]": str(draft_id),
        "visible": str(visible),
        "_qf__mod_label_mod_form": "1",
    }

    # 2. Call the generic function
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
        # Re-raise as a more specific error if needed, or just pass it through
        raise MoodleLabelError(f"Failed to add label: {e}")


def delete_label(
    session: requests.Session,
    base_url: str,
    sesskey: str,
    cmid: int,
) -> bool:
    """
    Deletes a label module by calling the generic module deletion function.
    """
    try:
        return delete_module(session, base_url, sesskey, cmid)
    except MoodleModuleError as e:
        raise MoodleLabelError(f"Failed to delete label: {e}")


def update_label(
    session: requests.Session,
    base_url: str,
    cmid: int,
    html: Optional[str] = None,
    name: Optional[str] = None,
    visible: Optional[int] = None,
) -> bool:
    """
    Updates a label's content, name, or visibility by calling the generic module update function.
    """

    # 1. Define the payload with only the fields that need to be changed
    specific_payload = {}
    if html is not None:
        specific_payload["introeditor[text]"] = html
    if name is not None:
        specific_payload["name"] = name
    if visible is not None:
        specific_payload["visible"] = str(visible)

    # 2. Call the generic update function
    try:
        return update_generic_module(
            session=session,
            base_url=base_url,
            cmid=cmid,
            specific_payload=specific_payload,
        )
    except MoodleModuleError as e:
        raise MoodleLabelError(f"Failed to update label: {e}")


__all__ = ["MoodleLabelError", "add_label", "delete_label", "update_label"]
