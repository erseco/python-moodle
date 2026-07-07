"""User management commands for ``py-moodle``."""

import typer
from rich.table import Table

from py_moodle.cli.output import OutputFormat, emit, get_console
from py_moodle.session import MoodleSession
from py_moodle.user import MoodleUserError, create_user, delete_user, list_course_users

app = typer.Typer(help="Manage Moodle users: list, create, delete.")

# CSV column definitions mirroring the fields shown by _render_table below.
_LIST_CSV_FIELDS = [
    ("ID", "id"),
    ("Full Name", "fullname"),
    ("Email", "email"),
]


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit()


@app.command("list")
def list_users_in_course(
    ctx: typer.Context,
    course_id: int = typer.Option(
        ..., "--course-id", help="ID of the course to list users from."
    ),
    output: OutputFormat = typer.Option(
        OutputFormat.TABLE,
        "--output",
        help="Output format: table, json, yaml, or csv.",
    ),
):
    """Lists users enrolled in a specific course."""
    ms = MoodleSession.get(ctx.obj["env"])
    if not ms.token:
        typer.echo(
            "Error: A webservice token is required for this operation.", err=True
        )
        raise typer.Exit(1)

    try:
        users = list_course_users(ms.session, ms.settings.url, ms.token, course_id)

        def _render_table(data):
            table = Table("ID", "Full Name", "Email")
            for user in data:
                table.add_row(
                    str(user.get("id", "")),
                    user.get("fullname", ""),
                    user.get("email", ""),
                )
            get_console(ctx).print(table)

        emit(users, output, table_fn=_render_table, csv_fields=_LIST_CSV_FIELDS)
    except MoodleUserError as e:
        typer.echo(f"Error listing users: {e}", err=True)
        raise typer.Exit(1)


@app.command("create")
def create_new_user(
    ctx: typer.Context,
    username: str = typer.Option(..., help="Username (must be unique)."),
    password: str = typer.Option(..., help="Password (must meet site policy)."),
    firstname: str = typer.Option(..., help="First name."),
    lastname: str = typer.Option(..., help="Last name."),
    email: str = typer.Option(..., help="Email address (must be unique)."),
):
    """Creates a new user in Moodle."""
    ms = MoodleSession.get(ctx.obj["env"])
    if not ms.token and not ms.sesskey:
        typer.echo(
            "Error: A webservice token or sesskey is required for this operation.",
            err=True,
        )
        raise typer.Exit(1)

    try:
        new_user = create_user(
            ms.session,
            ms.settings.url,
            ms.token,
            username,
            password,
            firstname,
            lastname,
            email,
            sesskey=ms.sesskey,
        )
        if not ctx.obj.get("quiet"):
            typer.echo(
                f"User created successfully. ID: {new_user['id']}, Username: {new_user['username']}"
            )
    except MoodleUserError as e:
        typer.echo(f"Error creating user: {e}", err=True)
        raise typer.Exit(1)


@app.command("delete")
def delete_a_user(
    ctx: typer.Context,
    user_id: int = typer.Argument(..., help="ID of the user to delete."),
    force: bool = typer.Option(
        False, "--force", help="Delete without asking for confirmation."
    ),
):
    """Deletes a user from Moodle by their ID."""
    ms = MoodleSession.get(ctx.obj["env"])
    if not ms.token and not ms.sesskey:
        typer.echo(
            "Error: A webservice token or sesskey is required for this operation.",
            err=True,
        )
        raise typer.Exit(1)

    if not force:
        confirm = typer.confirm(
            f"Are you sure you want to delete the user with ID {user_id}? This action cannot be undone."
        )
        if not confirm:
            typer.echo("Operation cancelled.")
            raise typer.Exit()

    try:
        delete_user(ms.session, ms.settings.url, ms.token, user_id, sesskey=ms.sesskey)
        if not ctx.obj.get("quiet"):
            typer.echo(f"User {user_id} deleted successfully.")
    except MoodleUserError as e:
        typer.echo(f"Error deleting user: {e}", err=True)
        raise typer.Exit(1)


__all__ = ["app"]
