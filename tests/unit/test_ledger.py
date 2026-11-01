from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from qmas.ledger import GENESIS_HASH, Ledger, LedgerError, NotPreRegisteredError
from tests.factories import make_thesis

FIXED_TIME = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)


@pytest.fixture
def ledger(tmp_path: Path) -> Ledger:
    return Ledger(tmp_path / "data" / "ledger.jsonl", clock=lambda: FIXED_TIME)


def _fill(ledger: Ledger, count: int = 3) -> None:
    for index in range(count):
        ledger.append("trial", {"family": "f", "index": index})


def _lines(ledger: Ledger) -> list[str]:
    return ledger.path.read_text(encoding="utf-8").splitlines()


def _write(ledger: Ledger, lines: list[str]) -> None:
    ledger.path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_empty_ledger_verifies(ledger: Ledger) -> None:
    result = ledger.verify()
    assert result.ok
    assert result.n_entries == 0
    assert list(ledger.entries()) == []


def test_append_and_read_back(ledger: Ledger) -> None:
    first = ledger.append("trial", {"family": "f", "sharpe": 0.5})
    second = ledger.append("verdict", {"verdict": "BROKEN"})
    assert first.previous_hash == GENESIS_HASH
    assert second.previous_hash == first.hash
    assert [entry.sequence for entry in ledger.entries()] == [1, 2]
    assert first.timestamp == FIXED_TIME.isoformat()
    assert ledger.verify().ok


def test_unknown_kind_is_rejected(ledger: Ledger) -> None:
    with pytest.raises(LedgerError, match="unknown entry kind"):
        ledger.append("note", {})  # type: ignore[arg-type]


def test_edited_line_is_detected(ledger: Ledger) -> None:
    _fill(ledger)
    lines = _lines(ledger)
    record = json.loads(lines[1])
    record["payload"]["index"] = 99
    lines[1] = json.dumps(record)
    _write(ledger, lines)
    result = ledger.verify()
    assert not result.ok
    assert result.error_line == 2
    assert result.reason == "content does not match its hash"


def test_deleted_line_is_detected(ledger: Ledger) -> None:
    _fill(ledger)
    lines = _lines(ledger)
    _write(ledger, [lines[0], lines[2]])
    result = ledger.verify()
    assert (result.ok, result.error_line, result.reason) == (False, 2, "sequence out of order")


def test_reordered_lines_are_detected(ledger: Ledger) -> None:
    _fill(ledger)
    lines = _lines(ledger)
    _write(ledger, [lines[1], lines[0], lines[2]])
    assert ledger.verify().error_line == 1


def test_rehashed_line_breaks_the_chain(ledger: Ledger) -> None:
    _fill(ledger)
    lines = _lines(ledger)
    record = json.loads(lines[0])
    record["payload"]["index"] = 42
    record.pop("hash")
    other = Ledger(ledger.path.parent / "other.jsonl", clock=lambda: FIXED_TIME)
    forged = other.append("trial", record["payload"])
    lines[0] = json.dumps({**record, "hash": forged.hash})
    _write(ledger, lines)
    assert ledger.verify().error_line == 2


def test_invalid_json_is_detected_and_blocks_reading(ledger: Ledger) -> None:
    _fill(ledger, 1)
    _write(ledger, [*_lines(ledger), "{not json"])
    assert ledger.verify().reason == "not valid JSON"
    with pytest.raises(LedgerError, match="corrupt at line 2"):
        list(ledger.entries())


def test_register_thesis_is_idempotent(ledger: Ledger) -> None:
    thesis = make_thesis()
    first = ledger.register_thesis(thesis)
    assert ledger.register_thesis(thesis) == first
    assert first.payload["content_hash"] == thesis.content_hash()
    assert len(list(ledger.entries())) == 1


def test_changed_content_needs_a_new_version(ledger: Ledger) -> None:
    ledger.register_thesis(make_thesis())
    with pytest.raises(LedgerError, match="bump the version"):
        ledger.register_thesis(make_thesis(cost_bps=20.0))
    assert ledger.register_thesis(make_thesis(cost_bps=20.0, version=2)).sequence == 2


def test_require_registered(ledger: Ledger) -> None:
    thesis = make_thesis()
    with pytest.raises(NotPreRegisteredError, match="test-thesis-v1"):
        ledger.require_registered(thesis)
    ledger.register_thesis(thesis)
    assert ledger.require_registered(thesis).kind == "thesis_registered"


def test_count_trials_by_family(ledger: Ledger) -> None:
    _fill(ledger, 3)
    ledger.append("trial", {"family": "other"})
    ledger.append("verdict", {"family": "f"})
    assert ledger.count_trials("f") == 3
    assert ledger.count_trials("other") == 1
    assert ledger.count_trials("missing") == 0
