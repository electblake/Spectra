"""Settings page for the dockable parameters panel."""

from PySide6.QtWidgets import QTabWidget, QVBoxLayout, QWidget


class ParametersWidget(QWidget):
    def __init__(self, settings_page, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.tabs = QTabWidget()
        self.tabs.setObjectName("parametersTabs")
        self.tabs.setMovable(True)
        layout.addWidget(self.tabs)
        self.tabs.addTab(settings_page, "&Settings")
