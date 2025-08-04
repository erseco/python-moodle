# tests/test_upload.py
from pathlib import Path

import pytest

# Import the function and exception to test
from py_moodle.upload import MoodleUploadError, ProgressTracker, upload_file_webservice

# --- Fixtures ---


@pytest.fixture
def base_url(request):
    """Base URL of the Moodle instance, from conftest.py."""
    return request.config.moodle_target.url


@pytest.fixture
def token(moodle):
    """
    Webservice token. Essential for this test.
    If there is no token, the test is skipped.
    """
    if not moodle.webservice_token:
        pytest.skip("No webservice token available for upload tests. This is required.")
    return moodle.webservice_token


@pytest.fixture
def temp_text_file(tmp_path: Path) -> Path:
    """Creates a temporary text file for upload tests."""
    file_path = tmp_path / "test_upload_webservice.txt"
    file_path.write_text("This is a test file for the Moodle webservice upload.")
    return file_path


# --- Tests ---


def test_upload_file_webservice_success(base_url, token, temp_text_file):
    """
    Test the "happy path": upload a file with a valid token.
    Should return an integer itemid.
    """
    try:
        itemid = upload_file_webservice(
            base_url=base_url, token=token, file_path=str(temp_text_file)
        )
        assert isinstance(itemid, int)
        assert itemid > 0  # Draft itemids are large positive integers.
    except MoodleUploadError as e:
        pytest.fail(f"upload_file_webservice failed unexpectedly: {e}")


def test_upload_file_with_invalid_token(base_url, temp_text_file):
    """
    Test that upload fails with a MoodleUploadError if the token is invalid.
    """
    invalid_token = "thisisnotavalidtoken"

    with pytest.raises(MoodleUploadError) as excinfo:
        upload_file_webservice(
            base_url=base_url, token=invalid_token, file_path=str(temp_text_file)
        )

    # Verify that the Moodle error message (or our wrapper) is propagated.
    assert "Invalid token" in str(excinfo.value) or "invalidtoken" in str(excinfo.value)


def test_upload_non_existent_file(base_url, token):
    """
    Test that the function raises a MoodleUploadError if the local file does not exist.
    """
    non_existent_path = "path/to/a/file/that/does/not/exist.zip"

    with pytest.raises(MoodleUploadError, match="File not found"):
        upload_file_webservice(
            base_url=base_url, token=token, file_path=non_existent_path
        )


def test_progress_tracker_initialization(temp_text_file):
    """
    Verify that ProgressTracker initializes with the file size and zero progress.
    """
    tracker = ProgressTracker(str(temp_text_file))

    assert tracker.size == temp_text_file.stat().st_size
    assert tracker.read_so_far == 0
    assert tracker.callback is None


def test_progress_tracker_read_updates_progress(temp_text_file):
    """
    Verify that reading file chunks updates the 'read_so_far' counter.
    """
    tracker = ProgressTracker(str(temp_text_file))

    # Read in small chunks
    chunk1 = tracker.read(5)
    assert len(chunk1) == 5
    assert tracker.read_so_far == 5

    chunk2 = tracker.read(10)
    assert len(chunk2) == 10
    assert tracker.read_so_far == 15

    # Read the remaining bytes
    tracker.read()
    assert tracker.read_so_far == tracker.size


def test_progress_tracker_calls_callback(temp_text_file):
    """
    Verify that the callback is invoked with the correct number of bytes read.
    """
    progress_updates = []

    # Define a simple callback that appends bytes to a list
    def my_callback(bytes_read):
        progress_updates.append(bytes_read)

    tracker = ProgressTracker(str(temp_text_file), progress_callback=my_callback)

    # Read the file
    tracker.read(5)
    tracker.read(10)

    # Verify that the callback was called
    assert len(progress_updates) == 2, "The callback should have been called twice."
    assert progress_updates[0] == 5
    assert progress_updates[1] == 10
    assert sum(progress_updates) == 15  # Total bytes tracked by the callback
