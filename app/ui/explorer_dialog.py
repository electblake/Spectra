"""File Explorer context menu installation controls."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPushButton,
    QVBoxLayout,
)


class ExplorerDialog(QDialog):
    def __init__(self, controller, parent):
        super().__init__(parent)
        self.controller = controller
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowTitle("Install in File Explorer")
        self.setMinimumWidth(380)
        layout = QVBoxLayout(self)
        hint = QLabel("Add Open in Spectra to right-click menus for folders, folder backgrounds, and drives.")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.install = QPushButton("Install in File Explorer")
        self.install.clicked.connect(controller.installExplorer)
        layout.addWidget(self.install, alignment=Qt.AlignmentFlag.AlignLeft)
        self.status = QLabel()
        layout.addWidget(self.status)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        controller.stateChanged.connect(self._sync)

    def _sync(self):
        self.install.setEnabled(not self.controller.busy)
        self.status.setText(self.controller.status)
        self.buttons.setEnabled(not self.controller.busy)

    def reject(self):
        if not self.controller.busy:
            super().reject()
