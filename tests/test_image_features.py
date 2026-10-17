import numpy as np
import pytest
from PIL import Image

from app.image_processors import (
    extract_brightness_contrast_features,
    extract_geometry_aspect_ratio_features,
    extract_histogram_features,
    extract_spatial_color_features,
    extract_texture_features,
    extract_visual_features,
)


@pytest.mark.parametrize("color_space,bins,occupied", [
    ("RGB", 32, [31, 32, 64]),
    ("HSV", 16, [0, 31, 47]),
])
def test_histogram_channel_order_and_normalization(color_space, bins, occupied):
    image = Image.new("RGB", (100, 100), "red")
    features = extract_histogram_features(image, color_space=color_space, bins_per_channel=bins)
    assert features.shape == (3 * bins,)
    np.testing.assert_array_equal(np.flatnonzero(features), occupied)
    np.testing.assert_allclose(features[occupied], 1 / 3)


def test_uniform_image_features():
    image = Image.new("RGB", (200, 100), "white")
    np.testing.assert_array_equal(extract_spatial_color_features(image), np.ones(48))
    np.testing.assert_array_equal(extract_texture_features(image), np.zeros(21))
    np.testing.assert_array_equal(extract_brightness_contrast_features(image), [1, 0, 1, 1, 1])
    np.testing.assert_allclose(extract_geometry_aspect_ratio_features(image), [0.6])


def test_spatial_color_order_is_row_major_rgb():
    image = Image.new("RGB", (100, 100))
    for box, color in [
        ((0, 0, 50, 50), "red"), ((50, 0, 100, 50), "green"),
        ((0, 50, 50, 100), "blue"), ((50, 50, 100, 100), "white"),
    ]:
        image.paste(color, box)
    np.testing.assert_array_equal(
        extract_spatial_color_features(image, grid_size=2),
        np.array([255, 0, 0, 0, 128, 0, 0, 0, 255, 255, 255, 255]) / 255,
    )


@pytest.mark.parametrize("mode", ["RGB", "RGBA", "L", "P"])
@pytest.mark.parametrize("reducing_gap", [None, 1.0, 2.0, 3.0])
def test_extractors_preserve_input_and_vector_shapes(mode, reducing_gap):
    rng = np.random.default_rng(7)
    image = Image.fromarray(rng.integers(0, 256, (120, 240, 3), dtype=np.uint8)).convert(mode)
    original = image.tobytes()
    outputs = [
        extract_histogram_features(image, color_space="RGB", bins_per_channel=32, reducing_gap=reducing_gap),
        extract_histogram_features(image, color_space="HSV", bins_per_channel=16, reducing_gap=reducing_gap),
        extract_spatial_color_features(image, reducing_gap=reducing_gap),
        extract_texture_features(image, reducing_gap=reducing_gap),
        extract_brightness_contrast_features(image, reducing_gap=reducing_gap),
        extract_geometry_aspect_ratio_features(image),
        extract_visual_features(image, reducing_gap=reducing_gap),
    ]
    assert [features.shape for features in outputs] == [(96,), (48,), (48,), (21,), (5,), (1,), (219,)]
    assert all(np.isfinite(features).all() for features in outputs)
    assert image.mode == mode
    assert image.size == (240, 120)
    assert image.tobytes() == original


def test_composite_weight_order_and_disabled_families():
    image = Image.new("RGB", (200, 100), "white")
    features = extract_visual_features(image, feature_weights=(0, 0, 0, 0, 2, 3))
    expected = np.array([2, 0, 2, 2, 2, 1.8]) / np.sqrt(19.24)
    assert features.shape == (6,)
    np.testing.assert_allclose(features, expected)
    assert image.getpixel((0, 0)) == (255, 255, 255)
