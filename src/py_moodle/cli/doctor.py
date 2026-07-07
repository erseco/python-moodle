"""Diagnostics command for py-moodle."""

import typer
from rich.console import Console
from rich.table import Table

from py_moodle.cli.output import OutputFormat, emit
from py_moodle.doctor import CheckStatus, run_diagnostics

app = typer.Typer(help="Diagnose connectivity, credentials, and session health.")

_STATUS_STYLE = {
    CheckStatus.PASS: "green",
    CheckStatus.WARN: "yellow",
    CheckStatus.FAIL: "red",
}


def _render_table(checks) -> None:
    """Render the diagnostic checks as a rich table.

    Args:
        checks: List of ``{"name", "status", "message"}`` dicts, as returned
            by ``DoctorReport.as_dicts()``.
    """
    table = Table("Check", "Status", "Message")
    for check in checks:
        style = _STATUS_STYLE.get(CheckStatus(check["status"]), "")
        status_text = check["status"]
        if style:
            status_text = f"[{style}]{status_text}[/{style}]"
        table.add_row(check["name"], status_text, check["message"])
    Console().print(table)


@app.command("run")
def run_cmd(
    ctx: typer.Context,
    output: OutputFormat = typer.Option(
        OutputFormat.TABLE, "--output", "-o", help="Output format."
    ),
) -> None:
    """Run all diagnostic checks for the selected --env and report status."""
    env = ctx.obj["env"]
    try:
        report = run_diagnostics(env)
    except ValueError as exc:
        typer.echo(f"Configuration error: {exc}", err=True)
        raise typer.Exit(2)

    emit(report.as_dicts(), output, table_fn=_render_table)

    raise typer.Exit(report.exit_code)


__all__ = ["app"]
