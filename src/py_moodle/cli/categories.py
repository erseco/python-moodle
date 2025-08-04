"""Category management commands for ``py-moodle``."""

import json

import typer
from rich.console import Console
from rich.table import Table

from py_moodle.category import (
    MoodleCategoryError,
    create_category,
    delete_category,
    list_categories,
)
from py_moodle.session import MoodleSession

app = typer.Typer(help="Manage course categories: list, create, delete.")


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """
    If `py-moodle categories` is called without a subcommand, show the help message.
    """
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit()


@app.command("list")
def list_all_categories(
    ctx: typer.Context,
    json_flag: bool = typer.Option(False, "--json", help="Output in JSON format."),
):
    """
    Lists all available course categories.
    """
    ms = MoodleSession.get(ctx.obj["env"])
    # Listing categories typically requires a webservice token.
    if not ms.token:
        typer.echo(
            "Error: A webservice token is required to list categories. Check your configuration.",
            err=True,
        )
        raise typer.Exit(1)

    try:
        categories = list_categories(ms.session, ms.settings.url, ms.token)
        if json_flag:
            typer.echo(json.dumps(categories, indent=2, ensure_ascii=False))
        else:
            table = Table("ID", "Name", "Parent ID", "Course Count")
            for category in categories:
                table.add_row(
                    str(category.get("id", "")),
                    category.get("name", ""),
                    str(category.get("parent", "")),
                    str(category.get("coursecount", "")),
                )
            Console().print(table)
    except MoodleCategoryError as e:
        typer.echo(f"Error listing categories: {e}", err=True)
        raise typer.Exit(1)


@app.command("create")
def create_new_category(
    ctx: typer.Context,
    name: str = typer.Option(..., "--name", help="Name for the new category."),
    parent_id: int = typer.Option(
        0, "--parent-id", help="Parent category ID (default: 0 for top level)."
    ),
):
    """
    Creates a new course category.
    This operation uses a session key (sesskey) and does not require a webservice token.
    """
    ms = MoodleSession.get(ctx.obj["env"])
    if not ms.sesskey:
        typer.echo(
            "Error: A session key (sesskey) is required to create a category.", err=True
        )
        raise typer.Exit(1)

    try:
        new_category = create_category(
            session=ms.session,
            base_url=ms.settings.url,
            sesskey=ms.sesskey,
            name=name,
            parent=parent_id,
        )
        typer.echo(
            f"Category '{new_category['name']}' created successfully. New category ID: {new_category['id']}"
        )
    except (MoodleCategoryError, ValueError) as e:
        typer.echo(f"Error creating category: {e}", err=True)
        raise typer.Exit(1)


@app.command("delete")
def delete_a_category(
    ctx: typer.Context,
    category_id: int = typer.Argument(..., help="ID of the category to delete."),
    force: bool = typer.Option(
        False, "--force", help="Delete without a confirmation prompt."
    ),
):
    """
    Deletes a course category by its ID. The category must be empty.
    This operation uses a session key (sesskey).
    """
    ms = MoodleSession.get(ctx.obj["env"])
    if not ms.sesskey:
        typer.echo(
            "Error: A session key (sesskey) is required to delete a category.", err=True
        )
        raise typer.Exit(1)

    if not force:
        confirm = typer.confirm(
            f"Are you sure you want to delete category {category_id}? This can only be done if the category is empty."
        )
        if not confirm:
            typer.echo("Operation cancelled.")
            raise typer.Exit()

    try:
        deleted = delete_category(
            session=ms.session,
            base_url=ms.settings.url,
            sesskey=ms.sesskey,
            categoryid=category_id,
        )
        if deleted:
            typer.echo(f"Category {category_id} deleted successfully.")
        else:
            # This case might not be reached if an exception is thrown, but it's good practice.
            typer.echo(
                f"Failed to delete category {category_id}. It might not be empty or you may lack permissions.",
                err=True,
            )
    except (MoodleCategoryError, ValueError) as e:
        typer.echo(f"Error deleting category: {e}", err=True)
        raise typer.Exit(1)


__all__ = ["app"]
