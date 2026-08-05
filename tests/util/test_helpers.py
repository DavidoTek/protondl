import json
from pathlib import Path

import pytest

from protondl.util.helpers import json_safe_load


def _write(tmp_path: Path, rel_path: str, data: object) -> Path:
    path = tmp_path / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_json_safe_load_returns_dict_for_valid_json(tmp_path: Path) -> None:
    json_file = _write(tmp_path, "config.json", {"games": [{"app_name": "a"}]})

    result = json_safe_load(json_file)

    assert result == {"games": [{"app_name": "a"}]}


def test_json_safe_load_raises_when_file_missing(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Loading .* failed"):
        json_safe_load(tmp_path / "missing.json")


def test_json_safe_load_raises_for_invalid_json(tmp_path: Path) -> None:
    json_file = tmp_path / "broken.json"
    json_file.write_text("{not valid", encoding="utf-8")

    with pytest.raises(ValueError, match="Loading .* failed"):
        json_safe_load(json_file)


def test_json_safe_load_raises_for_non_dict_root(tmp_path: Path) -> None:
    json_file = _write(tmp_path, "list.json", [1, 2, 3])

    with pytest.raises(ValueError, match="did not return a dict"):
        json_safe_load(json_file)
