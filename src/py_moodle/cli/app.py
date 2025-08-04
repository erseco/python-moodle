"""Command line interface application for ``py-moodle``.

This module initializes the Typer application and aggregates all
sub-command applications. It is imported by :mod:`py_moodle.__main__`
to provide a single entry point for the CLI.
"""

import typer
from dotenv import load_dotenv

from . import (
    admin,
    categories,
    courses,
    folders,
    modules,
    pages,
    resources,
    sections,
    urls,
    users,
)

load_dotenv()

app = typer.Typer(
    help="A CLI to manage Moodle via AJAX sessions and web services.",
    # With this setting, subcommands are required.
    context_settings={"help_option_names": ["-h", "--help"]},
    no_args_is_help=True,
)


@app.callback()
def main(
    ctx: typer.Context,
    env: str = typer.Option(
        "local",
        "--env",
        "-e",
        help="Environment to use: local | staging | prod (also respects MOODLE_ENV)",
    ),
):
    """
    Main callback for the Moodle CLI.
    Loads the environment and passes it to the subcommands.
    """
    ctx.ensure_object(dict)
    # Store the 'env' in the context so subcommands can access it.
    ctx.obj = {"env": env}


# Add commands from other files to the main app
app.add_typer(courses.app, name="courses")
app.add_typer(categories.app, name="categories")
app.add_typer(sections.app, name="sections")
app.add_typer(modules.app, name="modules")
app.add_typer(users.app, name="users")
app.add_typer(admin.app, name="admin")
app.add_typer(folders.app, name="folders")
app.add_typer(pages.app, name="pages")
app.add_typer(resources.app, name="resources")
app.add_typer(urls.app, name="urls")

# ...and so on for each new command group you create.

__all__ = ["app"]
