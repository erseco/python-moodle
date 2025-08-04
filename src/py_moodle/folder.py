# src/moodle/folder.py
"""
Folder module management for Moodle CLI.

Provides functions to create, update, and delete 'folder' modules, as well
as manage their contents (add, remove, rename files) using Moodle's
web forms and AJAX endpoints.

All code and comments are in English.
"""
import json
import re
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup

from .course import get_course_context_id
from .draftfile import upload_file_to_draft_area

# Reuse the more robust generic functions
from .module import (
    MoodleModuleError,
    add_generic_module,
    delete_module,
    get_module_info,
    update_generic_module,
)


class MoodleFolderError(Exception):
    """Exception raised for errors in folder operations."""


# --- Basic Folder Operations (Create, Update, Delete) ---


def add_folder(
    session: requests.Session,
    base_url: str,
    sesskey: str,
    course_id: int,
    section_id: int,
    name: str,
    files_itemid: int,
    intro_html: str = "",
    visible: int = 1,
) -> int:
    """Creates a new folder module by calling the generic module creation function."""
    intro_itemid = int(time.time() * 1000)
    specific_payload = {
        "_qf__mod_folder_mod_form": "1",
        "name": name,
        "introeditor[text]": f"<p>{intro_html}</p>",
        "introeditor[format]": "1",
        "introeditor[itemid]": str(intro_itemid),
        "showdescription": "0",
        "files": str(files_itemid),
        "display": "0",
        "showexpanded": "1",
        "showdownloadfolder": "1",
        "visible": str(visible),
        "cmidnumber": "",
        "availabilityconditionsjson": json.dumps({"op": "&", "c": [], "showc": []}),
        "completionunlocked": "1",
        "submitbutton": "Save and return to course",
    }
    try:
        return add_generic_module(
            session=session,
            base_url=base_url,
            sesskey=sesskey,
            module_name="folder",
            course_id=course_id,
            section_id=section_id,
            specific_payload=specific_payload,
        )
    except MoodleModuleError as e:
        raise MoodleFolderError(f"Failed to add folder: {e}")


def delete_folder(
    session: requests.Session, base_url: str, sesskey: str, cmid: int
) -> bool:
    """Deletes a folder module by calling the generic module deletion function."""
    try:
        return delete_module(session, base_url, sesskey, cmid)
    except MoodleModuleError as e:
        raise MoodleFolderError(f"Failed to delete folder (cmid={cmid}): {e}")


# --- Folder Content Management ---


def _get_current_user_fullname(session: requests.Session, base_url: str) -> str:
    """Scrapes the user's full name from the profile dropdown."""
    try:
        my_page_resp = session.get(f"{base_url}/my/")
        my_page_resp.raise_for_status()
        soup = BeautifulSoup(my_page_resp.text, "lxml")
        user_menu = soup.select_one(".usermenu .usertext")
        if user_menu:
            return user_menu.get_text(strip=True)
    except Exception:
        # Fallback if scraping fails
        return "Admin User"
    return "Unknown User"


def _get_folder_context_and_item_id(
    session: requests.Session, base_url: str, cmid: int
) -> tuple[int, int]:
    """Scrapes the contextid and persistent itemid from the folder edit page."""
    edit_url = f"{base_url}/course/modedit.php?update={cmid}"
    try:
        resp = session.get(edit_url)
        resp.raise_for_status()
        text = resp.text

        contextid_match = re.search(r'["\']contextid["\']\s*:\s*(\d+)', text)
        files_input = BeautifulSoup(text, "lxml").find(
            "input", {"name": "files", "type": "hidden"}
        )

        if not contextid_match or not files_input:
            raise MoodleFolderError(
                "Could not find contextid or itemid on the edit page."
            )

        return int(contextid_match.group(1)), int(files_input["value"])
    except requests.RequestException as e:
        raise MoodleFolderError(f"Failed to load folder edit page for cmid {cmid}: {e}")


def _manage_folder_file(
    session: requests.Session,
    base_url: str,
    sesskey: str,
    cmid: int,
    ajax_action: str,
    ajax_payload: Dict[str, Any],
    progress_callback: Optional[Callable[[int], None]] = None,
) -> Tuple[bool, Optional[str]]:
    """
    Generic function to perform an AJAX action and then save the form.
    Returns a tuple (success, final_filename) for upload actions.
    """

    final_filename: Optional[str] = None
    module_info = get_module_info(session, base_url, sesskey, cmid)
    course_id = module_info.get("cm", {}).get("course")

    # Get the module's context_id if available; otherwise search for it on the course page.
    # The module's contextid is more specific and preferable for the file picker.
    context_id_module = module_info.get("cm", {}).get("contextid")
    if not context_id_module:
        context_id_module = get_course_context_id(session, base_url, course_id)

    context_id, itemid = _get_folder_context_and_item_id(session, base_url, cmid)

    savepath = ajax_payload.get("subfolder", "/")

    # Perform the specific AJAX action
    if ajax_action == "upload":

        # Wait and unpack the tuple (itemid, final_filename)
        # The returned itemid is the same as the one passed, so we ignore it with _
        _, final_filename = upload_file_to_draft_area(
            session=session,
            base_url=base_url,
            sesskey=sesskey,
            course_id=course_id,
            course_context_id=context_id_module,
            file_path=ajax_payload["file_path"],
            itemid=itemid,
            savepath=savepath,
            progress_callback=progress_callback,
        )

    elif ajax_action == "delete":
        url = f"{base_url}/repository/draftfiles_ajax.php?action=delete"
        payload = {**ajax_payload, "sesskey": sesskey, "itemid": itemid}
        session.post(url, data=payload).raise_for_status()
    elif ajax_action == "rename":
        url = f"{base_url}/repository/draftfiles_ajax.php?action=updatefile"
        payload = {**ajax_payload, "sesskey": sesskey, "itemid": itemid}
        session.post(url, data=payload).raise_for_status()

    time.sleep(1)

    # Persist changes using update_generic_module, which submits all required form fields.
    try:
        # Ensure the 'files' field has the correct itemid; the helper handles the rest.
        success = update_generic_module(
            session, base_url, cmid, specific_payload={"files": str(itemid)}
        )
        return success, final_filename
    except MoodleModuleError as e:
        raise MoodleFolderError(
            f"Failed to save folder changes after AJAX operation: {e}"
        )


def add_file_to_folder(
    session: requests.Session,
    base_url: str,
    sesskey: str,
    cmid: int,
    file_path: str,
    subfolder: str = "/",
    progress_callback: Optional[Callable[[int], None]] = None,
) -> Tuple[bool, Optional[str]]:
    """
    Adds a file to an existing folder and saves.
    Returns a tuple: (success_status, final_filename_on_moodle).
    """
    return _manage_folder_file(
        session,
        base_url,
        sesskey,
        cmid,
        ajax_action="upload",
        ajax_payload={"file_path": file_path, "subfolder": subfolder},
        progress_callback=progress_callback,
    )


def delete_file_from_folder(
    session: requests.Session, base_url: str, sesskey: str, cmid: int, filename: str
) -> bool:
    """Deletes a file from an existing folder and saves."""
    return _manage_folder_file(
        session,
        base_url,
        sesskey,
        cmid,
        ajax_action="delete",
        ajax_payload={"filepath": "/", "filename": filename},
    )


def rename_file_in_folder(
    session: requests.Session,
    base_url: str,
    sesskey: str,
    cmid: int,
    old_filename: str,
    new_filename: str,
) -> bool:
    """Renames a file in an existing folder and saves."""
    author = _get_current_user_fullname(session, base_url)
    payload = {
        "client_id": f"client{time.time()}",
        "filepath": "/",
        "filename": old_filename,
        "newfilename": new_filename,
        "newfilepath": "/",
        # "newlicense": "unknown",
        "newauthor": author,
    }

    return _manage_folder_file(
        session,
        base_url,
        sesskey,
        cmid,
        ajax_action="rename",
        ajax_payload=payload,
    )


def list_folder_content(
    session: requests.Session, base_url: str, cmid: int
) -> List[str]:
    """Lists the files inside a folder module by parsing its view page."""
    view_url = f"{base_url}/mod/folder/view.php?id={cmid}"
    try:
        resp = session.get(view_url)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        file_links = soup.select(
            '.folder_tree a[href*="/pluginfile.php/"], .foldertree a[href*="/pluginfile.php/"]'
        )
        filenames = [
            link.text.strip()
            for link in file_links
            if "pluginfile.php" in link.get("href", "")
        ]
        return sorted(list(set(filenames)))
    except requests.RequestException as e:
        raise MoodleFolderError(
            f"Failed to load folder content page (cmid={cmid}): {e}"
        )


__all__ = [
    "MoodleFolderError",
    "add_folder",
    "delete_folder",
    "add_file_to_folder",
    "delete_file_from_folder",
    "rename_file_in_folder",
    "list_folder_content",
]
