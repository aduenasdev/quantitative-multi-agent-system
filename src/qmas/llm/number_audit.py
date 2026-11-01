"""Number audit: every figure in an LLM-written text must come from a stored result.

Rule: RULE-AUDIT-01. Numbers are extracted from the text (decimals, percentages, negatives)
and matched against the allowed values at the precision they are written with; percentages also
match the value divided by 100. Identifiers such as ``A10`` or ``P7`` and years are ignored.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable
from dataclasses import dataclass

NUMBER = re.compile(r"(?<![A-Za-z0-9_.])(-?\d+(?:\.\d+)?)(\s?%)?(?![A-Za-z0-9_])")
MIN_YEAR, MAX_YEAR = 1900, 2100


@dataclass(frozen=True)
class AuditResult:
    """Outcome of the audit."""

    ok: bool
    unknown: tuple[str, ...]
    checked: int


def _decimals(token: str) -> int:
    return len(token.split(".")[1]) if "." in token else 0


def _matches(value: float, decimals: int, allowed: Iterable[float]) -> bool:
    tolerance = 0.5 * 10 ** (-decimals) + 1e-9
    return any(math.isfinite(a) and abs(a - value) <= tolerance for a in allowed)


def audit_numbers(text: str, allowed: Iterable[float]) -> AuditResult:
    """Check that every number written in ``text`` appears (rounded) among ``allowed``."""
    values = [float(v) for v in allowed]
    unknown: list[str] = []
    checked = 0
    for match in NUMBER.finditer(text):
        token, percent = match.group(1), match.group(2)
        number = float(token)
        if not percent and "." not in token and MIN_YEAR <= abs(number) <= MAX_YEAR:
            continue
        checked += 1
        decimals = _decimals(token)
        candidates = values + ([v * 100 for v in values] if percent else [])
        if not _matches(number, decimals, candidates):
            unknown.append(match.group(0).strip())
    return AuditResult(ok=not unknown, unknown=tuple(unknown), checked=checked)
