"""Repository check: English-only text, private-string denylist and forbidden files.

Runs over every file git would publish (tracked plus untracked-but-not-ignored). Settings come
from the ``[tool.check-repo]`` table of ``pyproject.toml``. The denylist is a plain-text file kept
**outside** the repository; its path is given by the ``QMAS_DENYLIST_FILE`` environment variable
(one case-insensitive string per line, ``#`` for comments). Without it, the denylist step is
skipped with a warning.

Exit code 0 when clean, 1 when there are findings.
"""

from __future__ import annotations

import fnmatch
import os
import re
import subprocess
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DENYLIST_VARIABLE = "QMAS_DENYLIST_FILE"

# Letters and punctuation that are common in Spanish and almost never appear in English text.
SPANISH_CHARACTERS = re.compile(r"[áéíóúñÁÉÍÓÚÑ¿¡]")

# Frequent Spanish words that are not English words. Python keywords and maths names that collide
# with Spanish words ("del", "sin", "con") are deliberately left out.
SPANISH_WORDS = frozenset(
    {
        "que",
        "para",
        "los",
        "las",
        "una",
        "por",
        "pero",
        "como",
        "esto",
        "esta",
        "este",
        "cuando",
        "donde",
        "porque",
        "tambien",
        "segun",
        "hasta",
        "desde",
        "entre",
        "sobre",
        "cada",
        "datos",
        "fecha",
        "fechas",
        "precios",
        "cartera",
        "semilla",
        "resultados",
        "ventana",
        "ventanas",
        "eventos",
        "tesis",
        "umbral",
        "nulo",
        "riesgo",
        "ensayo",
        "ensayos",
        "libro",
        "cementerio",
        "ataque",
        "ataques",
        "paso",
        "pasos",
        "carpeta",
        "fichero",
        "clave",
        "claves",
        "señal",
        "senal",
        "cargar",
        "guardar",
        "calcular",
        "devuelve",
        "escribe",
    }
)

WORD = re.compile(r"[A-Za-zÀ-ÿ]+")

TEXT_SUFFIXES = frozenset(
    {
        ".py",
        ".md",
        ".toml",
        ".yaml",
        ".yml",
        ".txt",
        ".json",
        ".cfg",
        ".ini",
        ".j2",
        ".sh",
        ".example",
        ".dockerignore",
        ".gitignore",
        ".gitattributes",
        "",
    }
)


@dataclass(frozen=True)
class CheckConfig:
    """Settings of the repository check."""

    allowed_words: tuple[str, ...] = ()
    max_file_bytes: int = 1_000_000
    forbidden_patterns: tuple[str, ...] = ()
    skip_language_check: tuple[str, ...] = ()


@dataclass
class Report:
    """Findings, one human-readable line each."""

    findings: list[str] = field(default_factory=list)

    def add(self, path: str, message: str) -> None:
        """Record a finding for ``path``."""
        self.findings.append(f"{path}: {message}")


def load_config(pyproject: Path) -> CheckConfig:
    """Read ``[tool.check-repo]`` from ``pyproject``."""
    table = (
        tomllib.loads(pyproject.read_text(encoding="utf-8")).get("tool", {}).get("check-repo", {})
    )
    return CheckConfig(
        allowed_words=tuple(table.get("allowed_words", ())),
        max_file_bytes=int(table.get("max_file_bytes", 1_000_000)),
        forbidden_patterns=tuple(table.get("forbidden_patterns", ())),
        skip_language_check=tuple(table.get("skip_language_check", ())),
    )


def publishable_files(root: Path) -> list[str]:
    """Return the files git would publish: tracked and untracked files that are not ignored."""
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=root,
        capture_output=True,
        check=True,
    )
    names = {name for name in result.stdout.decode("utf-8").split("\0") if name}
    return sorted(name for name in names if (root / name).is_file())


def load_denylist(path: Path) -> list[str]:
    """Read denylisted strings: one per line, blank lines and ``#`` comments ignored."""
    lines = path.read_text(encoding="utf-8").splitlines()
    return [line.strip().lower() for line in lines if line.strip() and not line.startswith("#")]


def is_text_file(name: str) -> bool:
    """Return whether ``name`` should be read as text."""
    path = Path(name)
    return path.suffix.lower() in TEXT_SUFFIXES or path.name in {"Dockerfile", "LICENSE"}


def check_language(name: str, text: str, config: CheckConfig, report: Report) -> None:
    """Report lines that look Spanish."""
    for number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line
        for word in config.allowed_words:
            line = line.replace(word, "")
        if SPANISH_CHARACTERS.search(line):
            report.add(f"{name}:{number}", "Spanish character")
            continue
        spanish = sorted({w for w in WORD.findall(line) if w.lower() in SPANISH_WORDS})
        if spanish:
            report.add(f"{name}:{number}", f"Spanish word(s): {', '.join(spanish)}")


def check_denylist(name: str, text: str, denylist: list[str], report: Report) -> None:
    """Report lines containing a denylisted string (the string itself is not printed)."""
    for number, line in enumerate(text.lower().splitlines(), start=1):
        for index, term in enumerate(denylist, start=1):
            if term in line:
                report.add(f"{name}:{number}", f"denylisted string #{index}")


def check_file(
    root: Path, name: str, config: CheckConfig, denylist: list[str], report: Report
) -> None:
    """Run every check on one file."""
    path = root / name
    if any(fnmatch.fnmatch(Path(name).name, pattern) for pattern in config.forbidden_patterns):
        report.add(name, "forbidden file type")
    size = path.stat().st_size
    if size > config.max_file_bytes:
        report.add(name, f"file too large ({size} bytes > {config.max_file_bytes})")
    if not is_text_file(name):
        return
    text = path.read_text(encoding="utf-8", errors="replace")
    if name not in config.skip_language_check:
        check_language(name, text, config, report)
    check_denylist(name, text, denylist, report)


def denylist_setting(root: Path) -> str | None:
    """Return ``QMAS_DENYLIST_FILE`` from the environment, else from ``<root>/.env``.

    A variable set in the environment wins even when empty, so a container can switch the step off.
    """
    if DENYLIST_VARIABLE in os.environ:
        return os.environ[DENYLIST_VARIABLE]
    env_file = root / ".env"
    if not env_file.is_file():
        return None
    for line in env_file.read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition("=")
        if separator and key.strip() == DENYLIST_VARIABLE:
            return value.strip().strip("\"'")
    return None


def run(root: Path, denylist_file: str | None) -> Report:
    """Check every publishable file under ``root``."""
    config = load_config(root / "pyproject.toml")
    report = Report()
    denylist: list[str] = []
    if not denylist_file:
        print(f"warning: {DENYLIST_VARIABLE} is not set; denylist check skipped", file=sys.stderr)
    elif not Path(denylist_file).is_file():
        report.add(DENYLIST_VARIABLE, "denylist file not found")
    else:
        denylist = load_denylist(Path(denylist_file))
    for name in publishable_files(root):
        check_file(root, name, config, denylist, report)
    return report


def main() -> int:
    """Run the check on this repository and print the findings."""
    report = run(REPO_ROOT, denylist_setting(REPO_ROOT))
    for finding in report.findings:
        print(finding)
    if report.findings:
        print(f"check_repo: {len(report.findings)} finding(s)", file=sys.stderr)
        return 1
    print("check_repo: clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
