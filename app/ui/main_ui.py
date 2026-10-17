"""Spectra Tkinter interface."""

import multiprocessing
import os
import queue
import re
import subprocess
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

from app.config import (
    APP_DESCRIPTION,
    APP_NAME,
    APP_VERSION,
    AUTO_DETERMINE,
    BACKUP,
    COUNT_START,
    DATE_PATTERN,
    DEFAULT_FEATURE_WEIGHTS,
    DRY_RUN,
    FEATURE_WORKERS,
    FILE_PREFIX,
    FOLDER_PATH,
    IMAGE_EXTENSIONS,
    INCLUDE_VIDEOS,
    PARSE_DATES,
    PNG_COMPRESS_LEVEL,
    RESIZE_OPTIMIZATION,
    RESIZE_REDUCING_GAPS,
    SEPARATOR,
    SIMILARITY_THRESHOLD,
    VIDEO_EXTENSIONS,
    VIDEO_FRAME_PERCENTAGE,
    VIDEO_WORKERS,
    read_user_settings,
    save_user_settings,
)
from app.main import (
    get_image_files,
    get_video_image_files,
    rename_images,
    rename_media,
    sort_with_tight_clustering,
)
from app.tabs import extras, settings

__version__ = APP_VERSION
APP_ICON_FILENAME = "Spectra.ico"


def app_icon_path() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / APP_ICON_FILENAME # pyright: ignore[reportAttributeAccessIssue]

    return Path(__file__).parent.parent.parent / APP_ICON_FILENAME


class ImageSorterGUI:
    def __init__(self, root):
        self.root = root
        self.root.title(f"{APP_NAME} v{__version__} - {APP_DESCRIPTION}")
        self.root.iconbitmap(app_icon_path())
        self.root.geometry("1440x960")
        self.root.resizable(True, True)

        user_settings, self.loaded_settings_path = read_user_settings()

        self.folder_path = tk.StringVar(value=user_settings["folder_path"])
        self.prefix = tk.StringVar(value=user_settings["file_prefix"])
        self.threshold = tk.StringVar(value=str(user_settings["similarity_threshold"]))
        self.auto_threshold = tk.BooleanVar(value=user_settings["auto_determine"])
        self.rgb_weight = tk.DoubleVar(value=user_settings["rgb_weight"])
        self.hsv_weight = tk.DoubleVar(value=user_settings["hsv_weight"])
        self.spatial_weight = tk.DoubleVar(value=user_settings["spatial_weight"])
        self.texture_weight = tk.DoubleVar(value=user_settings["texture_weight"])
        self.brightness_weight = tk.DoubleVar(value=user_settings["brightness_weight"])
        self.aspect_ratio_weight = tk.DoubleVar(value=user_settings["aspect_ratio_weight"])
        self.video_frame_percentage = tk.IntVar(
            value=user_settings["video_frame_percentage"]
        )
        self.dry_run = tk.BooleanVar(value=user_settings["dry_run"])
        self.backup = tk.BooleanVar(value=user_settings["backup"])
        self.include_videos = tk.BooleanVar(value=user_settings["include_videos"])
        self.parse_dates = tk.BooleanVar(value=user_settings["parse_dates"])
        self.date_pattern = tk.StringVar(value=user_settings["date_pattern"])
        self.date_pattern_preview = tk.StringVar()
        self.separator = tk.StringVar(value=user_settings["separator"])
        self.count_start = tk.IntVar(value=user_settings["count_start"])
        self.feature_workers = tk.IntVar(value=user_settings["feature_workers"])
        self.video_workers = tk.IntVar(value=user_settings["video_workers"])
        self.png_compress_level = tk.IntVar(value=user_settings["png_compress_level"])
        self.resize_optimization = tk.StringVar(value=user_settings["resize_optimization"])
        self.is_processing = False
        self.stop_event = threading.Event()

        self.setup_ui()

    def setup_ui(self):
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        self.main_panes = ttk.Panedwindow(self.root, orient=tk.HORIZONTAL)
        self.main_panes.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        runtime_frame = ttk.Frame(self.root, padding=(10, 6, 10, 0))
        runtime_frame.grid(row=1, column=0, sticky=(tk.W, tk.E))
        runtime_frame.columnconfigure(0, weight=1)

        check_frame = ttk.Frame(runtime_frame)
        check_frame.grid(row=0, column=0, pady=(0, 6))
        ttk.Checkbutton(
            check_frame,
            text="Include videos",
            variable=self.include_videos,
            command=self.toggle_video_settings,
        ).pack(side=tk.LEFT, padx=(0, 15))
        ttk.Checkbutton(
            check_frame,
            text="Dry Run (preview only, don't rename)",
            variable=self.dry_run,
        ).pack(side=tk.LEFT, padx=(0, 15))
        ttk.Checkbutton(
            check_frame,
            text="Create backup of original files",
            variable=self.backup,
        ).pack(side=tk.LEFT)

        button_frame = ttk.Frame(runtime_frame)
        button_frame.grid(row=1, column=0)

        self.start_button = ttk.Button(
            button_frame,
            text="Start Sorting",
            command=self.start_sorting,
        )
        self.start_button.pack(side=tk.LEFT, padx=5)

        self.stop_button = ttk.Button(
            button_frame,
            text="Stop",
            command=self.stop_sorting,
            state=tk.DISABLED,
        )
        self.stop_button.pack(side=tk.LEFT, padx=5)

        self.save_settings_button = ttk.Button(
            button_frame,
            text="Save Settings",
            command=self.save_settings,
        )
        self.save_settings_button.pack(side=tk.LEFT, padx=5)

        self.defaults_button = ttk.Button(
            button_frame,
            text="Restore Defaults",
            command=self.restore_default_settings,
        )
        self.defaults_button.pack(side=tk.LEFT, padx=5)

        self.open_folder_button = ttk.Button(
            button_frame,
            text="Open Folder",
            command=self.open_input_folder,
        )
        self.open_folder_button.pack(side=tk.LEFT, padx=5)

        status_frame = ttk.Frame(self.root, padding=(10, 6))
        status_frame.grid(row=2, column=0, sticky=(tk.W, tk.E))
        status_frame.columnconfigure(1, weight=1)

        self.status_text = tk.StringVar(value="Ready 0/0")
        self.progress_percent_text = tk.StringVar(value="0%")
        self.progress_metrics_text = tk.StringVar(value="— items/s  — s")
        self.progress_stage = None
        ttk.Label(status_frame, textvariable=self.status_text).grid(
            row=0, column=0, sticky=tk.W, padx=(0, 10)
        )
        self.progress = ttk.Progressbar(
            status_frame,
            mode="determinate",
            maximum=100,
        )
        self.progress.grid(row=0, column=1, sticky=(tk.W, tk.E))
        ttk.Label(status_frame, textvariable=self.progress_percent_text).grid(
            row=0, column=2, sticky=tk.E, padx=(10, 0)
        )
        ttk.Label(status_frame, textvariable=self.progress_metrics_text).grid(
            row=0, column=3, sticky=tk.E, padx=(10, 0)
        )

        controls_pane = ttk.Frame(self.main_panes)
        log_frame = ttk.Frame(self.main_panes, padding="5")
        self.main_panes.add(controls_pane, weight=1)
        self.main_panes.add(log_frame, weight=1)

        controls_pane.columnconfigure(0, weight=1)
        controls_pane.rowconfigure(0, weight=1)

        self.notebook = ttk.Notebook(controls_pane)
        self.notebook.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        self.sort_rename_tab = ttk.Frame(self.notebook)
        self.extras_tab = extras.ExtrasTab(self.notebook)
        self.notebook.add(self.sort_rename_tab, text="Sort & Rename")
        self.settings_tab = settings.SettingsTab(
            self.notebook, self.feature_workers, self.png_compress_level,
            self.resize_optimization,
            self.video_workers,
        )
        self.notebook.add(self.settings_tab, text="Settings")
        self.notebook.add(self.extras_tab, text="Extras")

        self.sort_rename_tab.columnconfigure(0, weight=1)
        self.sort_rename_tab.rowconfigure(0, weight=1)

        self.main_canvas = tk.Canvas(self.sort_rename_tab, highlightthickness=0)
        self.main_canvas.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        self.main_scrollbar = ttk.Scrollbar(
            self.sort_rename_tab,
            orient=tk.VERTICAL,
            command=self.main_canvas.yview,
        )
        self.main_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.main_canvas.configure(yscrollcommand=self.main_scrollbar.set)

        main_frame = ttk.Frame(self.main_canvas, padding="10")
        self.main_frame = main_frame
        self.main_canvas_window = self.main_canvas.create_window(
            (0, 0),
            window=main_frame,
            anchor=tk.NW,
        )
        main_frame.bind("<Configure>", self.configure_main_scroll)
        self.main_canvas.bind("<Configure>", self.resize_main_content)
        main_frame.columnconfigure(1, weight=1)

        row = 0

        title = ttk.Label(main_frame, text=f"{APP_NAME} v{__version__}",
                         font=('Arial', 16, 'bold'))
        title.grid(row=row, column=0, columnspan=3, pady=(0, 20))
        row += 1

        ttk.Label(main_frame, text="Media Folder:").grid(row=row, column=0, sticky=tk.W, pady=5)
        folder_entry = ttk.Entry(main_frame, textvariable=self.folder_path, width=50)
        folder_entry.grid(row=row, column=1, sticky=(tk.W, tk.E), padx=5)
        folder_button_frame = ttk.Frame(main_frame)
        folder_button_frame.grid(row=row, column=2, padx=5)
        ttk.Button(folder_button_frame, text="Browse", command=self.browse_folder).pack(
            side=tk.LEFT
        )
        ttk.Button(
            folder_button_frame,
            text="Open",
            command=self.open_input_folder,
        ).pack(
            side=tk.LEFT,
            padx=(5, 0),
        )
        row += 1

        clusters_frame = ttk.LabelFrame(main_frame, text="Clusters", padding="10")
        clusters_frame.grid(row=row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)
        clusters_frame.columnconfigure(1, weight=1)
        row += 1

        ttk.Label(clusters_frame, text="Similarity Threshold:").grid(
            row=0, column=0, sticky=tk.W, pady=5
        )

        threshold_frame = ttk.Frame(clusters_frame)
        threshold_frame.grid(row=0, column=1, columnspan=2, sticky=tk.W, padx=5)

        self.threshold_entry = ttk.Entry(
            threshold_frame,
            textvariable=self.threshold,
            width=10,
        )
        self.threshold_entry.pack(side=tk.LEFT)
        ttk.Checkbutton(threshold_frame, text="Auto-determine",
                       variable=self.auto_threshold,
                       command=self.toggle_threshold).pack(side=tk.LEFT, padx=10)
        self.toggle_threshold()

        threshold_hint = ttk.Label(clusters_frame,
                                   text="Lower = tighter clusters (0.005-0.05 typical, 0.01 recommended)",
                                   font=('Arial', 8))
        threshold_hint.grid(row=1, column=1, columnspan=2, sticky=tk.W, padx=5)

        renaming_frame = ttk.LabelFrame(main_frame, text="Renaming", padding="10")
        renaming_frame.grid(
            row=row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5
        )
        renaming_frame.columnconfigure(1, weight=1)
        row += 1

        renaming_row = 0

        ttk.Label(renaming_frame, text="Prefix:").grid(
            row=renaming_row, column=0, sticky=tk.W, pady=5
        )
        self.prefix_entry = ttk.Entry(renaming_frame, textvariable=self.prefix, width=40)
        self.prefix_entry.grid(
            row=renaming_row, column=1, sticky=tk.W, padx=5
        )
        ttk.Label(renaming_frame, text="(e.g., 'sorted_' → sorted_001.jpg)").grid(
            row=renaming_row, column=2, sticky=tk.W
        )
        renaming_row += 1

        ttk.Label(renaming_frame, text="Start counting at:").grid(
            row=renaming_row, column=0, sticky=tk.W, pady=5
        )
        ttk.Entry(
            renaming_frame,
            textvariable=self.count_start,
            width=10,
        ).grid(row=renaming_row, column=1, sticky=tk.W, padx=5)
        ttk.Label(renaming_frame, text="(e.g., 200 → sorted_200.jpg)").grid(
            row=renaming_row, column=2, sticky=tk.W
        )
        renaming_row += 1

        ttk.Checkbutton(
            renaming_frame,
            text="Parse file dates",
            variable=self.parse_dates,
            command=self.toggle_date_pattern,
        ).grid(row=renaming_row, column=0, columnspan=3, sticky=tk.W, pady=5)
        renaming_row += 1

        ttk.Label(renaming_frame, text="Date pattern:").grid(
            row=renaming_row, column=0, sticky=tk.W, pady=5
        )
        self.date_pattern_entry = ttk.Entry(
            renaming_frame,
            textvariable=self.date_pattern,
            width=40,
        )
        self.date_pattern_entry.grid(
            row=renaming_row,
            column=1,
            sticky=tk.W,
            padx=5,
        )
        ttk.Label(
            renaming_frame,
            text="(e.g., matches 2025-01-31 or 2025.01.31)",
        ).grid(row=renaming_row, column=2, sticky=tk.W)
        renaming_row += 1

        self.date_pattern_button = ttk.Button(
            renaming_frame,
            text="Update examples",
            command=self.update_date_pattern_examples,
        )
        self.date_pattern_button.grid(
            row=renaming_row,
            column=1,
            sticky=tk.W,
            padx=5,
            pady=(0, 5),
        )
        renaming_row += 1

        ttk.Label(
            renaming_frame,
            textvariable=self.date_pattern_preview,
            justify=tk.LEFT,
        ).grid(
            row=renaming_row,
            column=0,
            columnspan=3,
            sticky=tk.W,
            pady=(0, 5),
        )
        self.update_date_pattern_examples()
        self.toggle_date_pattern()
        renaming_row += 1

        ttk.Label(renaming_frame, text="Separator:").grid(
            row=renaming_row, column=0, sticky=tk.W, pady=5
        )
        ttk.Entry(
            renaming_frame,
            textvariable=self.separator,
            width=10,
        ).grid(row=renaming_row, column=1, sticky=tk.W, padx=5)

        weights_frame = ttk.LabelFrame(main_frame, text="Feature Weights", padding="10")
        weights_frame.grid(row=row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)
        weights_frame.columnconfigure(1, weight=1)
        row += 1

        ttk.Label(weights_frame, text="RGB histogram:").grid(row=0, column=0, sticky=tk.W)
        tk.Scale(
            weights_frame, from_=0.0, to=3.0, resolution=0.1,
            orient=tk.HORIZONTAL, variable=self.rgb_weight
        ).grid(row=0, column=1, sticky=(tk.W, tk.E))
        ttk.Label(
            weights_frame,
            text=(
                "Compares the overall red, green, and blue color mix. "
                "Higher values prioritize matching exact colors; lower values reduce color's influence."
            ),
            font=('Arial', 8),
            wraplength=600,
        ).grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=(0, 5))

        ttk.Label(weights_frame, text="HSV histogram:").grid(row=2, column=0, sticky=tk.W)
        tk.Scale(
            weights_frame, from_=0.0, to=3.0, resolution=0.1,
            orient=tk.HORIZONTAL, variable=self.hsv_weight
        ).grid(row=2, column=1, sticky=(tk.W, tk.E))
        ttk.Label(
            weights_frame,
            text=(
                "Compares hue, saturation, and color brightness. "
                "Higher values prioritize similar perceived colors and intensity; lower values reduce their influence."
            ),
            font=('Arial', 8),
            wraplength=600,
        ).grid(row=3, column=0, columnspan=2, sticky=tk.W, pady=(0, 5))

        ttk.Label(weights_frame, text="Spatial color:").grid(row=4, column=0, sticky=tk.W)
        tk.Scale(
            weights_frame, from_=0.0, to=3.0, resolution=0.1,
            orient=tk.HORIZONTAL, variable=self.spatial_weight
        ).grid(row=4, column=1, sticky=(tk.W, tk.E))
        ttk.Label(
            weights_frame,
            text=(
                "Compares where colors appear within the image. "
                "Higher values favor similar color layouts; lower values allow colors to appear in different places."
            ),
            font=('Arial', 8),
            wraplength=600,
        ).grid(row=5, column=0, columnspan=2, sticky=tk.W, pady=(0, 5))

        ttk.Label(weights_frame, text="Texture:").grid(row=6, column=0, sticky=tk.W)
        tk.Scale(
            weights_frame, from_=0.0, to=3.0, resolution=0.1,
            orient=tk.HORIZONTAL, variable=self.texture_weight
        ).grid(row=6, column=1, sticky=(tk.W, tk.E))
        ttk.Label(
            weights_frame,
            text=(
                "Compares edges, patterns, and variations in detail. "
                "Higher values prioritize similar smoothness or complexity; lower values reduce texture's influence."
            ),
            font=('Arial', 8),
            wraplength=600,
        ).grid(row=7, column=0, columnspan=2, sticky=tk.W, pady=(0, 5))

        ttk.Label(weights_frame, text="Brightness and contrast:").grid(row=8, column=0, sticky=tk.W)
        tk.Scale(
            weights_frame, from_=0.0, to=3.0, resolution=0.1,
            orient=tk.HORIZONTAL, variable=self.brightness_weight
        ).grid(row=8, column=1, sticky=(tk.W, tk.E))
        ttk.Label(
            weights_frame,
            text=(
                "Compares overall lightness, darkness, and tonal range. "
                "Higher values favor similar lighting and contrast; lower values allow greater tonal differences."
            ),
            font=('Arial', 8),
            wraplength=600,
        ).grid(row=9, column=0, columnspan=2, sticky=tk.W, pady=(0, 5))

        ttk.Label(weights_frame, text="Aspect ratio:").grid(row=10, column=0, sticky=tk.W)
        tk.Scale(
            weights_frame, from_=0.0, to=3.0, resolution=0.05,
            orient=tk.HORIZONTAL, variable=self.aspect_ratio_weight
        ).grid(row=10, column=1, sticky=(tk.W, tk.E))
        ttk.Label(
            weights_frame,
            text=(
                "Compares image proportions, such as portrait, square, or landscape. "
                "Higher values favor similar shapes; lower values allow more varied proportions."
            ),
            font=('Arial', 8),
            wraplength=600,
        ).grid(row=11, column=0, columnspan=2, sticky=tk.W)

        videos_frame = ttk.LabelFrame(main_frame, text="Video", padding="10")
        videos_frame.grid(row=row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)
        videos_frame.columnconfigure(1, weight=1)
        row += 1

        ttk.Label(videos_frame, text="Video Frame position (%):").grid(
            row=0, column=0, sticky=tk.W
        )
        self.video_frame_scale = tk.Scale(
            videos_frame, from_=0, to=100, resolution=1,
            orient=tk.HORIZONTAL, variable=self.video_frame_percentage
        )
        self.video_frame_scale.grid(row=0, column=1, sticky=(tk.W, tk.E))
        self.toggle_video_settings()

        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD)
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        self.log_redirector = TextRedirector(
            self.log_text,
            "stdout",
            self.update_status_from_output,
        )
        sys.stdout = self.log_redirector

        self.log(f"{APP_NAME} v{__version__} loaded.")
        if self.loaded_settings_path is not None:
            self.log(f"Settings file loaded: {self.loaded_settings_path}")
        self.log_settings(
            "Settings loaded:"
            if self.loaded_settings_path is not None
            else "Default settings loaded:"
        )
        self.log("")
        self.log("Ready. Select a folder containing images or videos to sort.")
        self.log(f"Supported image formats: {', '.join(sorted(IMAGE_EXTENSIONS))}")
        self.log(f"Supported video formats: {', '.join(sorted(VIDEO_EXTENSIONS))}")

    def configure_main_scroll(self, _event=None):
        self.main_canvas.configure(scrollregion=self.main_canvas.bbox("all"))
        if self.main_frame.winfo_reqheight() > self.main_canvas.winfo_height():
            self.main_scrollbar.grid()
        else:
            self.main_scrollbar.grid_remove()

    def resize_main_content(self, event):
        self.main_canvas.itemconfigure(self.main_canvas_window, width=event.width)
        self.root.after_idle(self.configure_main_scroll)

    def browse_folder(self):
        folder = filedialog.askdirectory(title="Select Media Folder")
        if folder:
            self.folder_path.set(folder)
            include_videos = self.include_videos.get()
            threading.Thread(
                target=self.scan_folder,
                args=(folder, include_videos),
                daemon=True,
            ).start()

    def scan_folder(self, folder, include_videos):
        try:
            image_files = get_image_files(folder)
            video_files = []
            if include_videos:
                print("Scanning video files...")
                with os.scandir(folder) as entries:
                    for i, entry in enumerate(entries, 1):
                        if entry.is_file() and Path(entry.name).suffix.lower() in VIDEO_EXTENSIONS:
                            video_files.append(Path(entry.path))
                        if i == 1 or i % 500 == 0:
                            print(f"Scanning video files: {i} entries checked, {len(video_files)} videos found...")
                print("Scanning video files 1/1")
            self.log(
                f"\nFound {len(image_files)} images and {len(video_files)} videos in {folder}"
            )
        except Exception as e:  # noqa: BLE001
            self.log(f"\nError: {e}")

    def toggle_threshold(self):
        if self.auto_threshold.get():
            self.threshold_entry.state(["disabled"])
        else:
            self.threshold_entry.state(["!disabled"])

    def toggle_date_pattern(self):
        if self.parse_dates.get():
            self.date_pattern_entry.state(["!disabled"])
            self.date_pattern_button.state(["!disabled"])
        else:
            self.date_pattern_entry.state(["disabled"])
            self.date_pattern_button.state(["disabled"])

    def update_date_pattern_examples(self):
        sample_filenames = (
            "IMG_2025-01-31.jpg",
            "scan_2024.12.05.png",
            "vacation_08-14-2023.jpeg",
        )

        try:
            pattern = re.compile(self.date_pattern.get())
        except re.error as error:
            self.date_pattern_preview.set(f"Invalid regular expression: {error}")
            return

        preview_lines = []
        for filename in sample_filenames:
            match = pattern.search(filename)
            parsed_value = match.group() if match else "No match"
            preview_lines.append(f"{filename} → {parsed_value}")
        self.date_pattern_preview.set("\n".join(preview_lines))

    def toggle_video_settings(self):
        if self.include_videos.get():
            self.video_frame_scale.config(state=tk.NORMAL)
        else:
            self.video_frame_scale.config(state=tk.DISABLED)

    def save_settings(self):
        save_user_settings(
            self.rgb_weight.get(),
            self.hsv_weight.get(),
            self.spatial_weight.get(),
            self.texture_weight.get(),
            self.brightness_weight.get(),
            self.aspect_ratio_weight.get(),
            self.video_frame_percentage.get(),
            self.dry_run.get(),
            self.backup.get(),
            float(self.threshold.get()),
            self.auto_threshold.get(),
            self.include_videos.get(),
            self.parse_dates.get(),
            self.date_pattern.get(),
            self.separator.get(),
            self.count_start.get(),
            self.folder_path.get(),
            self.prefix.get(),
            self.feature_workers.get(),
            self.png_compress_level.get(),
            self.resize_optimization.get(),
            self.video_workers.get(),
        )
        self.log("Settings saved.")

    def restore_default_settings(self):
        (
            rgb_weight,
            hsv_weight,
            spatial_weight,
            texture_weight,
            brightness_weight,
            aspect_ratio_weight,
        ) = DEFAULT_FEATURE_WEIGHTS
        self.rgb_weight.set(rgb_weight)
        self.hsv_weight.set(hsv_weight)
        self.spatial_weight.set(spatial_weight)
        self.texture_weight.set(texture_weight)
        self.brightness_weight.set(brightness_weight)
        self.aspect_ratio_weight.set(aspect_ratio_weight)
        self.video_frame_percentage.set(VIDEO_FRAME_PERCENTAGE)
        self.dry_run.set(DRY_RUN)
        self.backup.set(BACKUP)
        self.threshold.set(str(SIMILARITY_THRESHOLD))
        self.auto_threshold.set(AUTO_DETERMINE)
        self.include_videos.set(INCLUDE_VIDEOS)
        self.parse_dates.set(PARSE_DATES)
        self.date_pattern.set(DATE_PATTERN)
        self.separator.set(SEPARATOR)
        self.count_start.set(COUNT_START)
        self.folder_path.set(FOLDER_PATH)
        self.prefix.set(FILE_PREFIX)
        self.feature_workers.set(FEATURE_WORKERS)
        self.video_workers.set(VIDEO_WORKERS)
        self.png_compress_level.set(PNG_COMPRESS_LEVEL)
        self.resize_optimization.set(RESIZE_OPTIMIZATION)
        self.toggle_threshold()
        self.toggle_date_pattern()
        self.update_date_pattern_examples()
        self.toggle_video_settings()
        self.log_settings("\nSettings reset to defaults:")

    def log_settings(self, heading):
        settings = (
            ("Image feature workers", self.feature_workers.get()),
            ("Video frame workers", self.video_workers.get()),
            ("PNG compression level", self.png_compress_level.get()),
            ("Resize optimization", self.resize_optimization.get()),
            ("Media folder", self.folder_path.get()),
            ("File prefix", self.prefix.get()),
            ("Similarity threshold", self.threshold.get()),
            ("Auto-determine threshold", self.auto_threshold.get()),
            ("RGB histogram weight", self.rgb_weight.get()),
            ("HSV histogram weight", self.hsv_weight.get()),
            ("Spatial color weight", self.spatial_weight.get()),
            ("Texture weight", self.texture_weight.get()),
            ("Brightness and contrast weight", self.brightness_weight.get()),
            ("Aspect ratio weight", self.aspect_ratio_weight.get()),
            ("Include videos", self.include_videos.get()),
            ("Video frame position (%)", self.video_frame_percentage.get()),
            ("Dry run", self.dry_run.get()),
            ("Create backup", self.backup.get()),
            ("Parse dates", self.parse_dates.get()),
            ("Date pattern", self.date_pattern.get()),
            ("Separator", self.separator.get()),
            ("Count start", self.count_start.get()),
        )

        self.log(heading)
        for name, value in settings:
            self.log(f"  {name}: {value!r}")

    def log(self, message):
        print(message)

    def update_status_from_output(self, text, timestamp):
        if self.stop_event.is_set():
            return
        if text.strip().endswith("..."):
            self.progress_stage = None
            self.progress_metrics_text.set("— items/s  — s")
            self.status_text.set(text.strip())
            if str(self.progress["mode"]) != "indeterminate":
                self.progress.config(mode="indeterminate", maximum=100)
                self.progress.start(50)
            self.progress_percent_text.set("…")
            return

        match = re.fullmatch(r"\s*(.+?)\s+(\d+)/(\d+)\s*", text)
        if match is None:
            return

        process_name, current_text, total_text = match.groups()
        current = int(current_text)
        total = int(total_text)
        stage = (process_name, total)
        if stage != self.progress_stage or current < self.progress_current:
            self.progress_stage = stage
            self.progress_started_at = timestamp
            self.progress_started_count = current
            self.progress_metrics_text.set("— items/s  — s")
        self.progress_current = current
        completed = current - self.progress_started_count
        if completed > 0:
            rate = completed / (timestamp - self.progress_started_at)
            seconds = round((total - current) / rate)
            hours, seconds = divmod(seconds, 3600)
            minutes, seconds = divmod(seconds, 60)
            eta = f"{seconds}s"
            if minutes or hours:
                eta = f"{minutes}m {eta}"
            if hours:
                eta = f"{hours}h {eta}"
            self.progress_metrics_text.set(f"{rate:.1f} items/s  {eta}")
        percentage = round(current / total * 100)
        self.status_text.set(f"{process_name} {current}/{total}")
        self.progress.stop()
        self.progress.config(mode="determinate", maximum=total, value=current)
        if current == 0 and total == 1:
            self.progress.config(mode="indeterminate", maximum=100)
            self.progress.start(50)
            self.progress_percent_text.set("…")
            return
        self.progress_percent_text.set(f"{percentage}%")

    def start_sorting(self):
        folder = self.folder_path.get()

        if not folder:
            messagebox.showwarning("No Folder", "Please select a folder containing images.")
            return

        if not Path(folder).exists():
            messagebox.showerror("Error", f"Folder does not exist: {folder}")
            return

        threshold_val = None
        if not self.auto_threshold.get():
            try:
                threshold_val = float(self.threshold.get())
                if threshold_val <= 0:
                    raise ValueError()
            except ValueError:
                messagebox.showerror("Invalid Threshold",
                                   "Threshold must be a positive number.")
                return

        feature_weights = (
            self.rgb_weight.get(),
            self.hsv_weight.get(),
            self.spatial_weight.get(),
            self.texture_weight.get(),
            self.brightness_weight.get(),
            self.aspect_ratio_weight.get(),
        )

        prefix = self.prefix.get()

        if not self.dry_run.get():
            response = messagebox.askyesno(
                "Confirm Rename",
                "This will rename all supported media files in the folder.\n"
                f"{'A backup will be created.' if self.backup.get() else 'NO BACKUP will be created!'}\n\n"
                "Continue?"
            )
            if not response:
                return

        self.is_processing = True
        self.stop_event.clear()
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.status_text.set("Scanning image files...")
        self.progress.stop()
        self.progress.config(mode="indeterminate", maximum=100, value=0)
        self.progress.start(50)
        self.progress_percent_text.set("…")

        self.progress_stage = None
        self.progress_metrics_text.set("— items/s  — s")

        self.log_text.delete(1.0, tk.END)
        self.log("="*60)
        self.log(r"Starting media sorting...")
        self.log(f"Folder: {folder}")
        self.log(f"Threshold: {threshold_val if threshold_val else 'auto'}")
        self.log(f"Feature weights: {feature_weights}")
        self.log(f"Image feature workers: {self.feature_workers.get()}")
        self.log(f"Video frame workers: {self.video_workers.get()}")
        self.log(f"PNG compression level: {self.png_compress_level.get()}")
        self.log(f"Resize optimization: {self.resize_optimization.get()}")
        self.log(f"Video frame position: {self.video_frame_percentage.get()}%")
        self.log(f"Include videos: {self.include_videos.get()}")
        self.log(f"Prefix: '{prefix}'")
        self.log(f"Parse dates: {self.parse_dates.get()}")
        self.log(f"Count start: {self.count_start.get()}")
        self.log(f"Dry Run: {self.dry_run.get()}")
        self.log(f"Backup: {self.backup.get()}")
        self.log("="*60 + "\n")

        thread = threading.Thread(
            target=self.run_sorting,
            args=(
                folder,
                threshold_val,
                feature_weights,
                self.video_frame_percentage.get(),
                self.include_videos.get(),
                self.feature_workers.get(),
                self.png_compress_level.get(),
                RESIZE_REDUCING_GAPS[self.resize_optimization.get()],
                prefix,
            ),
            kwargs={"video_workers": self.video_workers.get()},
            daemon=True
        )
        thread.start()

    def run_sorting(
        self,
        folder,
        threshold_val,
        feature_weights,
        video_frame_percentage,
        include_videos,
        feature_workers,
        png_compress_level,
        reducing_gap,
        prefix,
        video_workers=VIDEO_WORKERS,
    ):
        try:
            image_files = get_image_files(folder, self.stop_event)
            video_image_files = (
                get_video_image_files(
                    folder, self.stop_event, video_frame_percentage, png_compress_level,
                    video_workers=video_workers,
                )
                if include_videos and not self.stop_event.is_set()
                else []
            )

            if self.stop_event.is_set():
                self.log("\nSorting stopped.")
                self.on_complete(False)
                return

            image_files.extend(video_image_files)

            if not image_files:
                self.log("\nError: No image files found!")
                self.on_complete(False)
                return

            sorted_images = sort_with_tight_clustering(
                image_files,
                threshold_val,
                feature_weights,
                feature_workers,
                reducing_gap,
                stop_event=self.stop_event,
            )

            if self.stop_event.is_set():
                self.log("\nSorting stopped.")
                self.on_complete(False)
                return

            if video_image_files:
                rename_media(
                    sorted_images,
                    folder,
                    prefix=prefix,
                    dry_run=self.dry_run.get(),
                    backup=self.backup.get(),
                    parse_dates=self.parse_dates.get(),
                    date_pattern=self.date_pattern.get(),
                    separator=self.separator.get(),
                    count_start=self.count_start.get(),
                    stop_event=self.stop_event,
                )
            else:
                rename_images(
                    sorted_images,
                    prefix=prefix,
                    dry_run=self.dry_run.get(),
                    backup=self.backup.get(),
                    parse_dates=self.parse_dates.get(),
                    date_pattern=self.date_pattern.get(),
                    separator=self.separator.get(),
                    count_start=self.count_start.get(),
                    stop_event=self.stop_event,
                )

            if self.stop_event.is_set():
                self.log("\nSorting stopped.")
            self.on_complete(not self.stop_event.is_set())

        except Exception as e:  # noqa: BLE001
            self.log(f"\n❌ Error: {e}")
            import traceback
            self.log(traceback.format_exc())
            self.on_complete(False)

    def on_complete(self, success):
        self.log_redirector.text_queue.put((lambda: self._on_complete_ui(success), None))

    def _on_complete_ui(self, success):
        self.progress.stop()
        self.progress.config(mode="determinate")
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.is_processing = False
        self.progress_stage = None
        self.progress_metrics_text.set("— items/s  0s" if success else "— items/s  — s")

        if success:
            self.status_text.set("Media sorting complete 1/1")
            self.progress.config(maximum=1, value=1)
            self.progress_percent_text.set("100%")
            if self.dry_run.get():
                self.show_completion_dialog(
                    "Dry Run Complete",
                    "Dry run completed successfully!\n"
                    "Check the log for preview of changes.\n\n"
                    "Uncheck 'Dry Run' to actually rename files.",
                )
            else:
                self.show_completion_dialog(
                    "Success",
                    "Media sorted and renamed successfully!\n"
                    "Check the log for details.",
                )
        else:
            outcome = "stopped" if self.stop_event.is_set() else "failed"
            self.status_text.set(f"Media sorting {outcome} 0/1")
            self.progress.config(maximum=1, value=0)
            self.progress_percent_text.set("0%")

    def show_completion_dialog(self, title, message):
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.transient(self.root)
        dialog.resizable(False, False)
        dialog.grab_set()

        ttk.Label(
            dialog,
            text=message,
            justify=tk.LEFT,
            padding=20,
        ).pack()

        button_frame = ttk.Frame(dialog, padding=(10, 0, 10, 10))
        button_frame.pack()
        ttk.Button(
            button_frame,
            text="Open Folder",
            command=self.open_input_folder,
        ).pack(side=tk.LEFT, padx=5)
        ttk.Button(
            button_frame,
            text="Open Folder and Quit",
            command=self.open_input_folder_and_quit,
        ).pack(side=tk.LEFT, padx=5)
        ttk.Button(
            button_frame,
            text="Close",
            command=dialog.destroy,
        ).pack(side=tk.LEFT, padx=5)
        ttk.Button(
            button_frame,
            text="Quit",
            command=self.root.destroy,
        ).pack(side=tk.LEFT, padx=5)

        dialog.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - dialog.winfo_width()) // 2
        y = self.root.winfo_rooty() + (self.root.winfo_height() - dialog.winfo_height()) // 2
        dialog.geometry(f"+{x}+{y}")

    def open_input_folder(self):
        folder = str(Path(self.folder_path.get()))
        if sys.platform == "win32":
            os.startfile(folder)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", folder])
        else:
            subprocess.Popen(["xdg-open", folder])

    def open_input_folder_and_quit(self):
        self.open_input_folder()
        self.root.destroy()

    def stop_sorting(self):
        self.stop_event.set()
        self.stop_button.config(state=tk.DISABLED)
        self.status_text.set("Stopping...")
        self.log("\nStop requested...")


class TextRedirector:
    def __init__(self, widget, tag, status_callback):
        self.widget = widget
        self.tag = tag
        self.status_callback = status_callback
        self.text_queue = queue.Queue()
        self.widget.after(50, self.write_queued_text)

    def write(self, text):
        self.text_queue.put((text, time.perf_counter()))

    def write_queued_text(self):
        for _ in range(200):
            if self.text_queue.empty():
                break
            text, timestamp = self.text_queue.get_nowait()
            if callable(text):
                self.widget.see(tk.END)
                text()
                continue
            self.widget.insert(tk.END, text)
            self.status_callback(text, timestamp)
        self.widget.see(tk.END)
        self.widget.after(50, self.write_queued_text)

    def flush(self):
        pass


def main():
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        create_mutex = ctypes.windll.kernel32.CreateMutexW
        create_mutex.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
        create_mutex.restype = wintypes.HANDLE
        # Windows keeps this mutex alive until the process exits.
        create_mutex(None, False, "electblake.Spectra.Running")

    root = tk.Tk()
    app = ImageSorterGUI(root)
    if len(sys.argv) > 1:
        app.folder_path.set(sys.argv[1])
    root.mainloop()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
