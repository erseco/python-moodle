"""Shared timeout defaults for HTTP operations.

``DEFAULT_REQUEST_TIMEOUT`` is the standard timeout for routine Moodle GET/POST
requests. ``DEFAULT_SCRAPE_TIMEOUT`` is shorter for quick HTML fetches used as
fallback probes. Upload helpers use ``(connect_timeout, read_timeout)`` tuples:
``DEFAULT_UPLOAD_TIMEOUT`` for typical uploads and
``DEFAULT_LARGE_UPLOAD_TIMEOUT`` for larger package transfers such as SCORM and
draft-file uploads.
"""

DEFAULT_REQUEST_TIMEOUT = 30
DEFAULT_SCRAPE_TIMEOUT = 15
DEFAULT_UPLOAD_TIMEOUT = (30, 3600)
DEFAULT_LARGE_UPLOAD_TIMEOUT = (300, 3600)

__all__ = [
    "DEFAULT_LARGE_UPLOAD_TIMEOUT",
    "DEFAULT_REQUEST_TIMEOUT",
    "DEFAULT_SCRAPE_TIMEOUT",
    "DEFAULT_UPLOAD_TIMEOUT",
]
