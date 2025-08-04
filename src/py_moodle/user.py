# src/moodle/user.py
"""
User management module for Moodle.

Provides functions to list, create, and delete users using Moodle webservice API,
with a fallback to form-based actions if webservice permissions are missing.
"""

import re
import time
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup


class MoodleUserError(Exception):
    """Exception raised for errors in user operations."""


def _create_user_form(
    session: requests.Session,
    base_url: str,
    sesskey: str,
    username: str,
    password: str,
    firstname: str,
    lastname: str,
    email: str,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Creates a user by simulating a POST to the 'Add a new user' form.
    This is used as a fallback when the webservice is not available.
    """
    post_url = f"{base_url}/user/editadvanced.php"

    payload = {
        "id": "-1",
        "course": "1",
        "sesskey": sesskey,
        "_qf__user_editadvanced_form": "1",
        "username": username,
        "auth": "manual",
        "suspended": "0",
        "newpassword": password,
        "preference_auth_forcepasswordchange": "0",
        "firstname": firstname,
        "lastname": lastname,
        "email": email,
        "maildisplay": "2",
        "timezone": "99",
        "lang": "en",
        "description_editor[text]": "",
        "description_editor[format]": "1",
        "submitbutton": "Create user",
        "interests": "_qf__force_multiselect_submission",
    }
    payload.update(kwargs)

    resp = session.post(post_url, data=payload, allow_redirects=False)

    if resp.status_code == 303 and "Location" in resp.headers:
        time.sleep(1)
        user_list_url = f"{base_url}/admin/user.php"
        users_page = session.get(user_list_url)
        soup = BeautifulSoup(users_page.text, "lxml")

        email_cell = soup.find("td", string=email)
        if email_cell and email_cell.parent:
            row = email_cell.parent
            edit_link = row.find("a", href=re.compile(r"editadvanced\.php\?id=\d+"))
            if edit_link:
                match = re.search(r"id=(\d+)", edit_link["href"])
                if match:
                    new_id = int(match.group(1))
                    return {"id": new_id, "username": username}
        return {"id": None, "username": username}

    soup = BeautifulSoup(resp.text, "lxml")
    error_div = soup.find("div", {"data-fieldtype": "error"}) or soup.find(
        "div", class_="error"
    )
    if error_div:
        raise MoodleUserError(f"Form error: {error_div.get_text(strip=True)}")

    raise MoodleUserError(f"Failed to create user via form. Status: {resp.status_code}")


def _delete_user_form(
    session: requests.Session, base_url: str, sesskey: str, user_id: int
) -> bool:
    """
    Deletes a user by simulating the form-based deletion flow, which involves
    clicking a confirmation link from a modal.
    """
    # Step 1: GET the user list page to find the specific delete link for the user.
    user_list_page_url = f"{base_url}/admin/user.php"
    resp_list = session.get(user_list_page_url)
    if resp_list.status_code != 200:
        raise MoodleUserError(
            f"Could not load the user list page. Status: {resp_list.status_code}"
        )

    soup = BeautifulSoup(resp_list.text, "lxml")

    # Step 2: Find the exact delete link. Moodle puts the final URL in a 'data-modal-destination' attribute.
    delete_link = soup.find(
        "a", {"data-modal-destination": re.compile(rf"delete={user_id}")}
    )

    if not delete_link or not delete_link.get("data-modal-destination"):
        raise MoodleUserError(
            f"Could not find a delete confirmation link for user ID {user_id}."
        )

    final_delete_url = delete_link["data-modal-destination"]

    # Step 3: Perform a GET request to the final deletion URL.
    resp_delete = session.get(final_delete_url, allow_redirects=False)

    # A successful deletion redirects (303) back to the user list page.
    if resp_delete.status_code == 303 and "user.php" in resp_delete.headers.get(
        "Location", ""
    ):
        return True

    raise MoodleUserError(
        f"Failed to delete user via form. Final status was {resp_delete.status_code}. Response: {resp_delete.text[:500]}"
    )


def list_course_users(
    session: requests.Session, base_url: str, token: str, course_id: int
) -> List[Dict[str, Any]]:
    """
    List all enrolled users in a specific course.
    """
    url = f"{base_url}/webservice/rest/server.php"
    params = {
        "wstoken": token,
        "wsfunction": "core_enrol_get_enrolled_users",
        "moodlewsrestformat": "json",
        "courseid": course_id,
    }
    resp = session.post(url, data=params)
    if resp.status_code != 200:
        raise MoodleUserError(f"Failed to list users. Status: {resp.status_code}")

    try:
        result = resp.json()
        if isinstance(result, dict) and "exception" in result:
            raise MoodleUserError(result.get("message", "Unknown error"))
        return sorted(result, key=lambda u: u.get("id", 0))
    except (ValueError, KeyError) as e:
        raise MoodleUserError(f"Failed to parse user list: {e}")


def create_user(
    session: requests.Session,
    base_url: str,
    token: str,
    username: str,
    password: str,
    firstname: str,
    lastname: str,
    email: str,
    sesskey: Optional[str] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Create a new user, trying webservice first and falling back to form post.
    """

    # Validate password strength: must include lowercase, uppercase, digit, symbol
    if not (
        re.search(r"[a-z]", password)
        and re.search(r"[A-Z]", password)
        and re.search(r"\d", password)
        and re.search(r"[^\w\s]", password)
    ):
        raise MoodleUserError(
            "Password must contain at least one lowercase letter, one uppercase letter, one number, and one symbol."
        )

    try:
        url = f"{base_url}/webservice/rest/server.php"
        user_data = {
            "username": username,
            "password": password,
            "firstname": firstname,
            "lastname": lastname,
            "email": email,
        }
        user_data.update(kwargs)
        params = {
            "wstoken": token,
            "wsfunction": "core_user_create_users",
            "moodlewsrestformat": "json",
        }
        for i, (key, value) in enumerate(user_data.items()):
            params[f"users[0][{key}]"] = value

        resp = session.post(url, data=params)
        if resp.status_code != 200:
            raise MoodleUserError(f"Failed to create user. Status: {resp.status_code}")

        result = resp.json()
        if isinstance(result, dict) and "exception" in result:
            raise MoodleUserError(f"{result.get('errorcode')}: {result.get('message')}")
        if not isinstance(result, list) or not result:
            raise MoodleUserError("User creation returned no data.")
        return result[0]
    except MoodleUserError as e:
        if "accessexception" in str(e) and sesskey:
            return _create_user_form(
                session,
                base_url,
                sesskey,
                username,
                password,
                firstname,
                lastname,
                email,
                **kwargs,
            )
        else:
            raise e
    except (ValueError, KeyError, requests.RequestException) as e:
        if sesskey:
            return _create_user_form(
                session,
                base_url,
                sesskey,
                username,
                password,
                firstname,
                lastname,
                email,
                **kwargs,
            )
        raise MoodleUserError(f"Failed to parse user creation response: {e}")


def delete_user(
    session: requests.Session,
    base_url: str,
    token: str,
    user_id: int,
    sesskey: Optional[str] = None,
) -> bool:
    """
    Delete a user, trying webservice first and falling back to form post.
    """
    try:
        url = f"{base_url}/webservice/rest/server.php"
        params = {
            "wstoken": token,
            "wsfunction": "core_user_delete_users",
            "moodlewsrestformat": "json",
            "userids[0]": user_id,
        }
        resp = session.post(url, data=params)
        if resp.status_code != 200:
            raise MoodleUserError(f"Failed to delete user. Status: {resp.status_code}")

        if resp.text.strip() == "null" or resp.text.strip() == "":
            return True
        result = resp.json()
        if isinstance(result, dict) and "exception" in result:
            errorcode = result.get("errorcode", "unknown_error")
            message = result.get("message", "Unknown error")
            raise MoodleUserError(f"{errorcode}: {message}")
        return True
    except MoodleUserError as e:
        if "accessexception" in str(e) and sesskey:
            return _delete_user_form(session, base_url, sesskey, user_id)
        else:
            raise e
    except (ValueError, requests.RequestException):
        if sesskey:
            return _delete_user_form(session, base_url, sesskey, user_id)
        return True


__all__ = ["MoodleUserError", "list_course_users", "create_user", "delete_user"]
