"""Red-team verdict contract."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class Severity(StrEnum):
    """How bad a failed attack is."""

    FATAL = "fatal"
    SERIOUS = "serious"
    EVIDENCE = "evidence"


class AttackOutcome(StrEnum):
    """Result of one attack."""

    PASSED = "passed"
    FAILED = "failed"
    INCONCLUSIVE = "inconclusive"


class Verdict(StrEnum):
    """Battery verdict (see docs/rules.md)."""

    BROKEN = "BROKEN"
    WOUNDED = "WOUNDED"
    NOT_PROVABLE = "NOT_PROVABLE"
    SURVIVES = "SURVIVES"


class AttackResult(BaseModel):
    """Outcome and evidence of one attack."""

    model_config = ConfigDict(frozen=True)

    attack_id: str = Field(pattern=r"^A\d{1,2}$")
    name: str
    severity: Severity
    outcome: AttackOutcome
    metrics: dict[str, float] = Field(default_factory=dict)
    message: str = ""


class RedTeamReport(BaseModel):
    """Verdict of the battery and the attacks behind it."""

    model_config = ConfigDict(frozen=True)

    verdict: Verdict
    claimed_sharpe: float
    suspicious: bool
    attacks: tuple[AttackResult, ...]

    def attack(self, attack_id: str) -> AttackResult:
        """Return the result of ``attack_id``; raise ``KeyError`` if it did not run."""
        for result in self.attacks:
            if result.attack_id == attack_id:
                return result
        raise KeyError(attack_id)

    def failed(self) -> tuple[str, ...]:
        """Return the identifiers of the failed attacks."""
        return tuple(r.attack_id for r in self.attacks if r.outcome is AttackOutcome.FAILED)


def aggregate_verdict(attacks: tuple[AttackResult, ...]) -> Verdict:
    """Combine attack outcomes: fatal failure, then serious failure, then missing evidence."""
    failed = {r.severity for r in attacks if r.outcome is AttackOutcome.FAILED}
    if Severity.FATAL in failed:
        return Verdict.BROKEN
    if Severity.SERIOUS in failed:
        return Verdict.WOUNDED
    if any(
        r.severity is Severity.EVIDENCE and r.outcome is not AttackOutcome.PASSED for r in attacks
    ):
        return Verdict.NOT_PROVABLE
    return Verdict.SURVIVES
