# tests/test_draftfile.py
# tests/test_draftfile.py
import random
import time
from pathlib import Path

import pytest

from py_moodle.course import (
    MoodleCourseError,
    create_course,
    delete_course,
    get_course_context_id,
)
from py_moodle.draftfile import (
    MoodleDraftFileError,
    detect_upload_repo,
    list_draft_files,
    upload_file_to_draft_area,
)
from py_moodle.upload import MoodleUploadError, upload_file_webservice

# --- Fixtures ---


@pytest.fixture
def base_url(request):
    return request.config.moodle_target.url


@pytest.fixture
def token(moodle):
    if not moodle.webservice_token:
        pytest.skip("No webservice token available for draftfile tests.")
    return moodle.webservice_token


@pytest.fixture
def sesskey(moodle):
    if not moodle.sesskey:
        pytest.skip("No sesskey available for draftfile tests.")
    return moodle.sesskey


@pytest.fixture
def temp_text_file(tmp_path: Path) -> Path:
    """Creates a temporary text file for upload tests."""
    file_path = tmp_path / "test_upload.txt"
    file_path.write_text("This is a test file for py-moodle draft area.")
    return file_path


@pytest.fixture(scope="module")
def temporary_course_for_draftfile(request):
    """
    Creates a temporary course for all tests in this module and deletes it afterwards.
    """
    target = request.config.moodle_target
    from py_moodle.auth import login

    moodle_session = login(
        url=target.url, username=target.username, password=target.password
    )
    if not moodle_session.sesskey:
        pytest.skip(
            "Could not get sesskey to create a temporary course for draftfile tests."
        )

    base_url = target.url
    sesskey = moodle_session.sesskey
    fullname = f"Test Course For Draftfile {random.randint(1000, 9999)}"
    shortname = f"TCDF{random.randint(1000, 9999)}"

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
        pytest.skip(f"Could not create temporary course for draftfile tests: {e}")

    yield course

    # Teardown
    try:
        delete_course(moodle_session, base_url, sesskey, course["id"], force=True)
    except MoodleCourseError as e:
        print(
            f"\nWARNING: Could not clean up temporary course {course['id']}. Error: {e}"
        )


# --- Tests ---


def test_upload_and_list_draft_file(moodle, base_url, token, sesskey, temp_text_file):
    """
    Tests the full lifecycle of a draft file: upload and then list to verify.
    """
    # 1. Upload the file to the user's private draft area using the webservice
    try:
        draft_itemid = upload_file_webservice(
            base_url=base_url,
            token=token,
            file_path=str(temp_text_file),
        )
        assert isinstance(draft_itemid, int)
    except MoodleUploadError as e:
        pytest.fail(f"upload_file_webservice failed unexpectedly: {e}")

    # 2. List the files in that draft area to confirm the upload
    try:
        # Listing still requires a session-based method
        files_in_draft = list_draft_files(moodle, base_url, sesskey, draft_itemid)
    except MoodleDraftFileError as e:
        pytest.fail(f"list_draft_files failed unexpectedly: {e}")

    assert isinstance(files_in_draft, list)
    assert (
        len(files_in_draft) == 1
    ), "There should be exactly one file in the new draft area."

    uploaded_file_info = files_in_draft[0]
    assert uploaded_file_info.get("filename") == temp_text_file.name
    assert "url" in uploaded_file_info


def test_detect_upload_repo_scraping(moodle, request, temporary_course_for_draftfile):
    """
    Tests that the 'upload' repository ID can be correctly detected by scraping
    the course edit page.
    """
    base_url = request.config.moodle_target.url
    course_id = temporary_course_for_draftfile["id"]

    try:
        # Call the function we want to test
        repo_id = detect_upload_repo(
            session=moodle, base_url=base_url, course_id=course_id
        )

        # 1. Verify that the result is an integer
        assert isinstance(repo_id, int), "The returned repo_id should be an integer."

        # 2. In a standard Moodle installation, the upload repository ID is 5.
        #    This is a good check to ensure we are not getting a random value.
        assert repo_id == 5, "The detected repo_id for 'upload' should typically be 5."

    except MoodleDraftFileError as e:
        pytest.fail(f"detect_upload_repo failed with an exception: {e}")


def test_upload_file_handles_existing_file_by_renaming(
    moodle, request, temporary_course_for_draftfile, temp_text_file
):
    """
    Tests that uploading the same file twice results in Moodle renaming the second
    file, and our function correctly returns the new filename.
    """
    base_url = request.config.moodle_target.url
    sesskey = moodle.sesskey
    course_id = temporary_course_for_draftfile["id"]

    try:
        course_context_id = get_course_context_id(moodle, base_url, course_id)
    except Exception as e:
        pytest.fail(f"Could not get course context ID: {e}")

    test_itemid = int(time.time() * 1000)

    # 1. First upload: This should succeed and return the original filename.
    try:
        itemid1, filename1 = upload_file_to_draft_area(
            session=moodle,
            base_url=base_url,
            sesskey=sesskey,
            course_id=course_id,
            course_context_id=course_context_id,
            file_path=str(temp_text_file),
            itemid=test_itemid,
        )
        assert itemid1 == test_itemid
        assert filename1 == temp_text_file.name
    except MoodleDraftFileError as e:
        pytest.fail(f"The first file upload failed unexpectedly: {e}")

    # 2. Second upload: Should succeed and return a *new* filename.
    try:
        itemid2, filename2 = upload_file_to_draft_area(
            session=moodle,
            base_url=base_url,
            sesskey=sesskey,
            course_id=course_id,
            course_context_id=course_context_id,
            file_path=str(temp_text_file),
            itemid=test_itemid,
        )
        assert itemid2 == test_itemid
        assert filename2 != temp_text_file.name
        # The default renaming format is "filename (1).ext"
        expected_new_name_part = f"{temp_text_file.stem} (1)"
        assert expected_new_name_part in filename2
    except MoodleDraftFileError as e:
        pytest.fail(f"The second upload failed when it should have been handled: {e}")

    # 3. Verify that both files now exist in the draft area.
    files_in_draft = list_draft_files(moodle, base_url, sesskey, test_itemid)
    assert len(files_in_draft) == 2
    filenames_in_draft = {f["filename"] for f in files_in_draft}
    assert temp_text_file.name in filenames_in_draft
    assert filename2 in filenames_in_draft
