"""Qt Widgets application bootstrap."""

import multiprocessing
import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from app.config import APP_NAME, APP_ORGANIZATION, APP_VERSION
from app.ui.controller import Controller
from app.ui.window import MainWindow


def main():
    multiprocessing.freeze_support()
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        create_mutex = ctypes.windll.kernel32.CreateMutexW
        create_mutex.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
        create_mutex.restype = wintypes.HANDLE
        # Windows keeps this mutex alive until the process exits.
        create_mutex(None, False, "electblake.Spectra.Running")

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_ORGANIZATION)
    app.setApplicationVersion(APP_VERSION)
    app.setWindowIcon(QIcon(str(Path(__file__).resolve().parents[2] / "Spectra.ico")))
    controller = Controller(sys.argv[1] if len(sys.argv) > 1 else None)
    window = MainWindow(controller)
    window.show()
    result = app.exec()
    if controller.install_requested:
        installer = str(controller.installer_path.resolve()).replace("'", "''")
        launcher = subprocess.Popen(
            [
                str(Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"),
                "-NoProfile", "-NonInteractive", "-Command",
                (
                    "$ErrorActionPreference = 'Stop'; "
                    f"$process = [System.Diagnostics.Process]::GetProcessById({os.getpid()}); "
                    "$null = $process.Handle; "
                    "[Console]::Out.WriteLine('ready'); "
                    "$process.WaitForExit(); "
                    f"Start-Process -FilePath '{installer}'"
                ),
            ],
            stdout=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        # Keep this process alive until the helper holds its process handle.
        launcher.stdout.readline()
        launcher.stdout.close()
    return result


if __name__ == "__main__":
    sys.exit(main())
