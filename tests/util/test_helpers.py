import json
from pathlib import Path

import pytest

from protondl.util.helpers import detect_hwcaps, json_safe_load, read_cpu_flags


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


def test_read_cpu_flags_returns_empty_without_proc_cpuinfo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("builtins.open", lambda *args, **kwargs: (_ for _ in ()).throw(OSError))

    assert read_cpu_flags() == frozenset()


def _detect_hwcaps(monkeypatch: pytest.MonkeyPatch, flags: set[str]) -> frozenset[str]:
    monkeypatch.setattr("protondl.util.helpers.read_cpu_flags", lambda: frozenset(flags))
    return detect_hwcaps()


def test_detect_hwcaps_plain_x86_64(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _detect_hwcaps(monkeypatch, {"sse4_1", "sse4_2"}) == {"x86_64"}


def test_detect_hwcaps_v2(monkeypatch: pytest.MonkeyPatch) -> None:
    flags = {"sse4_1", "sse4_2", "ssse3"}
    assert _detect_hwcaps(monkeypatch, flags) == {"x86_64", "x86_64_v2"}


def test_detect_hwcaps_v3(monkeypatch: pytest.MonkeyPatch) -> None:
    flags = {"sse4_1", "sse4_2", "ssse3", "avx", "avx2"}
    assert _detect_hwcaps(monkeypatch, flags) == {"x86_64", "x86_64_v2", "x86_64_v3"}


def test_detect_hwcaps_v4(monkeypatch: pytest.MonkeyPatch) -> None:
    flags = {
        "sse4_1",
        "sse4_2",
        "ssse3",
        "avx",
        "avx2",
        "avx512f",
        "avx512bw",
        "avx512cd",
        "avx512dq",
        "avx512vl",
    }
    assert _detect_hwcaps(monkeypatch, flags) == {
        "x86_64",
        "x86_64_v2",
        "x86_64_v3",
        "x86_64_v4",
    }


def test_detect_hwcaps_missing_required_flag_excludes_level(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    flags = {"sse4_1", "sse4_2", "ssse3", "avx"}
    assert _detect_hwcaps(monkeypatch, flags) == {"x86_64", "x86_64_v2"}
