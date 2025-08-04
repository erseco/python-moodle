"""Administrative commands for ``py-moodle``."""

import typer

from py_moodle.auth import LoginError, enable_webservice
from py_moodle.session import MoodleSession

app = typer.Typer(help="Moodle site administration tasks.")


@app.command("enable-webservice")
def enable_webservice_cmd(
    ctx: typer.Context,
    service_id: int = typer.Option(
        1,
        "--service-id",
        help="Web service ID to activate (default: 1 for 'Moodle mobile app').",
    ),
):
    """
    Activates a web service in Moodle. Requires administrator permissions.
    """
    ms = MoodleSession.get(ctx.obj["env"])

    typer.echo(
        f"You will attempt to activate web service with ID={service_id} at {ms.settings.url}."
    )
    if not typer.confirm(
        "This action requires administrator permissions. Do you want to continue?"
    ):
        typer.echo("Operation cancelled.")
        raise typer.Exit()

    try:
        success = enable_webservice(
            session=ms.session,
            base_url=ms.settings.url,
            sesskey=ms.sesskey,
            service_id=service_id,
        )
        if success:
            typer.echo(
                f"Web service {service_id} activated successfully. "
                "You should now be able to obtain a webservice token when logging in."
            )
    except LoginError as e:
        typer.echo(f"Error activating web service: {e}", err=True)
        raise typer.Exit(1)


__all__ = ["app"]
