"""Webservice (REST API) transport strategy for talking to Moodle.

Calls ``{base_url}/webservice/rest/server.php`` with a ``wstoken``,
delegating the actual socket-level request to the shared HTTP client in
:mod:`py_moodle.http`.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import requests

from ..http import MoodleHttpError, MoodleWebserviceError, request_webservice
from . import TransportError, TransportUnavailableError

#: Substrings (case-insensitive) identifying a Moodle webservice failure
#: that means "this call path isn't usable right now, try another
#: transport" rather than a genuine webservice-level failure worth
#: surfacing immediately:
#:   - an invalid/expired token;
#:   - a webservice-side context-validation failure (observed in practice
#:     as "You cannot execute functions in the course context (course
#:     id:N). ... Context does not exist"), e.g. when the target course's
#:     context is momentarily stale relative to the calling user's cached
#:     session state. The AJAX transport re-derives context from the
#:     current page/session instead of a cached webservice-side lookup,
#:     so it is not subject to the same failure.
_TRANSPORT_UNAVAILABLE_MARKERS = (
    "invalid token",
    "cannot execute functions in the course context",
)


def call(
    session: requests.Session,
    base_url: str,
    wsfunction: str,
    token: str,
    params: Optional[Dict[str, Any]] = None,
) -> Any:
    """Call a Moodle webservice function via the REST API.

    Args:
        session: Authenticated requests session.
        base_url: Base URL of the Moodle instance.
        wsfunction: Name of the webservice function to invoke.
        token: Webservice token (``wstoken``).
        params: Additional parameters for the webservice call.

    Returns:
        Any: The parsed JSON response (list or dict) on success.

    Raises:
        TransportUnavailableError: If Moodle reports an invalid/expired
            token, or a context-validation failure, indicating the caller
            should fall back to another transport (see
            :data:`_TRANSPORT_UNAVAILABLE_MARKERS`).
        TransportError: If the call fails for any other reason (network
            error, non-token/context Moodle exception, invalid JSON).
    """
    try:
        return request_webservice(session, base_url, wsfunction, params, token=token)
    except MoodleWebserviceError as exc:
        message = str(exc).lower()
        if any(marker in message for marker in _TRANSPORT_UNAVAILABLE_MARKERS):
            raise TransportUnavailableError(str(exc)) from exc
        raise TransportError(str(exc)) from exc
    except MoodleHttpError as exc:
        raise TransportError(str(exc)) from exc


__all__ = ["call"]
