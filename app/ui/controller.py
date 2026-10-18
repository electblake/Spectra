"""Qt adapter: application requests in, queued events out."""

import os
import threading
from functools import partial

from PySide6.QtCore import Property, QObject, QThread, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices
from PySide6.QtQml import QmlElement, QmlUncreatable

from app import application, config, integrations
from app.events import Log

QML_IMPORT_NAME = "Spectra"
QML_IMPORT_MAJOR_VERSION = 1


class TaskThread(QThread):
    reported = Signal(object)
    result = Signal(object)

    def __init__(self, operation, parent):
        super().__init__(parent)
        self.operation = operation

    def run(self):
        self.result.emit(self.operation(self.reported.emit))


@QmlElement
@QmlUncreatable("The application supplies its controller")
class Controller(QObject):
    settingsChanged = Signal()
    stateChanged = Signal()
    logMessage = Signal(str)
    clearLog = Signal()
    completed = Signal(bool)
    updateAvailable = Signal(str)
    closeReady = Signal()

    def __init__(self, folder=None):
        super().__init__()
        self._settings, self.settings_path = config.read_user_settings()
        if folder is not None:
            self._settings["folder_path"] = folder
        self._busy = False
        self._status = "Ready"
        self._fraction = 0.0
        self._indeterminate = False
        self._metrics = ""
        self._examples = application.date_examples(self._settings["date_pattern"])
        self._update_status = f"Installed: {config.APP_VERSION}"
        self._stage = None
        self._current = 0
        self._stop = threading.Event()
        self._thread = None
        self._closing = False
        self._completed_request = None
        self._release = None
        self._kind = "idle"

    @Property("QVariantMap", notify=settingsChanged)
    def settings(self):
        return self._settings.copy()

    @Property(str, constant=True)
    def title(self):
        return f"{config.APP_NAME} {config.APP_VERSION} — {config.APP_DESCRIPTION}"

    @Property(bool, notify=stateChanged)
    def busy(self):
        return self._busy

    @Property(bool, notify=stateChanged)
    def stopping(self):
        return self._stop.is_set()

    @Property(bool, notify=stateChanged)
    def cancellable(self):
        return self._busy and self._kind in {"sort", "scan"} and not self._stop.is_set()

    @Property(str, notify=stateChanged)
    def status(self):
        return self._status

    @Property("double", notify=stateChanged)
    def fraction(self):
        return self._fraction

    @Property(bool, notify=stateChanged)
    def indeterminate(self):
        return self._indeterminate

    @Property(str, notify=stateChanged)
    def metrics(self):
        return self._metrics

    @Property(str, notify=stateChanged)
    def examples(self):
        return self._examples

    @Property(str, notify=stateChanged)
    def updateStatus(self):
        return self._update_status

    @Slot(str, "QVariant")
    def setSetting(self, key, value):
        self._settings[key] = type(config.default_settings()[key])(value)
        self.settingsChanged.emit()

    @Slot()
    def saveSettings(self):
        config.save_user_settings(**self._settings)
        self.logMessage.emit("Settings saved.")

    @Slot()
    def restoreDefaults(self):
        self._settings = config.default_settings()
        self.settingsChanged.emit()
        self.updateExamples()
        self.logMessage.emit("Settings reset to defaults.")

    @Slot()
    def updateExamples(self):
        self._examples = application.date_examples(self._settings["date_pattern"])
        self.stateChanged.emit()

    @Slot(QUrl)
    def selectFolder(self, url):
        self.setSetting("folder_path", url.toLocalFile())
        self._launch("scan", partial(
            application.scan_folder, self._settings["folder_path"],
            self._settings["include_videos"], self._stop,
        ))

    @Slot()
    def start(self):
        request = application.RunRequest(**self._settings)
        self.clearLog.emit()
        self._launch("sort", partial(application.run_sorting, request, self._stop))

    def _launch(self, kind, operation):
        self._kind = kind
        self._stop.clear()
        self._busy = True
        self._status = "Working..."
        self._indeterminate = True
        self._fraction = 0.0
        self._metrics = ""
        self._stage = None
        self._thread = TaskThread(operation, self)
        self._thread.reported.connect(self._receive_event)
        self._thread.result.connect(self._receive_result)
        self._thread.finished.connect(self._finished)
        self.stateChanged.emit()
        self._thread.start()

    @Slot(object)
    def _receive_event(self, event):
        if isinstance(event, Log):
            self.logMessage.emit(event.text)
            return
        if self._stop.is_set():
            return
        stage = (event.stage, event.total)
        if stage != self._stage or event.current < self._current:
            self._stage = stage
            self._started_at = event.timestamp
            self._started_count = event.current
            self._metrics = ""
        self._current = event.current
        self._indeterminate = event.total is None or event.current == 0
        self._status = event.stage.strip()
        if event.total is not None:
            self._status += f" {event.current}/{event.total}"
            self._fraction = event.current / event.total if event.total else 0.0
            completed = event.current - self._started_count
            if completed > 0:
                rate = completed / (event.timestamp - self._started_at)
                seconds = round((event.total - event.current) / rate)
                self._metrics = f"{rate:.1f} items/s · {seconds // 60}m {seconds % 60}s remaining"
        self.stateChanged.emit()

    @Slot(object)
    def _receive_result(self, result):
        self._indeterminate = False
        self._metrics = ""
        if self._kind == "sort":
            self._completed_request = result.request
            self._status = "Sorting stopped" if result.stopped else "Sorting complete"
            self._fraction = 0.0 if result.stopped else 1.0
            if not result.stopped and not self._closing:
                self.completed.emit(result.request.dry_run)
        elif self._kind == "scan":
            self._status = result
        elif self._kind == "check":
            self._release = result
            version = result["tag_name"].removeprefix("v")
            newer = integrations._version_tuple(version) > integrations._version_tuple(config.APP_VERSION)
            self._update_status = f"Installed: {config.APP_VERSION} · Latest: {version}"
            self._status = "Update available" if newer else "Up to date"
            if newer and not self._closing:
                self.updateAvailable.emit(version)
        elif self._kind == "download":
            self._status = f"Opening {result.name}"
            os.startfile(result)
        elif self._kind == "install":
            self._status = "Installed in File Explorer"
        self.stateChanged.emit()

    @Slot()
    def _finished(self):
        self._thread.wait()
        self._thread.deleteLater()
        self._thread = None
        self._busy = False
        self._indeterminate = False
        self.stateChanged.emit()
        if self._closing:
            self.closeReady.emit()

    @Slot()
    def stop(self):
        self._stop.set()
        self._status = "Stopping..."
        self.stateChanged.emit()

    @Slot(result=bool)
    def requestClose(self):
        self._closing = True
        if self._busy:
            self.stop()
            return False
        return True

    @Slot()
    def openFolder(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(self._settings["folder_path"]))

    @Slot()
    def openCompletedFolder(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(self._completed_request.folder_path))

    @Slot()
    def checkUpdates(self):
        self._launch("check", lambda report: integrations._latest_release())

    @Slot()
    def downloadUpdate(self):
        version = self._release["tag_name"].removeprefix("v")
        asset = integrations._setup_asset(self._release, version)
        self._launch("download", lambda report: integrations._download_setup(asset))

    @Slot()
    def installExplorer(self):
        self._launch("install", lambda report: integrations.install())

    @Slot()
    def viewReleases(self):
        QDesktopServices.openUrl(QUrl(integrations.RELEASES_URL))
