import numpy as np
from PIL import Image

from app.config import DEFAULT_FEATURE_WEIGHTS

from .features.brightness_contrast import extract_brightness_contrast_features
from .features.geometry import extract_geometry_aspect_ratio_features
from .features.histograms import extract_histogram_features
from .features.spatial_color import extract_spatial_color_features
from .features.texture import extract_texture_features


def extract_visual_features(
    image: Image.Image,
    *,
    feature_weights: tuple[float, float, float, float, float, float] = DEFAULT_FEATURE_WEIGHTS,
    reducing_gap: float | None = None,
) -> np.ndarray:
    """Return the L2-normalized weighted feature vector without modifying image.

    Family order: RGB histogram, HSV histogram, spatial color, texture,
    brightness/contrast, aspect ratio. Zero-weight families are omitted.
    Default weights produce 219 values. The caller owns the image lifetime.
    """
    (
        rgb_weight,
        hsv_weight,
        spatial_weight,
        texture_weight,
        brightness_weight,
        aspect_ratio_weight,
    ) = feature_weights

    # Preserve family order; a zero weight omits that family from the vector.
    weighted_features = []
    if rgb_weight != 0:
        weighted_features.append(
            extract_histogram_features(image, color_space="RGB", bins_per_channel=32, reducing_gap=reducing_gap) * rgb_weight
        )
    if hsv_weight != 0:
        weighted_features.append(
            extract_histogram_features(image, color_space="HSV", bins_per_channel=16, reducing_gap=reducing_gap) * hsv_weight
        )
    if spatial_weight != 0:
        weighted_features.append(
            extract_spatial_color_features(image, grid_size=4, reducing_gap=reducing_gap) * spatial_weight
        )
    if texture_weight != 0:
        weighted_features.append(extract_texture_features(image, reducing_gap=reducing_gap) * texture_weight)
    if brightness_weight != 0:
        weighted_features.append(
            extract_brightness_contrast_features(image, reducing_gap=reducing_gap) * brightness_weight
        )
    if aspect_ratio_weight != 0:
        weighted_features.append(extract_geometry_aspect_ratio_features(image) * aspect_ratio_weight)

    features = np.concatenate(weighted_features)

    # Normalize after weighting so relative family contributions are preserved.
    norm = np.linalg.norm(features)
    if norm > 0:
        features = features / norm

    return features
