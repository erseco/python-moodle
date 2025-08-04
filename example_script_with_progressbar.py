# example_script.py
"""
Example script to demonstrate the use of the py-moodle library for automation.

This script performs the following actions:
1.  Logs into the Moodle instance configured in your .env file.
2.  Creates a specified number of temporary courses.
3.  For each course, it demonstrates a wide range of content creation:
    - Adds multiple sections.
    - Adds HTML labels to a section.
    - Creates an 'assignment' activity.
    - Creates a 'SCORM' activity by uploading a package from local files.
    - Creates a 'folder' module.
    - Uploads multiple files of different types to the created folder.
    - Renames one of the uploaded files inside the folder.
4.  Shows a rich summary of the contents of each course created.
5.  Cleans up all created resources (courses and their contents) at the end.

This script is an ideal starting point for automating bulk course creation,
modification, or auditing tasks.

Prerequisites:
- A working `.env` file with Moodle credentials (see `.env.example`).
- The necessary dependencies installed (`pip install -r requirements.txt`).

To execute:
`python example_script.py`
"""
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    TextColumn,
    TimeElapsedColumn,
    TransferSpeedColumn,
)
from rich.table import Table

# Import all the necessary functions from the library
from py_moodle.assign import MoodleAssignError, add_assign
from py_moodle.course import create_course, delete_course, get_course
from py_moodle.folder import (
    MoodleFolderError,
    add_file_to_folder,
    add_folder,
    rename_file_in_folder,
)
from py_moodle.label import add_label
from py_moodle.scorm import MoodleScormError, add_scorm
from py_moodle.section import create_section
from py_moodle.session import MoodleSession, MoodleSessionError

# Load the environment variables from the .env file at the beginning of the script
load_dotenv()

# Script configuration
# You can change these values to create more or less content.
NUM_COURSES_TO_CREATE = 1  # Let's keep it to 1 to see all actions clearly
NUM_SECTIONS_TO_ADD = 2
NUM_LABELS_TO_ADD = 2
# Environment to use (must match a section in your .env file, e.g., [local])
MOODLE_ENV = "local"
# Path to fixture files for uploads. Assumes the script is run from the repo root.
FIXTURES_DIR = Path(__file__).parent / "tests" / "fixtures"
FILES_TO_UPLOAD_TO_FOLDER = ["sample.pdf", "test.jpg"]
SCORM_FILE_TO_UPLOAD = "scorm.zip"
FILE_TO_RENAME = "test.jpg"
NEW_FILENAME_FOR_RENAME = f"renamed_{int(time.time())}.jpg"


def print_course_summary(course_contents: list, course_name: str):
    """Prints a beautiful summary of the course contents using Rich."""
    console = Console()
    console.print(f"\n[bold cyan]Summary for course: '{course_name}'[/bold cyan]")

    table = Table(
        title="Course Contents", show_header=True, header_style="bold magenta"
    )
    table.add_column("Section ID", style="dim", width=12)
    table.add_column("Section Name", width=30)
    table.add_column("Modules", justify="left")

    for section in course_contents:
        section_id = str(section.get("id", "N/A"))
        section_name = section.get("name") or f"Section {section.get('section', 'N/A')}"

        modules_str = []
        for module in section.get("modules", []):
            mod_name = module.get("name", "Unnamed")
            mod_type = module.get("modname", "unknown")
            modules_str.append(
                f"  • [green]{mod_name}[/green] ([italic]{mod_type}[/italic])"
            )

        table.add_row(section_id, section_name, "\n".join(modules_str))

    console.print(table)


def main():
    """Main function of the script."""
    console = Console()
    console.print(
        f"[bold yellow]Starting test script for the environment '{MOODLE_ENV}'...[/bold yellow]"
    )

    if not FIXTURES_DIR.is_dir():
        console.print(
            f"[bold red]Error:[/bold red] Fixtures directory not found at '{FIXTURES_DIR}'"
        )
        console.print("Please make sure you have the 'tests/fixtures' directory.")
        return

    try:
        ms = MoodleSession.get(MOODLE_ENV)
        session = ms.session
        base_url = ms.settings.url
        sesskey = ms.sesskey
        token = ms.token
    except MoodleSessionError as e:
        console.print(f"[bold red]Error logging in:[/bold red] {e}")
        return

    created_course_ids = []

    # Create a reusable Progress object for all uploads
    progress = Progress(
        TextColumn("[bold blue]{task.description}", justify="right"),
        BarColumn(bar_width=None),
        "[progress.percentage]{task.percentage:>3.0f}%",
        "•",
        TransferSpeedColumn(),
        "•",
        TimeElapsedColumn(),
    )

    try:
        # Main loop: create courses and their content
        for i in range(NUM_COURSES_TO_CREATE):
            course_num = i + 1
            timestamp = int(time.time())
            fullname = f"API Test Course {course_num} - {timestamp}"
            shortname = f"API-TEST-{course_num}-{timestamp}"

            console.print(
                f"\n[bold]➡️  Step {course_num}.1: Creating course '{fullname}'...[/bold]"
            )
            course = create_course(
                session,
                base_url,
                sesskey,
                fullname=fullname,
                shortname=shortname,
                categoryid=1,
                numsections=1,
            )
            course_id = course["id"]
            created_course_ids.append(course_id)
            console.print(f"[green]✅ Course created with ID: {course_id}[/green]")

            course_contents = get_course(
                session, base_url, sesskey, course_id, token=token
            )
            first_section = next(
                (s for s in course_contents if s.get("section") == 1), None
            )
            if not first_section:
                console.print(
                    "[red]Error: Could not find the first thematic section.[/red]"
                )
                continue
            section_id_for_content = first_section["id"]

            console.print(
                f"[bold]➡️  Step {course_num}.2: Adding {NUM_SECTIONS_TO_ADD} sections...[/bold]"
            )
            for _ in range(NUM_SECTIONS_TO_ADD):
                new_section = create_section(session, base_url, sesskey, course_id)
                console.print(
                    f"  - Section added (ID: {new_section.get('fields', {}).get('id')})"
                )

            console.print(
                f"[bold]➡️  Step {course_num}.3: Adding {NUM_LABELS_TO_ADD} labels...[/bold]"
            )
            for j in range(NUM_LABELS_TO_ADD):
                html_content = f"<h3>Test Label #{j + 1}</h3><p>Auto-generated content for course '{shortname}'.</p>"
                cmid = add_label(
                    session,
                    base_url,
                    sesskey,
                    course_id,
                    section_id_for_content,
                    html_content,
                )
                console.print(
                    f"  - Label added (cmid: {cmid}) in section {section_id_for_content}"
                )

            console.print(
                f"[bold]➡️  Step {course_num}.4: Adding an assignment...[/bold]"
            )
            try:
                assign_cmid = add_assign(
                    session,
                    base_url,
                    sesskey,
                    course_id,
                    section_id_for_content,
                    name=f"Automated Assignment {timestamp}",
                    intro="Please submit your assignment here.",
                )
                console.print(f"  - Assignment added (cmid: {assign_cmid})")
            except MoodleAssignError as e:
                console.print(f"  - [red]Error adding assignment:[/red] {e}")
            console.print(
                f"[bold]➡️  Step {course_num}.5: Adding a SCORM package...[/bold]"
            )
            scorm_path = FIXTURES_DIR / SCORM_FILE_TO_UPLOAD
            if not scorm_path.exists():
                console.print(
                    f"  - [yellow]Warning: SCORM file not found at {scorm_path}, skipping.[/yellow]"
                )
            else:
                try:
                    with progress:
                        task_id = progress.add_task(
                            f"Uploading {scorm_path.name}",
                            total=os.path.getsize(scorm_path),
                        )

                        def scorm_callback(bytes_uploaded):
                            progress.update(task_id, advance=bytes_uploaded)

                        scorm_cmid = add_scorm(
                            session,
                            base_url,
                            sesskey,
                            course_id,
                            section_id_for_content,
                            name=f"Automated SCORM {timestamp}",
                            file_path=str(scorm_path),
                            progress_callback=scorm_callback,
                        )
                    console.print(f"  - SCORM package added (cmid: {scorm_cmid})")
                except MoodleScormError as e:
                    console.print(f"  - [red]Error adding SCORM:[/red] {e}")

            console.print(f"[bold]➡️  Step {course_num}.6: Managing a folder...[/bold]")
            try:
                console.print("  - Creating an empty folder...")
                empty_itemid = int(time.time() * 1000)
                folder_cmid = add_folder(
                    session,
                    base_url,
                    sesskey,
                    course_id,
                    section_id_for_content,
                    name=f"Test Folder {timestamp}",
                    files_itemid=empty_itemid,
                )
                console.print(f"    - Folder created (cmid: {folder_cmid})")
                time.sleep(1)
                console.print("  - Adding files to the folder...")
                with progress:
                    for filename in FILES_TO_UPLOAD_TO_FOLDER:
                        file_path = FIXTURES_DIR / filename
                        if not file_path.exists():
                            console.print(
                                f"    - [yellow]Warning: File {filename} not found, skipping.[/yellow]"
                            )
                            continue

                        task_id = progress.add_task(
                            f"Uploading {filename}", total=os.path.getsize(file_path)
                        )

                        def folder_callback(bytes_uploaded):
                            progress.update(task_id, advance=bytes_uploaded)

                        add_file_to_folder(
                            session,
                            base_url,
                            sesskey,
                            folder_cmid,
                            str(file_path),
                            progress_callback=folder_callback,
                        )
                        console.print(f"    - Added '{filename}'")
                        time.sleep(1)

                console.print("  - Renaming a file...")
                rename_file_in_folder(
                    session,
                    base_url,
                    sesskey,
                    folder_cmid,
                    old_filename=FILE_TO_RENAME,
                    new_filename=NEW_FILENAME_FOR_RENAME,
                )
                console.print(
                    f"    - Renamed '{FILE_TO_RENAME}' to '{NEW_FILENAME_FOR_RENAME}'"
                )

            except MoodleFolderError as e:
                console.print(f"  - [red]Error during folder management:[/red] {e}")

            console.print(
                f"[bold]➡️  Step {course_num}.7: Showing final course summary...[/bold]"
            )
            final_course_contents = get_course(
                session, base_url, sesskey, course_id, token=token
            )
            print_course_summary(final_course_contents, fullname)

    except Exception as e:
        console.print(f"\n[bold red]An error occurred during execution:[/bold red] {e}")
        console.print("The script will stop. Will attempt to clean up created courses.")

    finally:
        if created_course_ids:
            console.print("\n[bold yellow]--- Cleanup Phase ---[/bold yellow]")
            for course_id in created_course_ids:
                try:
                    console.print(f"🗑️  Deleting test course with ID: {course_id}...")
                    delete_course(session, base_url, sesskey, course_id, force=True)
                    console.print(
                        f"[green]  - Course {course_id} deleted successfully.[/green]"
                    )
                except Exception as e:
                    console.print(
                        f"[bold red]  - Error deleting course {course_id}:[/bold red] {e}"
                    )
            console.print("[bold yellow]Cleanup completed.[/bold yellow]")


if __name__ == "__main__":
    main()
