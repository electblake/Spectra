"""Spectra application."""

import multiprocessing
import os
import re
import shutil
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.spatial.distance import cdist
from sklearn.cluster import DBSCAN

from app.config import (
    COUNT_START,
    DATE_PATTERN,
    DEFAULT_FEATURE_WEIGHTS,
    FEATURE_WORKERS,
    IMAGE_EXTENSIONS,
    PNG_COMPRESS_LEVEL,
    SEPARATOR,
    VIDEO_EXTENSIONS,
    VIDEO_FRAME_PERCENTAGE,
    VIDEO_WORKERS,
)
from app.workers.video_frames import (
    prepare_video_frames,
    video_frame_path,
    video_frame_source,
    video_frames_worker,
)

VIDEO_FRAME_PROCESS_TIMEOUT_SECONDS = 25


def extract_color_histogram(img: Image.Image, bins_per_channel: int = 32, reducing_gap: float | None = None) -> np.ndarray:
    img_rgb = img.convert('RGB')
    img_rgb = img_rgb.resize((100, 100), Image.Resampling.LANCZOS, reducing_gap=reducing_gap)

    img_array = np.array(img_rgb)

    hist_r = np.histogram(img_array[:, :, 0], bins=bins_per_channel, range=(0, 256))[0]
    hist_g = np.histogram(img_array[:, :, 1], bins=bins_per_channel, range=(0, 256))[0]
    hist_b = np.histogram(img_array[:, :, 2], bins=bins_per_channel, range=(0, 256))[0]

    hist = np.concatenate([hist_r, hist_g, hist_b])
    hist = hist / (hist.sum() + 1e-10)

    return hist


def extract_hsv_histogram(img: Image.Image, bins_per_channel: int = 16, reducing_gap: float | None = None) -> np.ndarray:
    img_hsv = img.convert('HSV')
    img_hsv = img_hsv.resize((100, 100), Image.Resampling.LANCZOS, reducing_gap=reducing_gap)

    img_array = np.array(img_hsv)

    hist_h = np.histogram(img_array[:, :, 0], bins=bins_per_channel, range=(0, 256))[0]
    hist_s = np.histogram(img_array[:, :, 1], bins=bins_per_channel, range=(0, 256))[0]
    hist_v = np.histogram(img_array[:, :, 2], bins=bins_per_channel, range=(0, 256))[0]

    hist = np.concatenate([hist_h, hist_s, hist_v])
    hist = hist / (hist.sum() + 1e-10)

    return hist


def extract_spatial_color_features(img: Image.Image, grid_size: int = 4, reducing_gap: float | None = None) -> np.ndarray:
    img_rgb = img.convert('RGB')
    img_rgb = img_rgb.resize((100, 100), Image.Resampling.LANCZOS, reducing_gap=reducing_gap)
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


def extract_texture_features(img: Image.Image, reducing_gap: float | None = None) -> np.ndarray:
    gray = img.convert('L')
    gray = gray.resize((100, 100), Image.Resampling.LANCZOS, reducing_gap=reducing_gap)
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


def extract_brightness_contrast(img: Image.Image, reducing_gap: float | None = None) -> np.ndarray:
    gray = img.convert('L')
    gray = gray.resize((100, 100), Image.Resampling.LANCZOS, reducing_gap=reducing_gap)
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
    reducing_gap: float | None = None,
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
                extract_color_histogram(img, bins_per_channel=32, reducing_gap=reducing_gap) * rgb_weight
            )
        if hsv_weight != 0:
            weighted_features.append(
                extract_hsv_histogram(img, bins_per_channel=16, reducing_gap=reducing_gap) * hsv_weight
            )
        if spatial_weight != 0:
            weighted_features.append(
                extract_spatial_color_features(img, grid_size=4, reducing_gap=reducing_gap) * spatial_weight
            )
        if texture_weight != 0:
            weighted_features.append(extract_texture_features(img, reducing_gap=reducing_gap) * texture_weight)
        if brightness_weight != 0:
            weighted_features.append(
                extract_brightness_contrast(img, reducing_gap=reducing_gap) * brightness_weight
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


def get_image_files(folder_path: str, stop_event: threading.Event | None = None) -> list[Path]:
    folder = Path(folder_path)

    if not folder.exists():
        raise FileNotFoundError(f"Folder not found: {folder_path}")

    if not folder.is_dir():
        raise NotADirectoryError(f"Not a directory: {folder_path}")

    print("Scanning image files...")
    image_files = []
    with os.scandir(folder) as entries:
        for i, entry in enumerate(entries, 1):
            if stop_event is not None and stop_event.is_set():
                return []
            if entry.is_file() and Path(entry.name).suffix.lower() in IMAGE_EXTENSIONS:
                image_files.append(Path(entry.path))
            if i == 1 or i % 500 == 0:
                print(f"Scanning image files: {i} entries checked, {len(image_files)} images found...")
    print(f"Found {len(image_files)} images")
    print("Scanning image files 1/1")

    return sorted(image_files)

def get_video_image_files(
    folder_path: str | Path,
    stop_event: threading.Event,
    frame_percentage: int = VIDEO_FRAME_PERCENTAGE,
    png_compress_level: int = PNG_COMPRESS_LEVEL,
    video_workers: int = VIDEO_WORKERS,
) -> list[Path]:
    folder_path = Path(folder_path)
    if not folder_path.exists():
        raise FileNotFoundError(f"Folder not found: {folder_path}")

    if not folder_path.is_dir():
        raise NotADirectoryError(f"Not a directory: {folder_path}")

    print("Scanning video files...")
    video_files = []
    with os.scandir(folder_path) as entries:
        for i, entry in enumerate(entries, 1):
            if stop_event.is_set():
                return []
            if entry.is_file() and Path(entry.name).suffix.lower() in VIDEO_EXTENSIONS:
                video_files.append(Path(entry.path))
            if i == 1 or i % 500 == 0:
                print(f"Scanning video files: {i} entries checked, {len(video_files)} videos found...")
    print(f"Found {len(video_files)} videos")
    print("Scanning video files 1/1")

    if not video_files:
        return []

    image_files, video_files = prepare_video_frames(video_files)
    print(f"Reusing {len(image_files)} cached video frames")
    if not video_files:
        return sorted(image_files)

    print(f"Extracting frames from {len(video_files)} videos...")
    print(f"Extracting video frames 0/{len(video_files)}")

    process_context = multiprocessing.get_context("spawn")
    workers = []
    for _ in range(min(video_workers, len(video_files))):
        parent_connection, child_connection = process_context.Pipe()
        video_process = process_context.Process(
            target=video_frames_worker,
            args=(child_connection,),
        )
        video_process.start()
        child_connection.close()
        workers.append({"process": video_process, "connection": parent_connection, "path": None})

    next_video = 0
    completed = 0
    try:
        while completed < len(video_files) and not stop_event.is_set():
            for worker in workers:
                if stop_event.is_set():
                    break
                parent_connection = worker["connection"]
                if worker["path"] is None and next_video < len(video_files):
                    video_file_path = video_files[next_video]
                    next_video += 1
                    if any(
                        0xD800 <= ord(character) <= 0xDFFF
                        for character in str(video_file_path)
                    ):
                        print(f"  Warning: Skipping invalid Unicode filename: {video_file_path.name!a}")
                        completed += 1
                        print(f"Extracting video frames {completed}/{len(video_files)}")
                        continue
                    image_file_path = video_frame_path(video_file_path)
                    parent_connection.send((
                        str(video_file_path), str(image_file_path), frame_percentage, png_compress_level,
                    ))
                    worker["path"] = video_file_path
                    worker["image"] = image_file_path
                    worker["deadline"] = time.monotonic() + VIDEO_FRAME_PROCESS_TIMEOUT_SECONDS

                if worker["path"] is None:
                    continue
                if parent_connection.poll():
                    frame_valid, frame_number = parent_connection.recv()
                    if frame_valid:
                        image_files.append(worker["image"])
                    else:
                        print(
                            f"  Warning: Skipping {worker['path'].name}: "
                            f"could not read frame {frame_number}"
                        )
                elif time.monotonic() >= worker["deadline"]:
                    worker["process"].terminate()
                    worker["process"].join()
                    parent_connection.close()
                    parent_connection, child_connection = process_context.Pipe()
                    video_process = process_context.Process(
                        target=video_frames_worker,
                        args=(child_connection,),
                    )
                    video_process.start()
                    child_connection.close()
                    worker["connection"] = parent_connection
                    worker["process"] = video_process
                    print(
                        f"  Warning: Skipping {worker['path'].name}: "
                        f"frame extraction timed out after {VIDEO_FRAME_PROCESS_TIMEOUT_SECONDS} seconds"
                    )
                else:
                    continue
                worker["path"] = None
                completed += 1
                print(f"Extracting video frames {completed}/{len(video_files)}")
            if completed < len(video_files) and stop_event.wait(0.05):
                break
    finally:
        for worker in workers:
            if worker["path"] is not None:
                worker["process"].terminate()
            else:
                worker["connection"].send(None)
            worker["process"].join()
            worker["connection"].close()

    if stop_event.is_set():
        print("Frame extraction stopped.")
        return []

    return sorted(image_files)


def sort_cluster_internally(cluster_features: np.ndarray, cluster_items: list) -> list:
    if len(cluster_items) <= 1:
        return cluster_items

    dist_matrix = cdist(cluster_features, cluster_features, metric='euclidean')

    visited = [False] * len(cluster_items)
    path = [0]
    visited[0] = True
    print(f"Sorting images in cluster 1/{len(cluster_items)}")

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
        if len(path) % 100 == 0 or len(path) == len(cluster_items):
            print(f"Sorting images in cluster {len(path)}/{len(cluster_items)}")

    return [cluster_items[i] for i in path]


class SortingOutput:
    def __init__(self, connection):
        self.connection = connection

    def write(self, text):
        self.connection.send(("output", text))

    def flush(self):
        pass


def sort_images_worker(connection, args):
    sys.stdout = SortingOutput(connection)
    result = sort_with_tight_clustering(*args)
    connection.send(("result", result))
    connection.close()


def sort_with_tight_clustering(
    image_files: list[Path],
    similarity_threshold: float | None = None,
    feature_weights: tuple[float, float, float, float, float, float] = DEFAULT_FEATURE_WEIGHTS,
    feature_workers: int = FEATURE_WORKERS,
    reducing_gap: float | None = None,
    stop_event: threading.Event | None = None,
) -> list[tuple[Path, np.ndarray]]:
    if stop_event is not None:
        if stop_event.is_set():
            return []
        process_context = multiprocessing.get_context("spawn")
        parent_connection, child_connection = process_context.Pipe(duplex=False)
        process = process_context.Process(
            target=sort_images_worker,
            args=(child_connection, (
                image_files, similarity_threshold, feature_weights,
                feature_workers, reducing_gap,
            )),
        )
        process.start()
        child_connection.close()
        try:
            while not stop_event.is_set():
                if parent_connection.poll(0.05):
                    kind, value = parent_connection.recv()
                    if kind == "result":
                        process.join()
                        return value
                    print(value, end="")
            return []
        finally:
            if process.is_alive():
                process.terminate()
            process.join()
            parent_connection.close()

    print(f"Loading {len(image_files)} images and extracting visual features...")
    print("(This includes color histograms, spatial layout, texture, brightness, and aspect ratio)\n")

    images_with_features = []
    features = []

    with ThreadPoolExecutor(max_workers=feature_workers) as executor:
        print("Submitting images for visual feature extraction...")
        print(f"Processing visual features 0/{len(image_files)}")
        extracted_features = [
            executor.submit(
                calculate_visual_features,
                str(img_path),
                feature_weights=feature_weights,
                reducing_gap=reducing_gap,
            )
            for img_path in image_files
        ]
        for i, (img_path, future) in enumerate(zip(image_files, extracted_features), 1):
            try:
                feat = future.result()
            except Exception as error:  # noqa: BLE001
                print(f"  Warning: Skipping {img_path}: {error}")
            else:
                images_with_features.append((img_path, feat))
                features.append(feat)
            print(f"Processing visual features {i}/{len(image_files)}")

    skipped_count = len(image_files) - len(images_with_features)
    print(f"Visual feature extraction complete: {len(images_with_features)} processed, {skipped_count} skipped")

    if not images_with_features:
        raise ValueError("No valid images found")

    if len(images_with_features) == 1:
        return images_with_features

    features = np.array(features)
    n_images = len(features)

    print(f"\nCalculating visual similarity between {n_images} images...")
    print("Calculating visual similarity 0/1")

    distance_matrix = cdist(features, features, metric='euclidean')

    print("Calculating visual similarity 1/1")

    if similarity_threshold is None:
        print(f"Determining similarity threshold 0/{n_images}")
        nn_distances = []
        for i in range(n_images):
            positive_distances = distance_matrix[i][distance_matrix[i] > 0]
            if positive_distances.size:
                nn_distances.append(np.min(positive_distances))
            if (i + 1) % 100 == 0 or i + 1 == n_images:
                print(f"Determining similarity threshold {i + 1}/{n_images}")
        similarity_threshold = float(np.percentile(nn_distances, 70))

    print(f"\nClustering with DBSCAN (eps={similarity_threshold:.4f})...")
    print("Clustering images 0/1")

    clustering = DBSCAN(
        eps=similarity_threshold, # type: ignore
        min_samples=1,
        metric='precomputed'
    )

    cluster_labels = clustering.fit_predict(distance_matrix)
    print("Clustering images 1/1")

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

    for cluster_number, (label, cluster_items) in enumerate(clusters.items(), 1):
        cluster_indices = [idx for idx, _ in cluster_items]
        cluster_feats = features[cluster_indices]
        sorted_items = sort_cluster_internally(cluster_feats, cluster_items)
        sorted_clusters[label] = sorted_items
        print(f"Sorting clusters {cluster_number}/{len(clusters)}")

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
        print("Ordering clusters 1/1")
    else:
        centroid_matrix = np.array([cluster_representatives[label] for label in cluster_labels_list])
        centroid_distances = cdist(centroid_matrix, centroid_matrix, metric='euclidean')

        visited = [False] * n_clusters
        ordered_labels = [cluster_labels_list[0]]
        visited[0] = True
        print(f"Ordering clusters 1/{n_clusters}")

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
                print(f"Ordering clusters {len(ordered_labels)}/{n_clusters}")

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
        print(f"Assembling final sequence {cluster_idx + 1}/{len(ordered_labels)}")

    print(f"  Final sequence: {len(sorted_images)} images")

    return sorted_images


def rename_images(sorted_images: list[tuple[Path, np.ndarray]],
                  prefix: str = "",
                  dry_run: bool = False,
                  backup: bool = True,
                  parse_dates: bool = False,
                  date_pattern: str = DATE_PATTERN,
                  separator: str = SEPARATOR,
                  count_start: int = COUNT_START,
                  stop_event: threading.Event | None = None) -> None:
    folder = sorted_images[0][0].parent

    backup_folder = folder / "backup_originals"
    if backup and not dry_run:
        backup_folder.mkdir(exist_ok=True)
        print(f"\nCreating backup in: {backup_folder}")

    padding = len(str(count_start + len(sorted_images) - 1))

    mapping = []
    temp_names = []
    temp_run_id = uuid.uuid4().hex

    print(f"\n{'DRY RUN - ' if dry_run else ''}Renaming images...")

    for i, (img_path, _) in enumerate(sorted_images, 1):
        if stop_event is not None and stop_event.is_set():
            if not dry_run:
                for original, temporary in mapping:
                    (folder / temporary).rename(folder / original)
            return
        ext = img_path.suffix
        temp_name = folder / f"__temp_{temp_run_id}_{i:0{padding}d}{ext}"

        if not dry_run:
            if backup:
                shutil.copy2(img_path, backup_folder / img_path.name)
            img_path.rename(temp_name)

        temp_names.append(temp_name)
        mapping.append((img_path.name, temp_name.name))
        print(f"Preparing images {i}/{len(sorted_images)}")

    final_mapping = []
    printed_parsed_date = False
    for i, temp_path in enumerate(temp_names, 1):
        if stop_event is not None and stop_event.is_set():
            if not dry_run:
                for (_, renamed), temporary in zip(final_mapping, temp_names):
                    (folder / renamed).rename(temporary)
                for original, temporary in mapping:
                    (folder / temporary).rename(folder / original)
            return
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
        print(f"Renaming images {i}/{len(temp_names)}")

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


def rename_media(sorted_images: list[tuple[Path, np.ndarray]],
                 folder_path: str | Path,
                 prefix: str = "",
                 dry_run: bool = False,
                 backup: bool = True,
                 parse_dates: bool = False,
                 date_pattern: str = DATE_PATTERN,
                 separator: str = SEPARATOR,
                 count_start: int = COUNT_START,
                 stop_event: threading.Event | None = None) -> None:
    folder = Path(folder_path)
    media_files = [
        video_frame_source(image_path, folder)
        for image_path, _ in sorted_images
    ]

    backup_folder = folder / "backup_originals"
    if backup and not dry_run:
        backup_folder.mkdir(exist_ok=True)
        print(f"\nCreating backup in: {backup_folder}")

    padding = len(str(count_start + len(media_files) - 1))
    temp_names = []
    temp_run_id = uuid.uuid4().hex

    print(f"\n{'DRY RUN - ' if dry_run else ''}Renaming media...")

    for i, media_path in enumerate(media_files, 1):
        if stop_event is not None and stop_event.is_set():
            if not dry_run:
                for original, temporary in zip(media_files, temp_names):
                    temporary.rename(original)
            return
        temp_name = (
            folder
            / f"__temp_media_{temp_run_id}_{i:0{padding}d}{media_path.suffix}"
        )

        if not dry_run:
            if backup:
                shutil.copy2(media_path, backup_folder / media_path.name)
            media_path.rename(temp_name)

        temp_names.append(temp_name)
        print(f"Preparing media {i}/{len(media_files)}")

    final_mapping = []
    for i, (media_path, temp_path) in enumerate(zip(media_files, temp_names), 1):
        if stop_event is not None and stop_event.is_set():
            if not dry_run:
                for (_, renamed), temporary in zip(final_mapping, temp_names):
                    (folder / renamed).rename(temporary)
                for original, temporary in zip(media_files, temp_names):
                    temporary.rename(original)
            return
        date_match = re.search(date_pattern, media_path.name) if parse_dates else None
        date = date_match.group() if date_match else ""
        count = count_start + i - 1
        if date:
            new_name = (
                f"{prefix}{count:0{padding}d}{separator}{date}{media_path.suffix}"
            )
        else:
            new_name = f"{prefix}{count:0{padding}d}{media_path.suffix}"
        final_path = folder / new_name

        if not dry_run:
            temp_path.rename(final_path)

        final_mapping.append((media_path.name, new_name))
        print(f"Renaming media {i}/{len(temp_names)}")

        if i <= 5 or i > len(temp_names) - 5:
            print(f"  {media_path.name} → {new_name}")
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
        print(f"\n✓ Successfully renamed {len(media_files)} media files!")
        if backup:
            print(f"✓ Original files backed up to: {backup_folder}")
