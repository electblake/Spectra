import threading
from pathlib import Path
from unittest.mock import Mock

import pytest
from PIL import Image
from PySide6.QtCore import QEventLoop, QObject, Qt, QTimer, QUrl
from PySide6.QtTest import QTest

from app import application, config, main
from app.events import Log, Progress
from app.ui.main_ui import create_engine


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


def test_qml_load_resize_binding_and_log(controller, qapp):
    engine = create_engine(controller)
    warnings = []
    engine.warnings.connect(lambda errors: warnings.extend(error.toString() for error in errors))
    window = engine.rootObjects()[0]
    for width, height in ((1440, 960), (800, 650)):
        window.setWidth(width)
        window.setHeight(height)
        QTest.qWait(100)
        assert window.isVisible()
        start = window.findChild(QObject, "startButton")
        assert start.property("width") > 0
    controller.setSetting("file_prefix", "qml_test_")
    assert window.findChild(QObject, "file_prefix").property("text") == "qml_test_"
    controller.restoreDefaults()
    assert window.findChild(QObject, "file_prefix").property("text") == ""
    prefix = window.findChild(QObject, "file_prefix")
    prefix.forceActiveFocus()
    QTest.keyClick(window, Qt.Key.Key_X)
    assert controller.settings["file_prefix"] == "x"
    controller.restoreDefaults()
    assert prefix.property("text") == ""
    controller.clearLog.emit()
    controller.logMessage.emit("<literal text>")
    assert window.findChild(QObject, "activityLog").property("text") == "<literal text>"
    controller.completed.emit(True)
    QTest.qWait(50)
    assert not warnings
    window.close()
    engine.deleteLater()
    qapp.processEvents()
