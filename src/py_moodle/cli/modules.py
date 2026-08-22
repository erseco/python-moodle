"""Module-related commands for ``py-moodle``."""

from typing import Optional

import typer

from py_moodle.assign import MoodleAssignError, add_assign
from py_moodle.cli.feedback import error, status, success, upload_progress, warning
from py_moodle.cli.output import OutputFormat, emit, render_dry_run_plan
from py_moodle.label import MoodleLabelError, add_label, update_label
from py_moodle.module import (
    MoodleModuleError,
    delete_module,
    format_module_table,
    get_module_info,
)
from py_moodle.scorm import MoodleScormError, add_scorm
from py_moodle.session import MoodleSession

app = typer.Typer(
    help="Manage course modules (resources/activities) like labels, SCORMs, etc.",
    no_args_is_help=True,
)

add_app = typer.Typer(help="Add a new module to a course.", no_args_is_help=True)
app.add_typer(add_app, name="add")

edit_app = typer.Typer(
    help="Edit existing course modules (labels, SCORMs, etc.)", no_args_is_help=True
)
app.add_typer(edit_app, name="edit")


@app.command("delete")
def delete_a_module(
    ctx: typer.Context,
    cmid: int = typer.Argument(..., help="ID of the module (cmid) to delete."),
):
    """Delete any module by its course module ID."""
    ms = MoodleSession.get(ctx.obj["env"])

    warning(ctx, f"This will delete the module with cmid={cmid}.")
    if not typer.confirm("Are you sure? This action cannot be undone."):
        warning(ctx, "Operation cancelled.")
        raise typer.Exit()

    try:
        with status(ctx, f"Deleting module {cmid}..."):
            delete_module(ms.session, ms.settings.url, ms.sesskey, cmid)
        success(ctx, f"Module {cmid} deleted successfully.")
    except MoodleModuleError as e:
        error(ctx, f"Error deleting module: {e}")
        raise typer.Exit(1)


@app.command("show")
def show_a_module(
    ctx: typer.Context,
    cmid: int = typer.Argument(..., help="ID of the module (cmid) to show."),
    output: OutputFormat = typer.Option(
        OutputFormat.TABLE, "--output", help="Output format: table, json, or yaml."
    ),
):
    """Show detailed information for a specific module."""
    ms = MoodleSession.get(ctx.obj["env"])
    try:
        with status(ctx, f"Fetching module {cmid}...", output):
            module_info = get_module_info(ms.session, ms.settings.url, ms.sesskey, cmid)

        def _render_table(data):
            typer.echo(format_module_table(data))

        emit(module_info, output, table_fn=_render_table)

    except MoodleModuleError as e:
        error(ctx, f"Error getting module info: {e}")
        raise typer.Exit(1)


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
    """Add a new label to a course section."""
    ms = MoodleSession.get(ctx.obj["env"])
    try:
        with status(ctx, "Creating label..."):
            new_cmid = add_label(
                session=ms.session,
                base_url=ms.settings.url,
                sesskey=ms.sesskey,
                course_id=course_id,
                section_id=section_id,
                html=html,
                name=name,
            )
        success(ctx, f"Label created. New module ID (cmid): {new_cmid}")
    except MoodleLabelError as e:
        error(ctx, f"Error creating label: {e}")
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
    output: OutputFormat = typer.Option(
        OutputFormat.TABLE, "--output", help="Output format: table, json, or yaml."
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Preview the SCORM package that would be added without uploading it.",
    ),
):
    """Add a new SCORM package to a course section."""
    if dry_run:
        plan = {
            "action": "add_scorm",
            "dry_run": True,
            "target": {"course_id": course_id, "section_id": section_id},
            "parameters": {
                "name": name,
                "file_path": file_path.name,
                "intro": intro,
            },
        }
        render_dry_run_plan(plan, output)
        return

    ms = MoodleSession.get(ctx.obj["env"])
    try:
        with upload_progress(ctx, file_path.name, output_format=output) as progress_callback:
            new_cmid = add_scorm(
                session=ms.session,
                base_url=ms.settings.url,
                sesskey=ms.sesskey,
                course_id=course_id,
                section_id=section_id,
                name=name,
                file_path=file_path.name,
                intro=intro,
                progress_callback=progress_callback,
            )
        if output == OutputFormat.TABLE:
            success(ctx, f"SCORM package added. New module ID (cmid): {new_cmid}")
    except MoodleScormError as e:
        error(ctx, f"Error adding SCORM package: {e}")
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
    """Add a new assignment to a course section."""
    ms = MoodleSession.get(ctx.obj["env"])
    try:
        with status(ctx, "Creating assignment..."):
            new_cmid = add_assign(
                session=ms.session,
                base_url=ms.settings.url,
                sesskey=ms.sesskey,
                course_id=course_id,
                section_id=section_id,
                name=name,
                intro=intro,
            )
        success(
            ctx,
            f"Assignment '{name}' created. New module ID (cmid): {new_cmid}",
        )
    except MoodleAssignError as e:
        error(ctx, f"Error creating assignment: {e}")
        raise typer.Exit(1)


@edit_app.command("label")
def edit_a_label(
    ctx: typer.Context,
    cmid: int = typer.Argument(..., help="ID of the label module to edit."),
    html: Optional[str] = typer.Option(
        None, "--html", help="New HTML content of the label."
    ),
    name: Optional[str] = typer.Option(
        None, "--name", help="New internal name for the label."
    ),
    visible: Optional[int] = typer.Option(
        None, "--visible", help="Set visibility (1 for visible, 0 for hidden)."
    ),
):
    """Edit an existing label module."""
    ms = MoodleSession.get(ctx.obj["env"])

    if all(opt is None for opt in [html, name, visible]):
        warning(ctx, "Nothing to update. Provide at least one option to change.")
        raise typer.Exit()

    try:
        with status(ctx, f"Updating label {cmid}..."):
            updated = update_label(
                session=ms.session,
                base_url=ms.settings.url,
                cmid=cmid,
                html=html,
                name=name,
                visible=visible,
            )
        if updated:
            success(ctx, f"Label {cmid} updated successfully.")
    except MoodleLabelError as e:
        error(ctx, f"Error updating label: {e}")
        raise typer.Exit(1)


@app.command("list-types")
def list_available_module_types(
    ctx: typer.Context,
    course_id: int = typer.Option(
        1,
        "--course-id",
        help="Course ID to check available modules for. Defaults to 1.",
    ),
    output: OutputFormat = typer.Option(
        OutputFormat.TABLE, "--output", help="Output format: table, json, or yaml."
    ),
):
    """List module types that can be added to a course."""
    ms = MoodleSession.get(ctx.obj["env"])

    try:
        from rich.table import Table

        from py_moodle.module import get_module_types

        with status(ctx, "Fetching available module types...", output):
            module_types = get_module_types(
                ms.session, ms.settings.url, ms.sesskey, course_id
            )

        def _render_table(data):
            table = Table(
                title=f"Available Module Types in Course ID {course_id}",
                show_header=True,
                header_style="bold magenta",
            )
            table.add_column("Module ID", style="dim", width=12)
            table.add_column("Name (modname)", width=20)
            table.add_column("Title (Translated)", justify="left")

            for module in data:
                table.add_row(
                    str(module.get("id")),
                    f"[bold green]{module.get('name')}[/bold green]",
                    module.get("title"),
                )

            from py_moodle.cli.output import get_console

            get_console(ctx).print(table)

        emit(module_types, output, table_fn=_render_table)

    except MoodleModuleError as e:
        error(ctx, f"Error listing module types: {e}")
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
    """Edit the name of any module."""
    ms = MoodleSession.get(ctx.obj["env"])

    try:
        from py_moodle.module import rename_module_name

        with status(ctx, f"Renaming module {cmid}..."):
            renamed = rename_module_name(
                session=ms.session,
                base_url=ms.settings.url,
                sesskey=ms.sesskey,
                cmid=cmid,
                name=name,
            )
        if renamed:
            success(ctx, f"Module {cmid} renamed successfully to '{name}'.")

    except MoodleModuleError as e:
        error(ctx, f"Error renaming module: {e}")
        raise typer.Exit(1)


__all__ = ["app"]
