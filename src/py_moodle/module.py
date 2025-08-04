# src/moodle/module.py
"""
Generic Moodle module management helpers.
All code and comments are in English.
"""
import json
import re
import time
import urllib.parse
from typing import Any, Dict, Optional

import requests
from bs4 import BeautifulSoup

from py_moodle.course import MoodleCourseError, get_course_with_sections_and_modules

# --- Cache for module IDs ---
# The key will be (base_url, course_id), the value will be a dict {name: id}
_MODULE_ID_CACHE: Dict[tuple[str, int], Dict[str, int]] = {}


class MoodleModuleError(Exception):
    """Generic exception for module operations."""


# --- Internal Helpers ---


def _get_base_modedit_payload(
    course_id: int,
    section_number: int,
    sesskey: str,
    module_name: str,
    module_id: int,
    instance: str = "",
    cmid: str = "",
    mode: str = "add",
) -> Dict[str, Any]:
    """
    Returns a base dictionary for modedit.php form submissions.
    This contains all the common fields required by Moodle forms.
    """
    return {
        "course": str(course_id),
        "section": str(section_number),
        "sesskey": sesskey,
        "modulename": module_name,
        "module": str(module_id),
        "instance": instance,
        "coursemodule": cmid,
        "add": module_name if mode == "add" else "",
        "update": cmid if mode == "update" else "0",
        "return": "0",
        "sr": "-1",
        "completionunlocked": "1",
        "availabilityconditionsjson": json.dumps({"op": "&", "c": [], "showc": []}),
        "submitbutton2": "Save and return to course",
    }


# --- Public Generic Functions ---


def add_generic_module(
    session: requests.Session,
    base_url: str,
    sesskey: str,
    module_name: str,
    course_id: int,
    section_id: int,
    specific_payload: Dict[str, Any],
    module_id: Optional[int] = None,
) -> int:
    """
    Adds a new module to a course section by simulating a form post to modedit.php.
    This is a generic function that handles the common logic for all module types.

    Returns:
        The new course module ID (cmid) as an integer.
    """
    token = getattr(session, "webservice_token", None)

    """
    Adds a new module. If module_id is not provided, it will be dynamically fetched.
    """
    if module_id is None:
        module_id = _get_module_id_from_name(
            session, base_url, sesskey, course_id, module_name
        )

    # 1. Get initial state to find section position and existing modules
    try:
        course_data = get_course_with_sections_and_modules(
            session, base_url, sesskey, course_id, token=token
        )
        target_section = next(
            (s for s in course_data["sections"] if int(s.get("id")) == int(section_id)),
            None,
        )
        if not target_section:
            raise MoodleModuleError(
                f"Section with ID {section_id} not found in course {course_id}."
            )

        section_number = target_section.get("section")
        before_cmids = {int(m["id"]) for m in target_section.get("modules", [])}
    except MoodleCourseError as e:
        raise MoodleModuleError(f"Failed to get initial section state: {e}")

    # 2. Build the full payload
    base_payload = _get_base_modedit_payload(
        course_id, section_number, sesskey, module_name, module_id, mode="add"
    )
    full_payload = {**base_payload, **specific_payload}

    # 3. POST to modedit.php
    url = f"{base_url}/course/modedit.php"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    encoded_payload = urllib.parse.urlencode(full_payload)
    resp = session.post(
        url, data=encoded_payload, headers=headers, allow_redirects=False
    )

    # A clear success is a redirect (302 or 303) to the course page.
    if resp.status_code not in [200, 302, 303]:
        # A 200 OK status almost always means a silent failure.
        # Parse the HTML to find Moodle's error message.
        soup = BeautifulSoup(resp.text, "lxml")
        error_div = soup.select_one(
            ".error, .errormessage, .alert-danger, div[data-fieldtype=error]"
        )
        if error_div:
            # Found a specific error message.
            error_message = error_div.get_text(strip=True)
            raise MoodleModuleError(
                f"Form submission failed. Moodle error: {error_message}"
            )
        else:
            # No clear error message, but creation failed.
            raise MoodleModuleError(
                f"Failed to create module. Status: {resp.status_code}. Moodle returned the edit form, indicating a silent failure. Check permissions or required fields."
            )

    # 4. Get final state and determine the new cmid
    time.sleep(1)  # Give Moodle a moment to process the change
    try:
        course_data_after = get_course_with_sections_and_modules(
            session, base_url, sesskey, course_id, token=token
        )
        target_section_after = next(
            (
                s
                for s in course_data_after["sections"]
                if int(s.get("id")) == int(section_id)
            ),
            None,
        )
        after_cmids = {int(m["id"]) for m in target_section_after.get("modules", [])}
    except MoodleCourseError as e:
        raise MoodleModuleError(f"Failed to get final section state: {e}")

    new_cmids = after_cmids - before_cmids
    if len(new_cmids) == 1:
        return new_cmids.pop()

    raise MoodleModuleError("Could not determine new module ID after creation.")


def update_generic_module(
    session: requests.Session,
    base_url: str,
    cmid: int,
    specific_payload: Dict[str, Any],
) -> bool:
    """
    Updates an existing module by fetching its edit form, modifying fields, and submitting it.
    This generic approach ensures that all existing form values are preserved.
    """
    if not specific_payload:
        # Nothing to update
        return True

    edit_url = f"{base_url}/course/modedit.php?update={cmid}"

    # 1. Fetch the edit page to get the current state of the form
    try:
        resp = session.get(edit_url)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
    except requests.RequestException as e:
        raise MoodleModuleError(f"Failed to load module edit page for cmid {cmid}: {e}")

    # 2. Parse the form and extract all input, textarea, and select fields
    form = soup.select_one('form[action*="modedit.php"]')
    if not form:
        raise MoodleModuleError("Could not find the edit form on the page.")

    form_data = {}

    for field in form.find_all(["input", "textarea", "select"]):
        name = field.get("name")
        # Ignore fields without a name or buttons
        if not name or field.get("type") in ["submit", "button", "reset"]:
            continue

        # Logic for different tag/type combinations
        if field.name == "textarea":
            form_data[name] = field.text or ""
        elif field.name == "select":
            selected_option = field.find("option", selected=True)
            if selected_option and selected_option.has_attr("value"):
                form_data[name] = selected_option["value"]
            else:
                # If no option is selected, browsers usually submit the first one.
                first_option = field.find("option", value=True)
                if first_option:
                    form_data[name] = first_option["value"]

        elif field.get("type") in ("checkbox", "radio"):
            if field.has_attr("checked"):
                form_data[name] = field.get("value", "1")
        else:  # Handles text, hidden, password, etc.
            form_data[name] = field.get("value", "")

    # 3. Modify the form data with the user's changes
    form_data.update(specific_payload)
    post_url = f"{base_url}/course/modedit.php"

    # 4. POST the modified form data back to the same URL
    resp = session.post(post_url, data=form_data, allow_redirects=False)

    if resp.status_code in [302, 303]:
        return True
    else:
        # If we get a 200, it's likely an error page. Check for Moodle error notifications.
        error_soup = BeautifulSoup(resp.text, "lxml")
        error_div = error_soup.select_one(
            ".error, .errormessage, .alert-danger, div[data-fieldtype=error]"
        )
        if error_div:
            raise MoodleModuleError(
                f"Failed to update module: {error_div.get_text(strip=True)}"
            )
        raise MoodleModuleError(
            f"Failed to update module. Status: {resp.status_code}. Response: {resp.text[:500]}"
        )


def delete_module(
    session: requests.Session,
    base_url: str,
    sesskey: str,
    cmid: int,
) -> bool:
    """
    Deletes any module by its cmid.
    It automatically discovers the course_id from the cmid.
    """
    try:
        module_info = get_module_info(session, base_url, sesskey, cmid)
        # The course ID is located inside the 'cm' dictionary
        course_id = module_info.get("cm", {}).get("course")
        if not course_id:
            raise MoodleModuleError(f"Could not determine course ID for module {cmid}.")
    except MoodleModuleError as e:
        # Re-raise with a more specific context if get_module_info fails
        raise MoodleModuleError(f"Failed to get module info before deletion: {e}")

    url = f"{base_url}/lib/ajax/service.php?sesskey={sesskey}&info=core_courseformat_update_course"
    payload = [
        {
            "index": 0,
            "methodname": "core_courseformat_update_course",
            "args": {
                "action": "cm_delete",
                "courseid": str(course_id),
                "ids": [str(cmid)],
            },
        }
    ]
    headers = {"Content-Type": "application/json"}
    resp = session.post(url, headers=headers, data=json.dumps(payload))

    if resp.status_code != 200:
        raise MoodleModuleError(
            f"Failed to delete module (cmid={cmid}). Status: {resp.status_code}"
        )

    result = resp.json()
    if result and isinstance(result, list) and result[0].get("error") is False:
        return True

    # Provide a cleaner error message if the AJAX call itself fails
    error_details = result[0].get("exception", {}).get("message", "Unknown AJAX error")
    raise MoodleModuleError(f"Error deleting module: {error_details}")


# """
# Webservice functions that return full records including “intro”
_EXTRA_INTRO_FUNCS = {
    "label": "mod_label_get_labels_by_courses",
    "page": "mod_page_get_pages_by_courses",
    "resource": "mod_resource_get_resources_by_courses",
    "url": "mod_url_get_urls_by_courses",
    "forum": "mod_forum_get_forums_by_courses",
    "folder": "mod_folder_get_folders_by_courses",
    "scorm": "mod_scorm_get_scorms_by_courses",
}


def get_module_info(
    session: requests.Session,
    base_url: str,
    sesskey: str,
    cmid: int,
) -> Dict[str, Any]:
    """
    Return raw info for a single module.

    Preference order:
    1. WebService REST call with token (core_course_get_course_module)
    2. Legacy AJAX call (fallback)

    Raises MoodleModuleError if both methods fail.
    """
    token = getattr(session, "webservice_token", None)
    # ---------- 1. Try WebService with token ---------- #
    if token:
        rest_url = f"{base_url}/webservice/rest/server.php"
        params = {
            "wstoken": token,
            "wsfunction": "core_course_get_course_module",
            "moodlewsrestformat": "json",
            "cmid": cmid,
        }
        r = session.get(rest_url, params=params)
        if r.status_code == 200:
            data = r.json()
            # If the response contains an errorcode field, Moodle returned an error
            if isinstance(data, dict) and data.get("exception"):
                errorcode = data.get("errorcode")
                message = data.get("message", "")
                if (
                    errorcode == "invalidrecordunknown"
                    or "invalid value for cmid" in message.lower()
                ):
                    raise MoodleModuleError(f"Module with ID {cmid} not found.")
                else:
                    raise MoodleModuleError(
                        f"Moodle API error: {errorcode} - {message}"
                    )

            # Enrich with intro/description when possible
            _maybe_add_intro(session, base_url, token, data)

            return data
        # If token call failed, fall back to AJAX below

    # ---------- 2. Fallback to AJAX without token ---------- #
    ajax_url = f"{base_url}/lib/ajax/service.php?sesskey={sesskey}"
    payload = [
        {
            "index": 0,
            "methodname": "core_course_get_course_module",
            "args": {"cmid": cmid},
        }
    ]
    r = session.post(
        ajax_url,
        headers={"Content-Type": "application/json"},
        data=json.dumps(payload),
    )
    if r.status_code != 200:
        raise MoodleModuleError(
            f"core_course_get_course_module failed ({r.status_code})"
        )
    result = r.json()[0]
    if result.get("error"):
        raise MoodleModuleError(result)
    data = result["data"]

    # Always try to enrich the module with its intro/description.  If no
    # web-service token is available we still call the helper passing an
    # empty string; for labels it will fall back to HTML scraping and for
    # other modules it will simply exit without changes.
    _maybe_add_intro(session, base_url, token or "", data)

    return data


def get_module_context_id(session: requests.Session, base_url: str, cmid: int) -> int:
    """
    Gets the context ID for a given course module by scraping its edit page.
    This is the most reliable method.

    Args:
        session: An authenticated requests.Session object.
        base_url: The base URL of the Moodle instance.
        cmid: The course module ID (cmid).

    Returns:
        The integer context ID of the module.

    Raises:
        MoodleModuleError: If the context ID cannot be found.
    """
    edit_page_url = f"{base_url}/course/modedit.php?update={cmid}"
    try:
        resp = session.get(edit_page_url)
        resp.raise_for_status()
        # Search for "contextid":12345 in the page's inline JavaScript
        match = re.search(r'["\']contextid["\']\s*:\s*(\d+)', resp.text)
        if match:
            return int(match.group(1))

        # Fallback for other patterns if needed
        match = re.search(r'name="contextid" value="(\d+)"', resp.text)
        if match:
            return int(match.group(1))

        raise MoodleModuleError(
            f"Could not find context ID for module {cmid} on its edit page."
        )
    except requests.RequestException as e:
        raise MoodleModuleError(
            f"Failed to fetch module edit page to get context ID: {e}"
        )


def _maybe_add_intro(
    session: requests.Session,
    base_url: str,
    token: str,
    module: Dict[str, Any],
) -> None:
    """
    If the module type supports a dedicated WS function that returns “intro”,
    call it and insert the intro into the module dict in-place.
    """
    cm = module.get("cm", {})
    modname = cm.get("modname")
    course_id = cm.get("course")
    instance = cm.get("instance")
    if not (modname and course_id) or modname not in _EXTRA_INTRO_FUNCS:
        return

    ws_func = _EXTRA_INTRO_FUNCS[modname]
    rest_url = f"{base_url}/webservice/rest/server.php"
    params = {
        "wstoken": token,
        "wsfunction": ws_func,
        "moodlewsrestformat": "json",
        "courseids[0]": course_id,
    }
    r = session.get(rest_url, params=params)
    if r.status_code != 200:
        return
    items = r.json()
    if isinstance(items, dict) and items.get("exception"):
        return

    # Normalise Moodle WS result to a list, covering:
    #   1) Plain list  → already fine
    #   2) Dict with a single list value → {"labels": [...]}
    #   3) Dict with "warnings" + one list key → {"labels": [...], "warnings": []}
    if isinstance(items, list):
        items_list = items
    elif isinstance(items, dict):
        # Pick the first value that is a list (ignore "warnings" or other metadata)
        items_list = next((v for v in items.values() if isinstance(v, list)), [])
    else:
        items_list = []

    for it in items_list:
        # Different WS use different keys: try several to match this cm
        if str(it.get("coursemodule", it.get("cmid", it.get("id")))) == str(
            cm.get("id")
        ) or str(it.get("id")) == str(instance):
            intro = it.get("intro")
            if intro is not None:
                module["intro"] = intro

            # Add associated files when the WS provides them (resources, folders, …)
            files = it.get("contentfiles") or it.get("files")
            if files:
                module["files"] = files
            break

    # ---------- Fallback scrape (no token or WS failed) ---------- #
    if modname == "label" and "intro" not in module:
        try:
            view_url = f"{base_url}/mod/label/view.php?id={cm.get('id')}"
            r2 = session.get(view_url, timeout=15)
            if r2.status_code == 200:
                soup = BeautifulSoup(r2.text, "lxml")
                div = soup.select_one("div.contentwithoutlink")
                if div:
                    module["intro"] = div.decode_contents()
        except Exception:
            # Ignore scraping errors silently; intro will stay absent
            pass


def format_module_table(module: Dict[str, Any]) -> str:
    """Pretty table with Rich if available, else plain text."""
    try:
        import io

        from rich.console import Console
        from rich.table import Table

        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("Field", style="dim", width=24)
        table.add_column("Value", width=70)
        for k, v in module.items():
            if isinstance(v, dict):
                # Pretty-print nested dictionaries as "key: value" lines
                pretty = "\n".join(f"{kk}: {vv}" for kk, vv in v.items())
                table.add_row(k, pretty)
            else:
                table.add_row(
                    k,
                    (
                        json.dumps(v, ensure_ascii=False)
                        if isinstance(v, list)
                        else str(v)
                    ),
                )
        buf = io.StringIO()
        Console(file=buf, width=120).print(table)
        return buf.getvalue()
    except ImportError:
        return "\n".join(f"{k}: {v}" for k, v in module.items())


def get_module_types(
    session: requests.Session,
    base_url: str,
    sesskey: str,
    course_id: int,
) -> list[dict[str, Any]]:
    """
    Fetches a list of all available module types that the user can add to a specific course.

    Args:
        session: Authenticated requests.Session object.
        base_url: Base URL of the Moodle instance.
        sesskey: Session key for the AJAX call.
        course_id: The ID of the course to check capabilities against.
            Can be 1, the default internal course in Moodle.

    Returns:
        A list of dictionaries, where each dict represents a module type.
        Example: [{'id': 12, 'name': 'label', 'title': 'Etiqueta'}, ...]
    """
    url = f"{base_url}/lib/ajax/service.php?sesskey={sesskey}"
    payload = [
        {
            "index": 0,
            "methodname": "core_course_get_course_content_items",
            "args": {"courseid": course_id},
        }
    ]
    headers = {"Content-Type": "application/json"}

    try:
        resp = session.post(url, headers=headers, data=json.dumps(payload))
        resp.raise_for_status()
        result = resp.json()

        if not result or not isinstance(result, list) or result[0].get("error"):
            error_details = (
                result[0].get("exception", {}).get("message", "Unknown AJAX error")
            )
            raise MoodleModuleError(f"Could not fetch module types: {error_details}")

        data = result[0].get("data", {})
        items = data.get("content_items", [])

        module_list = [
            {"id": item.get("id"), "name": item.get("name"), "title": item.get("title")}
            for item in items
        ]

        # Sort alphabetically by module name
        return sorted(module_list, key=lambda x: x["name"])

    except (requests.RequestException, json.JSONDecodeError) as e:
        raise MoodleModuleError(
            f"Failed to communicate with Moodle to get module types: {e}"
        )


def _get_module_id_from_name(
    session: requests.Session,
    base_url: str,
    sesskey: str,
    course_id: int,
    module_name: str,
) -> int:
    """
    Helper function to get a module's ID by its name (e.g., 'label'), using a cache.
    """
    cache_key = (base_url, course_id)
    if cache_key not in _MODULE_ID_CACHE:
        all_types = get_module_types(session, base_url, sesskey, course_id)
        _MODULE_ID_CACHE[cache_key] = {mod["name"]: mod["id"] for mod in all_types}

    module_map = _MODULE_ID_CACHE[cache_key]
    module_id = module_map.get(module_name)

    if module_id is None:
        raise MoodleModuleError(
            f"Module type '{module_name}' not found or user lacks permission to add it in course {course_id}."
        )
    return module_id


def rename_module_name(
    session: requests.Session,
    base_url: str,
    sesskey: str,
    cmid: int,
    name: str,
) -> bool:
    """
    Renames the name of any course module using the generic 'inplace_editable' AJAX endpoint.

    Args:
        session: Authenticated requests.Session object.
        base_url: Base URL of the Moodle instance.
        sesskey: Session key for the AJAX call.
        cmid: The course module ID (cmid) of the activity to rename.
        name: The new name for the module.

    Returns:
        True if the renaming was successful.

    Raises:
        MoodleModuleError: If the AJAX call fails or returns an error.
    """
    ajax_url = f"{base_url}/lib/ajax/service.php?sesskey={sesskey}&info=core_update_inplace_editable"

    payload = [
        {
            "index": 0,
            "methodname": "core_update_inplace_editable",
            "args": {
                "component": "core_course",
                "itemtype": "activityname",
                "itemid": str(cmid),
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

        if result and isinstance(result, list) and result[0].get("error") is False:
            return True

        error_details = (
            result[0].get("exception", {}).get("message", "Unknown AJAX error")
        )
        raise MoodleModuleError(f"Error renaming module name: {error_details}")

    except (requests.RequestException, json.JSONDecodeError) as e:
        raise MoodleModuleError(
            f"Failed to communicate with Moodle to rename module: {e}"
        )


__all__ = [
    "MoodleModuleError",
    "add_generic_module",
    "update_generic_module",
    "delete_module",
    "get_module_info",
    "get_module_context_id",
    "format_module_table",
    "get_module_types",
    "rename_module_name",
]
