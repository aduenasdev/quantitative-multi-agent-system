from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check_repo.py"

PYPROJECT = """
[tool.check-repo]
allowed_words = ["Dueñas"]
max_file_bytes = 500
forbidden_patterns = ["*.db", ".env"]
skip_language_check = []
"""


def load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_repo", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_repo"] = module
    spec.loader.exec_module(module)
    return module


check_repo = load_script()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / "pyproject.toml").write_text(PYPROJECT, encoding="utf-8")
    return tmp_path


def findings(repo: Path, denylist: str | None = None) -> list[str]:
    report = check_repo.run(repo, denylist)
    assert isinstance(report.findings, list)
    return [str(item) for item in report.findings]


def test_check_repo_clean(repo: Path) -> None:
    (repo / "notes.md").write_text("Plain English text.\n", encoding="utf-8")
    assert findings(repo) == []


def test_check_repo_flags_spanish_characters(repo: Path) -> None:
    (repo / "notes.md").write_text("ok\nla señal\n", encoding="utf-8")
    assert findings(repo) == ["notes.md:2: Spanish character"]


def test_check_repo_flags_spanish_words_in_identifiers(repo: Path) -> None:
    (repo / "code.py").write_text("def cargar_precios():\n    pass\n", encoding="utf-8")
    assert findings(repo) == ["code.py:1: Spanish word(s): cargar, precios"]


def test_check_repo_allows_listed_words(repo: Path) -> None:
    (repo / "AUTHORS").write_text("Alejandro Dueñas\n", encoding="utf-8")
    assert findings(repo) == []


def test_check_repo_denylist_hides_the_term(
    repo: Path, tmp_path_factory: pytest.TempPathFactory
) -> None:
    deny = tmp_path_factory.mktemp("outside") / "denylist.txt"
    deny.write_text("# comment\n\nsecret-host.example\n", encoding="utf-8")
    (repo / "notes.md").write_text("see SECRET-HOST.example\n", encoding="utf-8")
    result = findings(repo, str(deny))
    assert result == ["notes.md:1: denylisted string #1"]
    assert "secret-host" not in result[0]


def test_check_repo_flags_forbidden_and_large_files(repo: Path) -> None:
    (repo / "panel.db").write_bytes(b"\0" * 10)
    (repo / "big.md").write_text("x" * 1000, encoding="utf-8")
    assert findings(repo) == [
        "big.md: file too large (1000 bytes > 500)",
        "panel.db: forbidden file type",
    ]


def test_check_repo_respects_gitignore(repo: Path) -> None:
    (repo / ".gitignore").write_text(".env\n", encoding="utf-8")
    (repo / ".env").write_text("TOKEN=x\n", encoding="utf-8")
    assert findings(repo) == []


def test_check_repo_main_exit_codes(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(check_repo, "REPO_ROOT", repo)
    (repo / "notes.md").write_text("Plain English.\n", encoding="utf-8")
    assert check_repo.main() == 0
    assert "check_repo: clean" in capsys.readouterr().out
    (repo / "notes.md").write_text("los datos\n", encoding="utf-8")
    assert check_repo.main() == 1
    assert "Spanish word(s): datos, los" in capsys.readouterr().out


def test_check_repo_reports_missing_denylist(repo: Path) -> None:
    assert findings(repo, str(repo / "missing.txt")) == [
        "QMAS_DENYLIST_FILE: denylist file not found"
    ]


def test_denylist_setting_prefers_environment(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (repo / ".env").write_text("OTHER=1\nQMAS_DENYLIST_FILE='/from/env-file'\n", encoding="utf-8")
    monkeypatch.delenv("QMAS_DENYLIST_FILE", raising=False)
    assert check_repo.denylist_setting(repo) == "/from/env-file"
    monkeypatch.setenv("QMAS_DENYLIST_FILE", "")
    assert check_repo.denylist_setting(repo) == ""


def test_denylist_setting_without_env_file(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("QMAS_DENYLIST_FILE", raising=False)
    assert check_repo.denylist_setting(repo) is None
    (repo / ".env").write_text("OTHER=1\n", encoding="utf-8")
    assert check_repo.denylist_setting(repo) is None
