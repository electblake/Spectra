"""Spectra application."""

import multiprocessing
import os
import re
import shutil
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
    MAPPING_CSV_FOLDER,
    OVERWRITE_MAPPING_CSV,
    PNG_COMPRESS_LEVEL,
    SEPARATOR,
    VIDEO_EXTENSIONS,
    VIDEO_FRAME_PERCENTAGE,
    VIDEO_WORKERS,
)
from app.events import Log, Progress, console_report
from app.image_processors import extract_visual_features
from app.workers.video_frames import (
    prepare_video_frames,
    video_frame_path,
    video_frame_source,
    video_frames_worker,
)

# Bound each video task independently of OpenCV open/read timeouts.
VIDEO_FRAME_PROCESS_TIMEOUT_SECONDS = 25


def _load_image_features(
    image_path: Path,
    *,
    feature_weights: tuple[float, float, float, float, float, float] = DEFAULT_FEATURE_WEIGHTS,
    reducing_gap: float | None = None,
) -> np.ndarray:
    # Keep file ownership in the loader; extractors receive an open Pillow image.
    with Image.open(image_path) as image:
        return extract_visual_features(
            image, feature_weights=feature_weights, reducing_gap=reducing_gap,
        )


def feature_distance(feat1: np.ndarray, feat2: np.ndarray) -> float:
    return np.linalg.norm(feat1 - feat2)


def get_image_files(folder_path: str, stop_event: threading.Event | None = None, report=console_report) -> list[Path]:
    folder = Path(folder_path)

    if not folder.exists():
        raise FileNotFoundError(f"Folder not found: {folder_path}")

    if not folder.is_dir():
        raise NotADirectoryError(f"Not a directory: {folder_path}")

    report(Progress("Scanning image files..."))
    image_files = []
    with os.scandir(folder) as entries:
        for i, entry in enumerate(entries, 1):
            if stop_event is not None and stop_event.is_set():
                return []
            if entry.is_file() and Path(entry.name).suffix.lower() in IMAGE_EXTENSIONS:
                image_files.append(Path(entry.path))
            if i == 1 or i % 500 == 0:
                report(Progress(f"Scanning image files: {i} entries checked, {len(image_files)} images found..."))
    report(Log(f"Found {len(image_files)} images"))
    report(Progress('Scanning image files', 1, 1))

    return sorted(image_files)

def get_video_image_files(
    folder_path: str | Path,
    stop_event: threading.Event,
    frame_percentage: int = VIDEO_FRAME_PERCENTAGE,
    png_compress_level: int = PNG_COMPRESS_LEVEL,
    video_workers: int = VIDEO_WORKERS,
    report=console_report,
) -> list[Path]:
    folder_path = Path(folder_path)
    if not folder_path.exists():
        raise FileNotFoundError(f"Folder not found: {folder_path}")

    if not folder_path.is_dir():
        raise NotADirectoryError(f"Not a directory: {folder_path}")

    report(Progress("Scanning video files..."))
    video_files = []
    with os.scandir(folder_path) as entries:
        for i, entry in enumerate(entries, 1):
            if stop_event.is_set():
                return []
            if entry.is_file() and Path(entry.name).suffix.lower() in VIDEO_EXTENSIONS:
                video_files.append(Path(entry.path))
            if i == 1 or i % 500 == 0:
                report(Progress(f"Scanning video files: {i} entries checked, {len(video_files)} videos found..."))
    report(Log(f"Found {len(video_files)} videos"))
    report(Progress('Scanning video files', 1, 1))

    if not video_files:
        return []

    image_files, video_files = prepare_video_frames(video_files)
    report(Log(f"Reusing {len(image_files)} cached video frames"))
    if not video_files:
        return sorted(image_files)

    report(Progress(f"Extracting frames from {len(video_files)} videos..."))
    report(Log(f"Extracting frames from {len(video_files)} videos..."))
    report(Progress('Extracting video frames', 0, len(video_files)))

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
                        report(Log(f"  Warning: Skipping invalid Unicode filename: {video_file_path.name!a}"))
                        completed += 1
                        report(Progress('Extracting video frames', completed, len(video_files)))
                        if completed % 10 == 0 or completed == len(video_files):
                            report(Log(f"Extracting video frames {completed}/{len(video_files)}"))
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
                        report(Log(f"  Warning: Skipping {worker['path'].name}: "
                            f"could not read frame {frame_number}"))
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
                    report(Log(f"  Warning: Skipping {worker['path'].name}: "
                        f"frame extraction timed out after {VIDEO_FRAME_PROCESS_TIMEOUT_SECONDS} seconds"))
                else:
                    continue
                worker["path"] = None
                completed += 1
                report(Progress('Extracting video frames', completed, len(video_files)))
                if completed % 10 == 0 or completed == len(video_files):
                    report(Log(f"Extracting video frames {completed}/{len(video_files)}"))
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
        report(Log("Frame extraction stopped."))
        return []

    report(Log(f"Frame extraction complete: {len(image_files)} frames available"))
    return sorted(image_files)


def sort_cluster_internally(cluster_features: np.ndarray, cluster_items: list, report=console_report) -> list:
    if len(cluster_items) <= 1:
        return cluster_items

    dist_matrix = cdist(cluster_features, cluster_features, metric='euclidean')

    visited = [False] * len(cluster_items)
    path = [0]
    visited[0] = True
    report(Progress('Sorting images in cluster', 1, len(cluster_items)))

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
            report(Progress('Sorting images in cluster', len(path), len(cluster_items)))

    return [cluster_items[i] for i in path]


def sort_images_worker(connection, args):
    result = sort_with_tight_clustering(
        *args, report=lambda event: connection.send(("event", event)),
    )
    connection.send(("result", result))
    connection.close()


def sort_with_tight_clustering(
    image_files: list[Path],
    similarity_threshold: float | None = None,
    feature_weights: tuple[float, float, float, float, float, float] = DEFAULT_FEATURE_WEIGHTS,
    feature_workers: int = FEATURE_WORKERS,
    reducing_gap: float | None = None,
    stop_event: threading.Event | None = None,
    report=console_report,
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
                    report(value)
            return []
        finally:
            if process.is_alive():
                process.terminate()
            process.join()
            parent_connection.close()

    report(Progress(f"Loading {len(image_files)} images and extracting visual features..."))
    report(Log("(This includes color histograms, spatial layout, texture, brightness, and aspect ratio)\n"))

    images_with_features = []
    features = []

    with ThreadPoolExecutor(max_workers=feature_workers) as executor:
        report(Progress("Submitting images for visual feature extraction..."))
        report(Progress('Processing visual features', 0, len(image_files)))
        extracted_features = [
            executor.submit(
                _load_image_features,
                img_path,
                feature_weights=feature_weights,
                reducing_gap=reducing_gap,
            )
            for img_path in image_files
        ]
        for i, (img_path, future) in enumerate(zip(image_files, extracted_features), 1):
            try:
                feat = future.result()
            except Exception as error:  # noqa: BLE001
                report(Log(f"  Warning: Skipping {img_path}: {error}"))
            else:
                images_with_features.append((img_path, feat))
                features.append(feat)
            report(Progress('Processing visual features', i, len(image_files)))

    skipped_count = len(image_files) - len(images_with_features)
    report(Log(f"Visual feature extraction complete: {len(images_with_features)} processed, {skipped_count} skipped"))

    if not images_with_features:
        raise ValueError("No valid images found")

    if len(images_with_features) == 1:
        return images_with_features

    features = np.array(features)
    n_images = len(features)

    report(Progress(f"\nCalculating visual similarity between {n_images} images..."))
    report(Progress('Calculating visual similarity', 0, 1))

    distance_matrix = cdist(features, features, metric='euclidean')

    report(Progress('Calculating visual similarity', 1, 1))

    if similarity_threshold is None:
        report(Progress('Determining similarity threshold', 0, n_images))
        nn_distances = []
        for i in range(n_images):
            positive_distances = distance_matrix[i][distance_matrix[i] > 0]
            if positive_distances.size:
                nn_distances.append(np.min(positive_distances))
            if (i + 1) % 100 == 0 or i + 1 == n_images:
                report(Progress('Determining similarity threshold', i + 1, n_images))
        similarity_threshold = float(np.percentile(nn_distances, 70))

    report(Progress(f"\nClustering with DBSCAN (eps={similarity_threshold:.4f})..."))
    report(Progress('Clustering images', 0, 1))

    clustering = DBSCAN(
        eps=similarity_threshold, # type: ignore
        min_samples=1,
        metric='precomputed'
    )

    cluster_labels = clustering.fit_predict(distance_matrix)
    report(Progress('Clustering images', 1, 1))

    clusters = {}
    for idx, label in enumerate(cluster_labels):
        if label not in clusters:
            clusters[label] = []
        clusters[label].append((idx, images_with_features[idx]))

    report(Log(f"  Found {len(clusters)} clusters"))
    cluster_sizes = sorted([len(items) for items in clusters.values()], reverse=True)
    report(Log(f"  Cluster sizes: {cluster_sizes[:10]}{'...' if len(cluster_sizes) > 10 else ''}"))

    report(Progress("\nSorting images within each cluster..."))
    sorted_clusters = {}

    for cluster_number, (label, cluster_items) in enumerate(clusters.items(), 1):
        cluster_indices = [idx for idx, _ in cluster_items]
        cluster_feats = features[cluster_indices]
        sorted_items = sort_cluster_internally(cluster_feats, cluster_items, report)
        sorted_clusters[label] = sorted_items
        report(Progress('Sorting clusters', cluster_number, len(clusters)))

    report(Log("  All clusters sorted internally"))

    report(Progress("\nOrdering clusters..."))

    cluster_representatives = {}
    for label, items in sorted_clusters.items():
        indices = [idx for idx, _ in items]
        centroid = np.mean(features[indices], axis=0)
        cluster_representatives[label] = centroid

    cluster_labels_list = list(sorted_clusters.keys())
    n_clusters = len(cluster_labels_list)

    if n_clusters == 1:
        ordered_labels = cluster_labels_list
        report(Progress('Ordering clusters', 1, 1))
    else:
        centroid_matrix = np.array([cluster_representatives[label] for label in cluster_labels_list])
        centroid_distances = cdist(centroid_matrix, centroid_matrix, metric='euclidean')

        visited = [False] * n_clusters
        ordered_labels = [cluster_labels_list[0]]
        visited[0] = True
        report(Progress('Ordering clusters', 1, n_clusters))

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
                report(Progress('Ordering clusters', len(ordered_labels), n_clusters))

    report(Progress("\nAssembling final sequence..."))
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
        report(Progress('Assembling final sequence', cluster_idx + 1, len(ordered_labels)))

    report(Log(f"  Final sequence: {len(sorted_images)} images"))

    return sorted_images


def rename_images(sorted_images: list[tuple[Path, np.ndarray]],
                  prefix: str = "",
                  dry_run: bool = False,
                  backup: bool = True,
                  parse_dates: bool = False,
                  date_pattern: str = DATE_PATTERN,
                  separator: str = SEPARATOR,
                  count_start: int = COUNT_START,
                  stop_event: threading.Event | None = None,
                  report=console_report,
                  mapping_csv_folder: str = MAPPING_CSV_FOLDER,
                  overwrite_mapping_csv: bool = OVERWRITE_MAPPING_CSV) -> None:
    folder = sorted_images[0][0].parent
    if prefix and not prefix.endswith(separator):
        prefix += separator

    backup_folder = folder / "backup_originals"
    if backup and not dry_run:
        backup_folder.mkdir(exist_ok=True)
        report(Log(f"\nCreating backup in: {backup_folder}"))

    padding = len(str(count_start + len(sorted_images) - 1))

    mapping = []
    temp_names = []
    temp_run_id = uuid.uuid4().hex

    report(Progress(f"\n{'DRY RUN - ' if dry_run else ''}Renaming images..."))

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
        report(Progress('Preparing images', i, len(sorted_images)))

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
            report(Log(f"Parsed date: {date}"))
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
        report(Progress('Renaming images', i, len(temp_names)))

        if i <= 5 or i > len(temp_names) - 5:
            report(Log(f"  {original_name} → {new_name}"))
        elif i == 6:
            report(Log(f"  ... ({len(temp_names) - 10} more) ..."))

    mapping_folder = (folder / mapping_csv_folder.replace("{workFolder}", str(folder.resolve()))).resolve()
    mapping_file = mapping_folder / "rename_mapping.csv"
    if not dry_run:
        mapping_folder.mkdir(parents=True, exist_ok=True)
        mapping_number = 1
        while not overwrite_mapping_csv and mapping_file.exists():
            mapping_file = mapping_folder / f"rename_mapping_{mapping_number}.csv"
            mapping_number += 1
        with open(mapping_file, 'w' if overwrite_mapping_csv else 'x', encoding='utf-8') as f:
            f.write("Original Name,New Name\n")
            f.writelines(f'"{orig}","{new}"\n' for orig, new in final_mapping)
        report(Log(f"\nMapping saved to: {mapping_file}"))

    if dry_run:
        report(Log("\n*** DRY RUN COMPLETE - No files were modified ***"))
    else:
        report(Log(f"\n✓ Successfully renamed {len(sorted_images)} images!"))
        if backup:
            report(Log(f"✓ Original files backed up to: {backup_folder}"))
def rename_media(sorted_images: list[tuple[Path, np.ndarray]],
                 folder_path: str | Path,
                 prefix: str = "",
                 dry_run: bool = False,
                 backup: bool = True,
                 parse_dates: bool = False,
                 date_pattern: str = DATE_PATTERN,
                 separator: str = SEPARATOR,
                 count_start: int = COUNT_START,
                 stop_event: threading.Event | None = None,
                 report=console_report,
                 mapping_csv_folder: str = MAPPING_CSV_FOLDER,
                 overwrite_mapping_csv: bool = OVERWRITE_MAPPING_CSV) -> None:
    folder = Path(folder_path)
    if prefix and not prefix.endswith(separator):
        prefix += separator
    media_files = [
        video_frame_source(image_path, folder)
        for image_path, _ in sorted_images
    ]

    backup_folder = folder / "backup_originals"
    if backup and not dry_run:
        backup_folder.mkdir(exist_ok=True)
        report(Log(f"\nCreating backup in: {backup_folder}"))

    padding = len(str(count_start + len(media_files) - 1))
    temp_names = []
    temp_run_id = uuid.uuid4().hex

    report(Progress(f"\n{'DRY RUN - ' if dry_run else ''}Renaming media..."))

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
        report(Progress('Preparing media', i, len(media_files)))

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
        report(Progress('Renaming media', i, len(temp_names)))

        if i <= 5 or i > len(temp_names) - 5:
            report(Log(f"  {media_path.name} → {new_name}"))
        elif i == 6:
            report(Log(f"  ... ({len(temp_names) - 10} more) ..."))

    mapping_folder = (folder / mapping_csv_folder.replace("{workFolder}", str(folder.resolve()))).resolve()
    mapping_file = mapping_folder / "rename_mapping.csv"
    if not dry_run:
        mapping_folder.mkdir(parents=True, exist_ok=True)
        mapping_number = 1
        while not overwrite_mapping_csv and mapping_file.exists():
            mapping_file = mapping_folder / f"rename_mapping_{mapping_number}.csv"
            mapping_number += 1
        with open(mapping_file, 'w' if overwrite_mapping_csv else 'x', encoding='utf-8') as f:
            f.write("Original Name,New Name\n")
            f.writelines(f'"{orig}","{new}"\n' for orig, new in final_mapping)
        report(Log(f"\nMapping saved to: {mapping_file}"))

    if dry_run:
        report(Log("\n*** DRY RUN COMPLETE - No files were modified ***"))
    else:
        report(Log(f"\n✓ Successfully renamed {len(media_files)} media files!"))
        if backup:
            report(Log(f"✓ Original files backed up to: {backup_folder}"))
