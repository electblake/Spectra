import tkinter as tk
from tkinter import ttk

from app.config import RESIZE_REDUCING_GAPS


class SettingsTab(ttk.Frame):
    def __init__(self, parent, feature_workers, png_compress_level, resize_optimization, video_workers):
        super().__init__(parent, padding=10)
        self.columnconfigure(0, weight=1)

        performance = ttk.LabelFrame(self, text="Performance", padding=10)
        performance.grid(row=0, column=0, sticky=tk.EW)
        performance.columnconfigure(1, weight=1)

        ttk.Label(performance, text="Image feature workers:").grid(
            row=0, column=0, sticky=tk.W, pady=5,
        )
        self.feature_workers_spinbox = ttk.Spinbox(
            performance, from_=1, to=64, textvariable=feature_workers,
            state="readonly", width=8,
        )
        self.feature_workers_spinbox.grid(row=0, column=1, sticky=tk.W, padx=10)
        ttk.Label(
            performance, text="Image feature extraction threads. Default: 4. More workers use more memory.",
            wraplength=430,
        ).grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=(0, 12))

        ttk.Label(performance, text="Video frame workers:").grid(
            row=2, column=0, sticky=tk.W, pady=5,
        )
        self.video_workers_spinbox = ttk.Spinbox(
            performance, from_=1, to=64, textvariable=video_workers,
            state="readonly", width=8,
        )
        self.video_workers_spinbox.grid(row=2, column=1, sticky=tk.W, padx=10)
        ttk.Label(
            performance, text="Video frame extraction processes. Default: 1. One video per worker.",
            wraplength=430,
        ).grid(row=3, column=0, columnspan=2, sticky=tk.W, pady=(0, 12))

        processing = ttk.LabelFrame(self, text="Image processing", padding=10)
        processing.grid(row=1, column=0, sticky=tk.EW, pady=(10, 0))
        processing.columnconfigure(1, weight=1)
        ttk.Label(processing, text="PNG compression level:").grid(
            row=0, column=0, sticky=tk.W, pady=5,
        )
        ttk.Spinbox(
            processing, from_=0, to=9, textvariable=png_compress_level,
            state="readonly", width=8,
        ).grid(row=0, column=1, sticky=tk.W, padx=10)
        ttk.Label(
            processing,
            text=("Temporary video frames only. Default: 1 (fast compression). "
                  "0: uncompressed; 9: smallest files. All levels preserve the same pixels."),
            wraplength=430,
        ).grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=(0, 12))

        ttk.Label(processing, text="Image resize optimization:").grid(
            row=2, column=0, sticky=tk.W, pady=5,
        )
        ttk.Combobox(
            processing, values=tuple(RESIZE_REDUCING_GAPS),
            textvariable=resize_optimization, state="readonly", width=12,
        ).grid(row=2, column=1, sticky=tk.W, padx=10)
        ttk.Label(
            processing,
            text=("Default: original resizing. Low: gentle optimization. "
                  "Medium: faster. High: strongest optimization.\n"
                  "Analysis remains 100 × 100 pixels; originals are unchanged. "
                  "Optimization can slightly change similarity and sorting results."),
            wraplength=430,
        ).grid(row=3, column=0, columnspan=2, sticky=tk.W, pady=(0, 12))

        ttk.Label(
            self, text="Changes apply to the next run. Use Save Settings to keep them.",
            wraplength=430,
        ).grid(row=2, column=0, sticky=tk.W, pady=10)
