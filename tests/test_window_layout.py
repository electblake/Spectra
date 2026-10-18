from unittest.mock import Mock

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from app import config
from app.ui.controller import Controller
from app.ui.window import MainWindow


def test_layout_debounces_and_restores(controller, qapp, monkeypatch):
    window = MainWindow(controller)
    window.show()
    QTest.qWait(400)
    save = Mock(wraps=config.save_window_layout)
    monkeypatch.setattr(config, "save_window_layout", save)
    for width in (1000, 1040, 1080):
        window.resize(width, 720)
        QTest.qWait(40)
    assert not save.called
    QTest.qWait(400)
    assert save.call_count == 1
    assert not window.sorting_splitter.opaqueResize()
    save.reset_mock()
    window.sorting_splitter.moveSplitter(610, 1)
    QTest.qWait(50)
    assert not save.called
    QTest.qWait(400)
    assert save.call_count == 1
    sizes = window.sorting_splitter.sizes()
    size = window.size()
    window.close()
    window.deleteLater()
    qapp.processEvents()
    restored = MainWindow(Controller())
    restored.show()
    QTest.qWait(50)
    assert restored.size() == size
    assert restored.sorting_splitter.sizes() == sizes
    restored.close()
    restored.deleteLater()
    qapp.processEvents()


def test_layout_waits_for_release_and_flushes_on_close(controller, qapp, monkeypatch):
    window = MainWindow(controller)
    window.show()
    QTest.qWait(400)
    save = Mock(wraps=config.save_window_layout)
    monkeypatch.setattr(config, "save_window_layout", save)
    monkeypatch.setattr("app.ui.window.QApplication.mouseButtons", lambda: Qt.MouseButton.LeftButton)
    window.resize(1050, 740)
    QTest.qWait(400)
    assert not save.called
    monkeypatch.setattr("app.ui.window.QApplication.mouseButtons", lambda: Qt.MouseButton.NoButton)
    QTest.qWait(400)
    assert save.call_count == 1
    window.resize(1030, 730)
    window.close()
    assert save.call_count == 2
    assert not window.layout_save_timer.isActive()
    window.deleteLater()
    qapp.processEvents()


def test_layout_follows_saved_config_folder(controller, qapp, tmp_path):
    window = MainWindow(controller)
    window.show()
    window.resize(1060, 740)
    chosen = tmp_path / "chosen"
    controller.setConfigFolder(str(chosen))
    window.save.click()
    assert config.settings_file().parent == chosen
    assert config.read_window_layout()["geometry"] == window.saveGeometry()
    assert config.read_user_settings()[0] == controller.settings
    window.showMaximized()
    QTest.qWait(400)
    window.close()
    window.deleteLater()
    qapp.processEvents()
    restored = MainWindow(Controller())
    restored.show()
    QTest.qWait(50)
    assert restored.isMaximized()
    restored.close()
    restored.deleteLater()
    qapp.processEvents()
