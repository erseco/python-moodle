"""Internal AJAX endpoint transport strategy for talking to Moodle.

Calls ``{base_url}/lib/ajax/service.php?sesskey=...`` with the
``[{"index": 0, "methodname": ..., "args": ...}]`` envelope Moodle expects,
delegating the actual socket-level requests to the shared HTTP client in
:mod:`py_moodle.http`.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import requests

from ..http import MoodleHttpError, request_ajax, request_html_get
from . import TransportError, TransportUnavailableError


def call(
    session: requests.Session,
    base_url: str,
    methodname: str,
    sesskey: str,
    args: Optional[Dict[str, Any]] = None,
) -> Any:
    """Call a Moodle method via the internal AJAX endpoint.

    Args:
        session: Authenticated requests session.
        base_url: Base URL of the Moodle instance.
        methodname: Name of the AJAX method to invoke (as used in
            ``lib/ajax/service.php``).
        sesskey: Moodle session key required by the AJAX endpoint.
        args: Additional method arguments.

    Returns:
        Any: The parsed ``data`` payload from the first entry of the AJAX
            JSON-array response, on success.

    Raises:
        TransportUnavailableError: If no usable ``sesskey`` is supplied.
        TransportError: If the HTTP call fails, or Moodle's AJAX response
            reports an error for the requested method.
    """
    if not sesskey:
        raise TransportUnavailableError("AJAX transport requires a valid sesskey.")

    # Refresh the session before the AJAX call to prevent "session expired"
    # errors that have been observed against real Moodle instances.
    try:
        request_html_get(session, f"{base_url}/my/")
    except MoodleHttpError as exc:
        raise TransportError(str(exc)) from exc

    url = f"{base_url}/lib/ajax/service.php?sesskey={sesskey}"
    payload = [{"index": 0, "methodname": methodname, "args": args or {}}]
    try:
        result = request_ajax(session, url, payload)
        return result[0]["data"]
    except MoodleHttpError as exc:
        raise TransportError(str(exc)) from exc


__all__ = ["call"]
