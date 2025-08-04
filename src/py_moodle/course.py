# src/moodle/course.py
"""
Course management module for Moodle.

Provides functions to list courses, retrieve course details,
and enumerate course sections using AJAX endpoints.
"""
import json
import time
import urllib.parse
from typing import Any, Dict, List

import requests


class MoodleCourseError(Exception):
    """Exception raised for errors in course operations."""


def get_course_context_id(
    session: requests.Session,
    base_url: str,
    course_id: int,
) -> int:
    """Get the context ID for a course by scraping its main page.

    This mimics how the frontend retrieves the ID, making it the most
    reliable method.

    Args:
        session: Authenticated requests session.
        base_url: Base URL of the Moodle instance.
        course_id: Identifier of the course.

    Returns:
        int: Context ID of the course.

    Raises:
        MoodleCourseError: If the context ID cannot be found.
    """
    import re

    course_page_url = f"{base_url}/course/view.php?id={course_id}"
    try:
        resp = session.get(course_page_url)
        resp.raise_for_status()
        # Search for "courseContextId":123 or "contextid":123 in the page's JS
        match = re.search(
            r'["\'](?:courseContextId|contextid)["\']\s*:\s*(\d+)', resp.text
        )
        if match:
            return int(match.group(1))
        raise MoodleCourseError(
            f"Could not determine course context ID for course {course_id} from page source."
        )
    except requests.RequestException as e:
        raise MoodleCourseError(f"Failed to fetch course page to get context ID: {e}")


def list_courses(
    session: requests.Session,
    base_url: str,
    *,
    token: str | None = None,
    sesskey: str | None = None,
) -> List[Dict[str, Any]]:
    """List all courses visible to the user.

    Uses the ``core_course_get_courses`` webservice when a token is
    available and falls back to the AJAX endpoint otherwise.

    Args:
        session: Authenticated requests session.
        base_url: Base URL of the Moodle instance.
        token: Webservice token for REST API (optional, preferred).
        sesskey: Session key for AJAX calls (optional, fallback).

    Returns:
        List[Dict[str, Any]]: List of course dictionaries.

    Raises:
        MoodleCourseError: If the request fails.
    """
    # Always try to get the token from the session if not provided
    if token is None and hasattr(session, "webservice_token"):
        token = getattr(session, "webservice_token", None)
    if sesskey is None and hasattr(session, "sesskey"):
        sesskey = getattr(session, "sesskey", None)

    # If token is present but invalid, fallback to AJAX if possible
    if token:
        url = f"{base_url}/webservice/rest/server.php"
        params = {
            "wstoken": token,
            "wsfunction": "core_course_get_courses",
            "moodlewsrestformat": "json",
        }
        resp = session.post(url, data=params)
        try:
            result = resp.json()
            # If token is invalid, fallback to AJAX if possible
            if (
                isinstance(result, dict)
                and "exception" in result
                and "Invalid token" in result.get("message", "")
            ):
                # fallback to AJAX below, do not raise
                pass
            elif isinstance(result, dict) and "exception" in result:
                raise MoodleCourseError(result.get("message", "Unknown error"))
            else:
                # Sort by ID ascending before returning
                return sorted(result, key=lambda c: c.get("id", 0))
        except Exception:
            # fallback to AJAX below if possible
            pass

    if not sesskey:
        raise MoodleCourseError(
            "No valid token or sesskey provided for listing courses."
        )
    url = f"{base_url}/lib/ajax/service.php?sesskey={sesskey}"

    # Refresh session before AJAX call to prevent "session expired" errors.
    session.get(f"{base_url}/my/")

    data = [{"index": 0, "methodname": "core_course_get_courses", "args": {}}]
    headers = {"Content-Type": "application/json"}
    resp = session.post(url, json=data, headers=headers)
    if resp.status_code != 200:
        raise MoodleCourseError(f"Failed to list courses. Status: {resp.status_code}")
    try:
        result = resp.json()
        # Defensive: check for error in AJAX response
        if (
            result
            and isinstance(result, list)
            and "error" in result[0]
            and result[0]["error"]
        ):
            raise MoodleCourseError(
                result[0].get("exception", {}).get("message", "Unknown error")
            )
        # The data is in result[0]["data"]
        courses = result[0]["data"]
        # Sort by ID ascending before returning
        return sorted(courses, key=lambda c: c.get("id", 0))
    except Exception as e:
        raise MoodleCourseError(f"Failed to parse courses: {e}")


def create_course(
    session: requests.Session,
    base_url: str,
    sesskey: str,
    fullname: str,
    shortname: str,
    categoryid: int = 1,
    visible: int = 1,
    summary: str = "",
    startdate: dict = None,
    enddate: dict = None,
    numsections: int = 4,
) -> Dict[str, Any]:
    """Create a new course using the web form.

    Simulates browser behavior by posting to ``edit.php``.

    Args:
        session: Authenticated requests session.
        base_url: Base URL of the Moodle instance.
        sesskey: Session key for AJAX calls.
        fullname: Full name of the course.
        shortname: Short name of the course.
        categoryid: Category ID.
        visible: Visibility flag (1 for visible, 0 for hidden).
        summary: Course summary.
        startdate: Dict with keys ``day``, ``month``, ``year``, ``hour``, ``minute``.
        enddate: Dict with keys ``enabled``, ``day``, ``month``, ``year``, ``hour``, ``minute``.
        numsections: Number of sections.

    Returns:
        Dict[str, Any]: Created course dictionary with at least ``id``, ``fullname`` and ``shortname``.

    Raises:
        MoodleCourseError: If the request fails.
    """
    from datetime import datetime

    # Try both /course/edit.php and /course/edit.php?category=...
    # Some sandboxes require the category param, others not.

    now = datetime.now()
    if startdate is None:
        startdate = {
            "day": now.day,
            "month": now.month,
            "year": now.year,
            "hour": 0,
            "minute": 0,
        }
    if enddate is None:
        enddate = {
            "enabled": 1,
            "day": now.day,
            "month": now.month,
            "year": now.year + 1,
            "hour": 0,
            "minute": 0,
        }

    # Get a draft itemid for summary_editor (optional, fallback to 0)
    try:
        from py_moodle.draftfile import get_new_draft_itemid

        get_new_draft_itemid(session, base_url, sesskey)
    except Exception:
        pass

    import random

    payload = {
        "returnto": "0",
        "returnurl": f"{base_url}/course/",
        "mform_isexpanded_id_descriptionhdr": "1",
        "addcourseformatoptionshere": "",
        "id": "",
        "sesskey": sesskey,
        "_qf__course_edit_form": "1",
        "mform_isexpanded_id_general": "1",
        "mform_isexpanded_id_courseformathdr": "0",
        "mform_isexpanded_id_appearancehdr": "0",
        "mform_isexpanded_id_filehdr": "0",
        "mform_isexpanded_id_completionhdr": "0",
        "mform_isexpanded_id_groups": "0",
        "mform_isexpanded_id_tagshdr": "0",
        "fullname": fullname,
        "shortname": shortname,
        "category": str(categoryid),
        "visible": "1" if visible else "0",
        "startdate[day]": str(startdate["day"]),
        "startdate[month]": str(startdate["month"]),
        "startdate[year]": str(startdate["year"]),
        "startdate[hour]": str(startdate["hour"]),
        "startdate[minute]": str(startdate["minute"]),
        "enddate[enabled]": str(enddate["enabled"]),
        "enddate[day]": str(enddate["day"]),
        "enddate[month]": str(enddate["month"]),
        "enddate[year]": str(enddate["year"]),
        "enddate[hour]": str(enddate["hour"]),
        "enddate[minute]": str(enddate["minute"]),
        "idnumber": "",
        "summary_editor[text]": summary,
        "summary_editor[format]": "1",
        "summary_editor[itemid]": str(random.randint(10000000, 99999999)),
        "overviewfiles_filemanager": str(random.randint(10000000, 99999999)),
        "format": "topics",
        "numsections": str(numsections),
        "hiddensections": "1",
        "coursedisplay": "0",
        "lang": "",
        "newsitems": "5",
        "showgrades": "1",
        "showreports": "0",
        "showactivitydates": "1",
        "maxbytes": "0",
        "enablecompletion": "1",
        "showcompletionconditions": "1",
        "groupmode": "0",
        "groupmodeforce": "0",
        "defaultgroupingid": "0",
        "tags": "_qf__force_multiselect_submission",
        "_qf__force_multiselect_submission": "",
        "saveanddisplay": "Save and display",
    }

    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    # Use only /course/edit.php as in the JS example, without category parameter
    url_plain = f"{base_url}/course/edit.php"
    # Important: send data as application/x-www-form-urlencoded, not as a plain dict

    encoded_payload = urllib.parse.urlencode(payload)
    resp = session.post(
        url_plain, data=encoded_payload, headers=headers, allow_redirects=False
    )

    # Moodle can respond with 303, 302, or even 200 if it doesn't redirect
    # Check if the shortname already exists (typical Moodle error)
    if resp.status_code == 200:
        # Detect duplicate shortname error in English and Spanish
        if (
            ("shortname" in resp.text and "already in use" in resp.text)
            or ("shortname" in resp.text and "is already in use" in resp.text)
            or ("Short name" in resp.text and "already in use" in resp.text)
            or ("The short name" in resp.text and "is already in use" in resp.text)
        ):
            raise MoodleCourseError(
                "Shortname already in use. Please use a unique shortname for the course."
            )
        # Detect if the response is the creation form (course was not created)
        if "<title>Add a new course" in resp.text:
            raise MoodleCourseError(
                "Failed to create course. Moodle returned the course creation form again. Check required fields or permissions."
            )

    if resp.status_code in (303, 302):
        location = resp.headers.get("Location", "")
        # Parse the course ID from the redirect URL.
        from urllib.parse import parse_qs, urlparse

        parsed_url = urlparse(location)
        query_params = parse_qs(parsed_url.query)
        course_id_str = query_params.get("id", [None])[0]
        course_id = (
            int(course_id_str) if course_id_str and course_id_str.isdigit() else None
        )

        # If the ID is missing in the redirect, attempt to find the course by listing courses.
        time.sleep(1)  # Give the server a moment to process the creation
        all_courses = list_courses(
            session,
            base_url,
            token=getattr(session, "webservice_token", None),
            sesskey=sesskey,
        )
        newly_created = next(
            (c for c in all_courses if c["shortname"] == shortname), None
        )
        if newly_created and "id" in newly_created:
            return newly_created
        return {"id": None, "fullname": fullname, "shortname": shortname}

        # Optionally, fetch course info if id was found
        if course_id:
            return {"id": course_id, "fullname": fullname, "shortname": shortname}
        else:
            return {"id": None, "fullname": fullname, "shortname": shortname}
    elif resp.status_code == 200 and "course/view.php?id=" in resp.text:
        # Find the id in the returned HTML
        import re

        m = re.search(r"course/view\.php\?id=(\d+)", resp.text)
        course_id = int(m.group(1)) if m else None
        if course_id:
            return {"id": course_id, "fullname": fullname, "shortname": shortname}
        else:
            return {"id": None, "fullname": fullname, "shortname": shortname}
    else:
        raise MoodleCourseError(
            f"Failed to create course. Status: {resp.status_code} - {resp.text[:500]}"
        )


def delete_course(
    session: requests.Session,
    base_url: str,
    sesskey: str,
    courseid: int,
    force: bool = False,
) -> None:
    """Delete a course by ID using the web interface.

    Args:
        session: Authenticated requests session.
        base_url: Base URL of the Moodle instance.
        sesskey: Session key for AJAX calls.
        courseid: ID of the course to delete.
        force: Whether to skip confirmation and delete directly.

    Raises:
        MoodleCourseError: If the request fails.
    """
    import re

    url = f"{base_url}/course/delete.php?id={courseid}"
    resp = session.get(url)
    if resp.status_code != 200:
        raise MoodleCourseError(
            f"Failed to access course delete page. Status: {resp.status_code}"
        )

    # Extract the course name to show in the confirmation
    m_title = re.search(r"<title>([^<]+)</title>", resp.text)
    course_title = m_title.group(1) if m_title else f"ID {courseid}"

    # Find the necessary values in the form
    m_sesskey = re.search(r'name="sesskey"\s+value="([^"]+)"', resp.text)
    m_delete = re.search(r'name="delete"\s+value="([^"]+)"', resp.text)
    confirm_sesskey = m_sesskey.group(1) if m_sesskey else sesskey
    delete_token = m_delete.group(1) if m_delete else None

    if not delete_token:
        raise MoodleCourseError("Could not find delete token in confirmation form.")

    # If not forced, ask for interactive confirmation
    if not force:
        confirm = input(
            f"Are you sure you want to delete course '{course_title}' (ID {courseid})? [y/N]: "
        )
        if confirm.strip().lower() not in ("y", "yes"):
            print("Aborted.")
            return

    # Step 2: send the confirmation form
    payload = {
        "id": str(courseid),
        "delete": delete_token,
        "sesskey": confirm_sesskey,
        "confirm": "1",
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    resp2 = session.post(
        f"{base_url}/course/delete.php",
        data=payload,
        headers=headers,
        allow_redirects=True,
    )
    # Consider it a success if there is no error and the confirmation form is not shown again
    if resp2.status_code != 200 or '<form method="post" action="' in resp2.text:
        if "error" in resp2.text.lower():
            raise MoodleCourseError(f"Failed to delete course: {resp2.text[:500]}")
        raise MoodleCourseError(
            "Failed to delete course: Moodle did not confirm deletion."
        )
    # If we get here, it's considered a success


def get_course(
    session: requests.Session,
    base_url: str,
    sesskey: str,
    courseid: int,
    token: str = None,
) -> List[Dict[str, Any]]:
    """Get details for a specific course.

    Attempts the webservice first and falls back to AJAX if necessary.

    Args:
        session: Authenticated requests session.
        base_url: Base URL of the Moodle instance.
        sesskey: Session key for AJAX calls.
        courseid: Identifier of the course to fetch.
        token: Webservice token (optional).

    Returns:
        List[Dict[str, Any]]: Course contents including sections and modules.

    Raises:
        MoodleCourseError: If both webservice and AJAX requests fail.
    """
    if token:
        try:
            url = f"{base_url}/webservice/rest/server.php"
            params = {
                "wstoken": token,
                "wsfunction": "core_course_get_contents",
                "moodlewsrestformat": "json",
                "courseid": courseid,
            }
            resp = session.post(url, data=params)
            resp.raise_for_status()

            # If Moodle returns an empty response, it is not valid JSON.
            if not resp.text or not resp.text.strip():
                raise MoodleCourseError("Empty response from webservice")

            result = resp.json()
            if isinstance(result, dict) and "exception" in result:
                raise MoodleCourseError(f"Webservice error: {result.get('message')}")

            if isinstance(result, list):
                return result  # Success: return the content

            # If the format is unexpected, force the fallback
            raise MoodleCourseError("Unexpected format from webservice")

        except (requests.RequestException, json.JSONDecodeError, MoodleCourseError):
            # Any failure here triggers the AJAX method.
            pass

    # Fallback to AJAX if there is no token or the token method failed.
    if not sesskey:
        raise MoodleCourseError(
            "Could not get course details. No valid token or sesskey worked."
        )

    url = f"{base_url}/lib/ajax/service.php?sesskey={sesskey}&info=core_courseformat_get_state"
    data = [
        {
            "index": 0,
            "methodname": "core_courseformat_get_state",
            "args": {"courseid": courseid},
        }
    ]
    resp = session.post(url, json=data)
    if resp.status_code != 200:
        raise MoodleCourseError(
            f"Failed to get course state via AJAX. Status: {resp.status_code}"
        )
    try:
        result = resp.json()
        if result and isinstance(result, list) and result[0].get("error"):
            raise MoodleCourseError(
                result[0].get("exception", {}).get("message", "Unknown AJAX error")
            )

        course_state = json.loads(result[0]["data"])
        sections = course_state.get("section", [])
        modules_by_id = {str(m["id"]): m for m in course_state.get("cm", [])}

        for section in sections:
            module_ids = section.get("cmlist", [])
            section["modules"] = [
                modules_by_id[str(mod_id)]
                for mod_id in module_ids
                if str(mod_id) in modules_by_id
            ]
            if "cmlist" in section:
                del section["cmlist"]

        return sections
    except Exception as e:
        raise MoodleCourseError(f"Failed to parse course state from AJAX: {e}")


def get_course_with_sections_and_modules(
    session: requests.Session,
    base_url: str,
    sesskey: str,
    courseid: int,
    token: str = None,
) -> Dict[str, Any]:
    """Return full course data with sections and modules.

    Args:
        session: Authenticated requests session.
        base_url: Base URL of the Moodle instance.
        sesskey: Session key for AJAX calls.
        courseid: Identifier of the course to fetch.
        token: Webservice token (optional).

    Returns:
        Dict[str, Any]: Course dictionary with keys ``id``, ``fullname``,
        ``shortname`` and a list of ``sections`` containing their modules.
    """
    # 1. Get the main course structure (sections and modules)
    sections_list = get_course(session, base_url, sesskey, courseid, token=token)

    # 2. Get top-level course details (like fullname, shortname)
    all_courses = list_courses(session, base_url, token=token, sesskey=sesskey)
    course_details = next((c for c in all_courses if c.get("id") == courseid), {})

    # 3. Build the final, clean dictionary
    course_summary = {
        "id": courseid,
        "fullname": course_details.get("fullname", "Unknown Course"),
        "shortname": course_details.get("shortname", "N/A"),
        "sections": [],
    }

    for s in sections_list:
        # The module list can be under "modules" (webservice) or "cmlist" (AJAX)
        modules_raw = s.get("modules", s.get("cmlist", []))

        # Normalize module data to a consistent format
        clean_modules = []
        for m in modules_raw:
            clean_modules.append(
                {
                    "id": m.get("id"),
                    "name": m.get("name"),
                    "modname": m.get(
                        "modname", m.get("mod", "unknown")
                    ),  # "mod" is fallback for some AJAX calls
                }
            )

        course_summary["sections"].append(
            {
                "id": s.get("id"),
                "section": s.get("section"),
                "name": s.get("name"),
                "summary": s.get("summary", ""),
                "modules": clean_modules,
            }
        )

    return course_summary


def list_sections(course_contents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Extract a list of sections from course contents.

    Args:
        course_contents: Output from ``get_course``.

    Returns:
        List[Dict[str, Any]]: Each dictionary represents a section.

    Notes:
        This function expects the output of ``get_course``.
    """
    return [
        {
            "id": section.get("id"),
            "section": section.get("section"),
            "name": section.get("name"),
            "summary": section.get("summary"),
            "modules": section.get("modules", []),
        }
        for section in course_contents
    ]


__all__ = [
    "MoodleCourseError",
    "get_course_context_id",
    "list_courses",
    "create_course",
    "delete_course",
    "get_course",
    "get_course_with_sections_and_modules",
    "list_sections",
]
