"""Sorting use cases and immutable run inputs. No UI dependencies."""

import os
from dataclasses import dataclass
from pathlib import Path

from app import main
from app.config import RESIZE_REDUCING_GAPS, VIDEO_EXTENSIONS
from app.events import Log, Progress


@dataclass(frozen=True)
class RunRequest:
    folder_path: str
    file_prefix: str
    similarity_threshold: float
    auto_determine: bool
    rgb_weight: float
    hsv_weight: float
    spatial_weight: float
    texture_weight: float
    brightness_weight: float
    aspect_ratio_weight: float
    video_frame_percentage: int
    dry_run: bool
    backup: bool
    include_videos: bool
    parse_dates: bool
    date_pattern: str
    separator: str
    count_start: int
    feature_workers: int
    video_workers: int
    png_compress_level: int
    resize_optimization: str
    mapping_csv_folder: str
    overwrite_mapping_csv: bool


@dataclass(frozen=True)
class RunResult:
    request: RunRequest
    stopped: bool


def run_sorting(request, stop, report):
    report(Log(f"Folder: {request.folder_path}"))
    report(Log(f"Run settings: {request}"))
    images = main.get_image_files(request.folder_path, stop, report=report)
    videos = []
    if request.include_videos and not stop.is_set():
        videos = main.get_video_image_files(
            request.folder_path, stop, request.video_frame_percentage,
            request.png_compress_level, request.video_workers, report=report,
        )
    if stop.is_set():
        return RunResult(request, stopped=True)
    ordered = main.sort_with_tight_clustering(
        images + videos,
        None if request.auto_determine else request.similarity_threshold,
        (request.rgb_weight, request.hsv_weight, request.spatial_weight,
         request.texture_weight, request.brightness_weight, request.aspect_ratio_weight),
        request.feature_workers,
        RESIZE_REDUCING_GAPS[request.resize_optimization],
        stop_event=stop, report=report,
    )
    if stop.is_set():
        return RunResult(request, stopped=True)
    options = {
        "prefix": request.file_prefix, "dry_run": request.dry_run, "backup": request.backup,
        "parse_dates": request.parse_dates, "date_pattern": request.date_pattern,
        "separator": request.separator, "count_start": request.count_start,
        "stop_event": stop, "report": report,
        "mapping_csv_folder": request.mapping_csv_folder,
        "overwrite_mapping_csv": request.overwrite_mapping_csv,
    }
    if videos:
        main.rename_media(ordered, request.folder_path, **options)
    else:
        main.rename_images(ordered, **options)
    return RunResult(request, stopped=stop.is_set())


def scan_folder(folder, include_videos, stop, report):
    images = main.get_image_files(folder, stop, report=report)
    videos = 0
    if include_videos:
        report(Progress("Scanning video files..."))
        with os.scandir(folder) as entries:
            for entry in entries:
                if stop.is_set():
                    break
                if entry.is_file() and Path(entry.name).suffix.lower() in VIDEO_EXTENSIONS:
                    videos += 1
    message = f"Found {len(images)} images and {videos} videos in {folder}"
    report(Log(message))
    return message
