"""Section management commands for ``py-moodle``."""

import json

import typer
from rich.box import SQUARE
from rich.console import Console
from rich.table import Table

# Import the new centralized function and corresponding error
from py_moodle.course import MoodleCourseError, get_course_with_sections_and_modules

# Keep the action functions (create/delete) that are still valid
from py_moodle.section import create_section, delete_section
from py_moodle.session import MoodleSession

# Create a Typer "sub-app" for section commands
app = typer.Typer(help="Manage course sections: list, show, create, delete.")


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """
    If `py-moodle sections` is called without a subcommand, show help.
    """
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit()


@app.command("list")
def list_course_sections(
    ctx: typer.Context,
    course_id: int = typer.Option(
        ..., "--course-id", help="ID of the course to list sections from."
    ),
    json_flag: bool = typer.Option(
        False, "--json", help="Display output in JSON format."
    ),
):
    """
    Lists a summary of all sections in a specific course.
    """
    ms = MoodleSession.get(ctx.obj["env"])
    try:
        # Use the new centralized function to get all course information
        course_data = get_course_with_sections_and_modules(
            ms.session, ms.settings.url, ms.sesskey, course_id, token=ms.token
        )
        sections = course_data.get("sections", [])

        if json_flag:
            typer.echo(json.dumps(sections, indent=2, ensure_ascii=False))
        else:
            table = Table(
                title=f"Sections in Course: '{course_data.get('fullname')}'",
                show_header=True,
                header_style="bold magenta",
            )
            table.add_column("ID", style="dim", width=10)
            table.add_column("Position", width=10)
            table.add_column("Name", width=40)
            table.add_column("Modules (Count)", justify="center")
            table.add_column("Visible", justify="center")

            for section in sections:
                # Visibility is found in the main section object
                visible_text = (
                    "[green]Yes[/green]"
                    if section.get("visible", True)
                    else "[red]No[/red]"
                )
                table.add_row(
                    str(section.get("id", "N/A")),
                    str(section.get("section", "N/A")),
                    section.get("name") or f"Section {section.get('section', '')}",
                    str(len(section.get("modules", []))),
                    visible_text,
                )
            Console().print(table)

    except MoodleCourseError as e:
        typer.echo(f"Error listing sections: {e}", err=True)
        raise typer.Exit(1)


@app.command("show")
def show_section_details(
    ctx: typer.Context,
    section_id: int = typer.Argument(..., help="ID of the section to show."),
    course_id: int = typer.Option(
        ..., "--course-id", help="ID of the course the section belongs to."
    ),
    json_flag: bool = typer.Option(False, "--json", help="Output in JSON format."),
):
    """
    Shows detailed information of a specific section, including its modules.
    """
    ms = MoodleSession.get(ctx.obj["env"])
    try:
        # Get the entire course structure to find our section
        course_data = get_course_with_sections_and_modules(
            ms.session, ms.settings.url, ms.sesskey, course_id, token=ms.token
        )

        # Search for the specific section by its ID
        target_section = next(
            (
                s
                for s in course_data.get("sections", [])
                if int(s.get("id")) == (section_id)
            ),
            None,
        )

        if not target_section:
            typer.echo(
                f"Error: Section with ID {section_id} not found in course {course_id}.",
                err=True,
            )
            raise typer.Exit(1)

        if json_flag:
            typer.echo(json.dumps(target_section, indent=2, ensure_ascii=False))
        else:
            console = Console()
            section_name = (
                target_section.get("name") or f"Section {target_section.get('section')}"
            )
            console.print(
                f"\n[bold cyan]Details for Section: '{section_name}'[/bold cyan]"
            )

            # Section details table
            details_table = Table(box=SQUARE, show_header=False)
            details_table.add_column("Field", style="dim")
            details_table.add_column("Value")
            details_table.add_row("ID", str(target_section.get("id")))
            details_table.add_row("Position", str(target_section.get("section")))
            details_table.add_row(
                "Visible",
                (
                    "[green]Yes[/green]"
                    if target_section.get("visible", True)
                    else "[red]No[/red]"
                ),
            )
            # The summary may contain HTML, so we show it as is.
            summary = target_section.get("summary", "[dim]No summary[/dim]")
            details_table.add_row(
                "Summary", summary if summary.strip() else "[dim]No summary[/dim]"
            )
            console.print(details_table)

            # Module table within the section
            modules = target_section.get("modules", [])
            modules_table = Table(
                title="Modules in this Section", header_style="bold magenta"
            )
            modules_table.add_column("Module ID (cmid)", style="dim")
            modules_table.add_column("Module Name")
            modules_table.add_column("Module Type")

            if not modules:
                console.print("[italic]This section contains no modules.[/italic]")
            else:
                for module in modules:
                    modules_table.add_row(
                        str(module.get("id", "N/A")),
                        module.get("name", "N/A"),
                        f"[green]{module.get('modname', 'unknown')}[/green]",
                    )
                console.print(modules_table)

    except MoodleCourseError as e:
        typer.echo(f"Error showing section details: {e}", err=True)
        raise typer.Exit(1)


@app.command("create")
def create_new_section(
    ctx: typer.Context,
    course_id: int = typer.Option(
        ..., "--course-id", help="ID of the course where to create the section."
    ),
):
    """
    Creates a new section at the end of a course.
    """
    ms = MoodleSession.get(ctx.obj["env"])
    try:
        new_section_event = create_section(
            ms.session, ms.settings.url, ms.sesskey, course_id
        )
        # The create section response is complex, extract the ID if possible
        new_section_id = new_section_event.get("fields", {}).get("id")
        typer.echo(f"Section created successfully. New section ID: {new_section_id}")
    except MoodleCourseError as e:  # Keep the specific error if relevant
        typer.echo(f"Error creating section: {e}", err=True)
        raise typer.Exit(1)


@app.command("delete")
def delete_a_section(
    ctx: typer.Context,
    course_id: int = typer.Option(
        ..., "--course-id", help="ID of the course the section belongs to."
    ),
    section_id: int = typer.Argument(..., help="ID of the section to delete."),
):
    """
    Deletes a specific section by its ID.
    """
    ms = MoodleSession.get(ctx.obj["env"])

    confirm = typer.confirm(
        f"Are you sure you want to delete section {section_id} from course {course_id}?"
    )
    if not confirm:
        typer.echo("Operation cancelled.")
        raise typer.Exit()

    try:
        delete_section(ms.session, ms.settings.url, ms.sesskey, course_id, section_id)
        typer.echo(f"Section {section_id} deleted successfully.")
    except MoodleCourseError as e:
        typer.echo(f"Error deleting section: {e}", err=True)
        raise typer.Exit(1)


__all__ = ["app"]
