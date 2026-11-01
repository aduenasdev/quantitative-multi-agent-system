from __future__ import annotations

import pytest

from qmas.stats.multiple_testing import benjamini_hochberg


def test_benjamini_hochberg_hand_worked_example() -> None:
    # m = 5, q = 0.10: thresholds 0.02, 0.04, 0.06, 0.08, 0.10. Sorted p: .005 .03 .07 .09 .5.
    # Largest k with p_(k) <= q k / m is k = 2 (0.03 <= 0.04; 0.07 > 0.06; 0.09 > 0.08).
    p_values = {"a": 0.005, "b": 0.03, "c": 0.07, "d": 0.09, "e": 0.5}
    assert benjamini_hochberg(p_values, 0.10) == {
        "a": True,
        "b": True,
        "c": False,
        "d": False,
        "e": False,
    }


def test_benjamini_hochberg_step_up_rejects_earlier_ranks() -> None:
    # p_(1) = 0.04 > 0.025 alone, but p_(2) = 0.045 <= 0.05 rejects both.
    assert benjamini_hochberg({"a": 0.04, "b": 0.045}, 0.05) == {"a": True, "b": True}


def test_benjamini_hochberg_is_monotone_in_q() -> None:
    p_values = {str(i): i / 100 for i in range(1, 30)}
    strict = sum(benjamini_hochberg(p_values, 0.05).values())
    loose = sum(benjamini_hochberg(p_values, 0.20).values())
    assert strict <= loose


def test_benjamini_hochberg_rejects_invalid_inputs() -> None:
    with pytest.raises(ValueError, match="q must"):
        benjamini_hochberg({"a": 0.1}, 1.0)
    with pytest.raises(ValueError, match="p-values"):
        benjamini_hochberg({"a": 1.5})
