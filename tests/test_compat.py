"""Unit tests for Moodle compatibility helpers."""

from py_moodle.compat import (
    LegacyCompatibilityStrategy,
    ModernCompatibilityStrategy,
    detect_moodle_compatibility,
)
from py_moodle.folder import _get_current_user_fullname, list_folder_content
from py_moodle.module import update_generic_module


class FakeResponse:
    """Minimal response object for unit tests."""

    def __init__(self, text="", status_code=200, json_data=None):
        self.text = text
        self.status_code = status_code
        self._json_data = json_data

    def raise_for_status(self):
        """Raise for failing HTTP statuses."""
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        """Return the configured JSON payload."""
        return self._json_data


class FakeSession:
    """Minimal requests.Session-like object for compatibility tests."""

    def __init__(self, get_responses=None, post_responses=None):
        self.get_responses = list(get_responses or [])
        self.post_responses = list(post_responses or [])
        self.post_calls = []
        self.moodle_compat = ModernCompatibilityStrategy()

    def get(self, url, *args, **kwargs):
        """Return a queued GET response."""
        if not self.get_responses:
            raise AssertionError(f"Unexpected GET request to {url}")
        return self.get_responses.pop(0)

    def post(self, url, *args, **kwargs):
        """Return a queued POST response and store the call."""
        self.post_calls.append({"url": url, "args": args, "kwargs": kwargs})
        if not self.post_responses:
            raise AssertionError(f"Unexpected POST request to {url}")
        return self.post_responses.pop(0)


def test_detect_moodle_compatibility_prefers_webservice_version():
    """Compatibility detection should use site info when a token is available."""
    session = FakeSession(
        post_responses=[
            FakeResponse(
                json_data={
                    "release": "4.5.2+ (Build: 20241001)",
                    "version": "2024100100",
                }
            )
        ]
    )

    compatibility = detect_moodle_compatibility(
        session, "https://moodle.example.test", token="token"
    )

    assert compatibility.version.major == 4
    assert compatibility.version.minor == 5
    assert compatibility.version.source == "webservice"
    assert isinstance(compatibility.strategy, ModernCompatibilityStrategy)


def test_detect_moodle_compatibility_falls_back_to_dashboard_html():
    """Compatibility detection should parse dashboard metadata without a token."""
    html = """
    <html>
      <head>
        <meta name="generator" content="Moodle 3.11.16+ (Build: 20230710)">
      </head>
    </html>
    """
    session = FakeSession(get_responses=[FakeResponse(text=html)])

    compatibility = detect_moodle_compatibility(session, "https://moodle.example.test")

    assert compatibility.version.major == 3
    assert compatibility.version.minor == 11
    assert compatibility.version.source == "html-meta"
    assert isinstance(compatibility.strategy, LegacyCompatibilityStrategy)


def test_update_generic_module_uses_compatibility_form_fallback():
    """Module updates should accept compatibility fallback selectors for modedit."""
    html = """
    <html>
      <body>
        <form id="mform1">
          <input type="hidden" name="id" value="17">
          <input type="text" name="name" value="Old name">
        </form>
      </body>
    </html>
    """
    session = FakeSession(
        get_responses=[FakeResponse(text=html)],
        post_responses=[FakeResponse(status_code=303)],
    )

    assert (
        update_generic_module(
            session,
            "https://moodle.example.test",
            17,
            specific_payload={"name": "New name"},
        )
        is True
    )
    assert session.post_calls[0]["kwargs"]["data"]["name"] == "New name"


def test_folder_content_uses_compatibility_selector_fallback():
    """Folder listing should work even when legacy folder tree classes are missing."""
    html = """
    <html>
      <body>
        <div class="activityinstance">
          <a href="https://moodle.example.test/pluginfile.php/12/mod_folder/content/0/test.pdf">
            test.pdf
          </a>
        </div>
      </body>
    </html>
    """
    session = FakeSession(get_responses=[FakeResponse(text=html)])

    assert list_folder_content(session, "https://moodle.example.test", 24) == [
        "test.pdf"
    ]


def test_current_user_fullname_uses_data_region_selector():
    """Folder file renames should support modern user menu markup."""
    html = """
    <html>
      <body>
        <div data-region="usermenu">
          <span class="userbutton">
            <span class="usertext">Jane Doe</span>
          </span>
        </div>
      </body>
    </html>
    """
    session = FakeSession(get_responses=[FakeResponse(text=html)])

    assert (
        _get_current_user_fullname(session, "https://moodle.example.test") == "Jane Doe"
    )
