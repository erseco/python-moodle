"""Role and permission utilities for Moodle operations."""

from __future__ import annotations

from functools import wraps
from typing import Callable

import requests

ROLE_HIERARCHY: dict[str, int] = {"user": 0, "manager": 1, "admin": 2}


class RoleError(PermissionError):
    """Raised when the current user does not meet the required role."""


def get_user_role(session: requests.Session, base_url: str) -> str:
    """Return the current user's role, caching the result on the session.

    The role is determined by checking the dashboard for administrator markers
    and the course management page for manager capabilities. If neither is
    accessible, the role defaults to ``"user"``.

    Args:
        session: Authenticated session.
        base_url: Base URL of the Moodle instance.

    Returns:
        The role name.
    """
    cached = getattr(session, "_moodle_role", None)
    if cached:
        return cached

    resp = session.get(f"{base_url}/my/")
    resp.raise_for_status()

    if 'data-key="siteadminnode"' in resp.text:
        role = "admin"
    else:
        manage_resp = session.get(f"{base_url}/course/management.php")
        role = "manager" if manage_resp.status_code == 200 else "user"

    setattr(session, "_moodle_role", role)
    return role


def requires_role(required: str) -> Callable:
    """Decorator enforcing a minimum user role for a function.

    The wrapped function must receive a ``requests.Session`` and the
    corresponding ``base_url`` as positional or keyword arguments.

    Args:
        required: Minimum role required to execute the function.

    Returns:
        Wrapped function that performs the role check before execution.
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            session = kwargs.get("session")
            base_url = kwargs.get("base_url")

            if session is None:
                for arg in args:
                    if isinstance(arg, requests.Session):
                        session = arg
                        break

            if base_url is None and session is not None:
                try:
                    idx = list(args).index(session)
                    if len(args) > idx + 1:
                        base_url = args[idx + 1]
                except ValueError:
                    pass

            if session is None or base_url is None:
                raise RoleError(
                    "Session and base_url are required for role verification."
                )

            current_role = get_user_role(session, base_url)
            if ROLE_HIERARCHY[current_role] < ROLE_HIERARCHY[required]:
                raise RoleError(
                    f"Operation requires role '{required}', current role is '{current_role}'."
                )
            return func(*args, **kwargs)

        return wrapper

    return decorator


__all__ = ["RoleError", "get_user_role", "requires_role"]
