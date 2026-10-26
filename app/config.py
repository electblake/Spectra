import tomllib
from configparser import ConfigParser
from pathlib import Path

from platformdirs import user_config_path
from PySide6.QtCore import QSettings

APP_NAME = "Spectra"
APP_ORGANIZATION = "electblake"
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
FEATURE_WORKERS = 4
VIDEO_WORKERS = 1
PNG_COMPRESS_LEVEL = 1
RESIZE_OPTIMIZATION = "Default"
RESIZE_REDUCING_GAPS = {"Default": None, "Low": 3.0, "Medium": 2.0, "High": 1.0}
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
PREFIX_FROM_FOLDER = False
PREFIX_FOLDER_INDEX = 0
MAPPING_CSV_FOLDER = "{workFolder}"
OVERWRITE_MAPPING_CSV = False

DEFAULT_FEATURE_WEIGHTS = (
    RGB_WEIGHT,
    HSV_WEIGHT,
    SPATIAL_WEIGHT,
    TEXTURE_WEIGHT,
    BRIGHTNESS_WEIGHT,
    ASPECT_RATIO_WEIGHT,
)

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp'}
VIDEO_EXTENSIONS = {'.mp4', '.avi', '.gif', '.wmv', '.mpeg', '.mov', '.m4v'}

def default_settings() -> dict:
    return {
        "feature_workers": FEATURE_WORKERS,
        "video_workers": VIDEO_WORKERS,
        "png_compress_level": PNG_COMPRESS_LEVEL,
        "resize_optimization": RESIZE_OPTIMIZATION,
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
        "prefix_from_folder": PREFIX_FROM_FOLDER,
        "prefix_folder_index": PREFIX_FOLDER_INDEX,
        "mapping_csv_folder": MAPPING_CSV_FOLDER,
        "overwrite_mapping_csv": OVERWRITE_MAPPING_CSV,
    }


SETTINGS_KEYS = {
    "feature_workers": "performance/feature_workers",
    "video_workers": "performance/video_workers",
    "png_compress_level": "performance/png_compress_level",
    "resize_optimization": "performance/resize_optimization",
    "rgb_weight": "feature_weights/rgb_weight",
    "hsv_weight": "feature_weights/hsv_weight",
    "spatial_weight": "feature_weights/spatial_weight",
    "texture_weight": "feature_weights/texture_weight",
    "brightness_weight": "feature_weights/brightness_weight",
    "aspect_ratio_weight": "feature_weights/aspect_ratio_weight",
    "video_frame_percentage": "videos/frame_percentage",
    "dry_run": "general/dry_run",
    "backup": "general/backup",
    "include_videos": "general/include_videos",
    "folder_path": "general/folder_path",
    "file_prefix": "renaming/file_prefix",
    "prefix_from_folder": "renaming/prefix_from_folder",
    "prefix_folder_index": "renaming/prefix_folder_index",
    "mapping_csv_folder": "renaming/mapping_csv_folder",
    "overwrite_mapping_csv": "renaming/overwrite_mapping_csv",
    "similarity_threshold": "clustering/similarity_threshold",
    "auto_determine": "clustering/auto_determine",
    "parse_dates": "renaming/parse_dates",
    "date_pattern": "renaming/date_pattern",
    "separator": "renaming/separator",
    "count_start": "renaming/count_start",
}


def settings_file() -> Path:
    default_folder = user_config_path(APP_NAME, appauthor=False, roaming=True)
    locations = QSettings(str(default_folder / "locations.ini"), QSettings.Format.IniFormat)
    locations.setFallbacksEnabled(False)
    return Path(locations.value("paths/config_folder", str(default_folder), type=str)) / "Spectra.ini"


def _settings_store() -> QSettings:
    settings = QSettings(str(settings_file()), QSettings.Format.IniFormat)
    settings.setFallbacksEnabled(False)
    return settings


def read_window_layout() -> dict:
    settings = QSettings(str(user_config_path(APP_NAME, appauthor=False, roaming=True) / "ui.ini"), QSettings.Format.IniFormat)
    settings.setFallbacksEnabled(False)
    return {
        key: settings.value(f"layout/{key}")
        for key in ("geometry", "main_window_state", "scroll_positions")
        if settings.contains(f"layout/{key}")
    }


def save_window_layout(geometry, main_window_state, scroll_positions) -> None:
    settings = QSettings(str(user_config_path(APP_NAME, appauthor=False, roaming=True) / "ui.ini"), QSettings.Format.IniFormat)
    settings.setFallbacksEnabled(False)
    settings.setValue("layout/geometry", geometry)
    settings.setValue("layout/main_window_state", main_window_state)
    settings.setValue("layout/scroll_positions", scroll_positions)
    settings.sync()


def read_user_settings() -> tuple[dict, Path | None]:
    path = settings_file()
    if not path.exists():
        legacy_path = user_config_path(APP_NAME, appauthor=False) / "settings.ini"
        if legacy_path.exists():
            save_user_settings(**_read_legacy_settings(legacy_path))
        else:
            return default_settings(), None
    settings = _settings_store()
    values = {
        key: settings.value(SETTINGS_KEYS[key], default, type=type(default))
        for key, default in default_settings().items()
    }
    return values, path


def save_user_settings(*, config_folder=None, **values) -> None:
    folder = Path(config_folder).expanduser().resolve() if config_folder is not None else settings_file().parent
    folder.mkdir(parents=True, exist_ok=True)
    settings = QSettings(str(folder / "Spectra.ini"), QSettings.Format.IniFormat)
    settings.setFallbacksEnabled(False)
    for key, setting_path in SETTINGS_KEYS.items():
        settings.setValue(setting_path, values[key])
    settings.sync()
    if config_folder is not None:
        default_folder = user_config_path(APP_NAME, appauthor=False, roaming=True)
        default_folder.mkdir(parents=True, exist_ok=True)
        locations = QSettings(str(default_folder / "locations.ini"), QSettings.Format.IniFormat)
        locations.setFallbacksEnabled(False)
        locations.setValue("paths/config_folder", str(folder))
        locations.sync()


def _read_legacy_settings(settings_path: Path) -> dict:
    settings = ConfigParser(interpolation=None)
    with settings_path.open(encoding="utf-8") as settings_file:
        settings.read_file(settings_file)

    return {
        "prefix_from_folder": PREFIX_FROM_FOLDER,
        "prefix_folder_index": PREFIX_FOLDER_INDEX,
        "mapping_csv_folder": MAPPING_CSV_FOLDER,
        "overwrite_mapping_csv": OVERWRITE_MAPPING_CSV,
        "feature_workers": settings.getint("performance", "feature_workers"),
        "video_workers": settings.getint("performance", "video_workers"),
        "png_compress_level": settings.getint("performance", "png_compress_level"),
        "resize_optimization": settings.get("performance", "resize_optimization"),
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
