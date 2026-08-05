import tomllib
from configparser import ConfigParser
from pathlib import Path

from platformdirs import user_config_path

APP_NAME = "Spectra"
APP_DESCRIPTION = "Visual Similarity Sorter"
with (Path(__file__).parent.parent / "pyproject.toml").open("rb") as pyproject_file:
    APP_VERSION = tomllib.load(pyproject_file)["project"]["version"]

RGB_WEIGHT = 2.0
HSV_WEIGHT = 1.5
SPATIAL_WEIGHT = 1.0
TEXTURE_WEIGHT = 0.5
BRIGHTNESS_WEIGHT = 0.8
ASPECT_RATIO_WEIGHT = 0.25
VIDEO_FRAME_PERCENTAGE = 50
DRY_RUN = True
BACKUP = True
SIMILARITY_THRESHOLD = 0.01
AUTO_DETERMINE = False
INCLUDE_VIDEOS = True
PARSE_DATES = False
DATE_PATTERN = r"[0-9]{4}[\.\-][0-9]{2}[\.\-][0-9]{2}"
SEPARATOR = "_"
COUNT_START = 1
FOLDER_PATH = ""
FILE_PREFIX = ""

DEFAULT_FEATURE_WEIGHTS = (
    RGB_WEIGHT,
    HSV_WEIGHT,
    SPATIAL_WEIGHT,
    TEXTURE_WEIGHT,
    BRIGHTNESS_WEIGHT,
    ASPECT_RATIO_WEIGHT,
)

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.webp'}
VIDEO_EXTENSIONS = {'.mp4', '.avi', '.gif', '.wmv', '.mpeg', '.mov', '.m4v'}

def read_user_settings() -> dict:
    settings_path = user_config_path(
        APP_NAME,
        appauthor=False,
    ) / "settings.ini"

    if not settings_path.exists():
        return {
            "rgb_weight": RGB_WEIGHT,
            "hsv_weight": HSV_WEIGHT,
            "spatial_weight": SPATIAL_WEIGHT,
            "texture_weight": TEXTURE_WEIGHT,
            "brightness_weight": BRIGHTNESS_WEIGHT,
            "aspect_ratio_weight": ASPECT_RATIO_WEIGHT,
            "video_frame_percentage": VIDEO_FRAME_PERCENTAGE,
            "dry_run": DRY_RUN,
            "backup": BACKUP,
            "similarity_threshold": SIMILARITY_THRESHOLD,
            "auto_determine": AUTO_DETERMINE,
            "include_videos": INCLUDE_VIDEOS,
            "parse_dates": PARSE_DATES,
            "date_pattern": DATE_PATTERN,
            "separator": SEPARATOR,
            "count_start": COUNT_START,
            "folder_path": FOLDER_PATH,
            "file_prefix": FILE_PREFIX,
        }

    settings = ConfigParser(interpolation=None)
    with settings_path.open(encoding="utf-8") as settings_file:
        settings.read_file(settings_file)

    return {
        "rgb_weight": settings.getfloat("feature_weights", "rgb_weight"),
        "hsv_weight": settings.getfloat("feature_weights", "hsv_weight"),
        "spatial_weight": settings.getfloat("feature_weights", "spatial_weight"),
        "texture_weight": settings.getfloat("feature_weights", "texture_weight"),
        "brightness_weight": settings.getfloat("feature_weights", "brightness_weight"),
        "aspect_ratio_weight": settings.getfloat("feature_weights", "aspect_ratio_weight"),
        "video_frame_percentage": settings.getint(
            "videos",
            "frame_percentage",
            fallback=VIDEO_FRAME_PERCENTAGE,
        ),
        "dry_run": settings.getboolean("general", "dry_run", fallback=DRY_RUN),
        "backup": settings.getboolean("general", "backup", fallback=BACKUP),
        "similarity_threshold": settings.getfloat(
            "clustering",
            "similarity_threshold",
            fallback=SIMILARITY_THRESHOLD,
        ),
        "auto_determine": settings.getboolean(
            "clustering",
            "auto_determine",
            fallback=AUTO_DETERMINE,
        ),
        "include_videos": settings.getboolean(
            "general",
            "include_videos",
            fallback=INCLUDE_VIDEOS,
        ),
        "parse_dates": settings.getboolean(
            "renaming",
            "parse_dates",
            fallback=PARSE_DATES,
        ),
        "date_pattern": settings.get(
            "renaming",
            "date_pattern",
            fallback=DATE_PATTERN,
        ),
        "separator": settings.get(
            "renaming",
            "separator",
            fallback=SEPARATOR,
        ),
        "count_start": settings.getint(
            "renaming",
            "count_start",
            fallback=COUNT_START,
        ),
        "folder_path": settings.get(
            "general",
            "folder_path",
            fallback=FOLDER_PATH,
        ),
        "file_prefix": settings.get(
            "renaming",
            "file_prefix",
            fallback=FILE_PREFIX,
        ),
    }


def save_user_settings(
    rgb_weight,
    hsv_weight,
    spatial_weight,
    texture_weight,
    brightness_weight,
    aspect_ratio_weight,
    video_frame_percentage,
    dry_run,
    backup,
    similarity_threshold,
    auto_determine,
    include_videos,
    parse_dates,
    date_pattern,
    separator,
    count_start,
    folder_path,
    file_prefix,
) -> None:
    settings_path = user_config_path(
        APP_NAME,
        appauthor=False,
        ensure_exists=True,
    ) / "settings.ini"

    settings = ConfigParser(interpolation=None)
    if settings_path.exists():
        with settings_path.open(encoding="utf-8") as settings_file:
            settings.read_file(settings_file)

    if not settings.has_section("feature_weights"):
        settings.add_section("feature_weights")
    if not settings.has_section("videos"):
        settings.add_section("videos")
    if not settings.has_section("general"):
        settings.add_section("general")
    if not settings.has_section("clustering"):
        settings.add_section("clustering")
    if not settings.has_section("renaming"):
        settings.add_section("renaming")

    settings.set("feature_weights", "rgb_weight", str(rgb_weight))
    settings.set("feature_weights", "hsv_weight", str(hsv_weight))
    settings.set("feature_weights", "spatial_weight", str(spatial_weight))
    settings.set("feature_weights", "texture_weight", str(texture_weight))
    settings.set("feature_weights", "brightness_weight", str(brightness_weight))
    settings.set("feature_weights", "aspect_ratio_weight", str(aspect_ratio_weight))
    settings.set("videos", "frame_percentage", str(video_frame_percentage))
    settings.set("general", "dry_run", str(dry_run))
    settings.set("general", "backup", str(backup))
    settings.set("clustering", "similarity_threshold", str(similarity_threshold))
    settings.set("clustering", "auto_determine", str(auto_determine))
    settings.set("general", "include_videos", str(include_videos))
    settings.set("renaming", "parse_dates", str(parse_dates))
    settings.set("renaming", "date_pattern", str(date_pattern))
    settings.set("renaming", "separator", str(separator))
    settings.set("renaming", "count_start", str(count_start))
    settings.set("general", "folder_path", str(folder_path))
    settings.set("renaming", "file_prefix", str(file_prefix))

    with settings_path.open("w", encoding="utf-8") as settings_file:
        settings.write(settings_file)
