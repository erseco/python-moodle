"""Shared output format and console/logging utilities for the ``py-moodle`` CLI."""

from __future__ import annotations

import csv
import enum
import io
import json
import logging
import os
import sys
from typing import Any, Callable, Optional, Sequence, Tuple, Union

import typer
import yaml
from rich.console import Console

#: A CSV column definition: a header name paired with either a dict key to
#: project directly, or a callable that extracts the value from a row.
CsvField = Tuple[str, Union[str, Callable[[Any], Any]]]

#: Name of the shared logger used by the CLI and library diagnostics.
LOGGER_NAME = "py_moodle"


class OutputFormat(str, enum.Enum):
    """Supported CLI output formats.

    Attributes:
        TABLE: Human-readable rich table (default).
        JSON: Machine-readable JSON.
        YAML: Machine-readable YAML.
        CSV: Machine-readable CSV, suitable for spreadsheets or shell
            pipelines (``awk``, ``cut``, ``csvkit``, etc.).
    """

    TABLE = "table"
    JSON = "json"
    YAML = "yaml"
    CSV = "csv"


def _csv_extractor(field: CsvField) -> Callable[[Any], Any]:
    """Return a callable that extracts a single CSV cell value from a row.

    Args:
        field: A ``(header, accessor)`` pair. ``accessor`` may be a plain
            dict key (``str``) or a callable taking the row and returning
            the cell value.

    Returns:
        A callable ``row -> value``.
    """
    _, accessor = field
    if callable(accessor):
        return accessor
    key = accessor

    def _extract(row: Any) -> Any:
        return row.get(key, "") if isinstance(row, dict) else ""

    return _extract


def _emit_csv(data: Any, csv_fields: Optional[Sequence[CsvField]] = None) -> None:
    """Render ``data`` as CSV and echo it to stdout.

    Args:
        data: A list of dict-like rows (or a single dict, treated as one
            row). Each row is projected using ``csv_fields`` when given.
        csv_fields: Optional explicit column definitions. When omitted,
            falls back to the union of keys present across all rows
            (best-effort), so ``emit()`` never hard-fails for a command
            that has not opted in to explicit CSV columns yet.
    """
    rows = data if isinstance(data, list) else [data]

    if csv_fields:
        headers = [header for header, _ in csv_fields]
        extractors = [_csv_extractor(field) for field in csv_fields]
    else:
        headers = []
        seen = set()
        for row in rows:
            if isinstance(row, dict):
                for key in row.keys():
                    if key not in seen:
                        seen.add(key)
                        headers.append(key)
        extractors = [_csv_extractor((header, header)) for header in headers]

    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(headers)
    for row in rows:
        writer.writerow([extractor(row) for extractor in extractors])

    typer.echo(buffer.getvalue(), nl=False)


def emit(
    data: Any,
    output_format: OutputFormat,
    table_fn: Optional[Callable[[Any], None]] = None,
    csv_fields: Optional[Sequence[CsvField]] = None,
) -> None:
    """Emit ``data`` in the requested output format.

    Args:
        data: The data to emit. For JSON/YAML/CSV this must be
            serializable (typically a list of dicts, or a single dict).
        output_format: The desired output format.
        table_fn: A callable that renders ``data`` as a rich table.
            Required when ``output_format`` is ``OutputFormat.TABLE``.
        csv_fields: Optional column definitions used when
            ``output_format`` is ``OutputFormat.CSV``. Each entry is a
            ``(header, accessor)`` pair, where ``accessor`` is either a
            dict key or a callable extracting the value from a row. When
            omitted, the union of keys present in ``data`` is used.

    Raises:
        ValueError: If ``output_format`` is ``TABLE`` and no ``table_fn``
            is provided.
    """
    if output_format == OutputFormat.JSON:
        typer.echo(json.dumps(data, indent=2, ensure_ascii=False))
    elif output_format == OutputFormat.YAML:
        typer.echo(
            yaml.dump(data, allow_unicode=True, default_flow_style=False),
            nl=False,
        )
    elif output_format == OutputFormat.CSV:
        _emit_csv(data, csv_fields=csv_fields)
    else:
        if table_fn is None:
            raise ValueError(
                "table_fn is required when output_format is OutputFormat.TABLE"
            )
        table_fn(data)


def get_console(ctx: Optional["typer.Context"] = None) -> Console:
    """Return a ``rich`` ``Console`` that honors the ``--no-color`` flag.

    Args:
        ctx: The current Typer context, if available. When
            ``ctx.obj["no_color"]`` is truthy, colors are disabled
            regardless of whether stdout is a terminal. The ``NO_COLOR``
            environment variable (https://no-color.org/) is also
            respected independently of the CLI flag.

    Returns:
        Console: A ``rich`` console configured with ``no_color=True`` and
        ``force_terminal=False`` when colors must be disabled; otherwise a
        plain ``Console()`` that falls back to rich's normal auto-detection
        (colors on for a TTY, off when output is redirected/piped).
    """
    no_color = False
    if ctx is not None and getattr(ctx, "obj", None):
        no_color = bool(ctx.obj.get("no_color"))
    if not no_color and os.environ.get("NO_COLOR"):
        no_color = True

    if no_color:
        return Console(no_color=True, force_terminal=False)
    return Console()


def configure_logging(verbose: bool = False, debug: bool = False) -> None:
    """Configure the shared ``py_moodle`` logger for CLI diagnostics.

    Diagnostic output (``--verbose``/``--debug``) is always written to
    stderr via the stdlib ``logging`` module, so it never mixes with the
    machine-readable payload (table/JSON/YAML/CSV) written to stdout.

    Args:
        verbose: Enable INFO-level diagnostics.
        debug: Enable DEBUG-level diagnostics, including HTTP-level
            tracing from the authentication layer. Any secret-bearing
            value (token, sesskey, password, cookie) is redacted before
            being logged.
    """
    logger = logging.getLogger(LOGGER_NAME)
    logger.handlers.clear()

    if debug:
        level = logging.DEBUG
    elif verbose:
        level = logging.INFO
    else:
        level = logging.WARNING

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False


__all__ = ["OutputFormat", "emit", "get_console", "configure_logging"]
