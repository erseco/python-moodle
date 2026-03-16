import os
import random
from dataclasses import dataclass
from pathlib import Path

import pytest
import requests
from dotenv import load_dotenv

from py_moodle.auth import LoginError, login
from py_moodle.course import (
    get_course_with_sections_and_modules,
)

# Load environment variables from .env file at the start
load_dotenv()

UNIT_TESTS_DIR = (Path(__file__).parent / "unit").resolve()


@dataclass(frozen=True)
class Target:
    """Represents a Moodle instance to test against."""

    name: str
    url: str
    username: str
    password: str


def pytest_addoption(parser):
    """Adds the --moodle-env command-line option to pytest."""
    parser.addoption(
        "--moodle-env",
        action="store",
        default="local",
        help="Moodle environment to target: local | staging | prod",
    )
    parser.addoption(
        "--integration",
        action="store_true",
        default=False,
        help="Run tests that require a live Moodle instance.",
    )


def _env(name: str) -> str:
    """Helper to get a required environment variable."""
    val = os.getenv(name)
    if not val:
        raise ValueError(f"Required environment variable {name!r} is missing.")
    return val


def _build_target(env: str) -> Target:
    """Builds the Moodle target configuration for the requested environment."""
    prefix = f"MOODLE_{env.upper()}"

    required_suffixes = ("URL", "USERNAME", "PASSWORD")
    missing_vars = []
    for suffix in required_suffixes:
        var_name = f"{prefix}_{suffix}"
        if not os.getenv(var_name):
            missing_vars.append(var_name)

    if missing_vars:
        message = (
            f"Configuration for Moodle environment '{env}' is incomplete or does not exist.\n"
            "Please ensure the following environment variables are set in your .env file:\n\n"
            f"  {', '.join(missing_vars)}\n"
        )
        pytest.exit(message)

    return Target(
        name=env,
        url=_env(f"{prefix}_URL"),
        username=_env(f"{prefix}_USERNAME"),
        password=_env(f"{prefix}_PASSWORD"),
    )


def _ensure_target_available(target: Target):
    """Checks that the configured Moodle host is reachable before tests run."""
    try:
        requests.get(target.url, timeout=5).raise_for_status()
    except requests.RequestException:
        if target.name == "local":
            message = (
                f"Host '{target.url}' for environment 'local' is not available.\n"
                "You may need to start the local Moodle instance. Try running:\n\n"
                "  docker compose up -d\n"
            )
        else:
            message = (
                f"Host '{target.url}' for environment '{target.name}' is not available. "
                "Please check the host and your network connection."
            )
        pytest.exit(message)


def pytest_configure(config):
    """
    Configures markers and, when requested, the Moodle target for integration
    tests.
    """
    config.addinivalue_line(
        "markers", "integration: tests that require a live Moodle instance"
    )

    if not config.getoption("--integration"):
        return

    env = config.getoption("--moodle-env")
    target = _build_target(env)
    config.moodle_target = target
    _ensure_target_available(target)


def pytest_collection_modifyitems(config, items):
    """Marks Moodle-backed tests as integration tests and skips them by default."""
    run_integration = config.getoption("--integration")
    skip_integration = pytest.mark.skip(
        reason="Use --integration to run tests that require a live Moodle instance."
    )

    for item in items:
        item_path = Path(item.path).resolve()
        if item_path == UNIT_TESTS_DIR or UNIT_TESTS_DIR in item_path.parents:
            continue
        item.add_marker(pytest.mark.integration)
        if not run_integration:
            item.add_marker(skip_integration)


@pytest.fixture(scope="function")
def moodle(request):
    """Provides an authenticated Moodle session for the target environment."""
    target = request.config.moodle_target
    try:
        session = login(
            url=target.url, username=target.username, password=target.password
        )
        return session
    except LoginError as e:
        # It's better to use pytest.fail() here because we are inside a fixture,
        # which is part of the test execution context, not the configuration phase.
        pytest.fail(f"Failed to log in to '{target.name}' Moodle: {e}", pytrace=False)


@pytest.fixture(scope="module")
def temporary_course_for_labels(request):
    """Creates a temporary course for label tests and deletes it when finished."""
    target = request.config.moodle_target
    from py_moodle.auth import login
    from py_moodle.course import create_course, delete_course

    moodle_session = login(
        url=target.url, username=target.username, password=target.password
    )
    if not moodle_session.sesskey:
        pytest.skip("Could not obtain sesskey to create the temporary course.")

    base_url = target.url
    sesskey = moodle_session.sesskey

    fullname = f"Test Course For Labels {random.randint(1000, 9999)}"
    shortname = f"TCL{random.randint(1000, 9999)}"

    course = create_course(
        session=moodle_session,
        base_url=base_url,
        sesskey=sesskey,
        fullname=fullname,
        shortname=shortname,
        categoryid=1,
        numsections=1,
    )

    yield course

    delete_course(moodle_session, base_url, sesskey, course["id"], force=True)


@pytest.fixture
def first_section_id(moodle, request, temporary_course_for_labels) -> int:
    """Gets the ID of the first thematic section (position 1) of the temporary course."""
    base_url = request.config.moodle_target.url
    course_id = temporary_course_for_labels["id"]
    token = getattr(moodle, "webservice_token", None)

    data = get_course_with_sections_and_modules(
        moodle, base_url, moodle.sesskey, course_id, token=token
    )
    sections = data.get("sections", [])

    target_section = next((s for s in sections if s.get("section") == 1), None)

    if target_section and "id" in target_section:
        return int(target_section["id"])

    pytest.fail("Could not find the first thematic section in the temporary course.")
