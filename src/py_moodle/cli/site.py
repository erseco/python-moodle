"""Site commands for ``py-moodle``."""

import json

import typer
from rich.console import Console
from rich.table import Table

from py_moodle.session import MoodleSession
from py_moodle.site import get_site_info

app = typer.Typer(help="Get site information.")
console = Console()


@app.command("info")
def info(
    ctx: typer.Context,
    as_json: bool = typer.Option(False, "--json", help="Output as JSON."),
):
    """Get site info."""
    ms = MoodleSession.get(ctx.obj["env"])
    site_info = get_site_info(ms)

    if as_json:
        # We need to handle the dataclasses in the site_info object
        # to make them serializable.
        class DataclassEncoder(json.JSONEncoder):
            def default(self, o):
                from dataclasses import asdict, is_dataclass

                if is_dataclass(o):
                    return asdict(o)
                return super().default(o)

        console.print(
            json.dumps(site_info, indent=4, cls=DataclassEncoder, ensure_ascii=False)
        )
        return

    table = Table(title="Site Info")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="magenta")

    for key, value in site_info.__dict__.items():
        if isinstance(value, list):
            table.add_row(key, str(len(value)) + " items")
        else:
            table.add_row(key, str(value))

    console.print(table)


__all__ = ["app"]
