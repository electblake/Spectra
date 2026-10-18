import csv
import hashlib
import shutil
import threading
from pathlib import Path
from unittest.mock import Mock

import pytest
from PIL import Image
from PySide6.QtCore import QEventLoop, QObject, Qt, QTimer, QUrl
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QFileDialog, QFormLayout, QMessageBox, QPushButton

from app import application, config, integrations, main
from app.events import Log, Progress
from app.ui.window import MainWindow


def test_settings_config_folder_picker_save_and_open(controller, qapp, tmp_path, monkeypatch):
    window = MainWindow(controller)
    window.show()
    window.tabs.setCurrentIndex(1)
    assert isinstance(window.settings_options.layout(), QFormLayout)
    assert window.config_path.text() == str(tmp_path)
    chosen = tmp_path / "chosen-config"
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", Mock(return_value=str(chosen)))
    browse = window.findChild(QPushButton, "browseConfigFolder")
    QTest.mouseClick(browse, Qt.MouseButton.LeftButton)
    assert window.config_path.text() == str(chosen)
    assert config.settings_file() == tmp_path / "Spectra.ini"
    QTest.mouseClick(window.save, Qt.MouseButton.LeftButton)
    assert config.settings_file() == chosen / "Spectra.ini"
    assert config.read_user_settings()[0] == controller.settings
    opened = Mock()
    monkeypatch.setattr("app.ui.controller.QDesktopServices.openUrl", opened)
    QTest.mouseClick(window.findChild(QPushButton, "openConfigFolder"), Qt.MouseButton.LeftButton)
    opened.assert_called_once_with(QUrl.fromLocalFile(str(chosen)))
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", Mock(return_value=""))
    QTest.mouseClick(browse, Qt.MouseButton.LeftButton)
    assert window.config_path.text() == str(chosen)
    window.close()
    window.deleteLater()
    qapp.processEvents()


def test_extras_update_dialog_download_and_install(controller, qapp, monkeypatch, tmp_path):
    import platform

    version = "99.0.0"
    name = f"Spectra-{version}-{platform.system().lower()}-{platform.machine().lower()}-Setup.exe"
    asset = {"name": name}
    release = {"tag_name": f"v{version}", "assets": [asset]}
    entered = threading.Event()
    proceed = threading.Event()

    def latest():
        entered.set()
        assert proceed.wait(10)
        return release

    monkeypatch.setattr(integrations, "_latest_release", latest)
    setup = tmp_path / name
    setup.write_bytes(b"test installer")
    download_entered = threading.Event()
    download_proceed = threading.Event()

    def download(asset_arg, report):
        assert asset_arg == asset
        report(Progress("Downloading update", 0, 100))
        report(Progress("Downloading update", 50, 100))
        download_entered.set()
        assert download_proceed.wait(10)
        return setup

    monkeypatch.setattr(integrations, "_download_setup", download)
    window = MainWindow(controller)
    window.show()
    window.tabs.setCurrentIndex(2)
    check = next(button for button in window.extras.findChildren(QPushButton)
                 if button.text() == "Check for Updates")
    QTest.mouseClick(check, Qt.MouseButton.LeftButton)
    dialog = window.update_dialog
    assert entered.wait(5)
    assert dialog.isVisible()
    assert dialog.progress.maximum() == 0
    assert not dialog.download.isEnabled()
    assert not dialog.install.isEnabled()
    proceed.set()
    finish_task(controller)
    assert dialog.download.isEnabled()
    assert not dialog.install.isEnabled()
    QTest.mouseClick(dialog.download, Qt.MouseButton.LeftButton)
    assert download_entered.wait(5)
    qapp.processEvents()
    assert dialog.progress.value() == 500
    assert not dialog.install.isEnabled()
    assert not controller.install_requested
    download_proceed.set()
    finish_task(controller)
    assert dialog.install.isEnabled()
    assert not dialog.download.isEnabled()
    assert controller.installer_path == setup
    QTest.mouseClick(dialog.install, Qt.MouseButton.LeftButton)
    assert controller.install_requested
    assert not window.isVisible()
    window.deleteLater()
    qapp.processEvents()


def test_update_dialog_up_to_date(controller, qapp, monkeypatch):
    monkeypatch.setattr(integrations, "_latest_release", lambda: {"tag_name": f"v{config.APP_VERSION}"})
    window = MainWindow(controller)
    window._check_updates()
    finish_task(controller)
    dialog = window.update_dialog
    assert "Up to date" in dialog.status.text()
    assert not dialog.download.isEnabled()
    assert not dialog.install.isEnabled()
    dialog.reject()
    window.close()
    window.deleteLater()
    qapp.processEvents()


def finish_task(controller):
    loop = QEventLoop()
    controller._thread.finished.connect(loop.quit)
    QTimer.singleShot(15000, loop.quit)
    loop.exec()
    assert not controller.busy


def test_settings_save_restore_and_snapshot(controller, monkeypatch):
    entered = threading.Event()
    release = threading.Event()
    requests = []

    def run(request, stop, report):
        requests.append(request)
        entered.set()
        release.wait(5)
        return application.RunResult(request, stopped=False)

    monkeypatch.setattr(application, "run_sorting", run)
    controller.setSetting("feature_workers", 5)
    controller.setSetting("video_workers", 3)
    controller.setSetting("file_prefix", "literal_")
    controller.setSetting("count_start", 200)
    controller.saveSettings()
    saved, _ = config.read_user_settings()
    assert saved == controller.settings
    controller.start()
    assert entered.wait(5)
    controller.setSetting("dry_run", False)
    controller.setSetting("file_prefix", "changed_")
    controller.restoreDefaults()
    release.set()
    finish_task(controller)
    assert requests[0].file_prefix == "literal_"
    assert requests[0].count_start == 200
    assert requests[0].dry_run
    assert requests[0].feature_workers == 5
    assert requests[0].video_workers == 3
    assert controller.settings == config.default_settings()


def test_structured_progress_uses_emission_time(controller):
    controller._receive_event(Progress("Features", 0, 100, 1.0))
    controller._receive_event(Progress("Features", 50, 100, 11.0))
    assert controller.fraction == 0.5
    assert controller.metrics == "5.0 items/s · 0m 10s remaining"
    controller._receive_event(Log("Unrelated text 999/1000"))
    assert controller.fraction == 0.5
    controller._receive_event(Progress("Clustering", 0, 1, 12.0))
    assert controller.indeterminate
    assert controller.metrics == ""


def test_stop_prevents_rename(monkeypatch, tmp_path):
    stop = threading.Event()
    request = application.RunRequest(**(config.default_settings() | {"include_videos": False}))
    monkeypatch.setattr(main, "get_image_files", Mock(return_value=[tmp_path / "a.png"]))

    def stop_analysis(*args, **kwargs):
        stop.set()
        return []

    monkeypatch.setattr(main, "sort_with_tight_clustering", stop_analysis)
    rename = Mock()
    monkeypatch.setattr(main, "rename_images", rename)
    assert application.run_sorting(request, stop, Mock()).stopped
    rename.assert_not_called()


def test_close_waits_for_worker_and_requests_cancellation(controller, monkeypatch):
    entered = threading.Event()

    def run(request, stop, report):
        entered.set()
        assert stop.wait(5)
        return application.RunResult(request, stopped=True)

    monkeypatch.setattr(application, "run_sorting", run)
    ready = Mock()
    controller.closeReady.connect(ready)
    controller.start()
    assert entered.wait(5)
    assert not controller.requestClose()
    finish_task(controller)
    ready.assert_called_once()
    assert controller.status == "Sorting stopped"
    assert controller.requestClose()


def test_folder_selection_scans_with_qt_thread(controller, tmp_path):
    (tmp_path / "image.png").touch()
    (tmp_path / "clip.mp4").touch()
    messages = []
    controller.logMessage.connect(messages.append)
    controller.selectFolder(QUrl.fromLocalFile(str(tmp_path)))
    finish_task(controller)
    assert "Found 1 images and 1 videos" in messages[-1]
    assert Path(controller.settings["folder_path"]) == tmp_path


def test_application_dispatches_video_options(monkeypatch, tmp_path):
    request = application.RunRequest(**(config.default_settings() | {
        "folder_path": str(tmp_path), "video_workers": 3,
        "video_frame_percentage": 75, "png_compress_level": 8,
    }))
    monkeypatch.setattr(main, "get_image_files", Mock(return_value=[]))
    extraction = Mock(return_value=[tmp_path / "frame.png"])
    monkeypatch.setattr(main, "get_video_image_files", extraction)
    monkeypatch.setattr(main, "sort_with_tight_clustering", Mock(return_value=[("frame", [])]))
    rename = Mock()
    monkeypatch.setattr(main, "rename_media", rename)
    stop = threading.Event()
    report = Mock()
    application.run_sorting(request, stop, report)
    extraction.assert_called_once_with(str(tmp_path), stop, 75, 8, 3, report=report)
    assert rename.call_args.args[1] == str(tmp_path)


@pytest.mark.parametrize("dry_run", [True, False])
def test_qt_run_through_real_analysis_and_rename(controller, tmp_path, dry_run):
    originals = {}
    for name, color in (("red.png", "red"), ("blue.png", "blue")):
        path = tmp_path / name
        Image.new("RGB", (20, 20), color).save(path)
        originals[name] = path.read_bytes()
    controller.setSetting("folder_path", str(tmp_path))
    controller.setSetting("include_videos", False)
    controller.setSetting("file_prefix", "sorted_")
    controller.setSetting("dry_run", dry_run)
    messages = []
    outcomes = []
    controller.logMessage.connect(messages.append)
    controller.completed.connect(outcomes.append)
    controller.start()
    finish_task(controller)
    assert outcomes == [dry_run]
    assert controller.status == "Sorting complete"
    assert controller.fraction == 1.0
    assert any("red.png →" in message for message in messages)
    if dry_run:
        assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == originals
    else:
        assert {p.read_bytes() for p in tmp_path.glob("sorted_*.png")} == set(originals.values())
        assert {p.name: p.read_bytes() for p in (tmp_path / "backup_originals").iterdir()} == originals
        assert (tmp_path / "rename_mapping.csv").is_file()


def test_qt_stop_during_real_analysis(controller, tmp_path, monkeypatch):
    image = tmp_path / "red.png"
    Image.new("RGB", (30, 30), "red").save(image)
    monkeypatch.setattr(main, "get_image_files", lambda *args, **kwargs: [image] * 2000)
    controller.setSetting("folder_path", str(tmp_path))
    controller.setSetting("include_videos", False)
    outcomes = []
    controller.completed.connect(outcomes.append)

    def stop_at_features():
        if controller.status.startswith("Processing visual features"):
            controller.stop()

    controller.stateChanged.connect(stop_at_features)
    controller.start()
    finish_task(controller)
    assert controller.stopping
    assert controller.status == "Sorting stopped"
    assert outcomes == []
    assert list(tmp_path.iterdir()) == [image]


def test_widget_tabs_resize_editing_and_log(controller, qapp):
    window = MainWindow(controller)
    window.show()
    for width, height in ((1440, 960), (800, 650)):
        window.resize(width, height)
        QTest.qWait(100)
        assert window.isVisible()
        start = window.findChild(QObject, "startButton")
        assert start.property("width") > 0
    assert window.tabs.count() == 3
    tab_bar = window.tabs.tabBar()
    QTest.mouseClick(tab_bar, Qt.MouseButton.LeftButton, pos=tab_bar.tabRect(1).center())
    assert window.tabs.currentIndex() == 1
    assert not window.start.isVisible()
    assert not window.log.isVisible()
    assert window.save.isVisible()
    QTest.keyClick(tab_bar, Qt.Key.Key_Tab, Qt.KeyboardModifier.ControlModifier)
    assert window.tabs.currentIndex() == 2
    assert not window.save.isVisible()
    QTest.mouseClick(tab_bar, Qt.MouseButton.LeftButton, pos=tab_bar.tabRect(0).center())
    assert window.start.isVisible()
    assert window.log.isVisible()
    controller.setSetting("file_prefix", "widget_test_")
    assert window.fields["file_prefix"].text() == "widget_test_"
    controller.restoreDefaults()
    prefix = window.fields["file_prefix"]
    assert prefix.text() == ""
    prefix.setFocus()
    QTest.keyClick(prefix, Qt.Key.Key_X)
    assert controller.settings["file_prefix"] == "x"
    controller.restoreDefaults()
    assert prefix.text() == ""
    controller.clearLog.emit()
    controller.logMessage.emit("<literal text>")
    assert window.log.toPlainText() == "<literal text>"
    controller.completed.emit(True)
    QTest.qWait(50)
    dialog = window.findChild(QMessageBox)
    assert dialog.windowTitle() == "Dry Run Complete"
    QTest.keyClick(dialog, Qt.Key.Key_Escape)
    assert not dialog.isVisible()
    window.close()
    window.deleteLater()
    qapp.processEvents()


def test_widget_settings_sync_without_feedback(controller, qapp):
    window = MainWindow(controller)
    changes = Mock()
    controller.settingsChanged.connect(changes)
    controller.setSetting("rgb_weight", 1.25)
    assert window.fields["rgb_weight"].value() == 1.25
    changes.assert_called_once()
    window.fields["feature_workers"].setValue(6)
    assert controller.settings["feature_workers"] == 6
    controller.setSetting("parse_dates", True)
    assert window.fields["date_pattern"].isEnabled()
    controller.setSetting("auto_determine", True)
    assert not window.fields["similarity_threshold"].isEnabled()
    controller.setSetting("include_videos", False)
    assert not window.fields["video_frame_percentage"].isEnabled()
    controller.restoreDefaults()
    assert window.fields["feature_workers"].value() == config.FEATURE_WORKERS
    window.deleteLater()
    qapp.processEvents()


def test_widget_start_confirmation_and_busy_controls(controller, qapp, monkeypatch):
    window = MainWindow(controller)
    controller.setSetting("folder_path", "media")
    controller.setSetting("dry_run", False)
    start = Mock()
    monkeypatch.setattr(controller, "start", start)
    monkeypatch.setattr(QMessageBox, "question", Mock(return_value=QMessageBox.StandardButton.No))
    window.start.click()
    start.assert_not_called()
    monkeypatch.setattr(QMessageBox, "question", Mock(return_value=QMessageBox.StandardButton.Yes))
    window.start.click()
    start.assert_called_once()
    controller._busy = True
    controller._kind = "sort"
    controller.stateChanged.emit()
    assert not window.start.isEnabled()
    assert window.stop.isEnabled()
    assert not window.fields["folder_path"].isEnabled()
    assert not window.fields["feature_workers"].isEnabled()
    window.stop.click()
    assert controller.stopping
    assert not window.stop.isEnabled()
    window.deleteLater()
    qapp.processEvents()


def test_project_samples_through_widget_preview_and_rename(controller, qapp, tmp_path):
    source = Path(__file__).resolve().parents[1] / "samples"
    media = sorted(path for path in source.iterdir()
                   if path.suffix.lower() in config.IMAGE_EXTENSIONS | config.VIDEO_EXTENSIONS)
    images = sum(path.suffix.lower() in config.IMAGE_EXTENSIONS for path in media)
    videos = len(media) - images
    assert images > 0 and videos > 0

    def digest(path):
        with path.open("rb") as stream:
            return hashlib.file_digest(stream, "sha256").hexdigest()

    originals = {path.name: digest(path) for path in media}
    working = tmp_path / "sample-copy"
    working.mkdir()
    for path in media:
        shutil.copy2(path, working / path.name)

    window = MainWindow(controller)
    window.show()
    QTest.qWait(100)
    QTest.keyClicks(window.fields["folder_path"], str(working))
    QTest.keyClicks(window.fields["file_prefix"], "qt_sample_")
    tab_bar = window.tabs.tabBar()
    QTest.mouseClick(tab_bar, Qt.MouseButton.LeftButton, pos=tab_bar.tabRect(1).center())
    workers = window.fields["video_workers"]
    workers.setFocus()
    QTest.keyClick(workers, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
    QTest.keyClicks(workers, "3")
    QTest.keyClick(workers, Qt.Key.Key_Tab)
    assert controller.settings["video_workers"] == 3
    QTest.mouseClick(tab_bar, Qt.MouseButton.LeftButton, pos=tab_bar.tabRect(0).center())
    assert window.fields["dry_run"].isChecked()
    assert window.fields["backup"].isChecked()
    assert window.fields["include_videos"].isChecked()

    QTest.mouseClick(window.start, Qt.MouseButton.LeftButton)
    assert not window.start.isEnabled()
    assert window.stop.isEnabled()
    finish_task(controller)
    assert window.status.text() == "Sorting complete"
    assert window.progress.value() == 100
    assert {path.name: digest(path) for path in working.iterdir()} == originals
    preview_log = window.log.toPlainText()
    assert f"{len(media)} processed, 0 skipped" in preview_log
    assert "qt_sample_" in preview_log
    assert "DRY RUN COMPLETE - No files were modified" in preview_log
    dialog = window.findChild(QMessageBox)
    assert dialog.windowTitle() == "Dry Run Complete"
    QTest.mouseClick(dialog.button(QMessageBox.StandardButton.Close), Qt.MouseButton.LeftButton)
    QTest.qWait(50)

    QTest.mouseClick(window.fields["dry_run"], Qt.MouseButton.LeftButton)
    assert not controller.settings["dry_run"]

    def confirm(button):
        dialog = qapp.activeModalWidget()
        assert isinstance(dialog, QMessageBox)
        assert dialog.windowTitle() == "Confirm Rename"
        QTest.mouseClick(dialog.button(button), Qt.MouseButton.LeftButton)

    QTimer.singleShot(0, lambda: confirm(QMessageBox.StandardButton.No))
    QTest.mouseClick(window.start, Qt.MouseButton.LeftButton)
    assert not controller.busy
    assert {path.name: digest(path) for path in working.iterdir()} == originals

    QTimer.singleShot(0, lambda: confirm(QMessageBox.StandardButton.Yes))
    QTest.mouseClick(window.start, Qt.MouseButton.LeftButton)
    finish_task(controller)
    assert window.status.text() == "Sorting complete"
    assert window.progress.value() == 100
    assert window.start.isEnabled()
    assert not window.stop.isEnabled()
    dialog = window.findChild(QMessageBox)
    assert dialog.windowTitle() == "Sorting Complete"
    QTest.mouseClick(dialog.button(QMessageBox.StandardButton.Close), Qt.MouseButton.LeftButton)

    with (working / "rename_mapping.csv").open(newline="", encoding="utf-8") as stream:
        mapping = list(csv.DictReader(stream))
    assert len(mapping) == len(media)
    assert {row["Original Name"] for row in mapping} == set(originals)
    assert sorted(int(Path(row["New Name"]).stem.removeprefix("qt_sample_"))
                  for row in mapping) == list(range(1, len(media) + 1))
    for row in mapping:
        assert digest(working / row["New Name"]) == originals[row["Original Name"]]
    assert {path.name: digest(path) for path in (working / "backup_originals").iterdir()} == originals
    assert {path.name: digest(path) for path in media} == originals
    assert not list(working.glob("__temp_media_*"))
    assert not (working / ".spectra_video_grabs").exists()
    print(f"Qt UI verified: {images} images + {videos} videos; preview, cancellation, rename, mapping, backups, and original hashes passed")
    window.close()
    window.deleteLater()
    qapp.processEvents()


def test_installer_launch_waits_for_qt_event_loop_exit(tmp_path):
    import subprocess
    import sys

    script = """
import sys
from pathlib import Path
from PySide6.QtCore import QThread, QTimer
from PySide6.QtWidgets import QApplication
from app import config
from app.ui import main_ui
config.user_config_path = lambda *a, **k: Path(sys.argv[1])
OriginalController = main_ui.Controller
class UpdateController(OriginalController):
    def __init__(self, folder=None):
        super().__init__()
        self.installer_path = Path('downloaded-setup.exe')
        QTimer.singleShot(0, self.quitAndInstall)
main_ui.Controller = UpdateController
launched = []
def startfile(path):
    assert QThread.currentThread().loopLevel() == 0
    assert not any(window.isVisible() for window in QApplication.topLevelWidgets())
    launched.append(path)
main_ui.os.startfile = startfile
assert main_ui.main() == 0
assert launched == [Path('downloaded-setup.exe')]
"""
    subprocess.run([sys.executable, "-c", script, str(tmp_path)], check=True, timeout=30)
