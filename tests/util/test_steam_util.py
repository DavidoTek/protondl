from pathlib import Path

import pytest

from protondl.util.steam import (
    SteamUser,
    calc_shortcut_app_id,
    determine_most_recent_steam_user,
    get_steam_ctool_info,
    get_steam_shortcuts,
    get_steam_users,
    get_steam_vdf_compat_tool_mapping,
    vdf_safe_load,
    write_steam_shortcuts,
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


def test_calc_shortcut_app_id() -> None:
    """
    Test that the shortcut appid is calculated from the executable and name.
    """
    assert calc_shortcut_app_id("Test Game", "/opt/games/test.exe") == -572422462


def test_get_steam_users_returns_users_from_loginusers(tmp_path: Path) -> None:
    """
    Test that Steam users are parsed from the loginusers.vdf file.
    """
    steam_root = tmp_path / "steam"
    config_dir = steam_root / "config"
    config_dir.mkdir(parents=True)
    (config_dir / "loginusers.vdf").write_text(
        '"users"\n'
        "{\n"
        '\t"76561197960265851"\n'
        "\t{\n"
        '\t\t"AccountName"\t\t"user1"\n'
        '\t\t"PersonaName"\t\t"Person 1"\n'
        '\t\t"MostRecent"\t\t"1"\n'
        '\t\t"Timestamp"\t\t"1234567890"\n'
        "\t}\n"
        "}\n",
        encoding="utf-8",
    )

    users = get_steam_users(steam_root)

    assert users == [
        SteamUser(
            long_id=76561197960265851,
            account_name="user1",
            persona_name="Person 1",
            most_recent=True,
            timestamp=1234567890,
        )
    ]
    assert users[0].short_id == 123


def test_get_steam_users_returns_empty_list_when_file_missing(tmp_path: Path) -> None:
    steam_root = tmp_path / "steam"

    assert get_steam_users(steam_root) == []


def test_determine_most_recent_steam_user_returns_most_recent() -> None:
    older = SteamUser(1, "a", "A", most_recent=False, timestamp=1)
    recent = SteamUser(2, "b", "B", most_recent=True, timestamp=2)

    assert determine_most_recent_steam_user([older, recent]) is recent


def test_determine_most_recent_steam_user_returns_first_without_recent() -> None:
    older = SteamUser(1, "a", "A", most_recent=False, timestamp=1)
    newer = SteamUser(2, "b", "B", most_recent=False, timestamp=2)

    assert determine_most_recent_steam_user([older, newer]) is older


def test_determine_most_recent_steam_user_returns_none_when_empty() -> None:
    assert determine_most_recent_steam_user([]) is None


def test_get_steam_shortcuts_returns_empty_list_when_no_userdata(tmp_path: Path) -> None:
    steam_root = tmp_path / "steam"

    assert get_steam_shortcuts(steam_root) == []


def test_write_and_get_steam_shortcuts_round_trip(tmp_path: Path) -> None:
    """
    Test that shortcuts can be written to and read back from the
    shortcuts.vdf file.
    """
    steam_root = tmp_path / "steam"
    shortcut = {
        "user": "123",
        "sid": "0",
        "appid": 1000,
        "name": "Test Game",
        "exe": "/opt/games/test.exe",
        "startdir": "/opt/games",
        "icon": "/opt/games/test.png",
    }

    write_steam_shortcuts(steam_root, [shortcut])

    assert get_steam_shortcuts(steam_root) == [shortcut]


def test_write_steam_shortcuts_updates_existing_and_deletes(tmp_path: Path) -> None:
    """
    Test that existing shortcuts are updated in place and marked shortcuts
    are removed.
    """
    steam_root = tmp_path / "steam"
    write_steam_shortcuts(
        steam_root,
        [
            {
                "user": "123",
                "sid": "0",
                "appid": 1000,
                "name": "Game",
                "exe": "/games/game",
                "startdir": "",
                "icon": "",
            },
            {
                "user": "123",
                "sid": "1",
                "appid": 1001,
                "name": "Game 2",
                "exe": "/games/game2",
                "startdir": "",
                "icon": "",
            },
        ],
    )

    write_steam_shortcuts(
        steam_root,
        [
            {
                "user": "123",
                "sid": "0",
                "appid": 1000,
                "name": "Renamed",
                "exe": "/games/renamed",
                "startdir": "/games",
                "icon": "/icons/renamed.png",
            }
        ],
        delete={"123": ["1"]},
    )

    entries = get_steam_shortcuts(steam_root)

    assert entries == [
        {
            "user": "123",
            "sid": "0",
            "appid": 1000,
            "name": "Renamed",
            "exe": "/games/renamed",
            "startdir": "/games",
            "icon": "/icons/renamed.png",
        }
    ]


def test_get_steam_shortcuts_converts_negative_appid_to_unsigned(tmp_path: Path) -> None:
    """
    Test that a negative appid stored in the shortcuts.vdf file is converted
    to an unsigned value when read.
    """
    steam_root = tmp_path / "steam"
    write_steam_shortcuts(
        steam_root,
        [
            {
                "user": "123",
                "sid": "0",
                "appid": -572422462,
                "name": "Test Game",
                "exe": "/opt/games/test.exe",
                "startdir": "",
                "icon": "",
            }
        ],
    )

    entries = get_steam_shortcuts(steam_root)

    assert entries[0]["appid"] == 3722544834
