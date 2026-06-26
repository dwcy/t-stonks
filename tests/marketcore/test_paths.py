from __future__ import annotations

import pytest

from marketcore.paths import config_base, settings_path, trades_path


def test_goldsilver_settings_path_unchanged() -> None:
    from goldsilver.data.settings import settings_path as gs_settings_path

    assert settings_path("goldsilver") == gs_settings_path()
    assert gs_settings_path().parent.name == "goldsilver"
    assert gs_settings_path().name == "settings.json"


def test_quantum_path_isolated_from_goldsilver() -> None:
    assert settings_path("quantum") != settings_path("goldsilver")
    assert settings_path("quantum").parent.name == "quantum"
    assert trades_path("quantum").parent.name == "quantum"


def test_invalid_app_name_rejected() -> None:
    for bad in ["", "Bad Name", "../escape", "UPPER"]:
        with pytest.raises(ValueError):
            config_base(bad)
