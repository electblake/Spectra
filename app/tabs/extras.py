import shutil
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

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


class ExtrasTab(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)

        self.install_file_explorer_button = ttk.Button(
            self,
            text="Install in File Explorer",
            command=self.install_in_file_explorer,
        )
        self.install_file_explorer_button.grid(
            row=0,
            column=0,
            padx=10,
            pady=10,
        )
        ttk.Label(
            self,
            text=(
                'Adds "Open in Spectra" to File Explorer right-click menus for '
                "folders, folder backgrounds, and drives."
            ),
        ).grid(row=1, column=0, padx=10, pady=(0, 10), sticky=tk.W)

    def install_in_file_explorer(self):
        install()
        messagebox.showinfo(
            "File Explorer",
            f"{APP_NAME} was installed in the File Explorer context menu.",
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
    launcher_icon = f"{_quote(launcher_command[0])},0"

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
