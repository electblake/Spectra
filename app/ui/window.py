"""Standard desktop widgets bound to the application controller."""

from PySide6.QtCore import QEvent, QSignalBlocker, Qt, QTimer, QUrl
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDockWidget,
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
    QVBoxLayout,
    QWidget,
)

from app import config
from app.ui.parameters_widget import ParametersWidget


class MainWindow(QMainWindow):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.fields = {}
        self.setWindowTitle(controller.title)
        self.resize(1100, 760)
        self._sorting_docks()
        self.central_content = QWidget()
        central_layout = QVBoxLayout(self.central_content)
        central_layout.addWidget(self._sorting_page(), 1)
        self.setCentralWidget(self.central_content)

        self.metrics = QLabel()
        self.statusBar().addPermanentWidget(self.metrics)

        self.parameters_dock = QDockWidget("Parameters", self)
        self.parameters_dock.setObjectName("parametersDock")
        self.parameters_dock.setWidget(ParametersWidget(self._settings_page(), self._extras_page()))
        self.parameters_dock.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )
        self.parameters_dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable | QDockWidget.DockWidgetFeature.DockWidgetClosable
        )
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.parameters_dock)
        file = self.menuBar().addMenu("&File")
        self.select_folder = file.addAction("&Select Folder…")
        self.select_folder.triggered.connect(self._browse)
        view = self.menuBar().addMenu("&View")
        for dock in (*self.sorting_docks, self.parameters_dock):
            view.addAction(dock.toggleViewAction())
        self.move_parameters_left = view.addAction("Move Parameters &Left")
        self.move_parameters_left.triggered.connect(
            lambda: self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.parameters_dock)
        )
        self.move_parameters_right = view.addAction("Move Parameters &Right")
        self.move_parameters_right.triggered.connect(
            lambda: self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.parameters_dock)
        )
        view.addSeparator()
        self.reset_layout = view.addAction("&Reset Layout")
        self.reset_layout.triggered.connect(self._reset_layout)
        self.default_layout = self.saveState()

        controller.settingsChanged.connect(self._sync_settings)
        controller.stateChanged.connect(self._sync_state)
        controller.logMessage.connect(self.log.appendPlainText)
        controller.clearLog.connect(self.log.clear)
        controller.completed.connect(self._show_completion)
        controller.closeReady.connect(self.close)
        self._sync_settings()
        saved_layout = config.read_window_layout()
        if "geometry" in saved_layout:
            self.restoreGeometry(saved_layout["geometry"])
        if "main_window_state" in saved_layout:
            self.restoreState(saved_layout["main_window_state"])
        self.layout_save_timer = QTimer(self)
        self.layout_save_timer.setSingleShot(True)
        self.layout_save_timer.setInterval(300)
        self.layout_save_timer.timeout.connect(self._save_settled_layout)
        for dock in (*self.sorting_docks, self.parameters_dock):
            dock.dockLocationChanged.connect(lambda area: self.layout_save_timer.start())
            dock.topLevelChanged.connect(lambda floating: self.layout_save_timer.start())
            dock.visibilityChanged.connect(self._dock_visibility_changed)
            dock.installEventFilter(self)
        self.save.clicked.connect(self._save_layout)
        self.installEventFilter(self)

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

    def _sorting_docks(self):
        media = QWidget()
        form = QFormLayout(media)
        form.addRow("Input &Folder:", self._text("folder_path", "Input Folder"))
        form.addRow(self._check("overwrite_mapping_csv", "Overwrite existing mapping CSV"))
        folder_actions = QHBoxLayout()
        browse = QPushButton("&Browse…")
        browse.clicked.connect(self._browse)
        self.open_folder = QPushButton("Open Folder")
        self.open_folder.clicked.connect(self.controller.openFolder)
        folder_actions.addWidget(browse)
        folder_actions.addWidget(self.open_folder)
        folder_actions.addStretch()
        form.addRow(folder_actions)

        clusters = QWidget()
        form = QFormLayout(clusters)
        form.addRow(self._check("auto_determine", "Auto-determine threshold"))
        form.addRow("Similarity threshold:", self._number(
            "similarity_threshold", "Similarity threshold", 0, 1, 0.001, 6,
        ))
        hint = QLabel("Lower values create tighter clusters. Typical range: 0.005–0.05.")
        hint.setWordWrap(True)
        form.addRow(hint)

        weights = QWidget()
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

        renaming = QWidget()
        form = QFormLayout(renaming)
        form.addRow("&Prefix:", self._text("file_prefix", "Prefix (used exactly as entered)"))
        form.addRow("Start counting at:", self._number("count_start", "Start counting at", 0, 2147483647))
        form.addRow(self._check("parse_dates", "Parse file dates"))
        form.addRow("Date pattern:", self._text("date_pattern", "Date pattern (regular expression)"))
        form.addRow("Date separator:", self._text("separator", "Separator before parsed date"))
        mapping_folder = self._text("mapping_csv_folder", "Mapping CSV folder")
        mapping_hint = (
            "{workFolder} is the input folder. Use {workFolder}/Data for a subfolder "
            "or {workFolder}/../Data for a sibling folder. Relative paths start at the input folder."
        )
        mapping_folder.setToolTip(mapping_hint)
        mapping_folder.setAccessibleDescription(mapping_hint)
        form.addRow("Mapping CSV folder:", mapping_folder)
        self.sorting_docks = []
        for name, title, content in (
            ("mediaDock", "Selected Media Folder", media),
            ("clustersDock", "Clusters", clusters),
            ("featuresDock", "Feature weights", weights),
            ("renamingDock", "Renaming", renaming),
        ):
            dock = QDockWidget(title, self)
            dock.setObjectName(name)
            dock.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QScrollArea.Shape.NoFrame)
            scroll.setWidget(content)
            dock.setWidget(scroll)
            area = Qt.DockWidgetArea.TopDockWidgetArea if name == "mediaDock" else Qt.DockWidgetArea.LeftDockWidgetArea
            self.addDockWidget(area, dock)
            self.sorting_docks.append(dock)
        for upper, lower in zip(self.sorting_docks[1:], self.sorting_docks[2:]):
            self.splitDockWidget(upper, lower, Qt.Orientation.Vertical)
        self.resizeDocks(self.sorting_docks[1:], [125, 200, 180], Qt.Orientation.Vertical)

    def _sorting_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        activity = QGroupBox("Activity")
        activity_layout = QVBoxLayout(activity)
        self.log = QPlainTextEdit("Ready. Choose a media folder to begin.")
        self.log.setObjectName("activityLog")
        self.log.setAccessibleName("Activity log")
        self.log.setReadOnly(True)
        activity_layout.addWidget(self.log)
        layout.addWidget(activity, 1)

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
        self.progress = QProgressBar()
        self.progress.setAccessibleName("Current stage progress")
        actions.addWidget(self.progress, 1)
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
        config_actions = QHBoxLayout()
        config_actions.addWidget(open_config)
        default_config = QPushButton("Set User Default")
        default_config.setObjectName("setUserDefaultConfigFolder")
        default_config.clicked.connect(lambda: self.controller.setConfigFolder(
            str(config.user_config_path(config.APP_NAME, appauthor=False, roaming=True))
        ))
        config_actions.addWidget(default_config)
        config_label = QLabel("&Config path:")
        config_label.setBuddy(self.config_path)
        form.addRow(config_label, config_row)
        form.addRow("", config_actions)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.settings_options)
        layout.addWidget(scroll)
        layout.addWidget(QLabel("Save Settings stores all options in the selected config folder."))
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
                elif field.value() != value:
                    field.setValue(value)
        if self.config_path.text() != self.controller.configFolder:
            self.config_path.setText(self.controller.configFolder)
        self._sync_state()

    def _sync_state(self):
        controller = self.controller
        settings = controller.settings
        self.select_folder.setEnabled(not controller.busy)
        for dock in self.sorting_docks:
            dock.widget().setEnabled(not controller.busy)
        for widget in (self.run_options, self.settings_options, self.extras, self.save, self.reset):
            widget.setEnabled(not controller.busy)
        self.fields["similarity_threshold"].setEnabled(not settings["auto_determine"])
        self.fields["date_pattern"].setEnabled(settings["parse_dates"])
        self.fields["video_frame_percentage"].setEnabled(settings["include_videos"])
        self.open_folder.setEnabled(bool(settings["folder_path"]))
        self.start.setEnabled(not controller.busy and bool(settings["folder_path"]))
        self.stop.setEnabled(controller.cancellable)
        self.update_status.setText(controller.updateStatus)
        self.statusBar().showMessage(controller.status)
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

    def eventFilter(self, watched, event):
        if watched in (self, *self.sorting_docks, self.parameters_dock) and event.type() in (QEvent.Type.Move, QEvent.Type.Resize, QEvent.Type.WindowStateChange):
            self.layout_save_timer.start()
        return super().eventFilter(watched, event)

    def _dock_visibility_changed(self, visible):
        if self.isVisible():
            self.layout_save_timer.start()

    def _save_settled_layout(self):
        if QApplication.mouseButtons() != Qt.MouseButton.NoButton:
            self.layout_save_timer.start()
        else:
            self._save_layout()

    def _reset_layout(self):
        self.restoreState(self.default_layout)
        self._save_layout()

    def _save_layout(self):
        self.layout_save_timer.stop()
        config.save_window_layout(self.saveGeometry(), self.saveState())

    def closeEvent(self, event):
        if self.controller.requestClose():
            self._save_layout()
            event.accept()
        else:
            event.ignore()
