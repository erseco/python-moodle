"""Unit tests for the logging-based debug output of ``py_moodle.auth``."""

import logging
from types import SimpleNamespace
from unittest.mock import MagicMock

from py_moodle.auth import MoodleAuth


def test_cas_login_logs_via_logging_and_redacts_password(caplog, capsys):
    """CAS login should log via ``logging``, redacting the password, not print()."""
    auth = MoodleAuth(
        base_url="https://moodle.example.test",
        username="user",
        password="super-secret-pw",
        use_cas=True,
        cas_url="https://cas.example.test",
        debug=True,
    )

    login_page_resp = MagicMock(
        status_code=200,
        text='<input name="execution" value="exec-token-123">',
    )
    post_resp = MagicMock(
        status_code=302,
        headers={"Location": "https://moodle.example.test/login/index.php?ticket=ST-1"},
    )
    redirect_resp = MagicMock(status_code=200, text="<html></html>")
    dashboard_resp = MagicMock(status_code=200, text="<html>Dashboard</html>")

    session = MagicMock()
    session.get.side_effect = [login_page_resp, redirect_resp, dashboard_resp]
    session.post.return_value = post_resp
    auth.session = session

    with caplog.at_level(logging.DEBUG, logger="py_moodle.auth"):
        auth._cas_login()

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""

    assert "super-secret-pw" not in caplog.text
    assert "REDACTED" in caplog.text
    assert any(record.name == "py_moodle.auth" for record in caplog.records)


def test_login_debug_logs_sesskey_obtained_via_logging(monkeypatch, caplog, capsys):
    """login() should log via logging (never print()), redacting the sesskey."""
    auth = MoodleAuth(
        base_url="https://moodle.example.test",
        username="user",
        password="pw",
        debug=True,
    )
    monkeypatch.setattr(auth, "_standard_login", lambda: None)
    monkeypatch.setattr(auth, "_get_sesskey", lambda: "sesskey-abc")
    monkeypatch.setattr(auth, "_get_webservice_token", lambda: None)
    monkeypatch.setattr(
        "py_moodle.auth.detect_moodle_compatibility",
        lambda session, base_url, token=None: SimpleNamespace(
            strategy=SimpleNamespace(version_range="generic"),
            version=SimpleNamespace(raw="4.1", source="test"),
        ),
    )

    with caplog.at_level(logging.DEBUG, logger="py_moodle.auth"):
        auth.login()

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""

    messages = [
        record.message for record in caplog.records if record.name == "py_moodle.auth"
    ]
    assert any("sesskey obtained: ***REDACTED***" in message for message in messages)
    assert not any("sesskey-abc" in message for message in messages)


def test_auth_module_has_no_print_calls():
    """The auth module source must contain zero ``print(`` calls."""
    import inspect

    import py_moodle.auth as auth_module

    source = inspect.getsource(auth_module)
    assert "print(" not in source
