"""A Pythonic CLI and library for Moodle management.

!!! warning
    This project is under active development and may change without notice.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("py-moodle")
except PackageNotFoundError:
    __version__ = "0.0.0"

from .models import (
    Assignment,
    Course,
    CourseModule,
    CourseSection,
    DeleteResult,
    Folder,
    Label,
    ModelValidationError,
    ScormPackage,
    UploadResult,
    User,
)
from .session import MoodleSession, MoodleSessionError
from .settings import Settings, load_settings

__all__ = [
    "Settings",
    "load_settings",
    "MoodleSession",
    "MoodleSessionError",
    "ModelValidationError",
    "Course",
    "CourseSection",
    "CourseModule",
    "User",
    "Folder",
    "Label",
    "Assignment",
    "ScormPackage",
    "UploadResult",
    "DeleteResult",
]
