"""
Course management module for Moodle.

Provides functions to list courses, retrieve course details,
and enumerate course sections using AJAX endpoints.
"""

from __future__ import annotations

import json
import time
import urllib.parse
from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional

import requests
from bs4 import BeautifulSoup

from .http import MoodleHttpError, request_form_post
from .permissions import requires_role
from .transport import TransportError, TransportUnavailableError
from .transport import ajax as ajax_transport
from .transport import webservice as webservice_transport


class MoodleCourseError(Exception):
    """Exception raised for errors in course operations."""


class ConfirmationRequired(MoodleCourseError):
    """Raised when a mutating operation needs interactive confirmation.

    Attributes:
        course_id: The course id pending confirmation.
        course_title: The human-readable title, if it could be determined.
    """

    def __init__(self, course_id: int, course_title: str) -> None:
        """Initialize the exception with the pending course id and title.

        Args:
            course_id: The course id pending confirmation.
            course_title: The human-readable title, if it could be determined.
        """
        self.course_id = course_id
        self.course_title = course_title
        super().__init__(
            f"Confirmation required to delete course '{course_title}' (ID {course_id})."
        )


EnsureStatus = Literal["created", "reused", "updated", "conflict"]


@dataclass
class EnsureCourseResult:
    """Outcome of an :func:`ensure_course` call.

    Attributes:
        status: One of ``"created"``, ``"reused"``, ``"updated"``, or
            ``"conflict"``.
        course: The resulting course dictionary (existing, created, or
            updated, depending on ``status``).
        differences: Populated only when ``status == "conflict"``, mapping
            each differing field name (``"fullname"`` and/or
            ``"categoryid"``) to a ``(existing_value, requested_value)``
            tuple. ``None`` otherwise.
    """

    status: EnsureStatus
    course: Dict[str, Any]
    differences: Optional[Dict[str, tuple]] = None


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
    available and falls back to the AJAX endpoint otherwise. Internally,
    each transport is delegated to :mod:`py_moodle.transport.webservice`
    and :mod:`py_moodle.transport.ajax` respectively; their
    ``TransportError``/``TransportUnavailableError`` exceptions are
    translated into ``MoodleCourseError`` (or used to decide the
    webservice-to-AJAX fallback) and never leak to callers of this
    function.

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

    if token:
        try:
            result = webservice_transport.call(
                session, base_url, "core_course_get_courses", token
            )
            # Sort by ID ascending before returning
            return sorted(result, key=lambda c: c.get("id", 0))
        except TransportUnavailableError:
            # The token is invalid/expired: fall through to the AJAX
            # transport below.
            pass
        except TransportError as exc:
            raise MoodleCourseError(str(exc)) from exc

    if not sesskey:
        raise MoodleCourseError(
            "Listing courses requires a valid webservice token or sesskey. "
            "Log in again, or use a user that can access the Moodle mobile "
            "web service."
        )

    try:
        result = ajax_transport.call(
            session, base_url, "core_course_get_courses", sesskey
        )
        # Sort by ID ascending before returning
        return sorted(result, key=lambda c: c.get("id", 0))
    except TransportError as exc:
        raise MoodleCourseError(str(exc)) from exc


@requires_role("manager")
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
    try:
        resp = request_form_post(
            session,
            url_plain,
            data=encoded_payload,
            headers=headers,
            allow_redirects=False,
            raise_for_status=False,
        )
    except MoodleHttpError as e:
        raise MoodleCourseError(f"Failed to create course: {e}") from e

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


def _extract_course_edit_form_data(soup: BeautifulSoup) -> Dict[str, Any]:
    """Extract current field values from a Moodle course edit form.

    Scrapes every ``input``, ``textarea``, and ``select`` element of the
    ``course/edit.php`` form so an update can resubmit each field unchanged
    except the ones the caller explicitly wants to change, mirroring the
    fetch-modify-submit pattern used elsewhere in this project for module
    edit forms.

    Args:
        soup: Parsed HTML of the ``course/edit.php`` page.

    Returns:
        Dict[str, Any]: Mapping of form field name to its current value.
        Empty if the course edit form could not be located in ``soup``.
    """
    marker = soup.find("input", attrs={"name": "_qf__course_edit_form"})
    form = marker.find_parent("form") if marker else None
    if form is None:
        return {}

    form_data: Dict[str, Any] = {}
    for field in form.find_all(["input", "textarea", "select"]):
        name = field.get("name")
        if not name or field.get("type") in ("submit", "button", "reset", "file"):
            continue

        if field.name == "textarea":
            form_data[name] = field.text or ""
        elif field.name == "select":
            selected_options = [
                option["value"]
                for option in field.find_all("option", selected=True)
                if option.has_attr("value")
            ]
            if field.has_attr("multiple"):
                if selected_options:
                    form_data[name] = selected_options
            elif selected_options:
                form_data[name] = selected_options[0]
            else:
                first_option = next(
                    (
                        option
                        for option in field.find_all("option")
                        if option.has_attr("value")
                    ),
                    None,
                )
                if first_option:
                    form_data[name] = first_option["value"]
        elif field.get("type") in ("checkbox", "radio"):
            if field.has_attr("checked"):
                form_data[name] = field.get("value", "1")
        else:
            form_data[name] = field.get("value", "")

    return form_data


def update_course_basic(
    session: requests.Session,
    base_url: str,
    sesskey: str,
    courseid: int,
    *,
    fullname: str | None = None,
    categoryid: int | None = None,
) -> Dict[str, Any]:
    """Apply a minimal, safe update to a course's name and/or category.

    Deliberately restricted to ``fullname`` and ``categoryid``: this helper
    fetches the current ``course/edit.php`` form, changes only the fields
    explicitly requested, and resubmits every other field unchanged, so it
    must never touch ``summary``, ``visible``, sections, or modules.

    Args:
        session: Authenticated requests session.
        base_url: Base URL of the Moodle instance.
        sesskey: Session key for form calls.
        courseid: ID of the course to update.
        fullname: New full name, or None to leave unchanged.
        categoryid: New category ID, or None to leave unchanged.

    Returns:
        Dict[str, Any]: The updated course dictionary, as looked up via
        ``list_courses`` after the update is applied.

    Raises:
        MoodleCourseError: If the update request fails.
    """
    if fullname is None and categoryid is None:
        courses = list_courses(session, base_url, sesskey=sesskey)
        return next((c for c in courses if c.get("id") == courseid), {})

    edit_url = f"{base_url}/course/edit.php?id={courseid}"
    try:
        resp = session.get(edit_url)
        resp.raise_for_status()
    except requests.RequestException as e:
        raise MoodleCourseError(
            f"Failed to load course edit form for course {courseid}: {e}"
        )

    soup = BeautifulSoup(resp.text, "lxml")
    form_data = _extract_course_edit_form_data(soup)
    if not form_data:
        raise MoodleCourseError(
            f"Could not find the course edit form for course {courseid}."
        )

    form_data["sesskey"] = sesskey
    if fullname is not None:
        form_data["fullname"] = fullname
    if categoryid is not None:
        form_data["category"] = str(categoryid)

    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    encoded_payload = urllib.parse.urlencode(form_data, doseq=True)
    resp2 = session.post(
        f"{base_url}/course/edit.php",
        data=encoded_payload,
        headers=headers,
        allow_redirects=False,
    )

    if resp2.status_code == 200 and "_qf__course_edit_form" in resp2.text:
        raise MoodleCourseError(
            f"Failed to update course {courseid}. Moodle returned the edit "
            "form again; check required fields or permissions."
        )
    if resp2.status_code not in (200, 302, 303):
        raise MoodleCourseError(
            f"Failed to update course {courseid}. Status: {resp2.status_code}"
        )

    updated_courses = list_courses(session, base_url, sesskey=sesskey)
    updated = next((c for c in updated_courses if c.get("id") == courseid), None)
    if updated is None:
        raise MoodleCourseError(f"Course {courseid} could not be found after updating.")
    return updated


def ensure_course(
    session: requests.Session,
    base_url: str,
    sesskey: str,
    *,
    shortname: str,
    fullname: str,
    category_id: int,
    token: str | None = None,
    update: bool = False,
    **create_kwargs: Any,
) -> EnsureCourseResult:
    """Ensure a course with the given shortname exists.

    Looks up an existing course by ``shortname`` via ``list_courses()``. If no
    course with that shortname is found, creates one via ``create_course()``.
    If a course is found and ``update`` is False, the existing course is left
    untouched: if ``fullname``/``category_id`` match the request the result is
    ``"reused"``; if they differ the result is ``"conflict"`` (nothing is
    changed, but the caller can inspect ``differences``). If a course is found
    and ``update`` is True, the differing fields among ``fullname``/
    ``category_id`` are updated via ``update_course_basic()`` and the result
    is ``"updated"``.

    Args:
        session: Authenticated requests session.
        base_url: Base URL of the Moodle instance.
        sesskey: Session key for AJAX/form calls.
        shortname: Unique shortname used to look up an existing course.
        fullname: Desired full name of the course.
        category_id: Desired category ID of the course.
        token: Optional webservice token, forwarded to ``list_courses``.
        update: If True and a course is found, apply a safe update to
            ``fullname``/``category_id`` instead of leaving it untouched.
        **create_kwargs: Extra keyword arguments forwarded to
            ``create_course`` when a new course must be created (e.g.
            ``visible``, ``summary``, ``numsections``).

    Returns:
        EnsureCourseResult: Typed result with ``status`` of ``"created"``,
        ``"reused"``, ``"updated"``, or ``"conflict"``.

    Raises:
        MoodleCourseError: If listing, creating, or updating fails.
    """
    existing_courses = list_courses(session, base_url, token=token, sesskey=sesskey)
    existing = next(
        (c for c in existing_courses if c.get("shortname") == shortname), None
    )

    if existing is None:
        created = create_course(
            session,
            base_url,
            sesskey,
            fullname=fullname,
            shortname=shortname,
            categoryid=category_id,
            **create_kwargs,
        )
        return EnsureCourseResult(status="created", course=created)

    differences: Dict[str, tuple] = {}
    if existing.get("fullname") != fullname:
        differences["fullname"] = (existing.get("fullname"), fullname)
    if existing.get("categoryid") != category_id:
        differences["categoryid"] = (existing.get("categoryid"), category_id)

    if not differences:
        return EnsureCourseResult(status="reused", course=existing)

    if not update:
        return EnsureCourseResult(
            status="conflict", course=existing, differences=differences
        )

    update_kwargs: Dict[str, Any] = {}
    if "fullname" in differences:
        update_kwargs["fullname"] = fullname
    if "categoryid" in differences:
        update_kwargs["categoryid"] = category_id

    updated_course = update_course_basic(
        session, base_url, sesskey, existing["id"], **update_kwargs
    )
    return EnsureCourseResult(status="updated", course=updated_course)


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
        ConfirmationRequired: If ``force`` is ``False``. Callers must catch
            this exception and re-invoke with ``force=True`` after obtaining
            confirmation themselves; this function performs no stdin/stdout
            I/O of its own.
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

    # If not forced, the caller must confirm before we proceed.
    if not force:
        raise ConfirmationRequired(courseid, course_title)

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
    "ConfirmationRequired",
    "get_course_context_id",
    "list_courses",
    "create_course",
    "ensure_course",
    "update_course_basic",
    "delete_course",
    "get_course",
    "get_course_with_sections_and_modules",
    "list_sections",
]
