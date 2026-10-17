"""Video frame extraction worker."""

import hashlib
import os
import uuid
from pathlib import Path

import cv2
from PIL import Image
from platformdirs import user_cache_path

from app.config import APP_NAME

VIDEO_OPEN_TIMEOUT_MS = 10_000
VIDEO_READ_TIMEOUT_MS = 10_000


def video_grabs_path(folder_path: str | Path) -> Path:
    source_folder = os.path.normcase(str(Path(folder_path).resolve()))
    folder_key = hashlib.sha256(source_folder.encode("utf-8", errors="surrogatepass")).hexdigest()
    return user_cache_path(APP_NAME, appauthor=False) / "video_frames" / folder_key


def video_frame_path(video_path: Path) -> Path:
    return video_grabs_path(video_path.parent) / f"{video_path.name}.png"


def prepare_video_frames(video_files: list[Path]) -> tuple[list[Path], list[Path]]:
    cached_frames = []
    pending_videos = []
    for video_path in video_files:
        frame_path = video_frame_path(video_path)
        if frame_path.is_file():
            cached_frames.append(frame_path)
        else:
            pending_videos.append(video_path)
    return cached_frames, pending_videos


def video_frame_source(image_path: Path, folder_path: Path) -> Path:
    if image_path.parent == video_grabs_path(folder_path):
        return folder_path / image_path.stem
    return image_path


def video_frames_worker(connection) -> None:
    while True:
        task = connection.recv()
        if task is None:
            break

        video_file_path, image_file_path, frame_percentage, png_compress_level = task
        video = cv2.VideoCapture(
            video_file_path,
            cv2.CAP_FFMPEG,
            [
                cv2.CAP_PROP_OPEN_TIMEOUT_MSEC,
                VIDEO_OPEN_TIMEOUT_MS,
                cv2.CAP_PROP_READ_TIMEOUT_MSEC,
                VIDEO_READ_TIMEOUT_MS,
                cv2.CAP_PROP_N_THREADS,
                1,
            ],
        )
        frame_count = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
        frame_number = round((frame_count - 1) * frame_percentage / 100)
        video.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
        frame_read, frame = video.read()
        video.release()

        frame_valid = frame_read and frame is not None and frame.size > 0
        if frame_valid:
            image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            image_file_path = Path(image_file_path)
            image_file_path.parent.mkdir(parents=True, exist_ok=True)
            pending_path = image_file_path.with_suffix(f".{uuid.uuid4().hex}.tmp")
            image.save(pending_path, format="PNG", compress_level=png_compress_level)
            pending_path.replace(image_file_path)

        connection.send((frame_valid, frame_number))

    connection.close()
