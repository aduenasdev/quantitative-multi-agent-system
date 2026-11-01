from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from qmas.config import SOURCE_ROOT
from qmas.contracts.thesis import load_thesis
from tests.factories import make_thesis, thesis_document


def test_thesis_key_and_defaults() -> None:
    thesis = make_thesis()
    assert thesis.key == "test-thesis-v1"
    assert thesis.thresholds.min_deflated_sharpe == 0.95


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"thesis_id": "Not A Slug"}, "thesis_id"),
        ({"holdout_window": {"start": "2019-06-01", "end": "2020-12-31"}}, "holdout"),
        ({"design_window": {"start": "2019-01-01", "end": "2018-01-01"}}, "window end"),
        ({"unexpected": 1}, "unexpected"),
        ({"signal": {"name": "os.system"}}, "name"),
        ({"data": {"source": "real", "seed": 1}}, "source"),
    ],
)
def test_thesis_rejects_invalid_documents(overrides: dict[str, object], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        make_thesis(**overrides)


def test_thesis_is_frozen() -> None:
    thesis = make_thesis()
    with pytest.raises(ValidationError):
        thesis.version = 2


def test_content_hash_ignores_key_order_but_not_values() -> None:
    document = thesis_document()
    reordered = dict(reversed(list(document.items())))
    assert make_thesis(**reordered).content_hash() == make_thesis().content_hash()
    assert make_thesis(cost_bps=11.0).content_hash() != make_thesis().content_hash()
    assert len(make_thesis().content_hash()) == 64


def test_load_thesis_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "thesis.yaml"
    path.write_text(yaml.safe_dump(thesis_document()), encoding="utf-8")
    assert load_thesis(path) == make_thesis()


def test_load_thesis_rejects_non_mapping(tmp_path: Path) -> None:
    path = tmp_path / "thesis.yaml"
    path.write_text("- a\n- list\n", encoding="utf-8")
    with pytest.raises(ValueError, match="mapping"):
        load_thesis(path)


def test_example_theses_are_valid() -> None:
    assert SOURCE_ROOT is not None
    examples = sorted((SOURCE_ROOT / "examples" / "theses").glob("*.yaml"))
    assert examples
    for path in examples:
        assert load_thesis(path).thesis_id == path.stem
