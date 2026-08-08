"""Spectra application."""

import multiprocessing
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import tkinter as tk
import uuid
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

import cv2
import numpy as np
from PIL import Image
from scipy.spatial.distance import cdist
from sklearn.cluster import DBSCAN

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
    FILE_PREFIX,
    FOLDER_PATH,
    IMAGE_EXTENSIONS,
    INCLUDE_VIDEOS,
    PARSE_DATES,
    SEPARATOR,
    SIMILARITY_THRESHOLD,
    VIDEO_EXTENSIONS,
    VIDEO_FRAME_PERCENTAGE,
    read_user_settings,
    save_user_settings,
)
from app.install import install as install_file_explorer

__version__ = APP_VERSION

VIDEO_GRABS_FOLDER = ".spectra_video_grabs"
VIDEO_OPEN_TIMEOUT_MS = 10_000
VIDEO_READ_TIMEOUT_MS = 10_000
VIDEO_FRAME_PROCESS_TIMEOUT_SECONDS = 25


def extract_video_frames_worker(connection) -> None:
    while True:
        task = connection.recv()
        if task is None:
            break

        video_file_path, image_file_path, frame_percentage = task
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
            image.save(image_file_path)

        connection.send((frame_valid, frame_number))

    connection.close()

def extract_color_histogram(img: Image.Image, bins_per_channel: int = 32) -> np.ndarray:
    img_rgb = img.convert('RGB')
    img_rgb = img_rgb.resize((100, 100), Image.Resampling.LANCZOS)

    img_array = np.array(img_rgb)

    hist_r = np.histogram(img_array[:, :, 0], bins=bins_per_channel, range=(0, 256))[0]
    hist_g = np.histogram(img_array[:, :, 1], bins=bins_per_channel, range=(0, 256))[0]
    hist_b = np.histogram(img_array[:, :, 2], bins=bins_per_channel, range=(0, 256))[0]

    hist = np.concatenate([hist_r, hist_g, hist_b])
    hist = hist / (hist.sum() + 1e-10)

    return hist


def extract_hsv_histogram(img: Image.Image, bins_per_channel: int = 16) -> np.ndarray:
    img_hsv = img.convert('HSV')
    img_hsv = img_hsv.resize((100, 100), Image.Resampling.LANCZOS)

    img_array = np.array(img_hsv)

    hist_h = np.histogram(img_array[:, :, 0], bins=bins_per_channel, range=(0, 256))[0]
    hist_s = np.histogram(img_array[:, :, 1], bins=bins_per_channel, range=(0, 256))[0]
    hist_v = np.histogram(img_array[:, :, 2], bins=bins_per_channel, range=(0, 256))[0]

    hist = np.concatenate([hist_h, hist_s, hist_v])
    hist = hist / (hist.sum() + 1e-10)

    return hist


def extract_spatial_color_features(img: Image.Image, grid_size: int = 4) -> np.ndarray:
    img_rgb = img.convert('RGB')
    img_rgb = img_rgb.resize((100, 100), Image.Resampling.LANCZOS)
    img_array = np.array(img_rgb)

    h, w = img_array.shape[:2]
    step_h = h // grid_size
    step_w = w // grid_size

    features = []
    for i in range(grid_size):
        for j in range(grid_size):
            region = img_array[i*step_h:(i+1)*step_h, j*step_w:(j+1)*step_w]
            mean_color = region.mean(axis=(0, 1))
            features.extend(mean_color)

    return np.array(features) / 255.0


def extract_texture_features(img: Image.Image) -> np.ndarray:
    gray = img.convert('L')
    gray = gray.resize((100, 100), Image.Resampling.LANCZOS)
    gray_array = np.array(gray, dtype=np.float32)

    grad_x = np.abs(np.diff(gray_array, axis=1))
    grad_y = np.abs(np.diff(gray_array, axis=0))

    features = [
        gray_array.std(),
        grad_x.mean(),
        grad_y.mean(),
        grad_x.std(),
        grad_y.std(),
    ]

    grid_size = 4
    h, w = gray_array.shape
    step_h = h // grid_size
    step_w = w // grid_size

    for i in range(grid_size):
        for j in range(grid_size):
            region = gray_array[i*step_h:(i+1)*step_h, j*step_w:(j+1)*step_w]
            features.append(region.std())

    return np.array(features) / 255.0


def extract_brightness_contrast(img: Image.Image) -> np.ndarray:
    gray = img.convert('L')
    gray = gray.resize((100, 100), Image.Resampling.LANCZOS)
    gray_array = np.array(gray, dtype=np.float32)

    features = [
        gray_array.mean() / 255.0,
        gray_array.std() / 255.0,
        np.median(gray_array) / 255.0,
        np.percentile(gray_array, 25) / 255.0,
        np.percentile(gray_array, 75) / 255.0,
    ]

    return np.array(features)


def extract_aspect_ratio(img: Image.Image) -> np.ndarray:
    width, height = img.size
    return np.array([np.tanh(np.log(width / height))])


def calculate_visual_features(
    image_path: str,
    feature_weights: tuple[float, float, float, float, float, float] = DEFAULT_FEATURE_WEIGHTS,
) -> np.ndarray:
    (
        rgb_weight,
        hsv_weight,
        spatial_weight,
        texture_weight,
        brightness_weight,
        aspect_ratio_weight,
    ) = feature_weights

    try:
        img = Image.open(image_path)

        weighted_features = []
        if rgb_weight != 0:
            weighted_features.append(
                extract_color_histogram(img, bins_per_channel=32) * rgb_weight
            )
        if hsv_weight != 0:
            weighted_features.append(
                extract_hsv_histogram(img, bins_per_channel=16) * hsv_weight
            )
        if spatial_weight != 0:
            weighted_features.append(
                extract_spatial_color_features(img, grid_size=4) * spatial_weight
            )
        if texture_weight != 0:
            weighted_features.append(extract_texture_features(img) * texture_weight)
        if brightness_weight != 0:
            weighted_features.append(
                extract_brightness_contrast(img) * brightness_weight
            )
        if aspect_ratio_weight != 0:
            weighted_features.append(extract_aspect_ratio(img) * aspect_ratio_weight)

        features = np.concatenate(weighted_features)

        norm = np.linalg.norm(features)
        if norm > 0:
            features = features / norm

        return features

    except Exception as e:  # noqa: BLE001
        raise ValueError(f"Could not process image: {e}")


def feature_distance(feat1: np.ndarray, feat2: np.ndarray) -> float:
    return np.linalg.norm(feat1 - feat2)


def get_image_files(folder_path: str) -> list[Path]:
    folder = Path(folder_path)

    if not folder.exists():
        raise FileNotFoundError(f"Folder not found: {folder_path}")

    if not folder.is_dir():
        raise NotADirectoryError(f"Not a directory: {folder_path}")

    image_files = [
        f for f in folder.iterdir()
        if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS
    ]

    return sorted(image_files)

def get_video_image_files(
    folder_path: str | Path,
    stop_event: threading.Event,
    frame_percentage: int = VIDEO_FRAME_PERCENTAGE,
) -> list[Path]:
    folder_path = Path(folder_path)
    if not folder_path.exists():
        raise FileNotFoundError(f"Folder not found: {folder_path}")

    if not folder_path.is_dir():
        raise NotADirectoryError(f"Not a directory: {folder_path}")

    video_files = [
        f for f in folder_path.iterdir()
        if f.is_file() and f.suffix.lower() in VIDEO_EXTENSIONS
    ]

    if not video_files:
        return []

    video_grabs_folder = folder_path / VIDEO_GRABS_FOLDER
    video_grabs_folder.mkdir(exist_ok=True)

    print(f"Extracting frames from {len(video_files)} videos...")

    process_context = multiprocessing.get_context("spawn")
    parent_connection, child_connection = process_context.Pipe()
    video_process = process_context.Process(
        target=extract_video_frames_worker,
        args=(child_connection,),
    )
    video_process.start()
    child_connection.close()

    image_files = []
    for i, video_file_path in enumerate(video_files, 1):
        if stop_event.is_set():
            parent_connection.send(None)
            video_process.join()
            parent_connection.close()
            cleanup_video_grabs(folder_path)
            print("Frame extraction stopped.")
            return []

        if any(
            0xD800 <= ord(character) <= 0xDFFF
            for character in str(video_file_path)
        ):
            print(
                f"  Warning: Skipping invalid Unicode filename: "
                f"{video_file_path.name!a}"
            )
            if i % 10 == 0 or i == len(video_files):
                print(f"  Extracted {i}/{len(video_files)}")
            continue

        image_file_path = video_grabs_folder / f"{video_file_path.name}.png"
        parent_connection.send(
            (str(video_file_path), str(image_file_path), frame_percentage)
        )

        if parent_connection.poll(VIDEO_FRAME_PROCESS_TIMEOUT_SECONDS):
            frame_valid, frame_number = parent_connection.recv()
        else:
            video_process.terminate()
            video_process.join()
            parent_connection.close()
            parent_connection, child_connection = process_context.Pipe()
            video_process = process_context.Process(
                target=extract_video_frames_worker,
                args=(child_connection,),
            )
            video_process.start()
            child_connection.close()
            print(
                f"  Warning: Skipping {video_file_path.name}: "
                f"frame extraction timed out after "
                f"{VIDEO_FRAME_PROCESS_TIMEOUT_SECONDS} seconds"
            )
            if i % 10 == 0 or i == len(video_files):
                print(f"  Extracted {i}/{len(video_files)}")
            continue

        if not frame_valid:
            print(
                f"  Warning: Skipping {video_file_path.name}: "
                f"could not read frame {frame_number}"
            )
        else:
            image_files.append(image_file_path)

        if i % 10 == 0 or i == len(video_files):
            print(f"  Extracted {i}/{len(video_files)}")

    parent_connection.send(None)
    video_process.join()
    parent_connection.close()

    return sorted(image_files)


def cleanup_video_grabs(folder_path: str | Path) -> None:
    shutil.rmtree(Path(folder_path) / VIDEO_GRABS_FOLDER)

def sort_cluster_internally(cluster_features: np.ndarray, cluster_items: list) -> list:
    if len(cluster_items) <= 1:
        return cluster_items

    dist_matrix = cdist(cluster_features, cluster_features, metric='euclidean')

    visited = [False] * len(cluster_items)
    path = [0]
    visited[0] = True

    for _ in range(len(cluster_items) - 1):
        current = path[-1]
        min_dist = float('inf')
        next_idx = -1

        for i in range(len(cluster_items)):
            if not visited[i] and dist_matrix[current, i] < min_dist:
                min_dist = dist_matrix[current, i]
                next_idx = i

        if next_idx != -1:
            path.append(next_idx)
            visited[next_idx] = True

    return [cluster_items[i] for i in path]


def sort_with_tight_clustering(
    image_files: list[Path],
    similarity_threshold: float | None = None,
    feature_weights: tuple[float, float, float, float, float, float] = DEFAULT_FEATURE_WEIGHTS,
) -> list[tuple[Path, np.ndarray]]:
    print(f"Loading {len(image_files)} images and extracting visual features...")
    print("(This includes color histograms, spatial layout, texture, brightness, and aspect ratio)\n")

    images_with_features = []
    features = []

    for i, img_path in enumerate(image_files, 1):
        try:
            feat = calculate_visual_features(str(img_path), feature_weights)
            images_with_features.append((img_path, feat))
            features.append(feat)
            if i % 10 == 0 or i == len(image_files):
                print(f"  Processed {i}/{len(image_files)}")
        except Exception as e:  # noqa: BLE001
            print(f"  Warning: Skipping {img_path.name}: {e}")

    if not images_with_features:
        raise ValueError("No valid images found")

    features = np.array(features)
    n_images = len(features)

    print(f"\nCalculating visual similarity between {n_images} images...")

    distance_matrix = cdist(features, features, metric='euclidean')

    print("  Distance matrix computed")

    if similarity_threshold is None:
        nn_distances = []
        for i in range(n_images):
            positive_distances = distance_matrix[i][distance_matrix[i] > 0]
            if positive_distances.size:
                nn_distances.append(np.min(positive_distances))
        similarity_threshold = float(np.percentile(nn_distances, 70))

    print(f"\nClustering with DBSCAN (eps={similarity_threshold:.4f})...")

    clustering = DBSCAN(
        eps=similarity_threshold, # type: ignore
        min_samples=1,
        metric='precomputed'
    )

    cluster_labels = clustering.fit_predict(distance_matrix)

    clusters = {}
    for idx, label in enumerate(cluster_labels):
        if label not in clusters:
            clusters[label] = []
        clusters[label].append((idx, images_with_features[idx]))

    print(f"  Found {len(clusters)} clusters")
    cluster_sizes = sorted([len(items) for items in clusters.values()], reverse=True)
    print(f"  Cluster sizes: {cluster_sizes[:10]}{'...' if len(cluster_sizes) > 10 else ''}")

    print("\nSorting images within each cluster...")
    sorted_clusters = {}

    for label, cluster_items in clusters.items():
        cluster_indices = [idx for idx, _ in cluster_items]
        cluster_feats = features[cluster_indices]
        sorted_items = sort_cluster_internally(cluster_feats, cluster_items)
        sorted_clusters[label] = sorted_items

    print("  All clusters sorted internally")

    print("\nOrdering clusters...")

    cluster_representatives = {}
    for label, items in sorted_clusters.items():
        indices = [idx for idx, _ in items]
        centroid = np.mean(features[indices], axis=0)
        cluster_representatives[label] = centroid

    cluster_labels_list = list(sorted_clusters.keys())
    n_clusters = len(cluster_labels_list)

    if n_clusters == 1:
        ordered_labels = cluster_labels_list
    else:
        centroid_matrix = np.array([cluster_representatives[label] for label in cluster_labels_list])
        centroid_distances = cdist(centroid_matrix, centroid_matrix, metric='euclidean')

        visited = [False] * n_clusters
        ordered_labels = [cluster_labels_list[0]]
        visited[0] = True

        for _ in range(n_clusters - 1):
            current_idx = cluster_labels_list.index(ordered_labels[-1])
            min_dist = float('inf')
            next_idx = -1

            for i in range(n_clusters):
                if not visited[i] and centroid_distances[current_idx, i] < min_dist:
                    min_dist = centroid_distances[current_idx, i]
                    next_idx = i

            if next_idx != -1:
                ordered_labels.append(cluster_labels_list[next_idx])
                visited[next_idx] = True

        print(f"  Ordered {len(ordered_labels)} clusters")

    print("\nAssembling final sequence...")
    sorted_images = []

    for cluster_idx, label in enumerate(ordered_labels):
        cluster_items = sorted_clusters[label]

        if cluster_idx > 0 and len(sorted_images) > 0 and len(cluster_items) > 1:
            prev_feat = sorted_images[-1][1]
            first_feat = cluster_items[0][1][1]
            last_feat = cluster_items[-1][1][1]

            dist_to_first = feature_distance(prev_feat, first_feat)
            dist_to_last = feature_distance(prev_feat, last_feat)

            if dist_to_last < dist_to_first:
                cluster_items = cluster_items[::-1]

        for item in cluster_items:
            sorted_images.append(item[1])

    print(f"  Final sequence: {len(sorted_images)} images")

    return sorted_images


def rename_images(sorted_images: list[tuple[Path, np.ndarray]],
                  prefix: str = "",
                  dry_run: bool = False,
                  backup: bool = True,
                  parse_dates: bool = False,
                  date_pattern: str = DATE_PATTERN,
                  separator: str = SEPARATOR,
                  count_start: int = COUNT_START) -> None:
    folder = sorted_images[0][0].parent

    backup_folder = folder / "backup_originals"
    if backup and not dry_run:
        backup_folder.mkdir(exist_ok=True)
        print(f"\nCreating backup in: {backup_folder}")

    padding = len(str(count_start + len(sorted_images) - 1))

    mapping = []
    temp_names = []

    print(f"\n{'DRY RUN - ' if dry_run else ''}Renaming images...")

    for i, (img_path, _) in enumerate(sorted_images, 1):
        ext = img_path.suffix
        temp_name = folder / f"__temp_{i:0{padding}d}{ext}"

        if not dry_run:
            if backup:
                shutil.copy2(img_path, backup_folder / img_path.name)
            img_path.rename(temp_name)

        temp_names.append(temp_name)
        mapping.append((img_path.name, temp_name.name))

    final_mapping = []
    printed_parsed_date = False
    for i, temp_path in enumerate(temp_names, 1):
        ext = temp_path.suffix
        original_name = mapping[i-1][0]
        date_match = re.search(date_pattern, original_name) if parse_dates else None
        date = date_match.group() if date_match else ""
        if date and not printed_parsed_date:
            print(f"Parsed date: {date}")
            printed_parsed_date = True
        count = count_start + i - 1
        if date:
            new_name = f"{prefix}{count:0{padding}d}{separator}{date}{ext}"
        else:
            new_name = f"{prefix}{count:0{padding}d}{ext}"
        final_path = folder / new_name

        if not dry_run:
            temp_path.rename(final_path)

        final_mapping.append((original_name, new_name))

        if i <= 5 or i > len(temp_names) - 5:
            print(f"  {original_name} → {new_name}")
        elif i == 6:
            print(f"  ... ({len(temp_names) - 10} more) ...")

    mapping_file = folder / "rename_mapping.csv"
    if not dry_run:
        with open(mapping_file, 'w', encoding='utf-8') as f:
            f.write("Original Name,New Name\n")
            f.writelines(f'"{orig}","{new}"\n' for orig, new in final_mapping)
        print(f"\nMapping saved to: {mapping_file}")

    if dry_run:
        print("\n*** DRY RUN COMPLETE - No files were modified ***")
    else:
        print(f"\n✓ Successfully renamed {len(sorted_images)} images!")
        if backup:
            print(f"✓ Original files backed up to: {backup_folder}")


def rename_videos(sorted_images: list[tuple[Path, np.ndarray]],
                  folder_path: str | Path,
                  prefix: str = "",
                  dry_run: bool = False,
                  backup: bool = True,
                  parse_dates: bool = False,
                  date_pattern: str = DATE_PATTERN,
                  separator: str = SEPARATOR,
                  count_start: int = COUNT_START) -> None:
    folder = Path(folder_path)
    video_files = [folder / image_path.stem for image_path, _ in sorted_images]

    backup_folder = folder / "backup_originals"
    if backup and not dry_run:
        backup_folder.mkdir(exist_ok=True)
        print(f"\nCreating backup in: {backup_folder}")

    padding = len(str(count_start + len(video_files) - 1))
    temp_names = []
    temp_run_id = uuid.uuid4().hex

    print(f"\n{'DRY RUN - ' if dry_run else ''}Renaming videos...")

    for i, video_path in enumerate(video_files, 1):
        temp_name = (
            folder
            / f"__temp_video_{temp_run_id}_{i:0{padding}d}{video_path.suffix}"
        )

        if not dry_run:
            if backup:
                shutil.copy2(video_path, backup_folder / video_path.name)
            video_path.rename(temp_name)

        temp_names.append(temp_name)

    final_mapping = []
    for i, (video_path, temp_path) in enumerate(zip(video_files, temp_names), 1):
        date_match = re.search(date_pattern, video_path.name) if parse_dates else None
        date = date_match.group() if date_match else ""
        count = count_start + i - 1
        if date:
            new_name = (
                f"{prefix}{count:0{padding}d}{separator}{date}{video_path.suffix}"
            )
        else:
            new_name = f"{prefix}{count:0{padding}d}{video_path.suffix}"
        final_path = folder / new_name

        if not dry_run:
            temp_path.rename(final_path)

        final_mapping.append((video_path.name, new_name))

        if i <= 5 or i > len(temp_names) - 5:
            print(f"  {video_path.name} → {new_name}")
        elif i == 6:
            print(f"  ... ({len(temp_names) - 10} more) ...")

    mapping_file = folder / "rename_mapping.csv"
    if not dry_run:
        with open(mapping_file, 'w', encoding='utf-8') as f:
            f.write("Original Name,New Name\n")
            f.writelines(f'"{orig}","{new}"\n' for orig, new in final_mapping)
        print(f"\nMapping saved to: {mapping_file}")

    if dry_run:
        print("\n*** DRY RUN COMPLETE - No files were modified ***")
    else:
        print(f"\n✓ Successfully renamed {len(video_files)} videos!")
        if backup:
            print(f"✓ Original files backed up to: {backup_folder}")


class ImageSorterGUI:
    def __init__(self, root):
        self.root = root
        self.root.title(f"{APP_NAME} v{__version__} - {APP_DESCRIPTION}")
        self.root.geometry("960x960")
        self.root.resizable(True, True)

        user_settings = read_user_settings()

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
        self.separator = tk.StringVar(value=user_settings["separator"])
        self.count_start = tk.IntVar(value=user_settings["count_start"])
        self.is_processing = False
        self.stop_event = threading.Event()

        self.setup_ui()

    def setup_ui(self):
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        self.main_canvas = tk.Canvas(self.root, highlightthickness=0)
        self.main_canvas.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        self.main_scrollbar = ttk.Scrollbar(
            self.root,
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
        ttk.Button(main_frame, text="Browse...", command=self.browse_folder).grid(
            row=row, column=2, padx=5
        )
        row += 1

        ttk.Separator(main_frame, orient='horizontal').grid(
            row=row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=15
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

        ttk.Label(renaming_frame, text="File Prefix:").grid(
            row=renaming_row, column=0, sticky=tk.W, pady=5
        )
        ttk.Entry(renaming_frame, textvariable=self.prefix, width=40).grid(
            row=renaming_row, column=1, sticky=tk.W, padx=5
        )
        ttk.Label(renaming_frame, text="(e.g., 'sorted_' → sorted_001.jpg)").grid(
            row=renaming_row, column=2, sticky=tk.W
        )
        renaming_row += 1

        ttk.Label(renaming_frame, text="Count start:").grid(
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
            text="Parse dates",
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

        ttk.Label(weights_frame, text="HSV histogram:").grid(row=1, column=0, sticky=tk.W)
        tk.Scale(
            weights_frame, from_=0.0, to=3.0, resolution=0.1,
            orient=tk.HORIZONTAL, variable=self.hsv_weight
        ).grid(row=1, column=1, sticky=(tk.W, tk.E))

        ttk.Label(weights_frame, text="Spatial color:").grid(row=2, column=0, sticky=tk.W)
        tk.Scale(
            weights_frame, from_=0.0, to=3.0, resolution=0.1,
            orient=tk.HORIZONTAL, variable=self.spatial_weight
        ).grid(row=2, column=1, sticky=(tk.W, tk.E))

        ttk.Label(weights_frame, text="Texture:").grid(row=3, column=0, sticky=tk.W)
        tk.Scale(
            weights_frame, from_=0.0, to=3.0, resolution=0.1,
            orient=tk.HORIZONTAL, variable=self.texture_weight
        ).grid(row=3, column=1, sticky=(tk.W, tk.E))

        ttk.Label(weights_frame, text="Brightness and contrast:").grid(row=4, column=0, sticky=tk.W)
        tk.Scale(
            weights_frame, from_=0.0, to=3.0, resolution=0.1,
            orient=tk.HORIZONTAL, variable=self.brightness_weight
        ).grid(row=4, column=1, sticky=(tk.W, tk.E))

        ttk.Label(weights_frame, text="Aspect ratio:").grid(row=5, column=0, sticky=tk.W)
        tk.Scale(
            weights_frame, from_=0.0, to=3.0, resolution=0.05,
            orient=tk.HORIZONTAL, variable=self.aspect_ratio_weight
        ).grid(row=5, column=1, sticky=(tk.W, tk.E))

        videos_frame = ttk.LabelFrame(main_frame, text="Videos", padding="10")
        videos_frame.grid(row=row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)
        videos_frame.columnconfigure(1, weight=1)
        row += 1

        ttk.Checkbutton(
            videos_frame,
            text="Include videos",
            variable=self.include_videos,
            command=self.toggle_video_settings,
        ).grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 5))

        ttk.Label(videos_frame, text="Frame position (%):").grid(
            row=1, column=0, sticky=tk.W
        )
        self.video_frame_scale = tk.Scale(
            videos_frame, from_=0, to=100, resolution=1,
            orient=tk.HORIZONTAL, variable=self.video_frame_percentage
        )
        self.video_frame_scale.grid(row=1, column=1, sticky=(tk.W, tk.E))
        self.toggle_video_settings()

        options_frame = ttk.Frame(main_frame)
        options_frame.grid(row=row, column=0, columnspan=3, sticky=tk.W, pady=5)
        row += 1

        ttk.Checkbutton(
            options_frame,
            text="Dry Run (preview only, don't rename)",
            variable=self.dry_run,
        ).pack(side=tk.LEFT, padx=(0, 15))
        ttk.Checkbutton(
            options_frame,
            text="Create backup of original files",
            variable=self.backup,
        ).pack(side=tk.LEFT)

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=row, column=0, columnspan=3, pady=15)
        row += 1

        self.start_button = ttk.Button(button_frame, text="Start Sorting",
                                       command=self.start_sorting)
        self.start_button.pack(side=tk.LEFT, padx=5)

        self.stop_button = ttk.Button(button_frame, text="Stop",
                                      command=self.stop_sorting,
                                      state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=5)

        self.save_settings_button = ttk.Button(
            button_frame,
            text="Save Settings",
            command=self.save_settings,
        )
        self.save_settings_button.pack(side=tk.LEFT, padx=5)

        self.defaults_button = ttk.Button(
            button_frame,
            text="Reset Default",
            command=self.restore_default_settings,
        )
        self.defaults_button.pack(side=tk.LEFT, padx=5)

        self.open_folder_button = ttk.Button(
            button_frame,
            text="Open Folder",
            command=self.open_input_folder,
        )
        self.open_folder_button.pack(side=tk.LEFT, padx=5)

        self.install_file_explorer_button = ttk.Button(
            button_frame,
            text="Install in File Explorer",
            command=self.install_in_file_explorer,
        )
        self.install_file_explorer_button.pack(side=tk.LEFT, padx=5)

        self.progress = ttk.Progressbar(main_frame, mode='indeterminate')
        self.progress.grid(row=row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)
        row += 1

        log_frame = ttk.LabelFrame(main_frame, text="Log Output", padding="5")
        log_frame.grid(row=row, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        main_frame.rowconfigure(row, weight=1)

        self.log_text = scrolledtext.ScrolledText(log_frame, height=15, wrap=tk.WORD)
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        sys.stdout = TextRedirector(self.log_text, "stdout")

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
            try:
                image_files = get_image_files(folder)
                video_files = (
                    [
                        file_path for file_path in Path(folder).iterdir()
                        if file_path.is_file()
                        and file_path.suffix.lower() in VIDEO_EXTENSIONS
                    ]
                    if self.include_videos.get()
                    else []
                )
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
        else:
            self.date_pattern_entry.state(["disabled"])

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
        self.toggle_threshold()
        self.toggle_date_pattern()
        self.toggle_video_settings()
        self.log("Settings reset to defaults.")

    def log(self, message):
        print(message)

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
        self.progress.start()

        self.log_text.delete(1.0, tk.END)
        self.log("="*60)
        self.log(r"Starting media sorting...")
        self.log(f"Folder: {folder}")
        self.log(f"Threshold: {threshold_val if threshold_val else 'auto'}")
        self.log(f"Feature weights: {feature_weights}")
        self.log(f"Video frame position: {self.video_frame_percentage.get()}%")
        self.log(f"Include videos: {self.include_videos.get()}")
        self.log(f"Prefix: '{self.prefix.get()}'")
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
            ),
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
    ):
        try:
            image_files = (
                get_video_image_files(folder, self.stop_event, video_frame_percentage)
                if include_videos
                else []
            )

            if self.stop_event.is_set():
                if image_files:
                    cleanup_video_grabs(folder)
                self.log("\nSorting stopped.")
                self.on_complete(False)
                return

            processing_videos = bool(image_files)

            if not processing_videos:
                image_files = get_image_files(folder)

            if not image_files:
                self.log("\nError: No image files found!")
                self.on_complete(False)
                return

            sorted_images = sort_with_tight_clustering(
                image_files,
                threshold_val,
                feature_weights,
            )

            if processing_videos:
                rename_images(
                    sorted_images,
                    prefix=self.prefix.get(),
                    dry_run=self.dry_run.get(),
                    backup=False,
                    parse_dates=self.parse_dates.get(),
                    date_pattern=self.date_pattern.get(),
                    separator=self.separator.get(),
                    count_start=self.count_start.get(),
                )
                rename_videos(
                    sorted_images,
                    folder,
                    prefix=self.prefix.get(),
                    dry_run=self.dry_run.get(),
                    backup=self.backup.get(),
                    parse_dates=self.parse_dates.get(),
                    date_pattern=self.date_pattern.get(),
                    separator=self.separator.get(),
                    count_start=self.count_start.get(),
                )
                cleanup_video_grabs(folder)
            else:
                rename_images(
                    sorted_images,
                    prefix=self.prefix.get(),
                    dry_run=self.dry_run.get(),
                    backup=self.backup.get(),
                    parse_dates=self.parse_dates.get(),
                    date_pattern=self.date_pattern.get(),
                    separator=self.separator.get(),
                    count_start=self.count_start.get(),
                )

            self.on_complete(True)

        except Exception as e:  # noqa: BLE001
            self.log(f"\n❌ Error: {e}")
            import traceback
            self.log(traceback.format_exc())
            self.on_complete(False)

    def on_complete(self, success):
        self.root.after(0, lambda: self._on_complete_ui(success))

    def _on_complete_ui(self, success):
        self.progress.stop()
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.is_processing = False

        if success:
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

    def install_in_file_explorer(self):
        install_file_explorer()
        messagebox.showinfo(
            "File Explorer",
            f"{APP_NAME} was installed in the File Explorer context menu.",
        )

    def stop_sorting(self):
        self.stop_event.set()
        self.stop_button.config(state=tk.DISABLED)
        self.log("\nStop requested...")


class TextRedirector:
    def __init__(self, widget, tag="stdout"):
        self.widget = widget
        self.tag = tag
        self.text_queue = queue.Queue()
        self.widget.after(50, self.write_queued_text)

    def write(self, text):
        self.text_queue.put(text)

    def write_queued_text(self):
        while not self.text_queue.empty():
            self.widget.insert(tk.END, self.text_queue.get_nowait())
        self.widget.see(tk.END)
        self.widget.after(50, self.write_queued_text)

    def flush(self):
        pass


def main():
    root = tk.Tk()
    app = ImageSorterGUI(root)
    if len(sys.argv) > 1:
        app.folder_path.set(sys.argv[1])
    root.mainloop()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
