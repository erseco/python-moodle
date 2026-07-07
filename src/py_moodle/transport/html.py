"""HTML scraping / form-submission transport strategy (interface only).

This module formalizes the calling convention for a future
``HtmlTransport`` that talks to Moodle by scraping HTML pages and
submitting HTML forms (e.g. ``course/edit.php``), for the cases where
Moodle exposes neither a webservice nor an AJAX equivalent.

No real Moodle interaction is wired up as part of this issue: :func:`call`
only documents the intended signature and always raises
:class:`NotImplementedError`. Migrating existing HTML-based flows (e.g.
``create_course``/``delete_course`` in :mod:`py_moodle.course`) onto this
transport is tracked as follow-up work.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import requests


def call(
    session: requests.Session,
    base_url: str,
    action: str,
    params: Optional[Dict[str, Any]] = None,
) -> Any:
    """Perform an HTML form-submission/scraping call against Moodle.

    Args:
        session: Authenticated requests session.
        base_url: Base URL of the Moodle instance.
        action: Relative path of the HTML page/form to interact with
            (e.g. ``"course/edit.php"``).
        params: Form fields or query parameters for the request.

    Returns:
        Any: Parsed result of the HTML interaction, in whatever shape a
        future concrete implementation defines.

    Raises:
        NotImplementedError: Always, for this issue. This module only
            formalizes the transport interface; no real HTML-based Moodle
            interaction is implemented yet.
    """
    raise NotImplementedError(
        "HtmlTransport is interface-only in this version of py-moodle; no "
        "HTML transport is implemented yet."
    )


__all__ = ["call"]
