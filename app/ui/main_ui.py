"""Qt Quick application bootstrap."""

import multiprocessing
import sys
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

from app.ui.controller import Controller


def create_engine(controller):
    engine = QQmlApplicationEngine()
    engine.setInitialProperties({"controller": controller})
    engine.load(QUrl.fromLocalFile(str(Path(__file__).parent / "qml" / "Main.qml")))
    return engine


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

    QQuickStyle.setStyle("Fusion")
    app = QGuiApplication(sys.argv)
    app.setApplicationName("Spectra")
    app.setWindowIcon(QIcon(str(Path(__file__).resolve().parents[2] / "Spectra.ico")))
    controller = Controller(sys.argv[1] if len(sys.argv) > 1 else None)
    engine = create_engine(controller)
    window = engine.rootObjects()[0]
    controller.closeReady.connect(window.close)
    exit_code = app.exec()
    del engine
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
