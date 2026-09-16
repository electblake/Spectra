import platform
import sys
from pathlib import Path

from app.tabs.extras import _launcher_command, _setup_asset, _version_tuple


def test_version_tuple_orders_release_versions() -> None:
    assert _version_tuple("0.5.2") > _version_tuple("0.5.1")
    assert _version_tuple("0.6.0") > _version_tuple("0.5.9")


def test_explorer_launcher_uses_current_interpreter(monkeypatch, tmp_path) -> None:
    unrelated_launcher = tmp_path / "spectra.exe"
    unrelated_launcher.touch()
    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.setattr(sys, "argv", [str(unrelated_launcher)])

    assert _launcher_command() == [str(Path(sys.executable).resolve()), "-I", "-m", "app"]


def test_setup_asset_selects_current_windows_architecture() -> None:
    version = "0.6.0"
    setup_name = (
        f"Spectra-{version}-{platform.system().lower()}-"
        f"{platform.machine().lower()}-Setup.exe"
    )
    setup_asset = {
        "name": setup_name,
        "browser_download_url": "https://example.test/Spectra-Setup.exe",
    }
    release = {
        "assets": [
            {"name": f"Spectra-{version}-windows-amd64-portable.zip"},
            setup_asset,
        ]
    }

    assert _setup_asset(release, version) == setup_asset
