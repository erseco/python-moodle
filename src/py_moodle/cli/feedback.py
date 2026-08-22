"""Shared Rich feedback helpers for the ``py-moodle`` CLI."""

from __future__ import annotations

from contextlib import contextmanager, nullcontext
from pathlib import Path
from typing import Callable, Iterator, Optional

import typer
from rich.progress import (
    BarColumn,
    Progress,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TransferSpeedColumn,
)

from py_moodle.cli.output import OutputFormat, get_console


def _is_quiet(ctx: Optional[typer.Context]) -> bool:
    """Return whether incidental CLI feedback should be suppressed."""
    return bool(ctx is not None and ctx.obj and ctx.obj.get("quiet"))


def _human_output(output_format: OutputFormat) -> bool:
    """Return whether the selected output format is intended for humans."""
    return output_format == OutputFormat.TABLE


def success(ctx: Optional[typer.Context], message: str) -> None:
    """Render a success message unless ``--quiet`` is active."""
    if _is_quiet(ctx):
        return
    get_console(ctx).print(f"[green]✓[/green] {message}")


def warning(ctx: Optional[typer.Context], message: str) -> None:
    """Render a warning message unless ``--quiet`` is active."""
    if _is_quiet(ctx):
        return
    get_console(ctx).print(f"[yellow]![/yellow] {message}")


def error(ctx: Optional[typer.Context], message: str) -> None:
    """Render an error message to stderr; errors are never suppressed."""
    console = get_console(ctx)
    original_file = console.file
    try:
        console.file = typer.get_text_stderr()
        console.print(f"[red]✗[/red] {message}")
    finally:
        console.file = original_file


@contextmanager
def status(
    ctx: Optional[typer.Context],
    message: str,
    output_format: OutputFormat = OutputFormat.TABLE,
) -> Iterator[None]:
    """Show a spinner for slow human-facing operations when appropriate."""
    console = get_console(ctx)
    if _is_quiet(ctx) or not _human_output(output_format) or not console.is_terminal:
        with nullcontext():
            yield
        return

    with console.status(message, spinner="dots"):
        yield


@contextmanager
def upload_progress(
    ctx: Optional[typer.Context],
    file_path: str,
    description: Optional[str] = None,
    output_format: OutputFormat = OutputFormat.TABLE,
) -> Iterator[Callable[[int], None]]:
    """Yield a byte-progress callback backed by Rich when output is interactive.

    The returned callback is always safe to call. In quiet mode, non-table output,
    or when stdout is not a TTY, it becomes a no-op so JSON/YAML/CSV and shell
    pipelines remain unchanged.
    """
    console = get_console(ctx)
    if _is_quiet(ctx) or not _human_output(output_format) or not console.is_terminal:
        yield lambda _bytes: None
        return

    path = Path(file_path)
    progress = Progress(
        TextColumn("{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TransferSpeedColumn(),
        TimeElapsedColumn(),
        console=console,
    )
    task_id = progress.add_task(
        description or f"Uploading {path.name}",
        total=path.stat().st_size,
    )

    with progress:
        yield lambda bytes_uploaded: progress.update(task_id, advance=bytes_uploaded)


__all__ = ["error", "status", "success", "upload_progress", "warning"]
