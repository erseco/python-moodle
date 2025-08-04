# FILE: tests/test_folder.py

import random
import time
from pathlib import Path

import pytest

from py_moodle.course import (
    MoodleCourseError,
    create_course,
    delete_course,
    get_course_with_sections_and_modules,
)
from py_moodle.folder import (
    MoodleFolderError,
    add_file_to_folder,
    add_folder,
    delete_file_from_folder,
    delete_folder,
    list_folder_content,
    rename_file_in_folder,
)
from py_moodle.upload import MoodleUploadError, upload_file_webservice

# --- Fixtures ---


@pytest.fixture(scope="module")
def temporary_course_for_folders(request):
    """
    Creates a temporary course for all folder tests and deletes it when finished.
    Improved to be more robust against creation/deletion failures.
    """
    target = request.config.moodle_target
    from py_moodle.auth import login

    moodle_session = login(
        url=target.url, username=target.username, password=target.password
    )
    if not moodle_session.sesskey:
        pytest.skip(
            "Could not get sesskey to create a temporary course for folder tests."
        )

    base_url = target.url
    sesskey = moodle_session.sesskey

    fullname = f"Test Course For Folders {random.randint(1000, 9999)}"
    shortname = f"TCF{random.randint(1000, 9999)}"

    try:
        course = create_course(
            session=moodle_session,
            base_url=base_url,
            sesskey=sesskey,
            fullname=fullname,
            shortname=shortname,
            categoryid=1,
            numsections=1,
        )
        assert isinstance(course, dict) and "id" in course
    except MoodleCourseError as e:
        pytest.skip(f"Could not create temporary course for folder tests: {e}")

    yield course

    # Teardown: attempt to delete the course, warn on failure
    try:
        delete_course(moodle_session, base_url, sesskey, course["id"], force=True)
    except MoodleCourseError as e:
        print(
            f"\nWARNING: Could not clean up temporary course {course['id']}. Error: {e}"
        )


@pytest.fixture
def first_section_id(moodle, request, temporary_course_for_folders) -> int:
    """Gets the ID of the first thematic section (position 1) of the temporary course."""
    base_url = request.config.moodle_target.url
    course_id = temporary_course_for_folders["id"]
    token = getattr(moodle, "webservice_token", None)
    data = get_course_with_sections_and_modules(
        moodle, base_url, moodle.sesskey, course_id, token=token
    )
    target_section = next(
        (s for s in data.get("sections", []) if s.get("section") == 1), None
    )
    if target_section and "id" in target_section:
        return int(target_section["id"])
    pytest.fail("Could not find the first thematic section for folder tests.")


# --- Parameterized Fixture for All File Types ---
FIXTURE_DIR = Path(__file__).parent / "fixtures"
ALL_FIXTURE_FILES = [p for p in FIXTURE_DIR.iterdir() if p.is_file()]


@pytest.fixture(params=ALL_FIXTURE_FILES, ids=[p.name for p in ALL_FIXTURE_FILES])
def fixture_file(request) -> Path:
    """A parameterized fixture that provides the path to each file in tests/fixtures."""
    return request.param


# --- Tests ---


def test_add_and_delete_folder_with_initial_file(
    moodle,
    request,
    fixture_file,
    temporary_course_for_folders,
    first_section_id,
):
    """
    Tests the full lifecycle of a folder: create with a single initial file, then delete.
    This test is run for every file type in the fixtures directory.
    """
    base_url = request.config.moodle_target.url
    sesskey = moodle.sesskey
    token = moodle.webservice_token
    if not token:
        pytest.skip("No webservice token available for folder tests.")
    course_id = temporary_course_for_folders["id"]

    # 1. Upload the fixture file to a new draft area
    try:
        files_itemid = upload_file_webservice(
            base_url=base_url,
            token=token,
            file_path=str(fixture_file),
        )
    except MoodleUploadError as e:
        pytest.fail(f"File upload failed for {fixture_file.name}: {e}")

    # 2. Create the folder using the draft area itemid
    folder_name = f"Test Folder for {fixture_file.name}"
    new_cmid = add_folder(
        session=moodle,
        base_url=base_url,
        sesskey=sesskey,
        course_id=course_id,
        section_id=first_section_id,
        name=folder_name,
        files_itemid=files_itemid,
    )
    assert isinstance(new_cmid, int)

    # 3. Verify the folder content contains the uploaded file
    time.sleep(1)
    content = list_folder_content(moodle, base_url, new_cmid)
    assert (
        fixture_file.name in content
    ), f"File {fixture_file.name} was not found in the new folder."

    # 4. Delete the folder
    deleted = delete_folder(moodle, base_url, sesskey, new_cmid)
    assert deleted is True, f"Failed to delete the folder with cmid {new_cmid}."


def test_add_and_delete_empty_folder(
    moodle, request, temporary_course_for_folders, first_section_id
):
    """
    Tests creating a folder with no initial files.
    """
    base_url = request.config.moodle_target.url
    sesskey = moodle.sesskey
    course_id = temporary_course_for_folders["id"]

    empty_itemid = int(time.time() * 1000)
    folder_name = "Empty Test Folder"

    new_cmid = add_folder(
        session=moodle,
        base_url=base_url,
        sesskey=sesskey,
        course_id=course_id,
        section_id=first_section_id,
        name=folder_name,
        files_itemid=empty_itemid,
    )
    assert isinstance(new_cmid, int)

    time.sleep(1)
    content = list_folder_content(moodle, base_url, new_cmid)
    assert content == [], "Folder created as empty should have no content."

    deleted = delete_folder(moodle, base_url, sesskey, new_cmid)
    assert deleted is True


@pytest.fixture
def temporary_folder(moodle, request, temporary_course_for_folders, first_section_id):
    """Fixture that creates an empty folder for content management tests and cleans it up."""
    base_url = request.config.moodle_target.url
    sesskey = moodle.sesskey

    empty_itemid = int(time.time() * 1000)
    cmid = add_folder(
        session=moodle,
        base_url=base_url,
        sesskey=sesskey,
        course_id=temporary_course_for_folders["id"],
        section_id=first_section_id,
        name=f"Managed Folder {random.randint(1000, 9999)}",
        files_itemid=empty_itemid,
    )
    yield cmid

    try:
        delete_folder(moodle, base_url, sesskey, cmid)
    except MoodleFolderError:
        pass


def test_folder_add_rename_and_delete_files(moodle, request, temporary_folder):
    """
    Tests adding multiple files, renaming one, and deleting another from an existing folder.
    """
    base_url = request.config.moodle_target.url
    sesskey = moodle.sesskey
    cmid = temporary_folder

    file1, file2 = ALL_FIXTURE_FILES[0], ALL_FIXTURE_FILES[1]

    success1, _ = add_file_to_folder(moodle, base_url, sesskey, cmid, str(file1))
    assert success1 is True, "Failed to add the first file."
    time.sleep(1)

    success2, _ = add_file_to_folder(moodle, base_url, sesskey, cmid, str(file2))
    assert success2 is True, "Failed to add the second file."
    time.sleep(1)

    content_after_add = sorted(list_folder_content(moodle, base_url, cmid))
    assert content_after_add == sorted([file1.name, file2.name])

    renamed_file1 = f"renamed_{random.randint(100, 999)}_{file1.name}"
    success_rename, _ = rename_file_in_folder(
        moodle, base_url, sesskey, cmid, file1.name, renamed_file1
    )
    assert success_rename is True
    time.sleep(1)

    content_after_rename = sorted(list_folder_content(moodle, base_url, cmid))
    assert content_after_rename == sorted([renamed_file1, file2.name])

    success_delete, _ = delete_file_from_folder(
        moodle, base_url, sesskey, cmid, file2.name
    )
    assert success_delete is True
    time.sleep(1)

    content_after_delete = list_folder_content(moodle, base_url, cmid)
    assert content_after_delete == [renamed_file1]


def test_add_file_to_subfolder(moodle, request, temporary_folder):
    """
    Tests uploading a file to a specific subfolder within an existing folder module.
    """
    base_url = request.config.moodle_target.url
    sesskey = moodle.sesskey
    cmid = temporary_folder

    file_to_upload = next((p for p in ALL_FIXTURE_FILES if p.name == "scorm.zip"), None)
    if not file_to_upload:
        pytest.skip("scorm.zip fixture not found for subfolder test.")

    subfolder_path = "/scorms/"

    try:
        success, _ = add_file_to_folder(
            session=moodle,
            base_url=base_url,
            sesskey=sesskey,
            cmid=cmid,
            file_path=str(file_to_upload),
            subfolder=subfolder_path,
        )
    except MoodleFolderError as e:
        pytest.fail(f"add_file_to_folder failed with an exception: {e}")

    assert success is True, "add_file_to_folder should return True on success."
    time.sleep(1)

    # Verify using the robust list_folder_content method
    content = list_folder_content(moodle, base_url, cmid)
    assert file_to_upload.name in content
