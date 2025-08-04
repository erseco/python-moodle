# src/moodle/assign.py
"""Assignment management module for ``py-moodle``."""

import random
import time
from datetime import datetime, timedelta
from typing import Any

import requests

from .module import MoodleModuleError, add_generic_module

# Constants for the 'assign' module
MODULE_NAME = "assign"


class MoodleAssignError(Exception):
    """Exception raised for errors in assign operations."""


def add_assign(
    session: requests.Session,
    base_url: str,
    sesskey: str,
    course_id: int,
    section_id: int,
    name: str,
    intro: str = "",
    # Optional arguments can be added here for more control
    **kwargs: Any,
) -> int:
    """
    Creates a new assign with sensible defaults, similar to add_label.

    Args:
        session: Authenticated requests.Session object.
        base_url: Base URL of the Moodle instance.
        sesskey: Session key for form submissions.
        course_id: The ID of the course to add the assign to.
        section_id: The ID of the section to add the assign to.
        name: The name of the assignment.
        intro: The introduction/description displayed on the course page.
        **kwargs: Optional overrides for advanced assign settings.
                  Examples: max_grade=50, due_date=datetime(...), etc.

    Returns:
        The new course module ID (cmid) of the created assign.
    """
    # --- Set Sensible Defaults ---
    now = datetime.now()
    defaults = {
        "activity_instructions": "",
        "visible": 1,
        "max_grade": 100,
        "allow_submissions_from_date": now,
        "due_date": now + timedelta(days=7),
        "grading_due_date": now + timedelta(days=14),
    }
    # User-provided kwargs will override the defaults
    settings = {**defaults, **kwargs}

    # Generate temporary itemids for the rich text editors
    itemid_base = int(time.time() * 1000)

    # --- Build the specific payload for the 'assign' module ---
    specific_payload = {
        "_qf__mod_assign_mod_form": "1",
        "name": name,
        "introeditor[text]": f"<p>{intro}</p>",
        "introeditor[format]": "1",
        "introeditor[itemid]": str(itemid_base + random.randint(100, 200)),
        "activityeditor[text]": f"<p>{settings['activity_instructions']}</p>",
        "activityeditor[format]": "1",
        "activityeditor[itemid]": str(itemid_base + random.randint(300, 400)),
        "introattachments": str(itemid_base + random.randint(500, 600)),
        # Availability Dates
        "allowsubmissionsfromdate[enabled]": "1",
        "allowsubmissionsfromdate[day]": str(
            settings["allow_submissions_from_date"].day
        ),
        "allowsubmissionsfromdate[month]": str(
            settings["allow_submissions_from_date"].month
        ),
        "allowsubmissionsfromdate[year]": str(
            settings["allow_submissions_from_date"].year
        ),
        "allowsubmissionsfromdate[hour]": "0",
        "allowsubmissionsfromdate[minute]": "0",
        "duedate[enabled]": "1",
        "duedate[day]": str(settings["due_date"].day),
        "duedate[month]": str(settings["due_date"].month),
        "duedate[year]": str(settings["due_date"].year),
        "duedate[hour]": "0",
        "duedate[minute]": "0",
        "gradingduedate[enabled]": "1",
        "gradingduedate[day]": str(settings["grading_due_date"].day),
        "gradingduedate[month]": str(settings["grading_due_date"].month),
        "gradingduedate[year]": str(settings["grading_due_date"].year),
        "gradingduedate[hour]": "0",
        "gradingduedate[minute]": "0",
        # Other settings from HAR with default values
        "alwaysshowdescription": "1",
        "assignsubmission_file_enabled": "1",
        "assignsubmission_comments_enabled": "1",
        "assignfeedback_comments_enabled": "1",
        "grade[modgrade_type]": "point",
        "grade[modgrade_point]": str(settings["max_grade"]),
        "visible": str(settings["visible"]),
        "submitbutton": "Save and display",
    }

    # --- Call the generic module creation function ---
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
        raise MoodleAssignError(f"Failed to add assign: {e}")


__all__ = ["MoodleAssignError", "add_assign"]
