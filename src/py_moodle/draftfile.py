# src/moodle/draftfile.py
"""
Draft file management module for Moodle CLI.

Provides functions to create draft areas, upload files to the draft area,
list draft files, and manage draft IDs needed for Moodle module creation.

All code and comments must be in English.
"""

import json
import mimetypes
import re
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import requests

from py_moodle.module import MoodleModuleError

from .upload import ProgressTracker


class MoodleDraftFileError(Exception):
    """Exception raised for errors in draft file operations."""


def get_new_draft_itemid(session: requests.Session, base_url: str, sesskey: str) -> int:
    """
    Obtain a new draft item ID for the current user.
    This is done by getting the user's private files info, which contains a valid itemid.
    """
    url = f"{base_url}/lib/ajax/service.php?sesskey={sesskey}"
    payload = [
        {"index": 0, "methodname": "core_user_get_private_files_info", "args": {}}
    ]

    try:
        response = session.post(url, json=payload)
        response.raise_for_status()
        data = response.json()

        if not isinstance(data, list) or not data:
            raise MoodleDraftFileError(
                "Invalid response format from core_user_get_private_files_info."
            )

        result = data[0]
        if result.get("error"):
            raise MoodleDraftFileError(
                f"API error: {result.get('exception', {}).get('message', 'Unknown error')}"
            )

        itemid = result.get("data", {}).get("filearea", {}).get("itemid")
        if not itemid:
            raise MoodleDraftFileError(
                "Could not find 'itemid' in the private files info response."
            )

        return int(itemid)
    except (requests.RequestException, json.JSONDecodeError, KeyError, ValueError) as e:
        raise MoodleDraftFileError(f"Failed to obtain new draft itemid: {e}")


# --- NEW EXTRACTION FUNCTION ---
def _extract_filemanager_options(text: str) -> Dict:
    """
    Finds the M.form_filemanager.init call and extracts its configuration object
    by correctly counting braces to handle nested JSON.
    """
    init_call_match = re.search(r"M\.form_filemanager\.init\s*\(\s*(?:Y\s*,)?\s*", text)
    if not init_call_match:
        raise MoodleDraftFileError(
            "Could not find the 'M.form_filemanager.init' call on the page."
        )

    start_pos = text.find("{", init_call_match.end())
    if start_pos == -1:
        raise MoodleDraftFileError(
            "Could not find the '{' configuration object after the init call."
        )

    brace_level = 1
    for i in range(start_pos + 1, len(text)):
        if text[i] == "{":
            brace_level += 1
        elif text[i] == "}":
            brace_level -= 1

        if brace_level == 0:
            end_pos = i + 1
            json_string = text[start_pos:end_pos]
            return json.loads(json_string)

    raise MoodleDraftFileError(
        "Could not find the corresponding closing brace for the configuration object."
    )


# --- IMPROVED detect_upload_repo FUNCTION ---
def detect_upload_repo(session: requests.Session, base_url: str, course_id: int) -> int:
    """
    Detects the upload repository ID by scraping the filemanager configuration
    from the course edit page. This is the most robust method.
    """
    page_url = f"{base_url}/course/edit.php?id={course_id}"
    try:
        response = session.get(page_url)
        response.raise_for_status()
    except requests.RequestException as e:
        raise MoodleDraftFileError(
            f"Failed to fetch page '{page_url}' for scraping: {e}"
        )

    options = _extract_filemanager_options(response.text)

    repositories = options.get("filepicker", {}).get("repositories", {})
    if not repositories:
        raise MoodleDraftFileError(
            "No 'repositories' key found in the filepicker configuration."
        )

    for repo_data in repositories.values():
        if repo_data.get("type") == "upload":
            return int(repo_data["id"])

    raise MoodleDraftFileError(
        "No repository with type='upload' found in the configuration."
    )


def upload_file_to_draft_area(
    session: requests.Session,
    base_url: str,
    sesskey: str,
    course_id: int,
    course_context_id: int,
    file_path: str,
    itemid: Optional[int] = None,
    savepath: str = "/",
    timeout: tuple = (300, 3600),
    progress_callback: Optional[Callable[[int], None]] = None,
) -> Tuple[int, str]:
    """
    Uploads a file to a draft area using the session-based AJAX endpoint,
    returning the itemid of the draft area and the final filename.
    If the file exists, Moodle renames it; this function returns the new name.
    """
    if itemid is None:
        # NOTE: For module creation, we usually need a *new* itemid for each new module.
        # Getting the user's private files itemid might reuse the same area.
        # Let's generate one based on time, which is what Moodle often does for new content.
        itemid = int(time.time() * 1000)

    path = Path(file_path)
    if not path.is_file():
        raise MoodleDraftFileError(f"File does not exist: {file_path}")

    upload_url = f"{base_url}/repository/repository_ajax.php?action=upload"

    # Instead of opening the file directly, use ProgressTracker
    progress_tracker = ProgressTracker(file_path, progress_callback)

    files = {
        "repo_upload_file": (
            path.name,
            progress_tracker,  # Use our tracking object
            mimetypes.guess_type(path.name)[0] or "application/octet-stream",
        )
    }

    # with open(path, "rb") as f:
    #     files = {
    #         "repo_upload_file": (
    #             path.name,
    #             f,
    #             mimetypes.guess_type(path.name)[0] or "application/octet-stream",
    #         )
    #     }
    try:
        repo_id = detect_upload_repo(session, base_url, course_id)

    except (MoodleDraftFileError, MoodleModuleError) as e:
        # If detection fails, warn and fall back to 5 as a last resort
        print(
            f"Warning: Could not auto-detect repo_id ({e}). Falling back to default ID 5."
        )
        repo_id = 5  # '5' is typically the "Upload a file" repository

    payload = {
        "sesskey": sesskey,
        "itemid": str(itemid),
        "repo_id": str(repo_id),
        "ctx_id": str(course_context_id),
        "savepath": savepath,
    }

    response = session.post(upload_url, data=payload, files=files, timeout=timeout)

    try:
        response.raise_for_status()
        data = response.json()

        # Check for Moodle's internal error format
        if isinstance(data, dict) and "error" in data and data["error"]:
            raise MoodleDraftFileError(
                f"Moodle returned an error on file upload: {data['error']}"
            )

        # Case 1: File already existed and was renamed by Moodle
        if isinstance(data, dict) and data.get("event") == "fileexists":
            new_filename = data.get("newfile", {}).get("filename")
            if not new_filename:
                raise MoodleDraftFileError(
                    "Moodle reported a file conflict but no new filename was provided."
                )
            return itemid, new_filename  # Return the new name

        # Case 2: New file was uploaded successfully
        if isinstance(data, dict) and "id" in data and "filename" in data:
            # The 'id' in the response is the confirmed itemid, and we get the filename.
            return int(data["id"]), data["filename"]
        elif isinstance(data, dict) and "id" in data and "file" in data:
            # Handle alternative response format where the key is 'file'
            return int(data["id"]), data["file"]

        # If we reach here, the response format is unexpected.
        raise MoodleDraftFileError(
            f"Unexpected response format from Moodle upload endpoint: {data!r}"
        )

    except (requests.RequestException, json.JSONDecodeError) as e:
        raise MoodleDraftFileError(f"Failed to upload file to draft area: {e}")


def list_draft_files(
    session: requests.Session, base_url: str, sesskey: str, draft_itemid: int
) -> List[Dict[str, Any]]:
    """
    List files in a Moodle draft area.
    """
    url = f"{base_url}/repository/draftfiles_ajax.php"
    params = {"itemid": draft_itemid, "action": "list", "sesskey": sesskey}
    resp = session.get(url, params=params)
    try:
        data = resp.json()

        # Moodle can return 'false' if the itemid is invalid or empty
        if not data:
            return []

        # The list of files is under the key 'list', not 'files'.
        return data.get("list", [])
    except (json.JSONDecodeError, KeyError) as e:
        raise MoodleDraftFileError(f"Failed to list draft files: {e}")


__all__ = [
    "MoodleDraftFileError",
    "get_new_draft_itemid",
    "detect_upload_repo",
    "upload_file_to_draft_area",
    "list_draft_files",
]
