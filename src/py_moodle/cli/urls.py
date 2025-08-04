"""URL module commands for ``py-moodle``."""

import typer

from py_moodle.session import MoodleSession
from py_moodle.url import MoodleUrlError, add_url, delete_url

app = typer.Typer(
    help="Manage URL modules: create and delete external links.",
    no_args_is_help=True,
)


@app.command("add")
def add_a_url(
    ctx: typer.Context,
    course_id: int = typer.Option(
        ..., "--course-id", help="ID of the course to add the URL to."
    ),
    section_id: int = typer.Option(
        ..., "--section-id", help="ID of the section to add the URL to."
    ),
    name: str = typer.Option(..., "--name", help="Name/title of the URL."),
    url: str = typer.Option(..., "--url", help="The external URL to link."),
    intro: str = typer.Option("", "--intro", help="Introduction or description."),
):
    """Add a new URL module to a course section."""
    ms = MoodleSession.get(ctx.obj["env"])
    try:
        new_cmid = add_url(
            session=ms.session,
            base_url=ms.settings.url,
            sesskey=ms.sesskey,
            course_id=course_id,
            section_id=section_id,
            name=name,
            external_url=url,
            intro=intro,
        )
        typer.echo(
            f"URL '{name}' created successfully. New module ID (cmid): {new_cmid}"
        )
    except MoodleUrlError as e:
        typer.echo(f"Error creating URL: {e}", err=True)
        raise typer.Exit(1)


@app.command("delete")
def delete_a_url(
    ctx: typer.Context,
    cmid: int = typer.Argument(..., help="ID of the URL module (cmid) to delete."),
    force: bool = typer.Option(
        False, "--force", "-f", help="Delete without confirmation."
    ),
):
    """Delete a URL module from a course."""
    ms = MoodleSession.get(ctx.obj["env"])
    if not force:
        typer.confirm(
            f"Are you sure you want to delete URL with cmid {cmid}? This cannot be undone.",
            abort=True,
        )
    try:
        delete_url(ms.session, ms.settings.url, ms.sesskey, cmid)
        typer.echo(f"URL {cmid} deleted successfully.")
    except MoodleUrlError as e:
        typer.echo(f"Error deleting URL: {e}", err=True)
        raise typer.Exit(1)


__all__ = ["app"]
