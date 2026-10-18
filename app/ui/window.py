"""Standard desktop widgets bound to the application controller."""

from PySide6.QtCore import QSignalBlocker, Qt, QUrl
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)


class MainWindow(QMainWindow):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.fields = {}
        self.setWindowTitle(controller.title)
        self.resize(1100, 760)
        self.tabs = QTabWidget()
        self.tabs.setObjectName("mainTabs")
        self.setCentralWidget(self.tabs)
        self.tabs.addTab(self._sorting_page(), "&Sort && Rename")
        self.tabs.addTab(self._settings_page(), "&Settings")
        self.tabs.addTab(self._extras_page(), "&Extras")

        self.status = QLabel()
        self.metrics = QLabel()
        self.progress = QProgressBar()
        self.progress.setAccessibleName("Current stage progress")
        self.statusBar().addWidget(self.status, 1)
        self.statusBar().addPermanentWidget(self.metrics)
        self.statusBar().addPermanentWidget(self.progress)

        controller.settingsChanged.connect(self._sync_settings)
        controller.stateChanged.connect(self._sync_state)
        controller.logMessage.connect(self.log.appendPlainText)
        controller.clearLog.connect(self.log.clear)
        controller.completed.connect(self._show_completion)
        controller.closeReady.connect(self.close)
        self._sync_settings()

    def _text(self, key, label):
        field = QLineEdit()
        field.textEdited.connect(lambda text: self.controller.setSetting(key, text))
        self._register(key, label, field)
        return field

    def _number(self, key, label, minimum, maximum, step=1, decimals=0):
        field = QDoubleSpinBox() if decimals else QSpinBox()
        if decimals:
            field.setDecimals(decimals)
        field.setRange(minimum, maximum)
        field.setSingleStep(step)
        field.valueChanged.connect(lambda value: self.controller.setSetting(key, value))
        self._register(key, label, field)
        return field

    def _check(self, key, label):
        field = QCheckBox(label)
        field.clicked.connect(lambda checked: self.controller.setSetting(key, checked))
        self._register(key, label, field)
        return field

    def _register(self, key, label, field):
        field.setObjectName(key)
        field.setAccessibleName(label.replace("&", ""))
        self.fields[key] = field

    def _sorting_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter, 1)
        self.sort_options = QWidget()
        options = QVBoxLayout(self.sort_options)

        media = QGroupBox("Media")
        form = QFormLayout(media)
        form.addRow("Media &folder:", self._text("folder_path", "Media folder"))
        folder_actions = QHBoxLayout()
        browse = QPushButton("&Browse…")
        browse.clicked.connect(self._browse)
        self.open_folder = QPushButton("Open Folder")
        self.open_folder.clicked.connect(self.controller.openFolder)
        folder_actions.addWidget(browse)
        folder_actions.addWidget(self.open_folder)
        folder_actions.addStretch()
        form.addRow(folder_actions)
        options.addWidget(media)

        clusters = QGroupBox("Clusters")
        form = QFormLayout(clusters)
        form.addRow(self._check("auto_determine", "Auto-determine threshold"))
        form.addRow("Similarity threshold:", self._number(
            "similarity_threshold", "Similarity threshold", 0, 1, 0.001, 6,
        ))
        hint = QLabel("Lower values create tighter clusters. Typical range: 0.005–0.05.")
        hint.setWordWrap(True)
        form.addRow(hint)
        options.addWidget(clusters)

        weights = QGroupBox("Feature weights")
        form = QFormLayout(weights)
        for key, label, description, step in (
            ("rgb_weight", "RGB histogram", "Overall red, green, and blue color mix.", 0.1),
            ("hsv_weight", "HSV histogram", "Hue, saturation, and color brightness.", 0.1),
            ("spatial_weight", "Spatial color", "Where colors appear within the image.", 0.1),
            ("texture_weight", "Texture", "Edges, patterns, and variations in detail.", 0.1),
            ("brightness_weight", "Brightness and contrast", "Lightness, darkness, and tonal range.", 0.1),
            ("aspect_ratio_weight", "Aspect ratio", "Portrait, square, and landscape proportions.", 0.05),
        ):
            field = self._number(key, label, 0, 3, step, 2)
            field.setToolTip(description)
            field.setAccessibleDescription(description)
            form.addRow(label + ":", field)
        options.addWidget(weights)

        renaming = QGroupBox("Renaming")
        form = QFormLayout(renaming)
        form.addRow("&Prefix:", self._text("file_prefix", "Prefix (used exactly as entered)"))
        form.addRow("Start counting at:", self._number("count_start", "Start counting at", 0, 2147483647))
        form.addRow(self._check("parse_dates", "Parse file dates"))
        form.addRow("Date pattern:", self._text("date_pattern", "Date pattern (regular expression)"))
        form.addRow("Date separator:", self._text("separator", "Separator before parsed date"))
        options.addWidget(renaming)
        options.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.sort_options)
        splitter.addWidget(scroll)

        activity = QGroupBox("Activity")
        activity_layout = QVBoxLayout(activity)
        self.log = QPlainTextEdit("Ready. Choose a media folder to begin.")
        self.log.setObjectName("activityLog")
        self.log.setAccessibleName("Activity log")
        self.log.setReadOnly(True)
        activity_layout.addWidget(self.log)
        splitter.addWidget(activity)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)

        self.run_options = QWidget()
        run_options = QHBoxLayout(self.run_options)
        run_options.addWidget(self._check("include_videos", "Include videos"))
        run_options.addWidget(self._check("dry_run", "Dry run (preview)"))
        run_options.addWidget(self._check("backup", "Create backup"))
        run_options.addStretch()
        layout.addWidget(self.run_options)
        actions = QHBoxLayout()
        self.start = QPushButton("Start Sorting")
        self.start.setObjectName("startButton")
        self.start.clicked.connect(self._start)
        self.stop = QPushButton("Stop")
        self.stop.setObjectName("stopButton")
        self.stop.clicked.connect(self.controller.stop)
        actions.addWidget(self.start)
        actions.addWidget(self.stop)
        actions.addStretch()
        layout.addLayout(actions)
        return page

    def _settings_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        self.settings_options = QWidget()
        form = QFormLayout(self.settings_options)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        form.addRow("Frame position (%):", self._number("video_frame_percentage", "Frame position (%)", 0, 100))
        self.fields["video_frame_percentage"].setToolTip("Applies to newly extracted frames. Existing cached frames are reused.")
        form.addRow("Image feature workers:", self._number("feature_workers", "Image feature workers", 1, 64))
        form.addRow("Video frame workers:", self._number("video_workers", "Video frame workers", 1, 64))
        form.addRow("PNG compression level:", self._number("png_compress_level", "PNG compression level", 0, 9))
        resize = QComboBox()
        resize.addItems(["Default", "Low", "Medium", "High"])
        resize.textActivated.connect(lambda value: self.controller.setSetting("resize_optimization", value))
        self._register("resize_optimization", "Resize optimization", resize)
        resize.setToolTip("Analysis remains 100 × 100 pixels. Stronger optimization is faster and may change similarity results; originals are unchanged.")
        form.addRow("Resize optimization:", resize)

        config_row = QHBoxLayout()
        self.config_path = QLineEdit(self.controller.configFolder)
        self.config_path.setObjectName("configPath")
        self.config_path.setAccessibleName("Config path")
        self.config_path.textEdited.connect(self.controller.setConfigFolder)
        config_row.addWidget(self.config_path)
        browse_config = QPushButton("Browse…")
        browse_config.setObjectName("browseConfigFolder")
        browse_config.clicked.connect(self._browse_config)
        config_row.addWidget(browse_config)
        open_config = QPushButton("Open Config Folder")
        open_config.setObjectName("openConfigFolder")
        open_config.clicked.connect(self.controller.openConfigFolder)
        config_row.addWidget(open_config)
        config_label = QLabel("&Config path:")
        config_label.setBuddy(self.config_path)
        form.addRow(config_label, config_row)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.settings_options)
        layout.addWidget(scroll)
        layout.addWidget(QLabel("Save Settings stores options from all tabs in the selected config folder."))
        actions = QHBoxLayout()
        self.save = QPushButton("Save Settings")
        self.save.clicked.connect(self.controller.saveSettings)
        self.reset = QPushButton("Restore Defaults")
        self.reset.clicked.connect(self.controller.restoreDefaults)
        actions.addWidget(self.save)
        actions.addWidget(self.reset)
        actions.addStretch()
        layout.addLayout(actions)
        return page

    def _extras_page(self):
        self.extras = QWidget()
        layout = QVBoxLayout(self.extras)
        explorer = QGroupBox("File Explorer")
        form = QVBoxLayout(explorer)
        hint = QLabel("Add Open in Spectra to right-click menus for folders, folder backgrounds, and drives.")
        hint.setWordWrap(True)
        form.addWidget(hint)
        install = QPushButton("Install in File Explorer")
        install.clicked.connect(self.controller.installExplorer)
        form.addWidget(install, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(explorer)
        updates = QGroupBox("Updates")
        form = QVBoxLayout(updates)
        self.update_status = QLabel()
        form.addWidget(self.update_status)
        check = QPushButton("Check for Updates")
        check.clicked.connect(self._check_updates)
        releases = QPushButton("View Releases")
        releases.clicked.connect(self.controller.viewReleases)
        form.addWidget(check, alignment=Qt.AlignmentFlag.AlignLeft)
        form.addWidget(releases, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(updates)
        layout.addStretch()
        return self.extras

    def _sync_settings(self):
        for key, value in self.controller.settings.items():
            field = self.fields[key]
            with QSignalBlocker(field):
                if isinstance(field, QLineEdit):
                    if field.text() != value:
                        field.setText(value)
                elif isinstance(field, QCheckBox):
                    field.setChecked(value)
                elif isinstance(field, QComboBox):
                    field.setCurrentText(value)
                else:
                    field.setValue(value)
        if self.config_path.text() != self.controller.configFolder:
            self.config_path.setText(self.controller.configFolder)
        self._sync_state()

    def _sync_state(self):
        controller = self.controller
        settings = controller.settings
        for widget in (self.sort_options, self.run_options, self.settings_options, self.extras, self.save, self.reset):
            widget.setEnabled(not controller.busy)
        self.fields["similarity_threshold"].setEnabled(not settings["auto_determine"])
        self.fields["date_pattern"].setEnabled(settings["parse_dates"])
        self.fields["video_frame_percentage"].setEnabled(settings["include_videos"])
        self.open_folder.setEnabled(bool(settings["folder_path"]))
        self.start.setEnabled(not controller.busy and bool(settings["folder_path"]))
        self.stop.setEnabled(controller.cancellable)
        self.update_status.setText(controller.updateStatus)
        self.status.setText(controller.status)
        self.metrics.setText(controller.metrics)
        self.progress.setRange(0, 0 if controller.indeterminate else 100)
        self.progress.setValue(round(controller.fraction * 100))

    def _browse(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Media Folder", self.controller.settings["folder_path"])
        if folder:
            self.controller.selectFolder(QUrl.fromLocalFile(folder))

    def _browse_config(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Config Folder", self.config_path.text())
        if folder:
            self.controller.setConfigFolder(folder)

    def _start(self):
        settings = self.controller.settings
        if not settings["dry_run"]:
            backup = "A backup will be created." if settings["backup"] else "No backup will be created."
            answer = QMessageBox.question(self, "Confirm Rename", f"Rename supported media in this folder? {backup}")
            if answer != QMessageBox.StandardButton.Yes:
                return
        self.controller.start()

    def _show_completion(self, dry_run):
        dialog = QMessageBox(self)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dialog.setWindowTitle("Dry Run Complete" if dry_run else "Sorting Complete")
        dialog.setText("Preview complete. Check the activity log for filename changes. Turn off Dry run to apply them." if dry_run else "Media sorted and renamed. Check the activity log for details.")
        dialog.setStandardButtons(QMessageBox.StandardButton.Close)
        open_folder = dialog.addButton("Open Folder", QMessageBox.ButtonRole.ActionRole)
        open_quit = dialog.addButton("Open Folder and Quit", QMessageBox.ButtonRole.ActionRole)
        quit_button = dialog.addButton("Quit", QMessageBox.ButtonRole.ActionRole)
        open_folder.clicked.connect(self.controller.openCompletedFolder)
        open_quit.clicked.connect(self.controller.openCompletedFolder)
        open_quit.clicked.connect(self.close)
        quit_button.clicked.connect(self.close)
        dialog.open()

    def _check_updates(self):
        from app.ui.update_dialog import UpdateDialog

        self.update_dialog = UpdateDialog(self.controller, self)
        self.update_dialog.open()
        self.controller.checkUpdates()

    def closeEvent(self, event):
        if self.controller.requestClose():
            event.accept()
        else:
            event.ignore()
