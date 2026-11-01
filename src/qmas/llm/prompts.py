"""Prompt registry: prompt files with a frozen SHA-256 in ``qmas/prompts/prompts.lock.json``.

A prompt whose text no longer matches its locked hash refuses to load, so a result can always be
traced to the exact prompt that produced it. Placeholders use ``$name`` (``string.Template``).
"""

from __future__ import annotations

import json
from pathlib import Path
from string import Template

from qmas.canonical import sha256_hex

LOCK_FILE = "prompts.lock.json"
PACKAGE_PROMPTS = Path(__file__).resolve().parents[1] / "prompts"


class PromptError(ValueError):
    """Raised for unknown, unlocked or modified prompts."""


class PromptRegistry:
    """Locked prompts of one directory."""

    def __init__(self, directory: Path = PACKAGE_PROMPTS) -> None:
        """Read the lock file of ``directory``."""
        self.directory = directory
        lock = directory / LOCK_FILE
        self._lock: dict[str, str] = (
            json.loads(lock.read_text(encoding="utf-8")) if lock.is_file() else {}
        )

    def _path(self, prompt_id: str) -> Path:
        return self.directory / f"{prompt_id}.md"

    def text(self, prompt_id: str) -> str:
        """Return the prompt text after checking it against its locked hash."""
        path = self._path(prompt_id)
        if not path.is_file():
            raise PromptError(f"unknown prompt {prompt_id!r}")
        text = path.read_text(encoding="utf-8")
        expected = self._lock.get(prompt_id)
        if expected is None:
            raise PromptError(f"prompt {prompt_id!r} is not locked")
        if sha256_hex(text) != expected:
            raise PromptError(f"prompt {prompt_id!r} changed since it was locked")
        return text

    def render(self, prompt_id: str, **values: str) -> str:
        """Return the prompt with its ``$placeholders`` substituted (all of them must be given)."""
        return Template(self.text(prompt_id)).substitute(values)

    def hash(self, prompt_id: str) -> str:
        """Return the locked hash of a prompt."""
        self.text(prompt_id)
        return self._lock[prompt_id]

    def lock(self) -> dict[str, str]:
        """Recompute the hash of every prompt file and write the lock file."""
        hashes = {
            path.stem: sha256_hex(path.read_text(encoding="utf-8"))
            for path in sorted(self.directory.glob("*.md"))
        }
        (self.directory / LOCK_FILE).write_text(
            json.dumps(hashes, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        self._lock = hashes
        return hashes
