"""Canonical JSON and SHA-256 hashing, shared by the thesis contract and the ledger."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_json(value: Any) -> str:
    """Serialise ``value`` deterministically: sorted keys, no whitespace, UTF-8 characters kept."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def sha256_hex(text: str) -> str:
    """Return the hexadecimal SHA-256 digest of ``text`` encoded as UTF-8."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
