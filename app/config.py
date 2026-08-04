from configparser import ConfigParser

from platformdirs import user_config_path

RGB_WEIGHT = 2.0
HSV_WEIGHT = 1.5
SPATIAL_WEIGHT = 1.0
TEXTURE_WEIGHT = 0.5
BRIGHTNESS_WEIGHT = 0.8

DEFAULT_FEATURE_WEIGHTS = (RGB_WEIGHT, HSV_WEIGHT, SPATIAL_WEIGHT, TEXTURE_WEIGHT, BRIGHTNESS_WEIGHT)

def read_user_settings() -> dict:
    settings_path = user_config_path(
        "Spectra",
        appauthor=False,
    ) / "settings.ini"

    if not settings_path.exists():
        return {
            "rgb_weight": RGB_WEIGHT,
            "hsv_weight": HSV_WEIGHT,
            "spatial_weight": SPATIAL_WEIGHT,
            "texture_weight": TEXTURE_WEIGHT,
            "brightness_weight": BRIGHTNESS_WEIGHT,
        }

    settings = ConfigParser()
    with settings_path.open(encoding="utf-8") as settings_file:
        settings.read_file(settings_file)

    return {
        "rgb_weight": settings.getfloat("feature_weights", "rgb_weight"),
        "hsv_weight": settings.getfloat("feature_weights", "hsv_weight"),
        "spatial_weight": settings.getfloat("feature_weights", "spatial_weight"),
        "texture_weight": settings.getfloat("feature_weights", "texture_weight"),
        "brightness_weight": settings.getfloat("feature_weights", "brightness_weight"),
    }

def save_user_settings(rgb_weight, hsv_weight, spatial_weight, texture_weight, brightness_weight) -> None:
    settings_path = user_config_path(
        "Spectra",
        appauthor=False,
        ensure_exists=True,
    ) / "settings.ini"

    settings = ConfigParser()
    if settings_path.exists():
        with settings_path.open(encoding="utf-8") as settings_file:
            settings.read_file(settings_file)

    if not settings.has_section("feature_weights"):
        settings.add_section("feature_weights")

    settings.set("feature_weights", "rgb_weight", str(rgb_weight))
    settings.set("feature_weights", "hsv_weight", str(hsv_weight))
    settings.set("feature_weights", "spatial_weight", str(spatial_weight))
    settings.set("feature_weights", "texture_weight", str(texture_weight))
    settings.set("feature_weights", "brightness_weight", str(brightness_weight))

    with settings_path.open("w", encoding="utf-8") as settings_file:
        settings.write(settings_file)
