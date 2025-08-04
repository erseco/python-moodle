"""Module-related commands for ``py-moodle``."""

import json
from typing import Optional

import typer

from py_moodle.assign import MoodleAssignError, add_assign
from py_moodle.label import MoodleLabelError, add_label, update_label

# Import functions from the library directly
from py_moodle.module import (
    MoodleModuleError,
    delete_module,
    format_module_table,
    get_module_info,
)
from py_moodle.scorm import MoodleScormError, add_scorm
from py_moodle.session import MoodleSession

# --- Main app for the "modules" command ---
app = typer.Typer(
    help="Manage course modules (resources/activities) like labels, SCORMs, etc.",
    no_args_is_help=True,
)

# --- Sub-app for the "add" command ---
add_app = typer.Typer(help="Add a new module to a course.", no_args_is_help=True)
app.add_typer(add_app, name="add")

# --- Sub-app for the "edit" command ---
edit_app = typer.Typer(
    help="Edit existing course modules (labels, SCORMs, etc.)", no_args_is_help=True
)
app.add_typer(edit_app, name="edit")


@app.command("delete")
def delete_a_module(
    ctx: typer.Context,
    cmid: int = typer.Argument(..., help="ID of the module (cmid) to delete."),
):
    """
    Deletes any module (label, SCORM, folder, etc.) by its ID.
    This uses the centralized delete function from the library.
    """
    ms = MoodleSession.get(ctx.obj["env"])

    typer.echo(f"This will delete the module with cmid={cmid}")
    if not typer.confirm("Are you sure? This action cannot be undone."):
        typer.echo("Operation cancelled.")
        raise typer.Exit()

    try:
        # The delete function is already centralized, no changes needed.
        delete_module(ms.session, ms.settings.url, ms.sesskey, cmid)
        typer.echo(f"Module {cmid} deleted successfully.")
    except MoodleModuleError as e:
        typer.echo(f"Error deleting module: {e}", err=True)
        raise typer.Exit(1)


@app.command("show")
def show_a_module(
    ctx: typer.Context,
    cmid: int = typer.Argument(..., help="ID of the module (cmid) to show."),
    json_flag: bool = typer.Option(False, "--json", help="Output in JSON format."),
):
    """
    Shows detailed information for a specific module.
    """
    ms = MoodleSession.get(ctx.obj["env"])
    try:
        # This function is also generic and doesn't need changes.
        module_info = get_module_info(ms.session, ms.settings.url, ms.sesskey, cmid)
        if json_flag:
            typer.echo(json.dumps(module_info, indent=2, ensure_ascii=False))
        else:
            table_str = format_module_table(module_info)
            typer.echo(table_str)

    except MoodleModuleError as e:
        typer.echo(f"Error getting module info: {e}", err=True)
        raise typer.Exit(1)


# --- Specific commands under "add" ---


@add_app.command("label")
def add_a_label_cmd(
    ctx: typer.Context,
    course_id: int = typer.Option(
        ..., "--course-id", help="ID of the course to add the label to."
    ),
    section_id: int = typer.Option(
        ..., "--section-id", help="ID of the section to add the label to."
    ),
    html: str = typer.Option(..., "--html", help="HTML content of the label."),
    name: str = typer.Option(
        "Label (from CLI)", "--name", help="Internal name for the label."
    ),
):
    """
    Adds a new label to a course section.
    """
    ms = MoodleSession.get(ctx.obj["env"])
    try:
        # --- KEY CHANGE ---
        # No longer calling a generic 'add_module' from the CLI.
        # Directly invoking the 'add_label' function from the library.
        new_cmid = add_label(
            session=ms.session,
            base_url=ms.settings.url,
            sesskey=ms.sesskey,
            course_id=course_id,
            section_id=section_id,
            html=html,
            name=name,
        )
        typer.echo(f"Label created successfully. New module ID (cmid): {new_cmid}")
    except MoodleLabelError as e:  # We use the module-specific error
        typer.echo(f"Error creating label: {e}", err=True)
        raise typer.Exit(1)


@add_app.command("scorm")
def add_a_scorm_cmd(
    ctx: typer.Context,
    course_id: int = typer.Option(
        ..., "--course-id", help="ID of the course to add the SCORM to."
    ),
    section_id: int = typer.Option(
        ..., "--section-id", help="ID of the section to add the SCORM to."
    ),
    name: str = typer.Option(..., "--name", help="Name of the SCORM package."),
    file_path: typer.FileText = typer.Option(
        ..., "--file", help="Path to the SCORM package .zip file."
    ),
    intro: str = typer.Option(
        "", "--intro", help="Introduction or description for the SCORM."
    ),
):
    """
    Adds a new SCORM package to a course section.
    """
    ms = MoodleSession.get(ctx.obj["env"])
    try:
        new_cmid = add_scorm(
            session=ms.session,
            base_url=ms.settings.url,
            sesskey=ms.sesskey,
            course_id=course_id,
            section_id=section_id,
            name=name,
            file_path=file_path.name,  # .name to get the file path
            intro=intro,
        )
        typer.echo(
            f"SCORM package added successfully. New module ID (cmid): {new_cmid}"
        )
    except MoodleScormError as e:  # We use the module-specific error
        typer.echo(f"Error adding SCORM package: {e}", err=True)
        raise typer.Exit(1)


@add_app.command("assign")
def add_an_assign_cmd(
    ctx: typer.Context,
    course_id: int = typer.Option(
        ..., "--course-id", help="ID of the course to add the assignment to."
    ),
    section_id: int = typer.Option(
        ..., "--section-id", help="ID of the section to add the assignment to."
    ),
    name: str = typer.Option(..., "--name", help="Name of the new assignment."),
    intro: str = typer.Option(
        "",
        "--intro",
        help="Introduction or description for the assignment (HTML supported).",
    ),
):
    """
    Adds a new assignment to a course section.
    """
    ms = MoodleSession.get(ctx.obj["env"])
    try:
        new_cmid = add_assign(
            session=ms.session,
            base_url=ms.settings.url,
            sesskey=ms.sesskey,
            course_id=course_id,
            section_id=section_id,
            name=name,
            intro=intro,
        )
        typer.echo(
            f"Assignment '{name}' created successfully. New module ID (cmid): {new_cmid}"
        )
    except MoodleAssignError as e:
        typer.echo(f"Error creating assignment: {e}", err=True)
        raise typer.Exit(1)


# UPDATED NOTE: To add support for "folder" or "file":
# 1. Create the `add_folder`, `add_file` functions in the library, following the pattern of calling `add_generic_module`.
# 2. Add a new command here: `@add_app.command("folder")` that calls `add_folder`.


@edit_app.command("label")
def edit_a_label(
    ctx: typer.Context,
    cmid: int = typer.Argument(..., help="ID of the label module to edit."),
    html: Optional[str] = typer.Option(
        None, "--html", help="New HTML content for the label."
    ),
    name: Optional[str] = typer.Option(
        None, "--name", help="New internal name for the label."
    ),
    visible: Optional[int] = typer.Option(
        None, "--visible", help="Set visibility (1 for visible, 0 for hidden)."
    ),
):
    """
    Edits an existing label module.
    """
    ms = MoodleSession.get(ctx.obj["env"])

    if all(opt is None for opt in [html, name, visible]):
        typer.echo(
            "Nothing to update. Please provide at least one option to change (e.g., --html)."
        )
        raise typer.Exit()

    try:
        success = update_label(
            session=ms.session,
            base_url=ms.settings.url,
            cmid=cmid,
            html=html,
            name=name,
            visible=visible,
        )
        if success:
            typer.echo(f"Label {cmid} updated successfully.")
    except MoodleLabelError as e:
        typer.echo(f"Error updating label: {e}", err=True)
        raise typer.Exit(1)


@app.command("list-types")
def list_available_module_types(
    ctx: typer.Context,
    course_id: int = typer.Option(
        1,
        "--course-id",
        help="Course ID to check available modules for. Defaults to 1.",
    ),
    json_flag: bool = typer.Option(False, "--json", help="Output in JSON format."),
):
    """
    Lists all available module types (activities/resources) that can be added to a course.
    """
    ms = MoodleSession.get(ctx.obj["env"])

    try:
        from rich.console import Console
        from rich.table import Table

        from py_moodle.module import get_module_types

        module_types = get_module_types(
            ms.session, ms.settings.url, ms.sesskey, course_id
        )

        if json_flag:
            typer.echo(json.dumps(module_types, indent=2, ensure_ascii=False))
        else:
            table = Table(
                title=f"Available Module Types in Course ID {course_id}",
                show_header=True,
                header_style="bold magenta",
            )
            table.add_column("Module ID", style="dim", width=12)
            table.add_column("Name (modname)", width=20)
            table.add_column("Title (Translated)", justify="left")

            for module in module_types:
                table.add_row(
                    str(module.get("id")),
                    f"[bold green]{module.get('name')}[/bold green]",
                    module.get("title"),
                )

            Console().print(table)

    except MoodleModuleError as e:
        typer.echo(f"Error listing module types: {e}", err=True)
        raise typer.Exit(1)


@edit_app.command("name")
def edit_module_name(
    ctx: typer.Context,
    cmid: int = typer.Argument(..., help="ID of the module (cmid) to rename."),
    name: str = typer.Option(
        ...,
        "--name",
        "-n",
        help="The new name for the module.",
    ),
):
    """
    Edits the name of any module (label, assign, SCORM, etc.).
    """
    ms = MoodleSession.get(ctx.obj["env"])

    try:
        from py_moodle.module import rename_module_name

        success = rename_module_name(
            session=ms.session,
            base_url=ms.settings.url,
            sesskey=ms.sesskey,
            cmid=cmid,
            name=name,
        )
        if success:
            typer.echo(f"Module {cmid} renamed successfully to '{name}'.")

    except MoodleModuleError as e:
        typer.echo(f"Error renaming module: {e}", err=True)
        raise typer.Exit(1)


__all__ = ["app"]
