import json
import subprocess
import sys
from configparser import ConfigParser
from io import BytesIO

from PySide6.QtCore import QSettings

from app import config, integrations


def test_existing_separator_and_prefix_settings_are_preserved(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "user_config_path", lambda *args, **kwargs: tmp_path)
    settings = QSettings(str(tmp_path / "Spectra.ini"), QSettings.Format.IniFormat)
    settings.setValue("renaming/file_prefix", "saved_")
    settings.setValue("renaming/separator", "_")
    settings.sync()
    loaded, _ = config.read_user_settings()
    assert loaded["file_prefix"] == "saved_"
    assert loaded["separator"] == "_"
    assert loaded["prefix_from_folder"] is False
    assert loaded["prefix_folder_index"] == 0
    config.save_user_settings(**loaded)
    assert config.read_user_settings()[0] == loaded


def test_qsettings_round_trip_in_fresh_process(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "user_config_path", lambda *args, **kwargs: tmp_path)
    values = config.default_settings() | {
        "folder_path": r"C:\media\2026\日本語",
        "file_prefix": "@prefix, 50% é_",
        "prefix_from_folder": True,
        "prefix_folder_index": -2,
        "separator": "-",
        "date_pattern": r"(?P<date>\d{4}\.\d{2}\.\d{2})",
        "dry_run": False,
        "backup": True,
        "rgb_weight": 1.25,
        "count_start": 27,
        "mapping_csv_folder": "{workFolder}/../Data/日本語",
        "overwrite_mapping_csv": True,
    }
    config.save_user_settings(**values)
    settings = QSettings(str(tmp_path / "Spectra.ini"), QSettings.Format.IniFormat)
    assert settings.status() == QSettings.Status.NoError
    assert set(settings.allKeys()) == set(config.SETTINGS_KEYS.values())
    result = subprocess.run([
        sys.executable, "-c",
        ("import json, sys; from pathlib import Path; from app import config; "
         "config.user_config_path = lambda *a, **k: Path(sys.argv[1]); "
         "print(json.dumps(config.read_user_settings()[0]))"),
        str(tmp_path),
    ], check=True, capture_output=True, text=True)
    loaded = json.loads(result.stdout)
    assert loaded == values
    assert all(type(loaded[key]) is type(value) for key, value in values.items())


def test_legacy_settings_converted_once_without_modifying_original(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "user_config_path", lambda *args, **kwargs: tmp_path)
    values = config.default_settings() | {
        "folder_path": r"C:\Users\test\media",
        "date_pattern": r"\d{4}[\.\-]\d{2}",
        "file_prefix": "préfix, @50%_",
        "dry_run": False,
    }
    legacy = ConfigParser(interpolation=None)
    for key, setting_path in config.SETTINGS_KEYS.items():
        group, name = setting_path.split("/")
        if not legacy.has_section(group):
            legacy.add_section(group)
        legacy.set(group, name, str(values[key]))
    legacy_path = tmp_path / "settings.ini"
    with legacy_path.open("w", encoding="utf-8") as stream:
        legacy.write(stream)
    original = legacy_path.read_bytes()
    loaded, path = config.read_user_settings()
    assert loaded == values
    assert path == tmp_path / "Spectra.ini"
    assert legacy_path.read_bytes() == original
    changed = values | {"file_prefix": "new_"}
    config.save_user_settings(**changed)
    assert config.read_user_settings()[0] == changed
    assert legacy_path.read_bytes() == original


def test_config_uses_roaming_platform_directory(tmp_path, monkeypatch):
    calls = []

    def config_path(*args, **kwargs):
        calls.append((args, kwargs))
        return tmp_path

    monkeypatch.setattr(config, "user_config_path", config_path)
    assert config.settings_file() == tmp_path / "Spectra.ini"
    assert calls == [((config.APP_NAME,), {"appauthor": False, "roaming": True})]
    assert not config._settings_store().fallbacksEnabled()


def test_update_download_uses_app_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(integrations, "user_cache_path", lambda *args, **kwargs: tmp_path / "cache")
    monkeypatch.setattr(integrations, "urlopen", lambda *args, **kwargs: BytesIO(b"installer"))
    events = []
    result = integrations._download_setup({
        "name": "Spectra-Setup.exe",
        "size": 9,
        "browser_download_url": "https://example.test/setup.exe",
    }, events.append)
    assert result == tmp_path / "cache" / "updates" / "Spectra-Setup.exe"
    assert result.read_bytes() == b"installer"
    assert [(event.current, event.total) for event in events] == [(0, 9), (9, 9)]


def test_custom_config_folder_survives_restart(tmp_path, monkeypatch):
    default = tmp_path / "platform-config"
    custom = tmp_path / "selected-config"
    monkeypatch.setattr(config, "user_config_path", lambda *args, **kwargs: default)
    values = config.default_settings() | {"file_prefix": "custom_"}
    config.save_user_settings(**config.default_settings())
    original = (default / "Spectra.ini").read_bytes()
    config.save_user_settings(config_folder=str(custom), **values)
    assert config.settings_file() == custom / "Spectra.ini"
    assert config.read_user_settings()[0] == values
    assert (default / "Spectra.ini").read_bytes() == original
    result = subprocess.run([
        sys.executable, "-c",
        ("import json, sys; from pathlib import Path; from app import config; "
         "config.user_config_path = lambda *a, **k: Path(sys.argv[1]); "
         "print(json.dumps([config.read_user_settings()[0], str(config.settings_file())]))"),
        str(default),
    ], check=True, capture_output=True, text=True)
    loaded, path = json.loads(result.stdout)
    assert loaded == values
    assert path == str(custom / "Spectra.ini")
