# src/moodle/section.py
"""
Section management module for Moodle CLI.

Provides functions to list, create, and delete course sections using AJAX endpoints.

All code and comments must be in English.
"""

from typing import Any, Dict

import requests


class MoodleSectionError(Exception):
    """Exception raised for errors in section operations."""


def list_sections(
    session: requests.Session, base_url: str, sesskey: str, courseid: int
) -> Dict[str, Any]:
    """
    List all sections and modules for a given course using core_courseformat_get_state.

    Args:
        session: Authenticated requests.Session object.
        base_url: Base URL of the Moodle instance.
        sesskey: Session key for AJAX calls.
        courseid: ID of the course.

    Returns:
        Dictionary with keys: 'course', 'section', 'cm' (modules).

    Raises:
        MoodleSectionError: If the request fails.
    """
    url = f"{base_url}/lib/ajax/service.php?sesskey={sesskey}"
    data = [
        {
            "index": 0,
            "methodname": "core_courseformat_get_state",
            "args": {"courseid": int(courseid)},
        }
    ]
    headers = {"Content-Type": "application/json"}
    resp = session.post(url, json=data, headers=headers)
    if resp.status_code != 200:
        raise MoodleSectionError(f"Failed to list sections. Status: {resp.status_code}")
    try:
        result = resp.json()
        if (
            result
            and isinstance(result, list)
            and "error" in result[0]
            and result[0]["error"]
        ):
            raise MoodleSectionError(
                result[0].get("exception", {}).get("message", "Unknown error")
            )
        data_json = result[0].get("data")
        if not data_json:
            raise MoodleSectionError("No data returned for course sections.")
        import json

        data = json.loads(data_json)
        return data
    except Exception as e:
        raise MoodleSectionError(f"Failed to parse sections: {e}")


def create_section(
    session: requests.Session, base_url: str, sesskey: str, courseid: int
) -> Dict[str, Any]:
    """
    Create a new section in a course.

    Args:
        session: Authenticated requests.Session object.
        base_url: Base URL of the Moodle instance.
        sesskey: Session key for AJAX calls.
        courseid: ID of the course.

    Returns:
        The last created section as a dictionary.

    Raises:
        MoodleSectionError: If the request fails.
    """
    url = f"{base_url}/lib/ajax/service.php?sesskey={sesskey}&info=core_courseformat_update_course"
    data = [
        {
            "index": 0,
            "methodname": "core_courseformat_update_course",
            "args": {"action": "section_add", "courseid": str(courseid), "ids": []},
        }
    ]
    headers = {"Content-Type": "application/json"}
    resp = session.post(url, json=data, headers=headers)
    if resp.status_code != 200:
        raise MoodleSectionError(
            f"Failed to create section. Status: {resp.status_code}"
        )
    try:
        result = resp.json()
        if result and isinstance(result, list):
            if "error" in result[0] and result[0]["error"]:
                msg = result[0].get("exception", {}).get("message", "Unknown error")
                if "section_state" in msg:
                    raise MoodleSectionError(
                        "Section add not supported for this course (section_state)."
                    )
                raise MoodleSectionError(msg)
            # The 'data' field is a JSON string with the updated course state
            data_json = result[0].get("data")
            if not data_json:
                raise MoodleSectionError(
                    "Section add returned no data (may not be supported)."
                )
            try:
                import json

                updated_course = json.loads(data_json)
            except Exception as e:
                raise MoodleSectionError(f"Could not parse updated course JSON: {e}")
            # Find the section with the highest number
            sections = [e for e in updated_course if e.get("name") == "section"]
            if not sections:
                raise MoodleSectionError("No sections found in updated course data.")
            last_section = max(
                sections, key=lambda s: s.get("fields", {}).get("number", -1)
            )
            return last_section
        raise MoodleSectionError("Unexpected response format from Moodle.")
    except Exception as e:
        if "section_state" in str(e):
            raise MoodleSectionError(
                "Section add not supported for this course (section_state)."
            )
        raise MoodleSectionError(f"Failed to parse create section response: {e}")


def delete_section(
    session: requests.Session,
    base_url: str,
    sesskey: str,
    courseid: int,
    sectionid: int,
) -> Dict[str, Any]:
    """
    Delete a section from a course.

    Args:
        session: Authenticated requests.Session object.
        base_url: Base URL of the Moodle instance.
        sesskey: Session key for AJAX calls.
        courseid: ID of the course.
        sectionid: ID of the section to delete.

    Returns:
        The response dictionary from Moodle.

    Raises:
        MoodleSectionError: If the request fails.
    """
    url = f"{base_url}/lib/ajax/service.php?sesskey={sesskey}&info=core_courseformat_update_course"
    data = [
        {
            "index": 0,
            "methodname": "core_courseformat_update_course",
            "args": {
                "action": "section_delete",
                "courseid": str(courseid),
                "ids": [str(sectionid)],
            },
        }
    ]
    headers = {"Content-Type": "application/json"}
    resp = session.post(url, json=data, headers=headers)
    if resp.status_code != 200:
        raise MoodleSectionError(
            f"Failed to delete section. Status: {resp.status_code}"
        )
    try:
        result = resp.json()
        if (
            result
            and isinstance(result, list)
            and "error" in result[0]
            and result[0]["error"]
        ):
            raise MoodleSectionError(
                result[0].get("exception", {}).get("message", "Unknown error")
            )
        return result[0].get("data", {})
    except Exception as e:
        raise MoodleSectionError(f"Failed to parse delete section response: {e}")


__all__ = [
    "MoodleSectionError",
    "list_sections",
    "create_section",
    "delete_section",
]
