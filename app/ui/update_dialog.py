"""Standard Qt controls for checking, downloading, and installing updates."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QProgressBar,
    QVBoxLayout,
)

from app import config


class UpdateDialog(QDialog):
    def __init__(self, controller, parent):
        super().__init__(parent)
        self.controller = controller
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowTitle("Check for updates")
        self.setMinimumWidth(460)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(config.APP_NAME))
        layout.addWidget(QLabel(f"Current version: {config.APP_VERSION}"))
        self.status = QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        layout.addWidget(self.progress)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        self.check = self.buttons.addButton("Check for Updates", QDialogButtonBox.ButtonRole.ActionRole)
        self.releases = self.buttons.addButton("View Releases", QDialogButtonBox.ButtonRole.ActionRole)
        self.download = self.buttons.addButton("Download Update", QDialogButtonBox.ButtonRole.ActionRole)
        self.install = self.buttons.addButton("Quit and Install", QDialogButtonBox.ButtonRole.ActionRole)
        self.download.setEnabled(False)
        self.install.setEnabled(False)
        self.check.clicked.connect(controller.checkUpdates)
        self.releases.clicked.connect(controller.viewReleases)
        self.download.clicked.connect(controller.downloadUpdate)
        self.install.clicked.connect(self._install)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        controller.stateChanged.connect(self._sync)
        self._sync()

    def _sync(self):
        controller = self.controller
        self.status.setText(f"{controller.updateStatus}\n{controller.status}")
        self.progress.setRange(0, 0 if controller.indeterminate else 1000)
        self.progress.setValue(round(controller.fraction * 1000))
        self.progress.setVisible(controller.busy)
        self.check.setEnabled(not controller.busy)
        self.download.setEnabled(not controller.busy and controller.update_available and not controller.update_ready)
        self.install.setEnabled(not controller.busy and controller.update_ready)
        self.buttons.button(QDialogButtonBox.StandardButton.Close).setEnabled(not controller.busy)

    def reject(self):
        if not self.controller.busy:
            super().reject()

    def _install(self):
        self.accept()
        self.controller.quitAndInstall()
