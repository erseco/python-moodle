# src/moodle/scorm.py
"""SCORM module management for ``py-moodle``."""

import random
import re
import time
from typing import Any, Callable, Optional

import requests

from .draftfile import MoodleDraftFileError, upload_file_to_draft_area
from .module import MoodleModuleError, add_generic_module
from .upload import MoodleUploadError, upload_file_webservice

# Constants for the 'scorm' module
MODULE_NAME = "scorm"


class MoodleScormError(Exception):
    """Exception raised for errors in SCORM operations."""


def add_scorm(
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
    **kwargs: Any,
) -> int:
    """
    Creates a new SCORM module using the webservice for file upload.

    Args:
        session: Authenticated requests.Session object.
        base_url: Base URL of the Moodle instance.
        sesskey: Session key for form submissions.
        course_id: ID of the course where the SCORM will be added.
        section_id: ID of the section where the SCORM will be added.
        name: Name of the SCORM activity.
        file_path: Local path to the SCORM package (.zip).
        intro: Introduction or description for the SCORM activity.
        visible: Visibility of the activity (1 for visible, 0 for hidden).
        progress_callback: Optional callback to report upload progress.
        **kwargs: Additional SCORM-specific settings.

    Returns:
        The new course module ID (cmid) of the created SCORM package.
    """
    # 1. Check for the token that was passed in as an argument.
    token = getattr(session, "webservice_token", None)

    if not token:
        raise MoodleScormError(
            "A webservice token is required for this upload method, but none was provided."
        )

    # 2. Upload the SCORM package using the webservice.
    try:
        package_draft_itemid = upload_file_webservice(
            base_url, token, file_path, (300, 3600), progress_callback
        )
    except MoodleUploadError as e:
        raise MoodleScormError(f"Failed to upload SCORM package via webservice: {e}")

    # 3. Generate a separate itemid for the text editor.
    intro_draft_itemid = int(time.time() * 1000)

    # 4. Define the specific payload for the SCORM module.
    specific_payload = {
        "_qf__mod_scorm_mod_form": "1",
        "name": name,
        "introeditor[text]": f"<p>{intro}</p>",
        "introeditor[format]": "1",
        "introeditor[itemid]": str(intro_draft_itemid),
        "packagefile": str(package_draft_itemid),  # Use the upload itemid
        "visible": str(visible),
        # Default settings
        "scormtype": "local",
        "updatefreq": "0",
        "popup": "0",
        "skipview": "0",
        "hidebrowse": "0",
        "hidetoc": "0",
        "nav": "1",
        "grademethod": "1",
        "maxgrade": "100",
        "maxattempt": "0",
        "whatgrade": "0",
        "forcecompleted": "0",
        "masteryoverride": "1",
        "submitbutton": "Save and display",
    }
    specific_payload.update(kwargs)

    # 5. Call the generic function to create the module.
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
        raise MoodleScormError(
            f"Failed to add SCORM module after successful upload: {e}"
        )


def add_scorm_ajax(
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
    **kwargs: Any,
) -> int:
    """
    Creates a new SCORM package module by uploading the file and using the generic module creation function.

    Args:
        session: Authenticated requests.Session object.
        base_url: Base URL of the Moodle instance.
        sesskey: Session key for form submissions.
        course_id: The ID of the course to add the SCORM to.
        section_id: The ID of the section to add the SCORM to.
        name: The name of the SCORM activity.
        file_path: The local path to the SCORM .zip file.
        intro: The introduction or description for the SCORM activity.
        visible: Whether the activity is visible (1) or hidden (0).
        **kwargs: Optional overrides for advanced SCORM settings.

    Returns:
        The new course module ID (cmid) of the created SCORM package.
    """
    # 1. Get course context ID needed for file upload
    course_context_id = None
    try:
        # Note: This assumes contextid is available, which might not be. A better approach is needed if not.
        # For now, we'll try to find it. A more robust way would be to scrape it from a page if needed.
        # A simple approximation can be done by getting course info, but let's assume we can find it.
        # Let's get it from the course page content.
        from bs4 import BeautifulSoup

        course_page_resp = session.get(f"{base_url}/course/view.php?id={course_id}")
        soup = BeautifulSoup(course_page_resp.text, "lxml")
        context_input = soup.find("input", {"name": "contextid"})
        if not context_input or not context_input.get("value"):
            raise MoodleScormError(
                "Could not determine the course context ID required for file upload."
            )
        course_context_id = int(context_input["value"])
    except Exception:
        # raise MoodleScormError(f"Could not retrieve course context ID: {e}")

        # The most reliable way to get the context ID is to parse it from the
        # JavaScript M.cfg object embedded in the course page HTML.
        course_page_resp = session.get(f"{base_url}/course/view.php?id={course_id}")

        course_page_resp.raise_for_status()

        # Regex to find "courseContextId":123 or "contextid":123 in the M.cfg block
        match = re.search(
            r'["\'](?:courseContextId|contextid)["\']\s*:\s*(\d+)',
            course_page_resp.text,
        )

        if match:
            course_context_id = int(match.group(1))
        else:
            raise MoodleScormError(
                "Could not determine the course context ID from the course page."
            )

    # 2. Upload the SCORM package to a new draft area
    try:
        # The function returns a tuple (itemid, filename); only the itemid is needed.
        package_draft_itemid, _ = upload_file_to_draft_area(
            session=session,
            base_url=base_url,
            sesskey=sesskey,
            course_id=course_id,
            course_context_id=course_context_id,
            file_path=file_path,
            progress_callback=progress_callback,
        )
    except MoodleDraftFileError as e:
        raise MoodleScormError(f"Failed to upload SCORM package: {e}")

    # 3. Define the payload specific to a 'scorm' module
    specific_payload = {
        "_qf__mod_scorm_mod_form": "1",
        "name": name,
        "introeditor[text]": f"<p>{intro}</p>",
        "introeditor[format]": "1",
        "introeditor[itemid]": str(
            # draft_itemid + random.randint(100, 200)
            package_draft_itemid
            + random.randint(100, 200)
        ),  # Needs a different itemid
        # "packagefile": str(draft_itemid),
        "packagefile": str(package_draft_itemid),
        "cmidnumber": 0,  # Add the missing field even if empty.
        "visible": str(visible),
        # Default settings from HAR to ensure it works
        "scormtype": "local",
        "updatefreq": "0",
        "popup": "0",
        "skipview": "0",
        "hidebrowse": "0",
        "hidetoc": "0",
        "nav": "1",
        "grademethod": "1",
        "maxgrade": "100",
        "maxattempt": "0",
        "whatgrade": "0",
        "forcecompleted": "0",
        "masteryoverride": "1",
        "submitbutton": "Save and display",
    }

    specific_payload.update(kwargs)  # Allow overriding defaults

    # 4. Call the generic module creation function
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
        raise MoodleScormError(f"Failed to add SCORM module: {e}")


__all__ = ["MoodleScormError", "add_scorm", "add_scorm_ajax"]
