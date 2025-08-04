# src/moodle/category.py
"""
Category management module for Moodle CLI.

Provides functions to list, create, and delete course categories using Moodle webservice API
or AJAX/form posts for greater compatibility.

All code and comments must be in English.
"""

import re
from typing import Any, Dict, List, Optional

import requests


class MoodleCategoryError(Exception):
    """Exception raised for errors in category operations."""


# --- Webservice-based functions (require token) ---


def list_categories(
    session: requests.Session, base_url: str, token: str
) -> List[Dict[str, Any]]:
    """List all course categories.

    Args:
        session: Authenticated requests session.
        base_url: Base URL of the Moodle instance.
        token: Webservice token used for the request.

    Returns:
        List[Dict[str, Any]]: Categories sorted by ID.

    Raises:
        MoodleCategoryError: If the request fails.
    """
    url = f"{base_url}/webservice/rest/server.php"
    params = {
        "wstoken": token,
        "wsfunction": "core_course_get_categories",
        "moodlewsrestformat": "json",
    }
    resp = session.post(url, params=params)
    if resp.status_code != 200:
        raise MoodleCategoryError(
            f"Failed to list categories via webservice. Status: {resp.status_code}"
        )
    try:
        result = resp.json()
        if isinstance(result, dict) and "exception" in result:
            raise MoodleCategoryError(result.get("message", "Unknown error"))
        return sorted(result, key=lambda c: c.get("id", 0))
    except Exception as e:
        raise MoodleCategoryError(f"Failed to parse categories: {e}")


def get_category(
    session: requests.Session, base_url: str, token: str, categoryid: int
) -> Dict[str, Any]:
    """Retrieve a single category by ID using the webservice.

    Args:
        session: Authenticated requests session.
        base_url: Base URL of the Moodle instance.
        token: Webservice token used for the request.
        categoryid: Identifier of the category to fetch.

    Returns:
        Dict[str, Any]: Category information.

    Raises:
        MoodleCategoryError: If the request fails or the category is missing.
    """
    url = f"{base_url}/webservice/rest/server.php"
    params = {
        "wstoken": token,
        "wsfunction": "core_course_get_categories",
        "moodlewsrestformat": "json",
        "criteria[0][key]": "id",
        "criteria[0][value]": str(categoryid),
    }

    resp = session.post(url, params=params)
    if resp.status_code != 200:
        raise MoodleCategoryError(
            f"Failed to get category via webservice. Status: {resp.status_code}"
        )

    try:
        result = resp.json()
        if isinstance(result, dict) and "exception" in result:
            raise MoodleCategoryError(result.get("message", "Unknown error"))
        if not result:
            raise MoodleCategoryError(f"Category id={categoryid} not found")
        return result[0]
    except Exception as e:
        raise MoodleCategoryError(f"Failed to parse category: {e}")


# --- AJAX / Form Post based functions (require sesskey) ---


def create_category_form(
    session: requests.Session,
    base_url: str,
    sesskey: str,
    name: str,
    parent: int = 0,
    description: str = "",
) -> Dict[str, Any]:
    """Create a new course category using the form endpoint.

    This method mimics a browser interaction and does not require webservice permissions.

    Args:
        session: Authenticated requests session.
        base_url: Base URL of the Moodle instance.
        sesskey: Session key for form submissions.
        name: Name of the category to create.
        parent: ID of the parent category.
        description: Optional HTML description.

    Returns:
        Dict[str, Any]: Newly created category data.

    Raises:
        MoodleCategoryError: If the category cannot be created.
    """
    # Step 1: GET the form page to retrieve dynamic parameters like the itemid for the editor.
    edit_url = f"{base_url}/course/editcategory.php?parent={parent}"
    try:
        get_resp = session.get(edit_url)
        get_resp.raise_for_status()
        form_html = get_resp.text
    except requests.RequestException as e:
        raise MoodleCategoryError(f"Failed to load the category creation form: {e}")

    # Step 2: Extract required dynamic values from the form's HTML.
    # The itemid is crucial for forms with rich text editors.
    itemid_match = re.search(
        r'name="description_editor\[itemid\]"\s+value="(\d+)"', form_html
    )
    if not itemid_match:
        raise MoodleCategoryError(
            "Could not find description_editor[itemid] on the form. The form structure might have changed."
        )
    description_itemid = itemid_match.group(1)

    # Use the sesskey from the form for maximum compatibility, although the passed one should work.
    form_sesskey_match = re.search(r'name="sesskey"\s+value="([^"]+)"', form_html)
    form_sesskey = form_sesskey_match.group(1) if form_sesskey_match else sesskey

    # Step 3: Build the payload exactly as seen in the HAR file.
    post_url = f"{base_url}/course/editcategory.php"  # POST URL has no query parameters
    payload = {
        "id": "0",
        "sesskey": form_sesskey,
        "_qf__core_course_editcategory_form": "1",  # This is a Moodle form identifier.
        "parent": str(parent),
        "name": name,
        "idnumber": "",
        "description_editor[text]": f"<p>{description or f'Category created via script: {name}'}</p>",
        "description_editor[format]": "1",  # 1 = HTML format
        "description_editor[itemid]": description_itemid,  # The dynamic ID we just extracted.
        "submitbutton": "Create category",  # The name of the submit button is 'submitbutton'.
    }

    # Step 4: POST the data and check for a redirect.
    resp = session.post(post_url, data=payload, allow_redirects=False)

    if resp.status_code == 303 and "Location" in resp.headers:
        location = resp.headers["Location"]
        # The redirect URL contains the ID of the new category.
        match = re.search(r"categoryid=(\d+)", location)
        if match:
            new_id = int(match.group(1))
            return {"id": new_id, "name": name, "parent": parent}
        else:
            raise MoodleCategoryError(
                f"Category created, but could not extract new ID from redirect: {location}"
            )
    else:
        # If we get a 200 OK, it means the form was re-rendered due to an error.
        if "A category with the same name already exists" in resp.text:
            raise MoodleCategoryError(
                f"A category with the name '{name}' already exists in this parent category."
            )
        error_details = (
            f"Failed to create category via form. Status: {resp.status_code}."
        )
        error_details += f" Response: {resp.text[:500]}"
        raise MoodleCategoryError(error_details)


def delete_category_form(
    session: requests.Session, base_url: str, sesskey: str, categoryid: int
) -> bool:
    """Delete a category by mimicking the browser flow.

    Uses ``course/management.php`` and does not require webservice permissions.

    Args:
        session: Authenticated requests session.
        base_url: Base URL of the Moodle instance.
        sesskey: Session key for form submissions.
        categoryid: ID of the category to delete.

    Returns:
        bool: ``True`` if the deletion appears successful.

    Raises:
        MoodleCategoryError: If the deletion fails.
    """
    # Step 1: GET the confirmation page, which is now part of management.php.
    # The URL is derived from the 'Referer' in the HAR file.
    confirm_get_url = f"{base_url}/course/management.php?categoryid={categoryid}&action=deletecategory&sesskey={sesskey}"
    try:
        get_resp = session.get(confirm_get_url)
        get_resp.raise_for_status()
        confirm_html = get_resp.text
    except requests.RequestException as e:
        raise MoodleCategoryError(
            f"Failed to load the category deletion confirmation page: {e}"
        )

    if "You cannot delete this category" in confirm_html:
        raise MoodleCategoryError(
            f"Cannot delete category {categoryid}, it might not be empty or is a default category."
        )

    # Step 2: Extract the most recent sesskey from the confirmation form.
    form_sesskey_match = re.search(r'name="sesskey"\s+value="([^"]+)"', confirm_html)
    form_sesskey = form_sesskey_match.group(1) if form_sesskey_match else sesskey

    # Step 3: Build the payload to POST to management.php, based on the HAR.
    post_url = f"{base_url}/course/management.php"
    payload = {
        "categoryid": str(categoryid),
        "action": "deletecategory",
        "sesskey": form_sesskey,
        "_qf__core_course_deletecategory_form": "1",  # Form identifier
        "mform_isexpanded_id_general": "1",  # UI state field
        "submitbutton": "Delete",  # Name of the submit button
    }

    # Step 4: POST the form and check for success.
    # The HAR shows a 200 OK with a success message, not a 303 redirect.
    resp = session.post(post_url, data=payload, allow_redirects=False)

    # A 200 OK with the success message is the new success indicator.
    # We keep the 303 check for backward compatibility or alternative Moodle configurations.
    if (
        resp.status_code == 200 and "Deleted course category" in resp.text
    ) or resp.status_code == 303:
        return True
    else:
        # Provide a detailed error message if it fails.
        raise MoodleCategoryError(
            f"Failed to delete category {categoryid}. Status: {resp.status_code}. Response: {resp.text[:500]}"
        )


# --- Facade functions that choose the method ---


def create_category(
    session: requests.Session,
    base_url: str,
    name: str,
    parent: int = 0,
    token: Optional[str] = None,
    sesskey: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a category using form post or webservice.

    Args:
        session: Authenticated requests session.
        base_url: Base URL of the Moodle instance.
        name: Name of the category.
        parent: ID of the parent category.
        token: Webservice token (optional).
        sesskey: Session key (optional).

    Returns:
        Dict[str, Any]: Created category data.

    Raises:
        ValueError: If neither ``sesskey`` nor ``token`` is provided.
    """
    if sesskey:
        return create_category_form(session, base_url, sesskey, name, parent)
    elif token:
        # Keep the webservice option just in case
        return session.post(
            f"{base_url}/webservice/rest/server.php",
            params={
                "wstoken": token,
                "wsfunction": "core_course_create_categories",
                "moodlewsrestformat": "json",
                "categories[0][name]": name,
                "categories[0][parent]": parent,
            },
        ).json()[0]
    raise ValueError("Either sesskey or token must be provided to create a category.")


def delete_category(
    session: requests.Session,
    base_url: str,
    categoryid: int,
    token: Optional[str] = None,
    sesskey: Optional[str] = None,
) -> bool:
    """Delete a category using form post or webservice.

    Args:
        session: Authenticated requests session.
        base_url: Base URL of the Moodle instance.
        categoryid: ID of the category to delete.
        token: Webservice token (optional).
        sesskey: Session key (optional).

    Returns:
        bool: ``True`` if the deletion appears successful.

    Raises:
        ValueError: If neither ``sesskey`` nor ``token`` is provided.
    """
    if sesskey:
        return delete_category_form(session, base_url, sesskey, categoryid)
    elif token:
        resp = session.post(
            f"{base_url}/webservice/rest/server.php",
            params={
                "wstoken": token,
                "wsfunction": "core_course_delete_categories",
                "moodlewsrestformat": "json",
                "categories[0][id]": categoryid,
            },
        )
        return resp.status_code == 200 and "exception" not in resp.text
    raise ValueError("Either sesskey or token must be provided to delete a category.")


__all__ = [
    "MoodleCategoryError",
    "list_categories",
    "get_category",
    "create_category_form",
    "delete_category_form",
    "create_category",
    "delete_category",
]
