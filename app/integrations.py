import json
import platform
import sys
from pathlib import Path
from urllib.request import Request, urlopen

from platformdirs import user_cache_path

from app.config import APP_NAME, APP_VERSION
from app.events import Progress

LATEST_RELEASE_URL = "https://api.github.com/repos/electblake/Spectra/releases/latest"
RELEASES_URL = "https://github.com/electblake/Spectra/releases"
GITHUB_API_VERSION = "2026-03-10"

MENU_ENTRY = {
    "key": APP_NAME,
    "label": f"Open in {APP_NAME}",
}

MENU_CONTEXTS = (
    (r"Software\Classes\Directory\shell", "%1"),
    (r"Software\Classes\Directory\Background\shell", "%V"),
    (r"Software\Classes\Drive\shell", "%1"),
)


def _github_request(url: str) -> Request:
    return Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"{APP_NAME}/{APP_VERSION}",
            "X-GitHub-Api-Version": GITHUB_API_VERSION,
        },
    )


def _latest_release() -> dict:
    with urlopen(_github_request(LATEST_RELEASE_URL), timeout=30) as response:
        return json.load(response)


def _version_tuple(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def _setup_asset(release: dict, version: str) -> dict:
    setup_name = (
        f"{APP_NAME}-{version}-{platform.system().lower()}-"
        f"{platform.machine().lower()}-Setup.exe"
    )
    return next(asset for asset in release["assets"] if asset["name"] == setup_name)


def _download_setup(asset: dict, report) -> Path:
    updates_path = user_cache_path(APP_NAME, appauthor=False) / "updates"
    updates_path.mkdir(parents=True, exist_ok=True)
    setup_path = updates_path / asset["name"]
    with (
        urlopen(_github_request(asset["browser_download_url"]), timeout=30) as response,
        setup_path.open("wb") as setup_file,
    ):
        downloaded = 0
        report(Progress("Downloading update", 0, asset["size"]))
        while chunk := response.read(256 * 1024):
            setup_file.write(chunk)
            downloaded += len(chunk)
            report(Progress("Downloading update", downloaded, asset["size"]))
    return setup_path


def _launcher_command() -> list[str]:
    if getattr(sys, "frozen", False):
        return [str(Path(sys.executable).resolve())]

    return [str(Path(sys.executable).resolve()), "-I", "-m", "app"]


def _menu_key(root: str):
    return rf"{root}\{MENU_ENTRY['key']}"


def _quote(part: str) -> str:
    return f'"{part}"'


def _command_value(command: list[str], target_arg: str) -> str:
    return " ".join(_quote(part) for part in [*command, target_arg])


def _delete_key_if_exists(winreg, key_path: str) -> None:
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key_path)
    except FileNotFoundError:
        pass


def install():
    """Register Spectra in the Windows File Explorer context menu."""
    import winreg

    launcher_command = _launcher_command()
    icon_root = Path(sys._MEIPASS) if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[1]
    launcher_icon = _quote(str(icon_root / "Spectra.ico"))

    for root, target_arg in MENU_CONTEXTS:
        menu_key = _menu_key(root)
        command_value = _command_value(launcher_command, target_arg)
        print(f"File Explorer command ({root}): {command_value}")
        with winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER,
            menu_key,
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, MENU_ENTRY["label"])
            winreg.SetValueEx(key, "Icon", 0, winreg.REG_SZ, launcher_icon)
        with winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER,
            menu_key + r"\command",
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, command_value)

    print(
        f"[OK] Installed {len(MENU_CONTEXTS)} File Explorer context menu "
        f"entry(s): {launcher_command[0]}"
    )
    return 0


def uninstall():
    import winreg

    for root, _target_arg in MENU_CONTEXTS:
        menu_key = _menu_key(root)
        _delete_key_if_exists(winreg, menu_key + r"\command")
        _delete_key_if_exists(winreg, menu_key)

    print(f"[OK] Removed {len(MENU_CONTEXTS)} {APP_NAME} context menu entry(s).")
    return 0
