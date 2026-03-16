"""Smoke tests that do not require a live Moodle instance."""

from typer.testing import CliRunner

from py_moodle import __version__
from py_moodle.cli.app import app


def test_package_version_is_exposed():
    """The package should expose a string version for tooling and docs."""
    assert isinstance(__version__, str)
    assert __version__


def test_cli_help_runs_without_environment():
    """The CLI help should render without contacting a Moodle instance."""
    runner = CliRunner()

    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "A CLI to manage Moodle via AJAX sessions and web services." in result.output
