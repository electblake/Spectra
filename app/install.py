import shutil
import sys
from pathlib import Path

from app.config import APP_NAME

MENU_ENTRY = {
    "key": APP_NAME,
    "label": f"Open in {APP_NAME}",
}

MENU_CONTEXTS = (
    (r"Software\Classes\Directory\shell", "%1"),
    (r"Software\Classes\Directory\Background\shell", "%V"),
    (r"Software\Classes\Drive\shell", "%1"),
)


def _launcher_command() -> list[str]:
    if getattr(sys, "frozen", False):
        return [str(Path(sys.executable).resolve())]

    argv_launcher = Path(sys.argv[0])
    if argv_launcher.exists() and argv_launcher.suffix.lower() in {".exe", ".bat", ".cmd"}:
        return [str(argv_launcher.resolve())]

    for command_name in (f"{APP_NAME.lower()}.exe", APP_NAME.lower()):
        launcher = shutil.which(command_name)
        if launcher:
            return [str(Path(launcher).resolve())]

    return [str(Path(sys.executable).resolve()), "-m", "app"]


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
    launcher_icon = launcher_command[0]

    for root, target_arg in MENU_CONTEXTS:
        menu_key = _menu_key(root)
        command_value = _command_value(launcher_command, target_arg)
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
