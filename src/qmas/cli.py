"""Command-line interface (``qmas``)."""

from __future__ import annotations

from typing import Annotated

import typer

from qmas import __version__
from qmas.config import get_settings
from qmas.logging_setup import configure_logging

app = typer.Typer(
    help="Quantitative multi-agent system: red-team trading hypotheses before trusting them.",
    no_args_is_help=True,
    add_completion=False,
)
config_app = typer.Typer(help="Inspect the configuration.", no_args_is_help=True)
app.add_typer(config_app, name="config")


def _print_version(value: bool) -> None:
    if value:
        typer.echo(f"qmas {__version__}")
        raise typer.Exit


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option("--version", callback=_print_version, is_eager=True, help="Show the version."),
    ] = False,
) -> None:
    """Configure logging before any command runs."""
    configure_logging(get_settings().log_level)


@config_app.command("show")
def config_show() -> None:
    """Print the effective settings as JSON."""
    typer.echo(get_settings().model_dump_json(indent=2))
