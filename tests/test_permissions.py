import pytest
import requests

from py_moodle.permissions import RoleError, requires_role


def test_requires_role_allows_admin(monkeypatch):
    session = requests.Session()
    monkeypatch.setattr("py_moodle.permissions.get_user_role", lambda s, u: "admin")

    @requires_role("manager")
    def dummy(session: requests.Session, base_url: str) -> int:
        return 1

    assert dummy(session, "https://example.com") == 1


def test_requires_role_denies_user(monkeypatch):
    session = requests.Session()
    monkeypatch.setattr("py_moodle.permissions.get_user_role", lambda s, u: "user")

    @requires_role("manager")
    def dummy(session: requests.Session, base_url: str) -> int:
        return 1

    with pytest.raises(RoleError):
        dummy(session, "https://example.com")
