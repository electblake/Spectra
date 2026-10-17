import numpy as np
from PIL import Image


def extract_texture_features(image: Image.Image, *, reducing_gap: float | None = None) -> np.ndarray:
    """Return 21 values / 255: intensity std, x/y gradient means and stds, then 4x4 regional stds.

    Leaves the input image unchanged.
    """
    gray = image.convert('L')
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

    # Sixteen regional values follow the five global texture statistics.
    grid_size = 4
    h, w = gray_array.shape
    step_h = h // grid_size
    step_w = w // grid_size

    for i in range(grid_size):
        for j in range(grid_size):
            region = gray_array[i*step_h:(i+1)*step_h, j*step_w:(j+1)*step_w]
            features.append(region.std())

    return np.array(features) / 255.0
