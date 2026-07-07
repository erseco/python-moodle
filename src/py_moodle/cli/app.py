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
    doctor,
    folders,
    modules,
    pages,
    resources,
    sections,
    site,
    urls,
    users,
)
from .output import configure_logging

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
    quiet: bool = typer.Option(
        False,
        "--quiet",
        "-q",
        help=(
            "Suppress incidental status output (banners, progress/confirmation "
            "messages). The command's primary result and any errors are still shown."
        ),
    ),
    no_color: bool = typer.Option(
        False,
        "--no-color",
        help=(
            "Disable ANSI colors in table output. The NO_COLOR environment "
            "variable is also respected."
        ),
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose (INFO-level) diagnostics on stderr.",
    ),
    debug: bool = typer.Option(
        False,
        "--debug",
        help=(
            "Enable debug-level diagnostics on stderr, including HTTP tracing "
            "from the authentication layer. Secret values are redacted."
        ),
    ),
):
    """
    Main callback for the Moodle CLI.
    Loads the environment and global output/diagnostic options and passes
    them to the subcommands via ``ctx.obj``.
    """
    ctx.ensure_object(dict)
    # Store the CLI-wide options in the context so subcommands can access them.
    ctx.obj = {
        "env": env,
        "quiet": quiet,
        "no_color": no_color,
        "verbose": verbose,
        "debug": debug,
    }
    configure_logging(verbose=verbose, debug=debug)


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
app.add_typer(site.app, name="site")
app.add_typer(doctor.app, name="doctor")

# ...and so on for each new command group you create.

__all__ = ["app"]
