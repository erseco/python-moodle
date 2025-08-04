"""Resource module commands for ``py-moodle``."""

import typer

from py_moodle.resource import MoodleResourceError, add_resource, delete_resource
from py_moodle.session import MoodleSession

app = typer.Typer(
    help="Manage resource modules: create and delete single-file resources.",
    no_args_is_help=True,
)


@app.command("add")
def add_a_resource(
    ctx: typer.Context,
    course_id: int = typer.Option(
        ..., "--course-id", help="ID of the course to add the resource to."
    ),
    section_id: int = typer.Option(
        ..., "--section-id", help="ID of the section to add the resource to."
    ),
    name: str = typer.Option(..., "--name", help="Name/title of the resource."),
    file: typer.FileText = typer.Option(
        ..., "--file", help="Path to the file to upload."
    ),
    intro: str = typer.Option(
        "", "--intro", help="Introduction or description for the resource."
    ),
):
    """Add a new resource (single file) to a course section."""
    ms = MoodleSession.get(ctx.obj["env"])
    try:
        new_cmid = add_resource(
            session=ms.session,
            base_url=ms.settings.url,
            sesskey=ms.sesskey,
            course_id=course_id,
            section_id=section_id,
            name=name,
            file_path=file.name,
            intro=intro,
        )
        typer.echo(
            f"Resource '{name}' created successfully. New module ID (cmid): {new_cmid}"
        )
    except MoodleResourceError as e:
        typer.echo(f"Error creating resource: {e}", err=True)
        raise typer.Exit(1)


@app.command("delete")
def delete_a_resource(
    ctx: typer.Context,
    cmid: int = typer.Argument(..., help="ID of the resource module (cmid) to delete."),
    force: bool = typer.Option(
        False, "--force", "-f", help="Delete without confirmation."
    ),
):
    """Delete a resource module from a course."""
    ms = MoodleSession.get(ctx.obj["env"])
    if not force:
        typer.confirm(
            f"Are you sure you want to delete resource with cmid {cmid}? This cannot be undone.",
            abort=True,
        )
    try:
        delete_resource(ms.session, ms.settings.url, ms.sesskey, cmid)
        typer.echo(f"Resource {cmid} deleted successfully.")
    except MoodleResourceError as e:
        typer.echo(f"Error deleting resource: {e}", err=True)
        raise typer.Exit(1)


__all__ = ["app"]
