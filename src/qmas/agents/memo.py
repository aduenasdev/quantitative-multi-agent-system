"""The reporter's memo: a deterministic template, the evidence for an LLM, and the number audit.

Rule: RULE-AUDIT-01. The LLM memo is accepted only if every figure in it appears in the evidence;
otherwise the deterministic memo is used.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from qmas.contracts.thesis import Thesis
from qmas.contracts.verdict import AttackOutcome, RedTeamReport, Verdict
from qmas.llm import LLMClient, LLMRequest, PromptRegistry, audit_numbers

NUMBER_IN_TEXT = re.compile(r"-?\d+(?:\.\d+)?")

LIMITS: dict[Verdict, str] = {
    Verdict.SURVIVES: "Surviving the battery is not proof of an edge: it only means no known "
    "defect was found. The holdout window and a forward record still have to confirm it.",
    Verdict.NOT_PROVABLE: "The data cannot tell a real edge from luck at this sample size; more "
    "history or a forward record is needed before any conclusion.",
    Verdict.WOUNDED: "A serious attack succeeded: the edge, if any, is not the one claimed.",
    Verdict.BROKEN: "A fatal attack succeeded: the backtest result is not real.",
}


@dataclass(frozen=True)
class Memo:
    """A memo and where it came from."""

    text: str
    source: str
    unknown_numbers: tuple[str, ...] = ()


def evidence_lines(report: RedTeamReport) -> str:
    """One line per attack with its outcome, metrics and message."""
    lines = []
    for attack in report.attacks:
        metrics = ", ".join(f"{name}={value:.3f}" for name, value in attack.metrics.items())
        lines.append(
            f"{attack.attack_id} | {attack.name} | {attack.outcome.value} | {metrics} "
            f"| {attack.message}"
        )
    return "\n".join(lines)


def allowed_numbers(thesis: Thesis, report: RedTeamReport) -> list[float]:
    """Every number a memo may quote: the report's metrics and the thesis' own figures."""
    values = [report.claimed_sharpe, float(len(report.attacks))]
    for attack in report.attacks:
        values.extend(attack.metrics.values())
        values.extend(float(n) for n in NUMBER_IN_TEXT.findall(attack.message))
    values.extend(
        [float(thesis.version), float(thesis.horizon_days), float(thesis.rebalance_every_days)]
    )
    values.append(thesis.cost_bps)
    for text in (thesis.title, thesis.hypothesis, thesis.key):
        values.extend(float(n) for n in NUMBER_IN_TEXT.findall(text))
    return values


def template_memo(thesis: Thesis, report: RedTeamReport) -> str:
    """Write the memo without any language model."""
    failed = [a for a in report.attacks if a.outcome is AttackOutcome.FAILED]
    passed = [a.attack_id for a in report.attacks if a.outcome is AttackOutcome.PASSED]
    open_ = [a.attack_id for a in report.attacks if a.outcome is AttackOutcome.INCONCLUSIVE]
    lines = [
        f"## {thesis.title}: {report.verdict.value}",
        "",
        f"Claimed annualised Sharpe ratio: {report.claimed_sharpe:.2f}.",
    ]
    if report.suspicious:
        lines.append("The Sharpe ratio is above 2: a person must review it before anything else.")
    if failed:
        lines += ["", "Decided by:"]
        lines += [f"- {a.attack_id} {a.name}: {a.message}." for a in failed]
    lines += [
        "",
        f"Passed: {', '.join(passed) or 'none'}. Inconclusive: {', '.join(open_) or 'none'}.",
    ]
    lines += ["", LIMITS[report.verdict]]
    return "\n".join(lines)


def write_memo(
    thesis: Thesis, report: RedTeamReport, client: LLMClient, prompts: PromptRegistry
) -> Memo:
    """Ask the LLM for the memo; keep it only if it passes the number audit."""
    draft = template_memo(thesis, report)
    request = LLMRequest(
        system=prompts.render("reporter_system"),
        prompt=prompts.render(
            "reporter_memo",
            title=thesis.title,
            thesis_key=thesis.key,
            hypothesis=thesis.hypothesis.strip(),
            verdict=report.verdict.value,
            claimed_sharpe=f"{report.claimed_sharpe:.2f}",
            suspicious="yes" if report.suspicious else "no",
            evidence=evidence_lines(report),
        ),
        max_output_tokens=client.settings.llm_max_output_tokens,
        fallback_text=draft,
    )
    response = client.complete(request)
    if response.provider == "simulated":
        return Memo(text=response.text, source="template")
    audit = audit_numbers(response.text, allowed_numbers(thesis, report))
    if not audit.ok:
        return Memo(
            text=draft,
            source="template (LLM memo failed the number audit)",
            unknown_numbers=audit.unknown,
        )
    return Memo(text=response.text, source=f"{response.provider}:{response.model}")
