"""Qt Widgets application bootstrap."""

import multiprocessing
import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

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
    app.setApplicationName("Spectra")
    app.setWindowIcon(QIcon(str(Path(__file__).resolve().parents[2] / "Spectra.ico")))
    controller = Controller(sys.argv[1] if len(sys.argv) > 1 else None)
    window = MainWindow(controller)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
