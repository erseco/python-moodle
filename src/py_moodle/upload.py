# src/moodle/upload.py
"""
File uploading module for Moodle CLI using the webservice endpoint.

This method requires a webservice token with 'core_files_upload' capability.
"""
import mimetypes
import os
from pathlib import Path
from typing import Callable, Optional

import requests


class MoodleUploadError(Exception):
    """Exception for webservice upload errors."""


class ProgressTracker:
    """
    A file-like object that tracks the progress of reads and calls a callback.
    This is used to monitor file uploads with a progress bar.
    """

    def __init__(
        self, file_path: str, progress_callback: Optional[Callable[[int], None]] = None
    ):
        self._file = open(file_path, "rb")
        self.size = os.path.getsize(file_path)
        self.read_so_far = 0
        self.callback = progress_callback

    def read(self, size=-1):
        chunk = self._file.read(size)
        if chunk:
            bytes_read = len(chunk)
            self.read_so_far += bytes_read
            if self.callback:
                self.callback(bytes_read)
        return chunk

    def __len__(self):
        return self.size

    def __getattr__(self, attr):
        # Delegate other file-like attributes (e.g., 'name') to the underlying file object
        return getattr(self._file, attr)


def upload_file_webservice(
    base_url: str,
    token: str,
    file_path: str,
    timeout: tuple = (30, 3600),
    progress_callback: Optional[Callable[[int], None]] = None,
) -> int:
    """
    Uploads a file to the user's private draft area using webservice/upload.php
    and returns its draft itemid.

    Args:
        base_url: The base URL of the Moodle instance.
        token: A valid Moodle webservice token.
        file_path: The local path to the file to upload.
        timeout: Request timeout in seconds. default (30, 3600)
            30s to connect, 1h to upload
        progress_callback: Optional function to call with bytes uploaded.

    Returns:
        The integer itemid of the newly created draft area.

    Raises:
        MoodleUploadError: If the upload fails or the response is invalid.
    """
    path = Path(file_path)
    if not path.is_file():
        raise MoodleUploadError(f"File not found at: {file_path}")

    upload_url = f"{base_url}/webservice/upload.php"

    # The webservice payload is simple, only the token in the params
    params = {"token": token, "filearea": "draft"}

    # Use ProgressTracker instead of opening the file directly
    progress_tracker = ProgressTracker(file_path, progress_callback)

    files = {
        "file": (
            path.name,
            progress_tracker,  # Use the tracking object
            mimetypes.guess_type(str(path))[0] or "application/octet-stream",
        )
    }

    try:
        resp = requests.post(upload_url, params=params, files=files, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()

        # The webservice returns an error inside a JSON with status 200
        if isinstance(data, dict) and "exception" in data:
            raise MoodleUploadError(
                f"Moodle API Error: {data.get('message', 'Unknown error')}"
            )

        if not isinstance(data, list) or not data:
            raise MoodleUploadError(f"Unexpected upload response format: {data!r}")

        # The response is a list with a dictionary containing the itemid
        return int(data[0]["itemid"])

    except requests.RequestException as e:
        raise MoodleUploadError(f"HTTP request failed during upload: {e}")
    except (ValueError, KeyError, IndexError) as e:
        raise MoodleUploadError(f"Could not parse itemid from webservice response: {e}")


__all__ = ["MoodleUploadError", "ProgressTracker", "upload_file_webservice"]
