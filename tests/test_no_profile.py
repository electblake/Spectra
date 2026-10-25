import os
import subprocess
import sys
from unittest.mock import Mock

import pytest
from PySide6.QtTest import QTest

from app import config
from app.ui import main_ui
from app.ui.controller import Controller
from app.ui.window import MainWindow


@pytest.mark.parametrize("existing_profile", [False, True])
def test_no_profile_ignores_config_and_never_saves(qapp, tmp_path, monkeypatch, existing_profile):
    profile = tmp_path / "profile"
    monkeypatch.setattr(config, "user_config_path", lambda *args, **kwargs: profile)
    if existing_profile:
        profile.mkdir()
        for name in ("Spectra.ini", "locations.ini", "ui.ini", "settings.ini"):
            (profile / name).write_text("invalid profile contents", encoding="utf-8")
    original = {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}
    operations = {}
    for name in ("read_user_settings", "settings_file", "read_window_layout",
                 "save_user_settings", "save_window_layout"):
        operations[name] = Mock(wraps=getattr(config, name))
        monkeypatch.setattr(config, name, operations[name])

    controller = Controller(no_profile=True)
    assert controller.settings == config.default_settings()
    assert controller.settings_path is None
    assert controller.configFolder == str(profile)
    window = MainWindow(controller)
    window.show()
    window.resize(1060, 740)
    window.move_parameters_left.trigger()
    QTest.qWait(400)
    assert not window.layout_save_timer.isActive()
    controller.setSetting("file_prefix", "temporary_")
    controller.setConfigFolder(str(tmp_path / "custom"))
    messages = []
    controller.logMessage.connect(messages.append)
    window.save.click()
    assert messages == ["Settings are not saved in -NoProfile mode."]
    assert controller.settings["file_prefix"] == "temporary_"
    assert controller.settings_path is None
    window.reset_layout.trigger()
    window.close()
    assert not window.layout_save_timer.isActive()
    window.deleteLater()
    qapp.processEvents()

    for operation in operations.values():
        operation.assert_not_called()
    assert {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()} == original
    assert not (tmp_path / "custom").exists()
    assert profile.exists() is existing_profile


@pytest.mark.parametrize(("arguments", "folder", "no_profile"), [
    ([], None, False),
    (["C:/media folder"], "C:/media folder", False),
    (["-NoProfile"], None, True),
    (["-NoProfile", "C:/media folder"], "C:/media folder", True),
    (["C:/media folder", "-NoProfile"], "C:/media folder", True),
])
def test_launch_arguments(qapp, tmp_path, monkeypatch, arguments, folder, no_profile):
    monkeypatch.setattr(config, "user_config_path", lambda *args, **kwargs: tmp_path)
    config.save_user_settings(**(config.default_settings() | {"file_prefix": "saved_"}))
    controller_factory = Mock(wraps=Controller)
    application = Mock()
    application.exec.return_value = 0
    application_factory = Mock(return_value=application)
    window_factory = Mock()
    monkeypatch.setattr(main_ui.sys, "argv", ["spectra", *arguments])
    monkeypatch.setattr(main_ui, "QApplication", application_factory)
    monkeypatch.setattr(main_ui, "Controller", controller_factory)
    monkeypatch.setattr(main_ui, "MainWindow", window_factory)

    assert main_ui.main() == 0
    controller_factory.assert_called_once_with(folder, no_profile=no_profile)
    controller = window_factory.call_args.args[0]
    assert controller.settings["folder_path"] == (folder or "")
    assert controller.settings["file_prefix"] == ("" if no_profile else "saved_")
    application_factory.assert_called_once_with(["spectra", *[arg for arg in arguments if arg != "-NoProfile"]])
    window_factory.return_value.show.assert_called_once_with()


def test_no_profile_module_launch_offscreen(tmp_path):
    result = subprocess.run(
        [sys.executable, "-c", """
import runpy
import sys
from pathlib import Path
from PySide6.QtCore import QTimer
from app import config
from app.ui import main_ui

profile = Path(sys.argv[1]) / "profile"
config.user_config_path = lambda *args, **kwargs: profile
OriginalWindow = main_ui.MainWindow

class TestWindow(OriginalWindow):
    def show(self):
        assert self.controller.no_profile
        assert self.controller.settings == config.default_settings()
        super().show()
        self.resize(1060, 740)
        self.save.click()
        QTimer.singleShot(500, self.close)

main_ui.MainWindow = TestWindow
sys.argv = ["spectra", "-NoProfile"]
runpy.run_module("app", run_name="__main__")
assert not profile.exists()
""", str(tmp_path)],
        env=os.environ | {"QT_QPA_PLATFORM": "offscreen"},
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
