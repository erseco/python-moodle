"""Centralized HTTP request handling for talking to Moodle.

This module is the single place responsible for:

- Applying the shared timeout policy from :mod:`py_moodle.config` by
  default, with an optional override for callers that need it.
- Retrying safe, idempotent GET-style requests with a small, bounded
  backoff on transient network errors (``ConnectionError``/``Timeout``),
  while *never* retrying POST/mutating requests automatically.
- Raising typed, normalized exceptions (:class:`MoodleHttpError`,
  :class:`MoodleTimeoutError`, :class:`MoodleWebserviceError`) instead of
  letting raw ``requests`` exceptions or ``json.JSONDecodeError`` escape.
- Parsing Moodle webservice error payloads (``exception``/``errorcode``/
  ``message``) into a typed exception with those fields accessible.
- Redacting known secret-shaped values (webservice token, ``sesskey``,
  password, cookies, ``Authorization`` header) from the URL, params,
  headers, and response body text used to build any exception message, so
  secrets never appear in ``str()``/``repr()`` of a raised exception.

Only a handful of call sites are migrated onto this module so far:
``session.py``'s ``MoodleSession.call()`` and ``course.py``'s
``list_courses()``/``create_course()``. The remaining modules that call
``session.get``/``session.post``/``requests.post`` directly are left
untouched and are tracked as follow-up work; new call sites should prefer
the helpers in this module.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, List, Mapping, Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests

from .config import (
    DEFAULT_REQUEST_TIMEOUT,
    DEFAULT_SCRAPE_TIMEOUT,
    DEFAULT_UPLOAD_TIMEOUT,
)

#: Marker substituted for any redacted secret value.
REDACTED = "***REDACTED***"

#: Maximum length of a response-body snippet kept in an exception message.
_TRUNCATE_LENGTH = 500

#: Keys (case-insensitive) treated as secret-shaped wherever they appear:
#: in query params, form/JSON data, or request headers.
_SECRET_KEYS = {
    "wstoken",
    "token",
    "sesskey",
    "password",
    "pass",
    "pwd",
    "authorization",
    "cookie",
    "set-cookie",
}

#: Total number of attempts made for retryable (GET-style) requests.
_RETRY_ATTEMPTS = 3

#: Base backoff delay, in seconds, multiplied by the attempt number.
_RETRY_BACKOFF_BASE_SECONDS = 0.01

#: Logger for redacted HTTP-flow tracing. It is a child of the shared
#: ``py_moodle`` logger, so the CLI ``--debug`` flag (which raises that
#: logger to ``DEBUG``) surfaces these traces on stderr, and library users
#: can enable them with ``logging.getLogger("py_moodle").setLevel(DEBUG)``.
#: Only the request method, the *redacted* URL, and the response status are
#: ever logged -- never params, form/JSON bodies, headers, or response text.
_logger = logging.getLogger("py_moodle.http")


class MoodleHttpError(Exception):
    """Base exception for HTTP-layer failures talking to Moodle.

    Attributes:
        status_code: HTTP status code of the failing response, if any.
        url: Redacted URL involved in the failing request, if known.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: Optional[int] = None,
        url: Optional[str] = None,
    ) -> None:
        """Initialize the error from an already-redacted message.

        Args:
            message: Human-readable, already-redacted error message.
            status_code: HTTP status code of the failing response, if any.
            url: Redacted URL involved in the failing request, if known.
        """
        super().__init__(message)
        self.status_code = status_code
        self.url = url


class MoodleTimeoutError(MoodleHttpError):
    """Raised when a request times out or fails to connect after retries."""


class MoodleWebserviceError(MoodleHttpError):
    """Raised when Moodle returns a webservice-shaped error payload.

    Attributes:
        errorcode: Moodle ``errorcode`` value from the failed response.
        moodle_exception: Moodle ``exception`` class name from the failed
            response (e.g. ``"invalid_parameter_exception"``).
    """

    def __init__(
        self,
        message: str,
        *,
        errorcode: Optional[str] = None,
        moodle_exception: Optional[str] = None,
        status_code: Optional[int] = None,
        url: Optional[str] = None,
    ) -> None:
        """Initialize the error with Moodle's error payload fields.

        Args:
            message: Human-readable, already-redacted error message.
            errorcode: Moodle ``errorcode`` value from the failed response.
            moodle_exception: Moodle ``exception`` class name from the
                failed response.
            status_code: HTTP status code of the failing response, if any.
            url: Redacted URL involved in the failing request, if known.
        """
        super().__init__(message, status_code=status_code, url=url)
        self.errorcode = errorcode
        self.moodle_exception = moodle_exception


# ---------------------------------------------------------------------------
# Redaction helpers
# ---------------------------------------------------------------------------


def _is_secret_key(key: Any) -> bool:
    """Return whether a param/header key is treated as secret-shaped."""
    return str(key).lower() in _SECRET_KEYS


def _collect_secrets(
    *,
    url: Optional[str] = None,
    params: Optional[Mapping[str, Any]] = None,
    headers: Optional[Mapping[str, Any]] = None,
    data: Optional[Any] = None,
) -> List[str]:
    """Collect literal secret values from a URL, params, headers, and body.

    Args:
        url: Request URL, whose query string may embed secrets.
        params: Query/form parameters that may contain secret values.
        headers: Request headers that may contain secret values.
        data: Form body, either a mapping or an already-urlencoded string,
            that may contain secret values.

    Returns:
        List[str]: Literal secret values found, for text scrubbing.
    """
    secrets: List[str] = []
    if url and "?" in url:
        query = urlsplit(url).query
        for key, value in parse_qsl(query, keep_blank_values=True):
            if _is_secret_key(key) and value:
                secrets.append(value)
    for source in (params, headers):
        if not source:
            continue
        for key, value in source.items():
            if _is_secret_key(key) and value:
                secrets.append(str(value))
    if data:
        if isinstance(data, Mapping):
            for key, value in data.items():
                if _is_secret_key(key) and value:
                    secrets.append(str(value))
        elif isinstance(data, str):
            for key, value in parse_qsl(data, keep_blank_values=True):
                if _is_secret_key(key) and value:
                    secrets.append(value)
    return secrets


def _redact_url(url: Optional[str]) -> Optional[str]:
    """Redact known secret query-string parameters embedded in a URL."""
    if not url or "?" not in url:
        return url
    parsed = urlsplit(url)
    if not parsed.query:
        return url
    pairs = parse_qsl(parsed.query, keep_blank_values=True)
    redacted_pairs = [
        (key, REDACTED if _is_secret_key(key) else value) for key, value in pairs
    ]
    return urlunsplit(parsed._replace(query=urlencode(redacted_pairs)))


def _redact_text(text: Optional[str], secrets: List[str]) -> Optional[str]:
    """Replace any literal secret value found in text with the marker."""
    if not text:
        return text
    redacted = text
    for secret in secrets:
        if secret:
            redacted = redacted.replace(secret, REDACTED)
    return redacted


def _truncate(text: Optional[str], length: int = _TRUNCATE_LENGTH) -> str:
    """Truncate a response body snippet for inclusion in an error message."""
    if not text:
        return ""
    if len(text) <= length:
        return text
    return text[:length] + "...(truncated)"


# ---------------------------------------------------------------------------
# Low-level request execution
# ---------------------------------------------------------------------------


def _send_request(
    session: Any,
    method: str,
    url: str,
    *,
    timeout: Any,
    retryable: bool,
    headers: Optional[Dict[str, Any]] = None,
    **kwargs: Any,
) -> Any:
    """Send a single HTTP request through ``session`` with policy applied.

    Args:
        session: A ``requests.Session``-like object (or the ``requests``
            module itself) exposing ``get``/``post`` callables.
        method: Either ``"get"`` or ``"post"``.
        url: Absolute URL to request.
        timeout: Timeout value/tuple forwarded to the underlying call.
        retryable: Whether transient connection/timeout errors should be
            retried with backoff. This must only ever be ``True`` for
            safe, idempotent GET-style requests; POST/mutating requests
            must always pass ``False`` so a non-idempotent Moodle mutation
            is never automatically duplicated.
        headers: Optional request headers.
        **kwargs: Additional keyword arguments forwarded to the
            underlying session call (e.g. ``params``, ``data``, ``json``).

    Returns:
        The response object returned by the underlying session call.

    Raises:
        MoodleTimeoutError: If the request times out, after retries are
            exhausted for retryable requests.
        MoodleHttpError: If a connection error occurs, after retries are
            exhausted for retryable requests.
    """
    call = getattr(session, method)
    request_kwargs: Dict[str, Any] = {"timeout": timeout, "headers": headers}
    request_kwargs.update(kwargs)

    secrets = _collect_secrets(url=url, params=kwargs.get("params"), headers=headers)
    redacted_url = _redact_url(url)
    method_label = method.upper()
    attempts = _RETRY_ATTEMPTS if retryable else 1
    last_error_kind: Optional[str] = None

    for attempt in range(1, attempts + 1):
        if attempt == 1:
            _logger.debug("HTTP %s %s", method_label, redacted_url)
        else:
            _logger.debug(
                "HTTP %s %s (retry %d/%d after %s error)",
                method_label,
                redacted_url,
                attempt,
                attempts,
                last_error_kind,
            )
        try:
            response = call(url, **request_kwargs)
            _logger.debug(
                "HTTP %s %s -> %s",
                method_label,
                redacted_url,
                getattr(response, "status_code", "?"),
            )
            return response
        except requests.exceptions.Timeout:
            last_error_kind = "timeout"
        except requests.exceptions.ConnectionError:
            last_error_kind = "connection"
        if attempt < attempts:
            time.sleep(_RETRY_BACKOFF_BASE_SECONDS * attempt)

    _logger.debug(
        "HTTP %s %s failed after %d attempt(s): %s error",
        method_label,
        redacted_url,
        attempts,
        last_error_kind,
    )
    message = _redact_text(
        f"Request to {redacted_url} failed after {attempts} attempt(s) "
        f"due to a {last_error_kind} error.",
        secrets,
    )
    if last_error_kind == "timeout":
        raise MoodleTimeoutError(message, url=redacted_url)
    raise MoodleHttpError(message, url=redacted_url)


def _raise_for_status(
    response: Any,
    *,
    url: Optional[str] = None,
    params: Optional[Mapping[str, Any]] = None,
    headers: Optional[Mapping[str, Any]] = None,
    data: Optional[Any] = None,
) -> None:
    """Raise ``MoodleHttpError`` for a 4xx/5xx response.

    Args:
        response: Response object with a ``status_code`` attribute.
        url: Request URL, used to build a redacted message.
        params: Request params, scanned for secret values to scrub.
        headers: Request headers, scanned for secret values to scrub.
        data: Request form body, scanned for secret values to scrub.

    Raises:
        MoodleHttpError: If the response's status code is 4xx/5xx.
    """
    status_code = getattr(response, "status_code", None)
    if status_code is None or status_code < 400:
        return
    secrets = _collect_secrets(url=url, params=params, headers=headers, data=data)
    body_snippet = _redact_text(_truncate(getattr(response, "text", "")), secrets)
    redacted_url = _redact_url(url)
    message = _redact_text(
        f"Moodle HTTP request to {redacted_url} failed with status "
        f"{status_code}: {body_snippet}",
        secrets,
    )
    raise MoodleHttpError(message, status_code=status_code, url=redacted_url)


def _parse_json(
    response: Any,
    *,
    url: Optional[str] = None,
    params: Optional[Mapping[str, Any]] = None,
    headers: Optional[Mapping[str, Any]] = None,
) -> Any:
    """Parse a JSON response body, raising typed exceptions on failure.

    Args:
        response: Response object exposing ``.json()`` and ``.text``.
        url: Request URL, used to build a redacted message.
        params: Request params, scanned for secret values to scrub.
        headers: Request headers, scanned for secret values to scrub.

    Returns:
        Any: The parsed JSON payload when it is not a Moodle error shape.

    Raises:
        MoodleHttpError: If the body is not valid JSON.
        MoodleWebserviceError: If the body has the Moodle webservice error
            shape (``exception``/``errorcode``/``message``).
    """
    secrets = _collect_secrets(url=url, params=params, headers=headers)
    status_code = getattr(response, "status_code", None)
    redacted_url = _redact_url(url)
    try:
        data = response.json()
    except (ValueError, json.JSONDecodeError) as exc:
        body_snippet = _redact_text(_truncate(getattr(response, "text", "")), secrets)
        message = _redact_text(
            f"Moodle response from {redacted_url} was not valid JSON: "
            f"{body_snippet}",
            secrets,
        )
        raise MoodleHttpError(
            message, status_code=status_code, url=redacted_url
        ) from exc

    if isinstance(data, dict) and ("exception" in data or "errorcode" in data):
        message = _redact_text(
            str(data.get("message", "Unknown Moodle error")), secrets
        )
        raise MoodleWebserviceError(
            message,
            errorcode=data.get("errorcode"),
            moodle_exception=data.get("exception"),
            status_code=status_code,
            url=redacted_url,
        )
    return data


# ---------------------------------------------------------------------------
# Public request helpers
# ---------------------------------------------------------------------------


def request_webservice(
    session: Any,
    base_url: str,
    wsfunction: str,
    params: Optional[Dict[str, Any]] = None,
    *,
    token: Optional[str] = None,
    timeout: Optional[Any] = None,
    method: str = "post",
) -> Any:
    """Call a Moodle webservice REST function and return its parsed payload.

    Args:
        session: Authenticated ``requests.Session``-like object.
        base_url: Base URL of the Moodle instance.
        wsfunction: Name of the Moodle webservice function to call.
        params: Additional parameters for the webservice call.
        token: Webservice token, sent as ``wstoken``.
        timeout: Optional timeout override; defaults to
            ``DEFAULT_REQUEST_TIMEOUT``.
        method: HTTP method to use: ``"post"`` (default, never retried,
            appropriate for most Moodle webservice calls) or ``"get"``
            (retried with backoff on transient network errors; only use
            for calls that are safe and idempotent).

    Returns:
        Any: Parsed JSON payload (typically a ``dict`` or ``list``).

    Raises:
        MoodleHttpError: On network failures or non-2xx status codes.
        MoodleTimeoutError: On repeated timeouts for GET-style calls.
        MoodleWebserviceError: When Moodle returns an error payload.
    """
    url = f"{base_url}/webservice/rest/server.php"
    request_params: Dict[str, Any] = {
        "moodlewsrestformat": "json",
        "wsfunction": wsfunction,
    }
    if token is not None:
        request_params["wstoken"] = token
    request_params.update(params or {})

    effective_timeout = timeout if timeout is not None else DEFAULT_REQUEST_TIMEOUT
    response = _send_request(
        session,
        method,
        url,
        timeout=effective_timeout,
        retryable=(method == "get"),
        params=request_params,
    )
    _raise_for_status(response, url=url, params=request_params)
    return _parse_json(response, url=url, params=request_params)


def request_html_get(
    session: Any,
    url: str,
    *,
    timeout: Optional[Any] = None,
    headers: Optional[Dict[str, str]] = None,
) -> Any:
    """Perform a safe, retryable GET request and return the raw response.

    Args:
        session: Authenticated ``requests.Session``-like object.
        url: Absolute URL to fetch.
        timeout: Optional timeout override; defaults to
            ``DEFAULT_SCRAPE_TIMEOUT``.
        headers: Optional request headers.

    Returns:
        The response object returned by the underlying session's ``get``.

    Raises:
        MoodleHttpError: On non-2xx status codes.
        MoodleTimeoutError: On repeated timeouts after retries.
    """
    effective_timeout = timeout if timeout is not None else DEFAULT_SCRAPE_TIMEOUT
    response = _send_request(
        session,
        "get",
        url,
        timeout=effective_timeout,
        retryable=True,
        headers=headers,
    )
    _raise_for_status(response, url=url, headers=headers)
    return response


def request_form_post(
    session: Any,
    url: str,
    *,
    data: Optional[Any] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: Optional[Any] = None,
    allow_redirects: bool = True,
    raise_for_status: bool = True,
) -> Any:
    """Perform a mutating form POST request; never retried automatically.

    Args:
        session: Authenticated ``requests.Session``-like object.
        url: Absolute URL to post to.
        data: Form-encoded body (dict or already-encoded string).
        headers: Optional request headers.
        timeout: Optional timeout override; defaults to
            ``DEFAULT_REQUEST_TIMEOUT``.
        allow_redirects: Whether to follow redirects (forwarded as-is).
        raise_for_status: Whether to raise ``MoodleHttpError`` for a
            4xx/5xx response. Callers that need to inspect Moodle's
            redirect/form-re-render behavior themselves can pass
            ``False`` and handle the raw response's status code.

    Returns:
        The response object returned by the underlying session's ``post``.

    Raises:
        MoodleHttpError: On network failures (never retried), or on a
            4xx/5xx status code when ``raise_for_status`` is ``True``.
    """
    effective_timeout = timeout if timeout is not None else DEFAULT_REQUEST_TIMEOUT
    response = _send_request(
        session,
        "post",
        url,
        timeout=effective_timeout,
        retryable=False,
        data=data,
        headers=headers,
        allow_redirects=allow_redirects,
    )
    if raise_for_status:
        _raise_for_status(response, url=url, headers=headers, data=data)
    return response


def request_ajax(
    session: Any,
    url: str,
    payload: Any,
    *,
    headers: Optional[Dict[str, str]] = None,
    timeout: Optional[Any] = None,
) -> Any:
    """Perform a Moodle ``lib/ajax/service.php`` call and parse its response.

    Args:
        session: Authenticated ``requests.Session``-like object.
        url: Absolute AJAX endpoint URL (typically including ``sesskey``).
        payload: JSON-serializable list of AJAX method-call descriptors.
        headers: Optional request headers; defaults to
            ``{"Content-Type": "application/json"}``.
        timeout: Optional timeout override; defaults to
            ``DEFAULT_REQUEST_TIMEOUT``.

    Returns:
        Any: Parsed JSON payload (typically a list of AJAX response
        entries).

    Raises:
        MoodleHttpError: On network failures, non-2xx status codes, a
            non-JSON body, or an AJAX error entry in the response. Never
            retried, since AJAX calls may be mutating.
    """
    effective_timeout = timeout if timeout is not None else DEFAULT_REQUEST_TIMEOUT
    effective_headers = headers or {"Content-Type": "application/json"}
    response = _send_request(
        session,
        "post",
        url,
        timeout=effective_timeout,
        retryable=False,
        json=payload,
        headers=effective_headers,
    )
    _raise_for_status(response, url=url, headers=effective_headers)
    data = _parse_json(response, url=url, headers=effective_headers)

    if (
        isinstance(data, list)
        and data
        and isinstance(data[0], dict)
        and data[0].get("error")
    ):
        secrets = _collect_secrets(url=url, headers=effective_headers)
        exception_payload = data[0].get("exception")
        if isinstance(exception_payload, dict):
            message = exception_payload.get("message", "Unknown AJAX error")
        else:
            message = (
                str(exception_payload) if exception_payload else ("Unknown AJAX error")
            )
        raise MoodleHttpError(_redact_text(str(message), secrets), url=_redact_url(url))
    return data


def upload_file(
    url: str,
    *,
    params: Optional[Dict[str, Any]] = None,
    files: Optional[Dict[str, Any]] = None,
    timeout: Optional[Any] = None,
) -> Any:
    """Upload a file via a direct, session-less POST request.

    Mirrors the pattern used by Moodle's webservice file-upload endpoint,
    which authenticates via a token query parameter rather than session
    cookies. Never retried, since uploads are mutating requests.

    Args:
        url: Absolute upload endpoint URL.
        params: Query parameters (e.g. ``{"token": ..., "filearea": ...}``).
        files: ``requests``-style ``files`` mapping for multipart upload.
        timeout: Optional timeout override; defaults to
            ``DEFAULT_UPLOAD_TIMEOUT``.

    Returns:
        The raw response returned by ``requests.post``.

    Raises:
        MoodleHttpError: On network failures or non-2xx status codes.
    """
    effective_timeout = timeout if timeout is not None else DEFAULT_UPLOAD_TIMEOUT
    response = _send_request(
        requests,
        "post",
        url,
        timeout=effective_timeout,
        retryable=False,
        params=params,
        files=files,
    )
    _raise_for_status(response, url=url, params=params)
    return response


__all__ = [
    "MoodleHttpError",
    "MoodleTimeoutError",
    "MoodleWebserviceError",
    "REDACTED",
    "request_ajax",
    "request_form_post",
    "request_html_get",
    "request_webservice",
    "upload_file",
]
