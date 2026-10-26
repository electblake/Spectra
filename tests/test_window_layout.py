import subprocess
import sys
from unittest.mock import Mock

from PySide6.QtCore import QSettings, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDockWidget, QFormLayout, QGroupBox, QSplitter

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
    save.reset_mock()
    height = window.sorting_docks[1].height()
    window.resizeDocks([window.sorting_docks[1]], [height + 80], Qt.Orientation.Vertical)
    QTest.qWait(50)
    assert not save.called
    QTest.qWait(400)
    assert save.call_count == 1
    assert window.sorting_docks[1].height() != height
    height = window.sorting_docks[1].height()
    size = window.size()
    window.close()
    window.deleteLater()
    qapp.processEvents()
    restored = MainWindow(Controller())
    restored.show()
    QTest.qWait(50)
    assert restored.size() == size
    assert restored.sorting_docks[1].height() == height
    restored.close()
    restored.deleteLater()
    qapp.processEvents()


def test_layout_waits_for_release_and_flushes_on_close(controller, qapp, monkeypatch, tmp_path):
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
    subprocess.run([
        sys.executable, "-c",
        ("import sys; from PySide6.QtCore import QSettings; "
         "s = QSettings(sys.argv[1], QSettings.Format.IniFormat); "
         "assert bytes(s.value('layout/geometry').toHex()).decode() == sys.argv[2]; "
         "assert bytes(s.value('layout/main_window_state').toHex()).decode() == sys.argv[3]"),
        str(tmp_path / "ui.ini"),
        bytes(window.saveGeometry().toHex()).decode(),
        bytes(window.saveState().toHex()).decode(),
    ], check=True)
    window.resize(1030, 730)
    window.close()
    assert save.call_count == 2
    assert not window.layout_save_timer.isActive()
    window.deleteLater()
    qapp.processEvents()


def test_layout_is_global_across_config_folders(controller, qapp, tmp_path):
    window = MainWindow(controller)
    window.show()
    window.resize(1060, 740)
    chosen = tmp_path / "chosen"
    controller.setConfigFolder(str(chosen))
    QTest.qWait(400)
    assert config.settings_file().parent == chosen
    assert config.read_window_layout()["geometry"] == window.saveGeometry()
    assert config.read_user_settings()[0] == controller.settings
    assert not QSettings(str(chosen / "Spectra.ini"), QSettings.Format.IniFormat).contains("layout/geometry")
    saved_layout = config.read_window_layout()
    config.save_user_settings(config_folder=tmp_path / "another", **controller.settings)
    assert config.read_window_layout() == saved_layout
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


def test_parameters_dock_placement_width_visibility_and_restore(controller, qapp):
    window = MainWindow(controller)
    window.show()
    QTest.qWait(50)
    dock = window.parameters_dock
    assert window.dockWidgetArea(dock) == Qt.DockWidgetArea.RightDockWidgetArea
    assert dock.allowedAreas() == (Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
    assert not dock.features() & QDockWidget.DockWidgetFeature.DockWidgetFloatable
    window.move_parameters_left.trigger()
    assert window.dockWidgetArea(dock) == Qt.DockWidgetArea.LeftDockWidgetArea
    window.resizeDocks([dock], [280], Qt.Orientation.Horizontal)
    QTest.qWait(400)
    width = dock.width()
    assert config.read_window_layout()["main_window_state"] == window.saveState()
    window.close()
    window.deleteLater()
    qapp.processEvents()

    restored = MainWindow(Controller())
    restored.show()
    QTest.qWait(50)
    dock = restored.parameters_dock
    assert restored.dockWidgetArea(dock) == Qt.DockWidgetArea.LeftDockWidgetArea
    assert dock.width() == width
    restored.move_parameters_right.trigger()
    assert restored.dockWidgetArea(dock) == Qt.DockWidgetArea.RightDockWidgetArea
    dock.toggleViewAction().trigger()
    assert not dock.isVisible()
    QTest.qWait(400)
    assert config.read_window_layout()["main_window_state"] == restored.saveState()
    restored.close()
    restored.deleteLater()
    qapp.processEvents()

    reopened = MainWindow(Controller())
    reopened.show()
    QTest.qWait(50)
    assert not reopened.parameters_dock.isVisible()
    reopened.parameters_dock.toggleViewAction().trigger()
    assert reopened.parameters_dock.isVisible()
    assert reopened.dockWidgetArea(reopened.parameters_dock) == Qt.DockWidgetArea.RightDockWidgetArea
    reopened.close()
    reopened.deleteLater()
    qapp.processEvents()


def test_sorting_docks_default_order_and_layout_restore(controller, qapp):
    window = MainWindow(controller)
    window.show()
    QTest.qWait(100)
    docks = window.sorting_docks
    assert [dock.windowTitle() for dock in docks] == ["Selected Media Folder", "Clusters", "Feature weights", "Renaming"]
    assert [dock.y() for dock in docks] == sorted(dock.y() for dock in docks)
    assert not window.findChildren(QSplitter)
    for index, dock in enumerate(docks):
        area = Qt.DockWidgetArea.TopDockWidgetArea if index == 0 else Qt.DockWidgetArea.LeftDockWidgetArea
        assert window.dockWidgetArea(dock) == area
        assert dock.allowedAreas() == Qt.DockWidgetArea.AllDockWidgetAreas
        assert dock.features() & QDockWidget.DockWidgetFeature.DockWidgetFloatable
        assert not dock.findChildren(QGroupBox)
        assert isinstance(dock.widget().widget().layout(), QFormLayout)
    assert window.central_content.isAncestorOf(window.log)
    assert not window.central_content.isAncestorOf(window.fields["folder_path"])
    areas = [Qt.DockWidgetArea.TopDockWidgetArea, Qt.DockWidgetArea.RightDockWidgetArea,
             Qt.DockWidgetArea.BottomDockWidgetArea, Qt.DockWidgetArea.LeftDockWidgetArea]
    for dock, area in zip(docks, areas):
        window.addDockWidget(area, dock)
        assert window.dockWidgetArea(dock) == area
    docks[0].close()
    docks[1].setFloating(True)
    QTest.qWait(400)
    window.close()
    window.deleteLater()
    qapp.processEvents()

    restored = MainWindow(Controller())
    restored.show()
    QTest.qWait(100)
    assert restored.sorting_docks[0].isHidden()
    assert restored.sorting_docks[1].isFloating()
    assert restored.dockWidgetArea(restored.sorting_docks[2]) == Qt.DockWidgetArea.BottomDockWidgetArea
    restored.sorting_docks[0].toggleViewAction().trigger()
    assert restored.sorting_docks[0].isVisible()
    restored.sorting_docks[1].setFloating(False)
    assert restored.dockWidgetArea(restored.sorting_docks[1]) == Qt.DockWidgetArea.RightDockWidgetArea
    restored.close()
    restored.deleteLater()
    qapp.processEvents()


def test_reset_layout_restores_all_docks_and_persists(controller, qapp):
    window = MainWindow(controller)
    window.show()
    QTest.qWait(100)
    for dock in window.sorting_docks:
        window.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, dock)
    window.sorting_docks[1].setFloating(True)
    window.sorting_docks[0].close()
    window.move_parameters_left.trigger()
    window.parameters_dock.close()
    view = window.menuBar().actions()[1].menu()
    assert view.actions()[-2].isSeparator()
    assert view.actions()[-1] == window.reset_layout
    window.reset_layout.trigger()
    qapp.processEvents()
    for index, dock in enumerate(window.sorting_docks):
        area = Qt.DockWidgetArea.TopDockWidgetArea if index == 0 else Qt.DockWidgetArea.LeftDockWidgetArea
        assert window.dockWidgetArea(dock) == area
        assert dock.isVisible()
        assert not dock.isFloating()
    assert window.dockWidgetArea(window.parameters_dock) == Qt.DockWidgetArea.RightDockWidgetArea
    assert window.parameters_dock.isVisible()
    assert [dock.y() for dock in window.sorting_docks[1:]] == sorted(
        dock.y() for dock in window.sorting_docks[1:]
    )
    QTest.qWait(400)
    assert config.read_window_layout()["main_window_state"] == window.saveState()
    window.close()
    window.deleteLater()
    qapp.processEvents()
    restored = MainWindow(Controller())
    restored.show()
    QTest.qWait(100)
    assert restored.dockWidgetArea(restored.sorting_docks[0]) == Qt.DockWidgetArea.TopDockWidgetArea
    assert all(dock.isVisible() and not dock.isFloating() for dock in restored.sorting_docks)
    assert restored.dockWidgetArea(restored.parameters_dock) == Qt.DockWidgetArea.RightDockWidgetArea
    restored.close()
    restored.deleteLater()
    qapp.processEvents()


def test_panel_scroll_positions_save_and_restore(controller, qapp):
    window = MainWindow(controller)
    window.show()
    window.resizeDocks([window.sorting_docks[2]], [100], Qt.Orientation.Vertical)
    QTest.qWait(50)
    scroll = window.scroll_areas["featuresDock"].verticalScrollBar()
    assert scroll.maximum() > 0
    scroll.setValue(scroll.maximum())
    position = scroll.value()
    QTest.qWait(400)
    assert config.read_window_layout()["scroll_positions"]["featuresDock"][1] == position
    window.close()
    window.deleteLater()
    qapp.processEvents()
    restored = MainWindow(Controller())
    restored.show()
    QTest.qWait(50)
    assert restored.scroll_areas["featuresDock"].verticalScrollBar().value() == position
    restored.close()
    restored.deleteLater()
    qapp.processEvents()


def test_scroll_restore_is_cancelled_when_window_is_deleted(controller, qapp, monkeypatch):
    import sys

    from shiboken6 import delete

    errors = []
    monkeypatch.setattr(sys, "excepthook", lambda *error: errors.append(error))
    window = MainWindow(controller)
    delete(window)
    QTest.qWait(50)
    assert errors == []


def test_hidden_panel_preserves_scroll_position_across_restart(controller, qapp):
    window = MainWindow(controller)
    window.show()
    dock = window.sorting_docks[2]
    window.resizeDocks([dock], [100], Qt.Orientation.Vertical)
    QTest.qWait(50)
    bar = window.scroll_areas["featuresDock"].verticalScrollBar()
    bar.setValue(40)
    assert bar.value() == 40
    dock.hide()
    window.close()
    window.deleteLater()
    qapp.processEvents()
    restored = MainWindow(Controller())
    restored.show()
    QTest.qWait(50)
    restored.sorting_docks[2].show()
    QTest.qWait(50)
    assert restored.scroll_areas["featuresDock"].verticalScrollBar().value() == 40
    restored.close()
    restored.deleteLater()
    qapp.processEvents()
