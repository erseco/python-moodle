"""Transport-layer abstractions for talking to Moodle.

``py-moodle`` talks to a Moodle instance through three fundamentally
different transports:

1. **Webservice / REST API** (:mod:`py_moodle.transport.webservice`) --
   ``POST {base_url}/webservice/rest/server.php`` with a ``wstoken``, e.g.
   ``core_course_get_courses``.
2. **Internal AJAX endpoint** (:mod:`py_moodle.transport.ajax`) --
   ``POST {base_url}/lib/ajax/service.php?sesskey=...`` with a JSON
   ``methodname``/``args`` payload, used when no webservice token is
   available or the webservice call fails.
3. **HTML scraping / form submission** (:mod:`py_moodle.transport.html`) --
   used where Moodle exposes no webservice or AJAX equivalent at all.

This package formalizes those transports as small, uniform ``call(...)``
functions built strictly on top of the shared HTTP client in
:mod:`py_moodle.http`, so a caller can implement "try transport A, on
failure fall back to transport B" without knowing the request-building
details of either transport.

Transport (webservice vs AJAX vs HTML) is a different, orthogonal axis from
Moodle-version compatibility, which remains isolated in
:mod:`py_moodle.compat`.
"""

from __future__ import annotations


class TransportError(Exception):
    """Base class for transport-layer errors."""


class TransportUnavailableError(TransportError):
    """Raised when a transport cannot be used for this call.

    Signals to the caller that it should try the next transport in the
    fallback chain (e.g. webservice -> AJAX), as opposed to a genuine
    business-logic failure that should propagate to the user.
    """


__all__ = ["TransportError", "TransportUnavailableError"]
