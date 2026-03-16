"""Shared output format utilities for the ``py-moodle`` CLI."""

from __future__ import annotations

import enum
import json
from typing import Any, Callable, Optional

import typer
import yaml


class OutputFormat(str, enum.Enum):
    """Supported CLI output formats.

    Attributes:
        TABLE: Human-readable rich table (default).
        JSON: Machine-readable JSON.
        YAML: Machine-readable YAML.
    """

    TABLE = "table"
    JSON = "json"
    YAML = "yaml"


def emit(
    data: Any,
    output_format: OutputFormat,
    table_fn: Optional[Callable[[Any], None]] = None,
) -> None:
    """Emit ``data`` in the requested output format.

    Args:
        data: The data to emit. For JSON/YAML this must be serializable.
        output_format: The desired output format.
        table_fn: A callable that renders ``data`` as a rich table.
            Required when ``output_format`` is ``OutputFormat.TABLE``.

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
    else:
        if table_fn is None:
            raise ValueError(
                "table_fn is required when output_format is OutputFormat.TABLE"
            )
        table_fn(data)


__all__ = ["OutputFormat", "emit"]
