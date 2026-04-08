from pathlib import Path

import pytest

from protondl.util.steam import (
    get_steam_ctool_info,
    get_steam_vdf_compat_tool_mapping,
    vdf_safe_load,
)


def test_vdf_safe_load_returns_dict_for_valid_vdf(tmp_path: Path) -> None:
    vdf_file = tmp_path / "config.vdf"
    vdf_file.write_text('"foo"\n{\n    "bar" "baz"\n}\n', encoding="utf-8")

    result = vdf_safe_load(vdf_file)

    assert result == {"foo": {"bar": "baz"}}


def test_vdf_safe_load_raises_value_error_when_file_cannot_be_read(tmp_path: Path) -> None:
    missing_file = tmp_path / "missing.vdf"

    with pytest.raises(ValueError, match="Loading .* failed"):
        vdf_safe_load(missing_file)


def test_get_steam_vdf_compat_tool_mapping_returns_mapping_for_valve_key() -> None:
    config_data = {
        "InstallConfigStore": {
            "Software": {
                "valve": {
                    "Steam": {
                        "CompatToolMapping": {
                            "275850": {
                                "name": "GE-Proton10-14",
                                "config": "",
                                "priority": "250",
                            }
                        }
                    }
                }
            }
        }
    }

    mapping = get_steam_vdf_compat_tool_mapping(config_data)

    assert mapping == {
        "275850": {
            "name": "GE-Proton10-14",
            "config": "",
            "priority": "250",
        }
    }


def test_get_steam_ctool_info_returns_compat_tool_mapping(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    steam_root = tmp_path
    appinfo_file = steam_root / "appcache" / "appinfo.vdf"
    appinfo_file.parent.mkdir(parents=True, exist_ok=True)
    appinfo_file.write_bytes(b"dummy")

    def mock_parse_appinfo(
        _fp: object, mapper: type[dict[object, object]] = dict
    ) -> tuple[dict[str, object], list[dict[str, object]]]:
        return (
            {"magic": b")DV\x07", "universe": 1},
            [
                {
                    "appid": 891390,
                    "data": {
                        "appinfo": {
                            "extended": {
                                "compat_tools": {
                                    "proton_experimental": {
                                        "appid": 1493710,
                                        "from_oslist": "windows",
                                    }
                                }
                            }
                        }
                    },
                }
            ],
        )

    monkeypatch.setattr("protondl.util.steam.parse_appinfo", mock_parse_appinfo)

    result = get_steam_ctool_info(steam_root)

    assert result == {
        "1493710": {
            "name": "proton_experimental",
            "from_oslist": "windows",
        }
    }
