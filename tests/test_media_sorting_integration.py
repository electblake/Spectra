import csv
import hashlib
import shutil
import threading
import pytest
from collections import Counter
from pathlib import Path

from PIL import Image

from app.config import (
    DEFAULT_FEATURE_WEIGHTS,
    IMAGE_EXTENSIONS,
    SIMILARITY_THRESHOLD,
    VIDEO_EXTENSIONS,
)
from app.main import (
    VIDEO_GRABS_FOLDER,
    cleanup_video_grabs,
    get_image_files,
    get_video_image_files,
    rename_media,
    sort_with_tight_clustering,
)

PROJECT_ROOT = Path(__file__).parent.parent
SAMPLES_FOLDER = PROJECT_ROOT / "samples"


def file_digest(file_path: Path) -> str:
    with file_path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


@pytest.mark.parametrize("extension", [".gif", ".GIF"])
def test_gif_frame_is_extracted_and_original_renamed_once(tmp_path: Path, extension: str) -> None:
    working_folder = tmp_path / "News & Politics"
    working_folder.mkdir()
    gif_path = working_folder / f"13n3jb0 03 She came prepared!{extension}"
    frames = [Image.new("RGB", (16, 16), color) for color in ("red", "green", "blue")]
    frames[0].save(gif_path, save_all=True, append_images=frames[1:], duration=100, loop=0)
    original_digest = file_digest(gif_path)

    image_files = get_image_files(working_folder)
    video_image_files = get_video_image_files(working_folder, threading.Event(), frame_percentage=50)
    assert image_files == []
    assert len(video_image_files) == 1
    with Image.open(video_image_files[0]) as extracted_frame:
        assert extracted_frame.convert("RGB").getpixel((0, 0)) == (0, 128, 0)

    sorted_media = sort_with_tight_clustering(
        image_files + video_image_files,
        SIMILARITY_THRESHOLD,
        DEFAULT_FEATURE_WEIGHTS,
    )
    rename_media(sorted_media, working_folder, prefix="sorted_", backup=True)
    cleanup_video_grabs(working_folder)

    assert file_digest(working_folder / f"sorted_1{extension}") == original_digest
    assert file_digest(working_folder / "backup_originals" / gif_path.name) == original_digest
    assert not gif_path.exists()
    assert not list(working_folder.glob("__temp_media_*"))
    with (working_folder / "rename_mapping.csv").open(newline="", encoding="utf-8") as mapping_file:
        assert list(csv.DictReader(mapping_file)) == [
            {"Original Name": gif_path.name, "New Name": f"sorted_1{extension}"},
        ]


@pytest.mark.parametrize("video_workers", [1, 3])
def test_sort_sample_images_and_videos_together(tmp_path: Path, video_workers: int) -> None:
    source_media = sorted(
        file_path
        for file_path in SAMPLES_FOLDER.iterdir()
        if file_path.is_file()
        and file_path.suffix.lower() in IMAGE_EXTENSIONS | VIDEO_EXTENSIONS
    )
    source_digests = {
        file_path.name: file_digest(file_path)
        for file_path in source_media
    }
    source_extension_counts = Counter(
        file_path.suffix.lower()
        for file_path in source_media
    )
    expected_image_count = sum(
        file_path.suffix.lower() in IMAGE_EXTENSIONS
        for file_path in source_media
    )
    expected_video_count = sum(
        file_path.suffix.lower() in VIDEO_EXTENSIONS
        for file_path in source_media
    )

    working_folder = tmp_path / "samples"
    working_folder.mkdir()
    for file_path in source_media:
        shutil.copy2(file_path, working_folder / file_path.name)

    image_files = get_image_files(working_folder)
    video_image_files = get_video_image_files(
        working_folder,
        threading.Event(),
        video_workers=video_workers,
    )
    visual_media = image_files + video_image_files

    assert expected_image_count > 0
    assert expected_video_count > 0
    assert len(image_files) == expected_image_count
    assert len(video_image_files) == expected_video_count
    assert len(visual_media) == len(source_media)

    sorted_media = sort_with_tight_clustering(
        visual_media,
        SIMILARITY_THRESHOLD,
        DEFAULT_FEATURE_WEIGHTS,
    )
    rename_media(
        sorted_media,
        working_folder,
        prefix="sorted_",
        backup=True,
    )
    cleanup_video_grabs(working_folder)

    with (working_folder / "rename_mapping.csv").open(
        newline="",
        encoding="utf-8",
    ) as mapping_file:
        rename_mapping = list(csv.DictReader(mapping_file))

    sorted_files = sorted(
        file_path
        for file_path in working_folder.iterdir()
        if file_path.is_file()
        and file_path.suffix.lower() in IMAGE_EXTENSIONS | VIDEO_EXTENSIONS
    )
    sorted_counts = sorted(
        int(file_path.stem.removeprefix("sorted_"))
        for file_path in sorted_files
    )

    assert len(rename_mapping) == len(source_media)
    assert {row["Original Name"] for row in rename_mapping} == {
        file_path.name for file_path in source_media
    }
    assert sorted_counts == list(range(1, len(source_media) + 1))
    assert Counter(
        file_path.suffix.lower()
        for file_path in sorted_files
    ) == source_extension_counts
    assert not (working_folder / VIDEO_GRABS_FOLDER).exists()

    backup_folder = working_folder / "backup_originals"
    assert {
        file_path.name: file_digest(file_path)
        for file_path in backup_folder.iterdir()
    } == source_digests
    assert {
        file_path.name: file_digest(file_path)
        for file_path in source_media
    } == source_digests
