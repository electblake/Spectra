import numpy as np
from PIL import Image


def extract_geometry_aspect_ratio_features(image: Image.Image) -> np.ndarray:
    """Return one value: tanh(log(width / height)).

    Leaves the input image unchanged.
    """
    width, height = image.size
    return np.array([np.tanh(np.log(width / height))])
