import json
import os
import platform
import shutil
import sys
import tempfile
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import messagebox, ttk
from urllib.request import Request, urlopen

from app.config import APP_NAME, APP_VERSION

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


class ExtrasTab(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.columnconfigure(0, weight=1)

        install_frame = ttk.LabelFrame(self, text="Install", padding=10)
        install_frame.grid(row=0, column=0, padx=10, pady=10, sticky=tk.EW)
        install_frame.columnconfigure(0, weight=1)

        self.install_file_explorer_button = ttk.Button(
            install_frame,
            text="Install in File Explorer",
            command=self.install_in_file_explorer,
        )
        self.install_file_explorer_button.grid(
            row=0,
            column=0,
            padx=10,
            pady=(0, 10),
            sticky=tk.W,
        )
        ttk.Label(
            install_frame,
            text=(
                'Adds "Open in Spectra" to File Explorer right-click menus for '
                "folders, folder backgrounds, and drives."
            ),
        ).grid(row=1, column=0, padx=10, pady=(0, 10), sticky=tk.W)

        update_actions = ttk.Frame(install_frame)
        update_actions.grid(
            row=2,
            column=0,
            padx=10,
            pady=(10, 10),
            sticky=tk.W,
        )

        self.check_updates_button = ttk.Button(
            update_actions,
            text="Check for Updates",
            command=self.check_for_updates,
        )
        self.check_updates_button.grid(
            row=0,
            column=0,
            sticky=tk.W,
        )
        ttk.Button(
            update_actions,
            text="View Releases",
            command=self.open_releases_page,
        ).grid(row=0, column=1, padx=(8, 0), sticky=tk.W)
        ttk.Label(
            install_frame,
            text=(
                "Checks the latest GitHub release and can download and open a "
                "newer Spectra Setup."
            ),
        ).grid(row=3, column=0, padx=10, pady=(0, 10), sticky=tk.W)
        self.update_status = ttk.Label(install_frame, text=f"Installed: {APP_VERSION}")
        self.update_status.grid(row=4, column=0, padx=10, sticky=tk.W)

    def install_in_file_explorer(self):
        install()
        messagebox.showinfo(
            "File Explorer",
            f"{APP_NAME} was installed in the File Explorer context menu.",
        )

    def check_for_updates(self):
        self.check_updates_button.config(state=tk.DISABLED)
        self.update_status.config(text="Checking GitHub for updates...")
        threading.Thread(target=self._check_for_updates, daemon=True).start()

    def open_releases_page(self):
        webbrowser.open(RELEASES_URL)

    def _check_for_updates(self):
        release = _latest_release()
        self.after(0, self._show_release, release)

    def _show_release(self, release):
        latest_version = release["tag_name"].removeprefix("v")
        if _version_tuple(latest_version) <= _version_tuple(APP_VERSION):
            self.update_status.config(text=f"Installed: {APP_VERSION} (up to date)")
            self.check_updates_button.config(state=tk.NORMAL)
            messagebox.showinfo(
                "No Updates Available",
                f"{APP_NAME} {APP_VERSION} is the latest version.",
                parent=self,
            )
            return

        self.update_status.config(
            text=f"Installed: {APP_VERSION} | Latest: {latest_version}"
        )
        download_update = messagebox.askyesno(
            "Update Available",
            (
                f"{APP_NAME} {latest_version} is available.\n\n"
                "Download and open the Setup now?"
            ),
            parent=self,
        )
        if not download_update:
            self.check_updates_button.config(state=tk.NORMAL)
            return

        asset = _setup_asset(release, latest_version)
        self.update_status.config(text=f"Downloading {asset['name']}...")
        threading.Thread(
            target=self._download_update,
            args=(asset,),
            daemon=True,
        ).start()

    def _download_update(self, asset):
        setup_path = _download_setup(asset)
        self.after(0, self._launch_setup, setup_path)

    def _launch_setup(self, setup_path):
        self.update_status.config(text=f"Opening {setup_path.name}...")
        os.startfile(setup_path)


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


def _download_setup(asset: dict) -> Path:
    setup_path = Path(tempfile.gettempdir()) / asset["name"]
    with (
        urlopen(_github_request(asset["browser_download_url"]), timeout=30) as response,
        setup_path.open("wb") as setup_file,
    ):
        shutil.copyfileobj(response, setup_file)
    return setup_path


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
