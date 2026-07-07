"""Course-related commands for ``py-moodle``."""

from dataclasses import asdict

import typer
from rich.console import Console
from rich.table import Table

from py_moodle.cli.output import OutputFormat, emit, render_dry_run_plan
from py_moodle.course import (
    ConfirmationRequired,
    MoodleCourseError,
    create_course,
    delete_course,
    ensure_course,
    get_course_with_sections_and_modules,
    list_courses,
)
from py_moodle.session import MoodleSession

# Create a Typer "sub-app" for course commands
app = typer.Typer(help="Manage courses: list, show, create, delete.")


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """
    If `py-moodle courses` is called without a subcommand, show help.
    """
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit()


@app.command("list")
def list_all_courses(
    ctx: typer.Context,
    output: OutputFormat = typer.Option(
        OutputFormat.TABLE, "--output", help="Output format: table, json, or yaml."
    ),
):
    """
    Lists all available courses.
    """
    ms = MoodleSession.get(ctx.obj["env"])
    courses = list_courses(
        ms.session, ms.settings.url, token=ms.token, sesskey=ms.sesskey
    )

    def _render_table(data):
        table = Table("ID", "Shortname", "Fullname", "Category", "Visible")
        for course in data:
            table.add_row(
                str(course.get("id", "")),
                course.get("shortname", ""),
                course.get("fullname", ""),
                str(course.get("categoryid", "")),
                str(course.get("visible", "")),
            )
        Console().print(table)

    emit(courses, output, table_fn=_render_table)


def _print_course_summary_table(course_data: dict):
    """Prints a rich summary table of the course contents."""
    console = Console()

    # Print main course info
    console.print(
        f"\n[bold cyan]Course Summary: '{course_data.get('fullname')}' (ID: {course_data.get('id')})[/bold cyan]"
    )

    # Print sections and modules table
    table = Table(
        title="Course Contents", show_header=True, header_style="bold magenta"
    )
    table.add_column("Section ID", style="dim", width=12)
    table.add_column("Section Name", width=30)
    table.add_column("Modules (ID : Type)", justify="left")

    for section in course_data.get("sections", []):
        section_id = str(section.get("id", "N/A"))
        # Use section 'name' if available, otherwise build a default one
        section_name = section.get("name") or f"Section {section.get('section', 'N/A')}"

        modules_str_list = []
        for module in section.get("modules", []):
            mod_id = module.get("id", "N/A")
            mod_type = module.get("modname", "unknown")
            modules_str_list.append(f"  • {mod_id} : [green]{mod_type}[/green]")

        modules_str = (
            "\n".join(modules_str_list) if modules_str_list else "[dim]No modules[/dim]"
        )
        table.add_row(section_id, section_name, modules_str)

    console.print(table)


@app.command("show")
def show_course(
    ctx: typer.Context,
    course_id: int = typer.Argument(..., help="ID of the course to show."),
    output: OutputFormat = typer.Option(
        OutputFormat.TABLE, "--output", help="Output format: table, json, or yaml."
    ),
):
    """
    Shows a detailed summary of a specific course, including its sections and modules.
    """
    ms = MoodleSession.get(ctx.obj["env"])

    try:
        course_data = get_course_with_sections_and_modules(
            ms.session, ms.settings.url, ms.sesskey, course_id, token=ms.token
        )

        emit(course_data, output, table_fn=_print_course_summary_table)

    except MoodleCourseError as e:
        typer.echo(f"Error getting course details: {e}", err=True)
        raise typer.Exit(1)


@app.command("create")
def create_new_course(
    ctx: typer.Context,
    fullname: str = typer.Option(
        ..., "--fullname", help="Full name for the new course."
    ),
    shortname: str = typer.Option(
        ..., "--shortname", help="Short name for the new course."
    ),
    categoryid: int = typer.Option(
        1, "--categoryid", help="Category ID for the new course."
    ),
    visible: int = typer.Option(1, "--visible", help="1 for visible, 0 for hidden."),
    summary: str = typer.Option("", "--summary", help="Course summary."),
    output: OutputFormat = typer.Option(
        OutputFormat.TABLE, "--output", help="Output format: table, json, or yaml."
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Preview the course that would be created without calling Moodle.",
    ),
):
    """
    Creates a new course.
    """
    if dry_run:
        plan = {
            "action": "create_course",
            "dry_run": True,
            # The real course id is assigned by Moodle and cannot be known
            # before the request is actually sent.
            "target": {"course_id": "<assigned-by-moodle>"},
            "parameters": {
                "fullname": fullname,
                "shortname": shortname,
                "categoryid": categoryid,
                "visible": visible,
                "summary": summary,
            },
        }
        render_dry_run_plan(plan, output)
        return

    ms = MoodleSession.get(ctx.obj["env"])
    try:
        course = create_course(
            ms.session,
            ms.settings.url,
            ms.sesskey,
            fullname,
            shortname,
            categoryid,
            visible,
            summary,
        )
        typer.echo(
            f"Course created: {course['id']} - {course['fullname']} ({course['shortname']})"
        )
    except Exception as e:
        if "shortname" in str(e).lower() and "use" in str(e).lower():
            typer.echo(
                "Error: The short name is already in use. Please use a unique one.",
                err=True,
            )
            raise typer.Exit(1)
        else:
            typer.echo(f"Error creating course: {e}", err=True)
            raise typer.Exit(1)


def _render_ensure_table(data: dict) -> None:
    """Prints a rich summary table for an ``ensure_course`` result."""
    course = data.get("course") or {}
    table = Table("Status", "ID", "Shortname", "Fullname", "Category")
    table.add_row(
        str(data.get("status", "")),
        str(course.get("id", "")),
        str(course.get("shortname", "")),
        str(course.get("fullname", "")),
        str(course.get("categoryid", "")),
    )
    Console().print(table)

    differences = data.get("differences")
    if differences:
        diff_table = Table("Field", "Existing", "Requested", title="Conflicting fields")
        for field_name, values in differences.items():
            existing_value, requested_value = values
            diff_table.add_row(field_name, str(existing_value), str(requested_value))
        Console().print(diff_table)


@app.command("ensure")
def ensure_a_course(
    ctx: typer.Context,
    shortname: str = typer.Option(
        ..., "--shortname", help="Unique shortname to look up or create."
    ),
    fullname: str = typer.Option(
        ..., "--fullname", help="Desired full name of the course."
    ),
    category_id: int = typer.Option(..., "--category-id", help="Desired category ID."),
    update: bool = typer.Option(
        False,
        "--update/--no-update",
        help="Update fullname/category if the course already exists.",
    ),
    output: OutputFormat = typer.Option(
        OutputFormat.TABLE, "--output", help="Output format: table, json, or yaml."
    ),
):
    """
    Ensures a course with the given shortname exists (create if missing).
    """
    ms = MoodleSession.get(ctx.obj["env"])
    try:
        result = ensure_course(
            ms.session,
            ms.settings.url,
            ms.sesskey,
            shortname=shortname,
            fullname=fullname,
            category_id=category_id,
            token=ms.token,
            update=update,
        )
    except MoodleCourseError as e:
        typer.echo(f"Error ensuring course: {e}", err=True)
        raise typer.Exit(1)

    emit(asdict(result), output, table_fn=_render_ensure_table)
    if result.status == "conflict":
        raise typer.Exit(code=1)


@app.command("delete")
def delete_a_course(
    ctx: typer.Context,
    course_id: int = typer.Argument(..., help="ID of the course to delete."),
    force: bool = typer.Option(
        False, "--force", help="Delete without asking for confirmation."
    ),
    output: OutputFormat = typer.Option(
        OutputFormat.TABLE, "--output", help="Output format: table, json, or yaml."
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help=(
            "Preview the deletion without calling Moodle or prompting for "
            "confirmation."
        ),
    ),
):
    """
    Deletes a course by its ID.
    """
    if dry_run:
        plan = {
            "action": "delete_course",
            "dry_run": True,
            "target": {"course_id": course_id},
            "parameters": {"force": force},
        }
        render_dry_run_plan(plan, output)
        return

    ms = MoodleSession.get(ctx.obj["env"])
    try:
        delete_course(ms.session, ms.settings.url, ms.sesskey, course_id, force=force)
        typer.echo(f"Course {course_id} deleted successfully.")
    except ConfirmationRequired as e:
        confirm = typer.confirm(
            f"Are you sure you want to delete course '{e.course_title}' "
            f"(ID {e.course_id})?",
            default=False,
        )
        if not confirm:
            typer.echo("Aborted.")
            raise typer.Exit(0)
        delete_course(ms.session, ms.settings.url, ms.sesskey, course_id, force=True)
        typer.echo(f"Course {course_id} deleted successfully.")
    except MoodleCourseError as e:
        typer.echo(f"Error deleting course: {e}", err=True)
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"Error deleting course: {e}", err=True)
        raise typer.Exit(1)


__all__ = ["app"]
