import numpy as np
from PIL import Image


def extract_spatial_color_features(image: Image.Image, *, grid_size: int = 4, reducing_gap: float | None = None) -> np.ndarray:
    """Return row-major grid RGB means / 255; length is 3 * grid_size ** 2.

    Leaves the input image unchanged.
    """
    img_rgb = image.convert('RGB')
    img_rgb = img_rgb.resize((100, 100), Image.Resampling.LANCZOS, reducing_gap=reducing_gap)
    img_array = np.array(img_rgb)

    h, w = img_array.shape[:2]
    step_h = h // grid_size
    step_w = w // grid_size

    # Traverse rows before columns and keep RGB order within each region.
    features = []
    for i in range(grid_size):
        for j in range(grid_size):
            region = img_array[i*step_h:(i+1)*step_h, j*step_w:(j+1)*step_w]
            mean_color = region.mean(axis=(0, 1))
            features.extend(mean_color)

    return np.array(features) / 255.0
