"""Page module commands for ``py-moodle``."""

import typer

from py_moodle.page import MoodlePageError, add_page, delete_page
from py_moodle.session import MoodleSession

app = typer.Typer(
    help="Manage page modules: create and delete HTML pages.",
    no_args_is_help=True,
)


@app.command("add")
def add_a_page(
    ctx: typer.Context,
    course_id: int = typer.Option(
        ..., "--course-id", help="ID of the course to add the page to."
    ),
    section_id: int = typer.Option(
        ..., "--section-id", help="ID of the section to add the page to."
    ),
    name: str = typer.Option(..., "--name", help="Name/title of the page."),
    content_file: typer.FileText = typer.Option(
        ..., "--file", help="Path to a file containing the HTML content."
    ),
    intro: str = typer.Option(
        "", "--intro", help="Introduction or description for the page."
    ),
):
    """Add a new page module with HTML content to a course section."""
    ms = MoodleSession.get(ctx.obj["env"])
    try:
        content = content_file.read()
        new_cmid = add_page(
            session=ms.session,
            base_url=ms.settings.url,
            sesskey=ms.sesskey,
            course_id=course_id,
            section_id=section_id,
            name=name,
            content=content,
            intro=intro,
        )
        typer.echo(
            f"Page '{name}' created successfully. New module ID (cmid): {new_cmid}"
        )
    except MoodlePageError as e:
        typer.echo(f"Error creating page: {e}", err=True)
        raise typer.Exit(1)


@app.command("delete")
def delete_a_page(
    ctx: typer.Context,
    cmid: int = typer.Argument(..., help="ID of the page module (cmid) to delete."),
    force: bool = typer.Option(
        False, "--force", "-f", help="Delete without confirmation."
    ),
):
    """Delete a page module from a course."""
    ms = MoodleSession.get(ctx.obj["env"])
    if not force:
        typer.confirm(
            f"Are you sure you want to delete page with cmid {cmid}? This cannot be undone.",
            abort=True,
        )
    try:
        delete_page(ms.session, ms.settings.url, ms.sesskey, cmid)
        typer.echo(f"Page {cmid} deleted successfully.")
    except MoodlePageError as e:
        typer.echo(f"Error deleting page: {e}", err=True)
        raise typer.Exit(1)


__all__ = ["app"]
