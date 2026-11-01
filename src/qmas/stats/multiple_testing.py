"""False discovery rate control.

Reference:
    Benjamini, Y. and Hochberg, Y. (1995). "Controlling the False Discovery Rate: A Practical
        and Powerful Approach to Multiple Testing." Journal of the Royal Statistical Society B
        57(1).
"""

from __future__ import annotations

from collections.abc import Mapping


def benjamini_hochberg(p_values: Mapping[str, float], q: float = 0.10) -> dict[str, bool]:
    """Return, for each hypothesis, whether it is rejected at false discovery rate ``q``.

    Sort the m p-values; find the largest rank k with p_(k) <= q * k / m; reject ranks 1..k.
    Rule: RULE-FDR-01 uses q = 0.10 across every thesis tested in a year.
    """
    if not 0.0 < q < 1.0:
        raise ValueError("q must be in (0, 1)")
    if any(not 0.0 <= p <= 1.0 for p in p_values.values()):
        raise ValueError("p-values must be in [0, 1]")
    ordered = sorted(p_values, key=lambda name: p_values[name])
    m = len(ordered)
    last_rejected = 0
    for rank, name in enumerate(ordered, start=1):
        if p_values[name] <= q * rank / m:
            last_rejected = rank
    return {name: rank <= last_rejected for rank, name in enumerate(ordered, start=1)}
