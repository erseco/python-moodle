# tests/test_scorm.py
import random
from pathlib import Path

import pytest

from py_moodle.course import (
    create_course,
    delete_course,
    get_course_with_sections_and_modules,
)

# Import helpers needed for testing
from py_moodle.module import delete_module

# Import the new scorm functionality
from py_moodle.scorm import MoodleScormError, add_scorm

# --- Fixtures ---


@pytest.fixture(scope="module")
def scorm_zip_path() -> Path:
    """Provides the path to a test SCORM file and ensures it exists."""
    # The test expects a 'fixtures' directory at the same level as the 'tests' directory
    # or inside it. Let's place it inside 'tests'.
    fixtures_dir = Path(__file__).parent / "fixtures"
    scorm_file = fixtures_dir / "scorm.zip"

    # Create a dummy scorm.zip if it doesn't exist, as a placeholder
    if not scorm_file.exists():
        fixtures_dir.mkdir(exist_ok=True)
        import zipfile

        with zipfile.ZipFile(scorm_file, "w") as zf:
            zf.writestr("imsmanifest.xml", "<manifest></manifest>")
        print(f"\n[INFO] Created a dummy '{scorm_file.name}' for testing.")

    return scorm_file


@pytest.fixture(scope="module")
def temporary_course_for_scorm(request):
    """Creates a temporary course for the SCORM tests and deletes it afterwards."""
    target = request.config.moodle_target
    from py_moodle.auth import login

    moodle_session = login(
        url=target.url, username=target.username, password=target.password
    )
    if not moodle_session.sesskey:
        pytest.skip("Could not get sesskey to create a temporary course.")

    base_url = target.url
    sesskey = moodle_session.sesskey

    fullname = f"Test Course For SCORM {random.randint(1000, 9999)}"
    shortname = f"TCSCRM{random.randint(1000, 9999)}"

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
def first_section_id_for_scorm(moodle, request, temporary_course_for_scorm) -> int:
    """Gets the ID of the first thematic section of the temporary course."""
    base_url = request.config.moodle_target.url
    course_id = temporary_course_for_scorm["id"]
    token = getattr(moodle, "webservice_token", None)

    data = get_course_with_sections_and_modules(
        moodle, base_url, moodle.sesskey, course_id, token=token
    )
    target_section = next(
        (s for s in data.get("sections", []) if s.get("section") == 1), None
    )

    if target_section and "id" in target_section:
        return int(target_section["id"])

    pytest.fail(
        "Could not find the first thematic section in the temporary course for SCORM."
    )


# --- Test ---


def test_add_scorm(
    moodle,
    request,
    temporary_course_for_scorm,
    first_section_id_for_scorm,
    scorm_zip_path,
):
    """
    Tests the creation of a SCORM module by uploading a file.
    """
    base_url = request.config.moodle_target.url
    course_id = temporary_course_for_scorm["id"]
    section_id = first_section_id_for_scorm
    sesskey = moodle.sesskey

    scorm_name = f"Test SCORM {random.randint(1000, 9999)}"
    intro_text = "A test SCORM package uploaded via script."

    # 1. Create the SCORM package
    new_cmid = None
    try:
        new_cmid = add_scorm(
            session=moodle,
            base_url=base_url,
            sesskey=sesskey,
            course_id=course_id,
            section_id=section_id,
            name=scorm_name,
            file_path=str(scorm_zip_path),
            intro=intro_text,
        )
    except MoodleScormError as e:
        pytest.fail(f"add_scorm failed with an exception: {e}")

    assert isinstance(
        new_cmid, int
    ), "add_scorm should return the new course module ID (cmid)."

    # 2. Verify the SCORM was created
    token = getattr(moodle, "webservice_token", None)
    course_data = get_course_with_sections_and_modules(
        moodle, base_url, sesskey, course_id, token
    )
    section = next((s for s in course_data["sections"] if s["id"] == section_id), {})
    new_module = next(
        (m for m in section.get("modules", []) if m["id"] == new_cmid), None
    )

    assert (
        new_module is not None
    ), "Newly created SCORM module was not found in the course section."
    assert new_module.get("name") == scorm_name
    assert new_module.get("modname") == "scorm"

    # 3. Clean up
    deleted = delete_module(moodle, base_url, sesskey, new_cmid)
    assert deleted is True, "Failed to clean up the created SCORM module."
