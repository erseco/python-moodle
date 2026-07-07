"""High-level, object-oriented facade over the ``py_moodle`` function API.

``MoodleClient`` wraps a ``requests.Session``, ``base_url``, ``token`` and
``sesskey`` tuple (obtained either explicitly or via :class:`MoodleSession`)
and exposes grouped resource namespaces (``courses``, ``sections``, ``users``,
``folders``, ``labels``, ``assignments``, ``scorm``) whose methods delegate to
the existing, already-tested functions in ``course.py``, ``section.py``,
``user.py``, ``folder.py``, ``label.py``, ``assign.py`` and ``scorm.py``.

This module is purely additive: it does not modify the signature or behavior
of any function it delegates to.
"""

from __future__ import annotations

from typing import Any, Optional

import requests

from . import assign, course, folder, label, scorm, section, user
from .session import MoodleSession
from .settings import Settings


class _ExplicitConnection:
    """Holds an explicitly provided session/base_url/token/sesskey tuple."""

    def __init__(
        self,
        session: requests.Session,
        base_url: str,
        token: Optional[str],
        sesskey: Optional[str],
    ) -> None:
        """Store the explicit connection values as-is.

        Args:
            session: Authenticated requests session.
            base_url: Base URL of the Moodle instance.
            token: Webservice token, if available.
            sesskey: Session key, if available.
        """
        self.session = session
        self.base_url = base_url
        self.token = token
        self.sesskey = sesskey


class _BaseResource:
    """Base class for resource-namespace proxies bound to a client."""

    def __init__(self, client: "MoodleClient") -> None:
        """Bind the resource proxy to its owning client.

        Args:
            client: The :class:`MoodleClient` instance owning this resource.
        """
        self._client = client

    @property
    def _session(self) -> requests.Session:
        """Return the client's current authenticated session."""
        return self._client.session

    @property
    def _base_url(self) -> str:
        """Return the client's Moodle base URL."""
        return self._client.base_url

    @property
    def _token(self) -> Optional[str]:
        """Return the client's webservice token, if any."""
        return self._client.token

    @property
    def _sesskey(self) -> Optional[str]:
        """Return the client's session key, if any."""
        return self._client.sesskey


class CoursesResource(_BaseResource):
    """Course-related operations, bound to a :class:`MoodleClient`."""

    def list(self, *args: Any, **kwargs: Any) -> Any:
        """Delegate to :func:`py_moodle.course.list_courses`."""
        return course.list_courses(
            self._session,
            self._base_url,
            *args,
            token=self._token,
            sesskey=self._sesskey,
            **kwargs,
        )

    def create(self, *args: Any, **kwargs: Any) -> Any:
        """Delegate to :func:`py_moodle.course.create_course`."""
        return course.create_course(
            self._session, self._base_url, self._sesskey, *args, **kwargs
        )

    def get(self, *args: Any, **kwargs: Any) -> Any:
        """Delegate to :func:`py_moodle.course.get_course`."""
        return course.get_course(
            self._session, self._base_url, self._sesskey, *args, **kwargs
        )

    def delete(self, *args: Any, **kwargs: Any) -> Any:
        """Delegate to :func:`py_moodle.course.delete_course`."""
        return course.delete_course(
            self._session, self._base_url, self._sesskey, *args, **kwargs
        )

    def get_with_sections_and_modules(self, *args: Any, **kwargs: Any) -> Any:
        """Delegate to :func:`py_moodle.course.get_course_with_sections_and_modules`."""
        return course.get_course_with_sections_and_modules(
            self._session, self._base_url, self._sesskey, *args, **kwargs
        )

    def context_id(self, *args: Any, **kwargs: Any) -> Any:
        """Delegate to :func:`py_moodle.course.get_course_context_id`."""
        return course.get_course_context_id(
            self._session, self._base_url, *args, **kwargs
        )


class SectionsResource(_BaseResource):
    """Section-related operations, bound to a :class:`MoodleClient`."""

    def list(self, *args: Any, **kwargs: Any) -> Any:
        """Delegate to :func:`py_moodle.section.list_sections`."""
        return section.list_sections(
            self._session, self._base_url, self._sesskey, *args, **kwargs
        )

    def create(self, *args: Any, **kwargs: Any) -> Any:
        """Delegate to :func:`py_moodle.section.create_section`."""
        return section.create_section(
            self._session, self._base_url, self._sesskey, *args, **kwargs
        )

    def delete(self, *args: Any, **kwargs: Any) -> Any:
        """Delegate to :func:`py_moodle.section.delete_section`."""
        return section.delete_section(
            self._session, self._base_url, self._sesskey, *args, **kwargs
        )


class UsersResource(_BaseResource):
    """User-related operations, bound to a :class:`MoodleClient`."""

    def list(self, *args: Any, **kwargs: Any) -> Any:
        """Delegate to :func:`py_moodle.user.list_course_users`."""
        return user.list_course_users(
            self._session, self._base_url, self._token, *args, **kwargs
        )

    def create(self, *args: Any, **kwargs: Any) -> Any:
        """Delegate to :func:`py_moodle.user.create_user`."""
        kwargs.setdefault("sesskey", self._sesskey)
        return user.create_user(
            self._session, self._base_url, self._token, *args, **kwargs
        )

    def delete(self, *args: Any, **kwargs: Any) -> Any:
        """Delegate to :func:`py_moodle.user.delete_user`."""
        kwargs.setdefault("sesskey", self._sesskey)
        return user.delete_user(
            self._session, self._base_url, self._token, *args, **kwargs
        )


class FoldersResource(_BaseResource):
    """Folder-module operations, bound to a :class:`MoodleClient`."""

    def add(self, *args: Any, **kwargs: Any) -> Any:
        """Delegate to :func:`py_moodle.folder.add_folder`."""
        return folder.add_folder(
            self._session, self._base_url, self._sesskey, *args, **kwargs
        )

    def delete(self, *args: Any, **kwargs: Any) -> Any:
        """Delegate to :func:`py_moodle.folder.delete_folder`."""
        return folder.delete_folder(
            self._session, self._base_url, self._sesskey, *args, **kwargs
        )

    def add_file(self, *args: Any, **kwargs: Any) -> Any:
        """Delegate to :func:`py_moodle.folder.add_file_to_folder`."""
        return folder.add_file_to_folder(
            self._session, self._base_url, self._sesskey, *args, **kwargs
        )

    def delete_file(self, *args: Any, **kwargs: Any) -> Any:
        """Delegate to :func:`py_moodle.folder.delete_file_from_folder`."""
        return folder.delete_file_from_folder(
            self._session, self._base_url, self._sesskey, *args, **kwargs
        )

    def rename_file(self, *args: Any, **kwargs: Any) -> Any:
        """Delegate to :func:`py_moodle.folder.rename_file_in_folder`."""
        return folder.rename_file_in_folder(
            self._session, self._base_url, self._sesskey, *args, **kwargs
        )

    def list_content(self, *args: Any, **kwargs: Any) -> Any:
        """Delegate to :func:`py_moodle.folder.list_folder_content`."""
        return folder.list_folder_content(
            self._session, self._base_url, *args, **kwargs
        )


class LabelsResource(_BaseResource):
    """Label-module operations, bound to a :class:`MoodleClient`."""

    def add(self, *args: Any, **kwargs: Any) -> Any:
        """Delegate to :func:`py_moodle.label.add_label`."""
        return label.add_label(
            self._session, self._base_url, self._sesskey, *args, **kwargs
        )

    def delete(self, *args: Any, **kwargs: Any) -> Any:
        """Delegate to :func:`py_moodle.label.delete_label`."""
        return label.delete_label(
            self._session, self._base_url, self._sesskey, *args, **kwargs
        )

    def update(self, *args: Any, **kwargs: Any) -> Any:
        """Delegate to :func:`py_moodle.label.update_label`."""
        return label.update_label(self._session, self._base_url, *args, **kwargs)


class AssignmentsResource(_BaseResource):
    """Assignment-module operations, bound to a :class:`MoodleClient`."""

    def add(self, *args: Any, **kwargs: Any) -> Any:
        """Delegate to :func:`py_moodle.assign.add_assign`."""
        return assign.add_assign(
            self._session, self._base_url, self._sesskey, *args, **kwargs
        )


class ScormResource(_BaseResource):
    """SCORM-module operations, bound to a :class:`MoodleClient`."""

    def add(self, *args: Any, **kwargs: Any) -> Any:
        """Delegate to :func:`py_moodle.scorm.add_scorm`."""
        return scorm.add_scorm(
            self._session, self._base_url, self._sesskey, *args, **kwargs
        )

    def add_ajax(self, *args: Any, **kwargs: Any) -> Any:
        """Delegate to :func:`py_moodle.scorm.add_scorm_ajax`."""
        return scorm.add_scorm_ajax(
            self._session, self._base_url, self._sesskey, *args, **kwargs
        )


class MoodleClient:
    """High-level, discoverable facade over the ``py_moodle`` function API.

    A ``MoodleClient`` owns a connected Moodle session and exposes grouped
    resource namespaces (``courses``, ``sections``, ``users``, ``folders``,
    ``labels``, ``assignments``, ``scorm``) instead of requiring callers to
    thread ``session``/``base_url``/``token``/``sesskey`` through every call.

    It can be built two ways:

    * From explicit settings: ``MoodleClient(settings)``, which lazily wraps
      a :class:`MoodleSession` (no network I/O happens until the session,
      token or sesskey is actually accessed).
    * From an explicit connection: ``MoodleClient(session=..., base_url=...,
      token=..., sesskey=...)``, for callers who already have these values.
    * From environment/profile: :meth:`MoodleClient.from_env`, which reuses
      :func:`py_moodle.settings.load_settings` and the cached,
      thread-safe :meth:`MoodleSession.get`.

    It also supports the context manager protocol, closing the underlying
    ``requests.Session`` on exit (if one was actually opened).
    """

    def __init__(
        self,
        settings: Optional[Settings] = None,
        *,
        session: Optional[requests.Session] = None,
        base_url: Optional[str] = None,
        token: Optional[str] = None,
        sesskey: Optional[str] = None,
    ) -> None:
        """Construct a client from explicit settings or an explicit connection.

        Args:
            settings: Environment settings used to lazily create a
                :class:`MoodleSession`. Mutually exclusive with the explicit
                ``session``/``base_url`` arguments.
            session: An already-authenticated ``requests.Session``. Requires
                ``base_url`` to also be provided.
            base_url: Base URL of the Moodle instance (used with ``session``).
            token: Webservice token (used with ``session``).
            sesskey: Session key (used with ``session``).

        Raises:
            ValueError: If neither ``settings`` nor a ``session``/``base_url``
                pair is provided.
        """
        self._moodle_session: Optional[MoodleSession] = None
        self._explicit: Optional[_ExplicitConnection] = None

        if settings is not None:
            self._moodle_session = MoodleSession(settings)
        elif session is not None and base_url is not None:
            self._explicit = _ExplicitConnection(session, base_url, token, sesskey)
        else:
            raise ValueError(
                "MoodleClient requires either a `settings` object or an "
                "explicit `session` and `base_url` pair."
            )

        self._bind_resources()

    def _bind_resources(self) -> None:
        """Create the resource-namespace proxies bound to this client."""
        self.courses = CoursesResource(self)
        self.sections = SectionsResource(self)
        self.users = UsersResource(self)
        self.folders = FoldersResource(self)
        self.labels = LabelsResource(self)
        self.assignments = AssignmentsResource(self)
        self.scorm = ScormResource(self)

    @classmethod
    def from_env(cls, env: Optional[str] = None) -> "MoodleClient":
        """Build a client from environment/profile configuration.

        Internally calls :meth:`MoodleSession.get` (which itself calls
        :func:`py_moodle.settings.load_settings`), reusing its existing
        per-environment caching, thread-safety, and lazy-login behavior.

        Args:
            env: Environment key (e.g. ``"local"``, ``"staging"``, ``"prod"``).
                Defaults to ``MoodleSession.get``'s own default (``"local"``).

        Returns:
            MoodleClient: A client wired to the cached session for ``env``.
        """
        instance = cls.__new__(cls)
        instance._moodle_session = MoodleSession.get(env)
        instance._explicit = None
        instance._bind_resources()
        return instance

    # ------------- connection properties -------------

    @property
    def base_url(self) -> str:
        """Return the Moodle instance's base URL."""
        if self._moodle_session is not None:
            return self._moodle_session.settings.url
        assert self._explicit is not None
        return self._explicit.base_url

    @property
    def session(self) -> requests.Session:
        """Return the authenticated ``requests.Session`` (login once)."""
        if self._moodle_session is not None:
            return self._moodle_session.session
        assert self._explicit is not None
        return self._explicit.session

    @property
    def token(self) -> Optional[str]:
        """Return the webservice token, or ``None`` if not available."""
        if self._moodle_session is not None:
            return self._moodle_session.token
        assert self._explicit is not None
        return self._explicit.token

    @property
    def sesskey(self) -> Optional[str]:
        """Return the session key, or ``None`` if not available."""
        if self._moodle_session is not None:
            return self._moodle_session.sesskey
        assert self._explicit is not None
        return self._explicit.sesskey

    # ------------- context manager -------------

    def __enter__(self) -> "MoodleClient":
        """Return this client, enabling ``with MoodleClient(...) as moodle``."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Close the underlying session on exit; never raises."""
        self.close()

    def close(self) -> None:
        """Close the underlying ``requests.Session``, if one was opened.

        Safe to call multiple times, and safe to call even if no HTTP session
        was ever established (it will not force a login just to close it).
        """
        opened_session = self._peek_opened_session()
        if opened_session is not None:
            try:
                opened_session.close()
            except Exception:
                pass

    def _peek_opened_session(self) -> Optional[requests.Session]:
        """Return the underlying session only if it already exists.

        Unlike the ``session`` property, this never triggers a lazy login.
        """
        if self._moodle_session is not None:
            return getattr(self._moodle_session, "_session", None)
        assert self._explicit is not None
        return self._explicit.session


__all__ = [
    "MoodleClient",
    "CoursesResource",
    "SectionsResource",
    "UsersResource",
    "FoldersResource",
    "LabelsResource",
    "AssignmentsResource",
    "ScormResource",
]
