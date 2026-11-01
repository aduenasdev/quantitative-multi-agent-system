"""Render an E1 report as Markdown and write it next to its JSON."""

from __future__ import annotations

from pathlib import Path

from qmas.contracts.verdict import Verdict
from qmas.evaluation.cases import TEMPLATES
from qmas.evaluation.e1 import E1Report


def _percent(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.0%}"


def render_markdown(report: E1Report) -> str:
    """Return the report as Markdown: criteria, confusion matrix and expected signal strength."""
    lines = [
        "# E1: battery discrimination",
        "",
        f"Seeds: {', '.join(map(str, report.seeds))}. "
        f"Placebo runs per case: {report.placebo_runs}.",
        f"Overall: **{'PASSED' if report.passed else 'FAILED'}**.",
        "",
        "## Pre-registered criteria",
        "",
        "| Criterion | Value | Threshold | Result | Detail |",
        "|---|---|---|---|---|",
    ]
    for criterion in report.criteria:
        lines.append(
            f"| {criterion.name} | {_percent(criterion.value)} | {_percent(criterion.threshold)} "
            f"| {'pass' if criterion.passed else 'fail'} | {criterion.detail} |"
        )
    verdicts = [verdict.value for verdict in Verdict]
    descriptions = {template.case_id: template.description for template in TEMPLATES}
    lines += [
        "",
        "## Confusion matrix",
        "",
        "| Case | Description | " + " | ".join(verdicts) + " |",
        "|---|---|" + "---|" * len(verdicts),
    ]
    for case_id, row in report.confusion.items():
        cells = " | ".join(str(row[verdict]) for verdict in verdicts)
        lines.append(f"| {case_id} | {descriptions[case_id]} | {cells} |")
    lines += [
        "",
        "## Planted signal strength",
        "",
        f"Minimum detectable annualised Sharpe ratio: {report.minimum_detectable_sharpe:.2f}.",
        "",
        "| Case | Expected Sharpe (calibration seeds) |",
        "|---|---|",
    ]
    lines += [
        f"| {case} | {sharpe:.2f} |" for case, sharpe in report.expected_signal_sharpe.items()
    ]
    lines += [
        "",
        "## Cases",
        "",
        "| Case | Seed | Claimed Sharpe | Verdict | Failed attacks | Expected attacks |",
        "|---|---|---|---|---|---|",
    ]
    for outcome in report.outcomes:
        lines.append(
            f"| {outcome.case_id} | {outcome.seed} | {outcome.claimed_sharpe:.2f} "
            f"| {outcome.verdict.value} | {', '.join(outcome.failed_attacks) or '-'} "
            f"| {', '.join(outcome.expected_attacks) or '-'} |"
        )
    return "\n".join(lines) + "\n"


def write_report(report: E1Report, directory: Path, name: str) -> tuple[Path, Path]:
    """Write ``<name>.json`` and ``<name>.md`` into ``directory``."""
    directory.mkdir(parents=True, exist_ok=True)
    json_path = directory / f"{name}.json"
    markdown_path = directory / f"{name}.md"
    json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    markdown_path.write_text(render_markdown(report), encoding="utf-8")
    return json_path, markdown_path
