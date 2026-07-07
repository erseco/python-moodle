"""Offline regression tests for the brittle HTML parsers in ``py_moodle.compat``.

These are characterization tests: the parsers already exist, so each test pins
the current extraction behavior against a hand-authored HTML fixture file that
mirrors representative Moodle markup. They run fully network-free under
``make test-unit`` so a future Moodle-markup change (or an accidental selector
regression) is caught early.

The fixtures live in ``tests/unit/fixtures/html/`` and are loaded from disk via
``pathlib`` relative to this file. Every embedded token/sesskey/version string
is an obviously-fake placeholder, never a real secret.
"""

from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from py_moodle.compat import (
    DEFAULT_COMPATIBILITY,
    LEGACY_COMPATIBILITY,
    LegacyCompatibilityStrategy,
    ModernCompatibilityStrategy,
    extract_version_from_dashboard,
    get_strategy_for_version,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "html"


def _load(name: str) -> str:
    """Read the text of an HTML fixture from the fixtures directory.

    Args:
        name: Fixture file name relative to ``fixtures/html/``.

    Returns:
        str: Decoded UTF-8 contents of the fixture.
    """
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


def _soup(name: str) -> BeautifulSoup:
    """Parse an HTML fixture into a ``BeautifulSoup`` tree.

    Args:
        name: Fixture file name relative to ``fixtures/html/``.

    Returns:
        BeautifulSoup: Parsed document tree, using the same ``lxml`` parser the
        production compatibility code relies on.
    """
    return BeautifulSoup(_load(name), "lxml")


def test_extract_login_token_from_modern_login_page():
    """The modern login fixture yields its fake ``logintoken`` value."""
    html = _load("login_page_modern.html")

    assert (
        DEFAULT_COMPATIBILITY.extract_login_token(html)
        == "fake-logintoken-9f8a7b6c5d4e3f2a"
    )


def test_extract_login_token_absent_returns_empty_string():
    """A page without a login form yields an empty login token."""
    html = _load("dashboard_modern.html")

    assert DEFAULT_COMPATIBILITY.extract_login_token(html) == ""


def test_extract_sesskey_from_config_page():
    """The ``M.cfg`` config fixture yields its fake sesskey value."""
    html = _load("sesskey_config_modern.html")

    assert DEFAULT_COMPATIBILITY.extract_sesskey(html) == "fakeSesskey1a2b3c"


def test_extract_sesskey_absent_returns_none():
    """A login page carrying no sesskey yields ``None``."""
    html = _load("login_page_modern.html")

    assert DEFAULT_COMPATIBILITY.extract_sesskey(html) is None


@pytest.mark.parametrize("strategy", [DEFAULT_COMPATIBILITY, LEGACY_COMPATIBILITY])
def test_extract_folder_filenames_is_stable_across_strategies(strategy):
    """Both strategies extract the same sorted filenames from the folder view.

    This exercises the legacy/modern selector split: the fixture uses a
    class-scoped ``pluginfile.php`` listing that both strategy selector orders
    must resolve identically.
    """
    soup = _soup("folder_view_modern.html")

    assert strategy.extract_folder_filenames(soup) == [
        "notes.txt",
        "slides.pdf",
        "syllabus.docx",
    ]


def test_extract_version_from_modern_dashboard():
    """The modern dashboard fixture parses to a 5.x ``MoodleVersion``."""
    version = extract_version_from_dashboard(_load("dashboard_modern.html"))

    assert version.major == 5
    assert version.minor == 1
    assert version.source == "html-meta"
    assert version.raw.startswith("Moodle 5.1")


def test_extract_version_from_legacy_dashboard():
    """The legacy dashboard fixture parses to a 3.x ``MoodleVersion``."""
    version = extract_version_from_dashboard(_load("dashboard_legacy.html"))

    assert version.major == 3
    assert version.minor == 11
    assert version.patch == 16
    assert version.source == "html-meta"


def test_extract_version_absent_returns_unknown():
    """A dashboard without a version marker degrades gracefully to unknown."""
    version = extract_version_from_dashboard(_load("dashboard_no_version.html"))

    assert version.major is None
    assert version.raw == "unknown"


@pytest.mark.parametrize(
    ("fixture", "expected_major", "expected_strategy"),
    [
        ("dashboard_legacy.html", 3, LegacyCompatibilityStrategy),
        ("dashboard_modern.html", 5, ModernCompatibilityStrategy),
    ],
)
def test_strategy_selection_matches_dashboard_version(
    fixture, expected_major, expected_strategy
):
    """Version parsed from a dashboard picks the matching legacy/modern strategy."""
    version = extract_version_from_dashboard(_load(fixture))

    assert version.major == expected_major
    assert isinstance(get_strategy_for_version(version), expected_strategy)
