"""Standard Qt controls for checking, downloading, and installing updates."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QProgressBar,
    QVBoxLayout,
)


class UpdateDialog(QDialog):
    def __init__(self, controller, parent):
        super().__init__(parent)
        self.controller = controller
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowTitle("Software Update")
        self.setMinimumWidth(460)
        layout = QVBoxLayout(self)
        self.status = QLabel("Checking GitHub for a new version...")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        layout.addWidget(self.progress)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        self.download = self.buttons.addButton("Download Update", QDialogButtonBox.ButtonRole.ActionRole)
        self.install = self.buttons.addButton("Quit and Install", QDialogButtonBox.ButtonRole.ActionRole)
        self.download.setEnabled(False)
        self.install.setEnabled(False)
        self.download.clicked.connect(controller.downloadUpdate)
        self.install.clicked.connect(self._install)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        controller.stateChanged.connect(self._sync)

    def _sync(self):
        controller = self.controller
        self.status.setText(f"{controller.updateStatus}\n{controller.status}")
        self.progress.setRange(0, 0 if controller.indeterminate else 1000)
        self.progress.setValue(round(controller.fraction * 1000))
        self.download.setEnabled(not controller.busy and controller.update_available and not controller.update_ready)
        self.install.setEnabled(not controller.busy and controller.update_ready)
        self.buttons.button(QDialogButtonBox.StandardButton.Close).setEnabled(not controller.busy)

    def reject(self):
        if not self.controller.busy:
            super().reject()

    def _install(self):
        self.accept()
        self.controller.quitAndInstall()
