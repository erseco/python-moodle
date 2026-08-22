"""Folder management commands for ``py-moodle``."""

import time
from pathlib import Path
from typing import List

import typer
from rich.table import Table

from py_moodle.cli.feedback import error, status, success, upload_progress, warning
from py_moodle.cli.output import get_console
from py_moodle.draftfile import MoodleDraftFileError, upload_file_to_draft_area
from py_moodle.folder import (
    MoodleFolderError,
    add_file_to_folder,
    add_folder,
    delete_file_from_folder,
    delete_folder,
    get_course_context_id,
    list_folder_content,
    rename_file_in_folder,
)
from py_moodle.session import MoodleSession

app = typer.Typer(
    help="Manage folder modules: create, delete, and manage their content.",
    no_args_is_help=True,
)


@app.command("add")
def add_a_folder(
    ctx: typer.Context,
    course_id: int = typer.Option(
        ..., "--course-id", help="ID of the course to add the folder to."
    ),
    section_id: int = typer.Option(
        ..., "--section-id", help="ID of the section to add the folder to."
    ),
    name: str = typer.Option(..., "--name", help="Name of the new folder."),
    intro: str = typer.Option(
        "",
        "--intro",
        help="Introduction or description for the folder (HTML supported).",
    ),
    files: List[typer.FileText] = typer.Option(
        None, "--file", help="Path to a file to include. Can be used multiple times."
    ),
):
    """Add a new folder to a course section, optionally with initial files."""
    ms = MoodleSession.get(ctx.obj["env"])
    files_itemid = int(time.time() * 1000)

    if files:
        try:
            with status(ctx, "Preparing folder upload..."):
                context_id = get_course_context_id(ms, course_id)

            for file_item in files:
                with upload_progress(ctx, file_item.name) as progress_callback:
                    upload_file_to_draft_area(
                        ms.session,
                        ms.settings.url,
                        ms.sesskey,
                        course_id,
                        context_id,
                        file_item.name,
                        itemid=files_itemid,
                        progress_callback=progress_callback,
                    )
            success(ctx, f"Uploaded {len(files)} file(s) to the folder draft area.")
        except (MoodleDraftFileError, MoodleFolderError) as e:
            error(ctx, f"Error during file upload: {e}")
            raise typer.Exit(1)

    try:
        with status(ctx, "Creating folder module..."):
            new_cmid = add_folder(
                session=ms.session,
                base_url=ms.settings.url,
                sesskey=ms.sesskey,
                course_id=course_id,
                section_id=section_id,
                name=name,
                intro_html=intro,
                files_itemid=files_itemid,
            )
        success(ctx, f"Folder '{name}' created. New module ID (cmid): {new_cmid}")
    except MoodleFolderError as e:
        error(ctx, f"Error creating folder: {e}")
        raise typer.Exit(1)


@app.command("delete")
def delete_a_folder(
    ctx: typer.Context,
    cmid: int = typer.Argument(..., help="ID of the folder module (cmid) to delete."),
    force: bool = typer.Option(
        False, "--force", "-f", help="Delete without confirmation."
    ),
):
    """Delete a folder module from a course."""
    ms = MoodleSession.get(ctx.obj["env"])
    if not force:
        typer.confirm(
            f"Are you sure you want to delete folder with cmid {cmid}? This cannot be undone.",
            abort=True,
        )

    try:
        with status(ctx, f"Deleting folder {cmid}..."):
            delete_folder(ms.session, ms.settings.url, ms.sesskey, cmid)
        success(ctx, f"Folder {cmid} deleted successfully.")
    except MoodleFolderError as e:
        error(ctx, f"Error deleting folder: {e}")
        raise typer.Exit(1)


@app.command("list-content")
def list_folder_files(
    ctx: typer.Context,
    cmid: int = typer.Argument(..., help="ID of the folder module (cmid) to inspect."),
):
    """List the files and subdirectories inside a folder."""
    ms = MoodleSession.get(ctx.obj["env"])
    console = get_console(ctx)
    try:
        with status(ctx, "Fetching folder content..."):
            content = list_folder_content(ms.session, ms.settings.url, cmid)

        table = Table(
            title=f"Content of Folder (cmid: {cmid})",
            show_header=True,
            header_style="bold magenta",
        )
        table.add_column("Filename", style="cyan")

        if not content:
            warning(ctx, f"Folder {cmid} is empty.")
            return

        for item in content:
            table.add_row(item)

        console.print(table)

    except MoodleFolderError as e:
        error(ctx, f"Error listing folder content: {e}")
        raise typer.Exit(1)


@app.command("add-file")
def add_file(
    ctx: typer.Context,
    cmid: int = typer.Option(
        ..., "--cmid", help="ID of the folder to add the file to."
    ),
    file_path: typer.FileText = typer.Option(
        ..., "--file", help="Path of the local file to upload."
    ),
    subfolder: str = typer.Option(
        "/",
        "--subfolder",
        help="Path to the subfolder inside the Moodle folder (e.g., '/scorms/'). Must start and end with '/'.",
    ),
):
    """Add a file to an existing folder."""
    ms = MoodleSession.get(ctx.obj["env"])
    try:
        with upload_progress(ctx, file_path.name) as progress_callback:
            uploaded, final_filename = add_file_to_folder(
                ms.session,
                ms.settings.url,
                ms.sesskey,
                cmid,
                file_path.name,
                subfolder=subfolder,
                progress_callback=progress_callback,
            )

        if uploaded:
            original_filename = Path(file_path.name).name
            if final_filename != original_filename:
                warning(
                    ctx,
                    f"File '{original_filename}' already existed and was uploaded as "
                    f"'{final_filename}' to folder {cmid}.",
                )
            else:
                success(
                    ctx,
                    f"File '{original_filename}' added successfully to folder {cmid}.",
                )

    except MoodleFolderError as e:
        error(ctx, f"Error adding file: {e}")
        raise typer.Exit(1)


@app.command("delete-file")
def delete_file(
    ctx: typer.Context,
    cmid: int = typer.Option(
        ..., "--cmid", help="ID of the folder containing the file."
    ),
    filename: str = typer.Option(
        ..., "--filename", help="Name of the file to delete from the folder."
    ),
    force: bool = typer.Option(
        False, "--force", "-f", help="Delete without confirmation."
    ),
):
    """Delete a file from an existing folder."""
    ms = MoodleSession.get(ctx.obj["env"])
    if not force:
        typer.confirm(
            f"Are you sure you want to delete '{filename}' from folder {cmid}?",
            abort=True,
        )

    try:
        with status(ctx, f"Deleting '{filename}'..."):
            delete_file_from_folder(
                ms.session, ms.settings.url, ms.sesskey, cmid, filename
            )
        success(ctx, f"File '{filename}' deleted successfully from folder {cmid}.")
    except MoodleFolderError as e:
        error(ctx, f"Error deleting file: {e}")
        raise typer.Exit(1)


@app.command("rename-file")
def rename_file(
    ctx: typer.Context,
    cmid: int = typer.Option(
        ..., "--cmid", help="ID of the folder containing the file."
    ),
    old_name: str = typer.Option(
        ..., "--old-name", help="The current name of the file."
    ),
    new_name: str = typer.Option(..., "--new-name", help="The new name for the file."),
):
    """Rename a file inside an existing folder."""
    ms = MoodleSession.get(ctx.obj["env"])
    try:
        with status(ctx, f"Renaming '{old_name}'..."):
            rename_file_in_folder(
                ms.session, ms.settings.url, ms.sesskey, cmid, old_name, new_name
            )
        success(
            ctx,
            f"File renamed from '{old_name}' to '{new_name}' in folder {cmid}.",
        )
    except MoodleFolderError as e:
        error(ctx, f"Error renaming file: {e}")
        raise typer.Exit(1)


__all__ = ["app"]
