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

#: Substring (case-insensitive) that identifies an invalid/expired token
#: Moodle exception, distinguishing "try another transport" from a genuine
#: webservice-level failure.
_INVALID_TOKEN_MARKER = "invalid token"


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
            token, indicating the caller should fall back to another
            transport.
        TransportError: If the call fails for any other reason (network
            error, non-token Moodle exception, invalid JSON).
    """
    try:
        return request_webservice(session, base_url, wsfunction, params, token=token)
    except MoodleWebserviceError as exc:
        if _INVALID_TOKEN_MARKER in str(exc).lower():
            raise TransportUnavailableError(str(exc)) from exc
        raise TransportError(str(exc)) from exc
    except MoodleHttpError as exc:
        raise TransportError(str(exc)) from exc


__all__ = ["call"]
