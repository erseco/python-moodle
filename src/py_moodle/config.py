"""Shared timeout defaults for HTTP operations.

Attributes:
    DEFAULT_REQUEST_TIMEOUT: Standard timeout in seconds for routine Moodle
        GET and POST requests.
    DEFAULT_SCRAPE_TIMEOUT: Shorter timeout in seconds for quick HTML fetches
        used as fallback probes.
    DEFAULT_UPLOAD_TIMEOUT: Tuple of ``(connect_timeout, read_timeout)`` used
        for typical webservice uploads.
    DEFAULT_LARGE_UPLOAD_TIMEOUT: Tuple of ``(connect_timeout, read_timeout)``
        used for larger package transfers such as SCORM and draft uploads.
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
