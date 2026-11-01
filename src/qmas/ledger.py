"""Append-only experiment ledger with a SHA-256 hash chain.

Each JSON line holds ``sequence``, ``timestamp``, ``kind``, ``payload``, ``previous_hash`` and
``hash``, where ``hash`` covers every other field and ``previous_hash`` is the hash of the line
before (64 zeros for the first). Editing, deleting, inserting or reordering lines breaks the chain
at that point.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from qmas.canonical import canonical_json, sha256_hex
from qmas.contracts.thesis import Thesis

GENESIS_HASH = "0" * 64
EntryKind = Literal["thesis_registered", "trial", "verdict", "decision"]
ENTRY_KINDS: frozenset[str] = frozenset({"thesis_registered", "trial", "verdict", "decision"})


class LedgerError(Exception):
    """Raised when the ledger is corrupt or a rule backed by it is broken."""


class NotPreRegisteredError(LedgerError):
    """Raised when a thesis is used before its registration (RULE-PREREG-01)."""


@dataclass(frozen=True)
class LedgerEntry:
    """One verified ledger line."""

    sequence: int
    timestamp: str
    kind: str
    payload: dict[str, Any]
    previous_hash: str
    hash: str


@dataclass(frozen=True)
class Verification:
    """Outcome of verifying the hash chain."""

    ok: bool
    n_entries: int
    error_line: int | None = None
    reason: str | None = None


def _entry_hash(fields: dict[str, Any]) -> str:
    return sha256_hex(canonical_json(fields))


def _utc_now() -> datetime:
    return datetime.now(UTC)


class Ledger:
    """The ledger file and the rules that read it."""

    def __init__(self, path: Path, clock: Callable[[], datetime] = _utc_now) -> None:
        """Open (without creating) the ledger at ``path``; ``clock`` stamps new entries."""
        self.path = path
        self._clock = clock

    # ------------------------------------------------------------------ reading
    def _raw_lines(self) -> list[str]:
        if not self.path.exists():
            return []
        return [line for line in self.path.read_text(encoding="utf-8").splitlines() if line]

    def verify(self) -> Verification:
        """Check every line: valid JSON, consecutive sequence, correct hashes and chain."""
        previous = GENESIS_HASH
        lines = self._raw_lines()
        for number, line in enumerate(lines, start=1):
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                return Verification(False, len(lines), number, "not valid JSON")
            stored_hash = record.pop("hash", None)
            if record.get("sequence") != number:
                return Verification(False, len(lines), number, "sequence out of order")
            if record.get("previous_hash") != previous:
                return Verification(False, len(lines), number, "previous hash does not match")
            if stored_hash != _entry_hash(record):
                return Verification(False, len(lines), number, "content does not match its hash")
            previous = stored_hash
        return Verification(True, len(lines))

    def entries(self) -> Iterator[LedgerEntry]:
        """Yield every entry after verifying the whole chain."""
        verification = self.verify()
        if not verification.ok:
            raise LedgerError(
                f"ledger corrupt at line {verification.error_line}: {verification.reason}"
            )
        for line in self._raw_lines():
            yield LedgerEntry(**json.loads(line))

    # ------------------------------------------------------------------ writing
    def append(self, kind: EntryKind, payload: dict[str, Any]) -> LedgerEntry:
        """Append one entry chained to the last one."""
        if kind not in ENTRY_KINDS:
            raise LedgerError(f"unknown entry kind: {kind}")
        existing = list(self.entries())
        fields: dict[str, Any] = {
            "sequence": len(existing) + 1,
            "timestamp": self._clock().isoformat(),
            "kind": kind,
            "payload": json.loads(canonical_json(payload)),
            "previous_hash": existing[-1].hash if existing else GENESIS_HASH,
        }
        entry = LedgerEntry(**fields, hash=_entry_hash(fields))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(canonical_json({**fields, "hash": entry.hash}) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        return entry

    # ------------------------------------------------------------------ rules
    def find_registration(self, thesis: Thesis) -> LedgerEntry | None:
        """Return the registration entry of this exact thesis content, if any."""
        content_hash = thesis.content_hash()
        for entry in self.entries():
            if entry.kind == "thesis_registered" and entry.payload["content_hash"] == content_hash:
                return entry
        return None

    def register_thesis(self, thesis: Thesis) -> LedgerEntry:
        """Register a thesis before any backtest; registering the same content again is a no-op.

        Rule: RULE-PREREG-01.
        """
        existing = self.find_registration(thesis)
        if existing is not None:
            return existing
        for entry in self.entries():
            if entry.kind == "thesis_registered" and entry.payload["key"] == thesis.key:
                raise LedgerError(
                    f"{thesis.key} is registered with other content: bump the version"
                )
        return self.append(
            "thesis_registered",
            {
                "key": thesis.key,
                "family": thesis.family,
                "content_hash": thesis.content_hash(),
                "thesis": thesis.model_dump(mode="json"),
            },
        )

    def require_registered(self, thesis: Thesis) -> LedgerEntry:
        """Return the registration entry or raise ``NotPreRegisteredError`` (RULE-PREREG-01)."""
        entry = self.find_registration(thesis)
        if entry is None:
            raise NotPreRegisteredError(f"{thesis.key} is not registered in the ledger")
        return entry

    def count_trials(self, family: str) -> int:
        """Return the number of trials recorded for ``family`` (RULE-TRIALS-01)."""
        return sum(
            1
            for entry in self.entries()
            if entry.kind == "trial" and entry.payload["family"] == family
        )
