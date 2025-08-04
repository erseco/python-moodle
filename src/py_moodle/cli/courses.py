"""Course-related commands for ``py-moodle``."""

import json

import typer
from rich.console import Console
from rich.table import Table

from py_moodle.course import (
    MoodleCourseError,
    create_course,
    delete_course,
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
    json_flag: bool = typer.Option(
        False, "--json", help="Display output in JSON format."
    ),
):
    """
    Lists all available courses.
    """
    ms = MoodleSession.get(ctx.obj["env"])
    courses = list_courses(
        ms.session, ms.settings.url, token=ms.token, sesskey=ms.sesskey
    )

    if json_flag:
        typer.echo(json.dumps(courses, indent=2, ensure_ascii=False))
    else:
        table = Table("ID", "Shortname", "Fullname", "Category", "Visible")
        for course in courses:
            table.add_row(
                str(course.get("id", "")),
                course.get("shortname", ""),
                course.get("fullname", ""),
                str(course.get("categoryid", "")),
                str(course.get("visible", "")),
            )
        Console().print(table)


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
    json_flag: bool = typer.Option(False, "--json", help="Output in JSON format."),
):
    """
    Shows a detailed summary of a specific course, including its sections and modules.
    """
    ms = MoodleSession.get(ctx.obj["env"])

    try:
        course_data = get_course_with_sections_and_modules(
            ms.session, ms.settings.url, ms.sesskey, course_id, token=ms.token
        )

        if json_flag:
            typer.echo(json.dumps(course_data, indent=2, ensure_ascii=False))
        else:
            _print_course_summary_table(course_data)

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
):
    """
    Creates a new course.
    """
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


@app.command("delete")
def delete_a_course(
    ctx: typer.Context,
    course_id: int = typer.Argument(..., help="ID of the course to delete."),
    force: bool = typer.Option(
        False, "--force", help="Delete without asking for confirmation."
    ),
):
    """
    Deletes a course by its ID.
    """
    ms = MoodleSession.get(ctx.obj["env"])
    try:
        delete_course(ms.session, ms.settings.url, ms.sesskey, course_id, force=force)
        typer.echo(f"Course {course_id} deleted successfully.")
    except Exception as e:
        typer.echo(f"Error deleting course: {e}", err=True)
        raise typer.Exit(1)


__all__ = ["app"]
