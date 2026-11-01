"""Command-line interface (``qmas``)."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError

from qmas import __version__
from qmas.config import get_settings
from qmas.contracts.thesis import load_thesis
from qmas.ledger import Ledger
from qmas.logging_setup import configure_logging

LEDGER_FILE_NAME = "ledger.jsonl"

app = typer.Typer(
    help="Quantitative multi-agent system: red-team trading hypotheses before trusting them.",
    no_args_is_help=True,
    add_completion=False,
)
config_app = typer.Typer(help="Inspect the configuration.", no_args_is_help=True)
thesis_app = typer.Typer(help="Work with thesis files.", no_args_is_help=True)
ledger_app = typer.Typer(help="Inspect the experiment ledger.", no_args_is_help=True)
app.add_typer(config_app, name="config")
app.add_typer(thesis_app, name="thesis")
app.add_typer(ledger_app, name="ledger")


def ledger_path() -> Path:
    """Return the ledger file inside the configured data directory."""
    return get_settings().data_dir / LEDGER_FILE_NAME


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


@thesis_app.command("validate")
def thesis_validate(
    path: Annotated[Path, typer.Argument(exists=True, dir_okay=False, help="Thesis YAML file.")],
) -> None:
    """Validate a thesis file and print its key and content hash."""
    try:
        thesis = load_thesis(path)
    except (ValidationError, ValueError) as error:
        typer.echo(f"invalid thesis: {error}", err=True)
        raise typer.Exit(code=1) from error
    typer.echo(f"{thesis.key} {thesis.content_hash()}")


@ledger_app.command("verify")
def ledger_verify() -> None:
    """Verify the hash chain of the ledger; exit code 1 if it was altered."""
    result = Ledger(ledger_path()).verify()
    if not result.ok:
        typer.echo(f"ledger corrupt at line {result.error_line}: {result.reason}", err=True)
        raise typer.Exit(code=1)
    typer.echo(f"ledger ok: {result.n_entries} entries")
