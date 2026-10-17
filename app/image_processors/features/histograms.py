from typing import Literal

import numpy as np
from PIL import Image


def extract_histogram_features(
    image: Image.Image,
    *,
    color_space: Literal["RGB", "HSV"],
    bins_per_channel: int,
    reducing_gap: float | None = None,
) -> np.ndarray:
    """Return concatenated channel histograms in RGB or HSV channel order.

    Length is 3 * bins_per_channel; normalize by total count plus 1e-10.
    Leaves the input image unchanged.
    """
    converted = image.convert(color_space)
    converted = converted.resize((100, 100), Image.Resampling.LANCZOS, reducing_gap=reducing_gap)

    img_array = np.array(converted)

    # Use the same 8-bit bin range for every RGB or Pillow HSV channel.
    hist_0 = np.histogram(img_array[:, :, 0], bins=bins_per_channel, range=(0, 256))[0]
    hist_1 = np.histogram(img_array[:, :, 1], bins=bins_per_channel, range=(0, 256))[0]
    hist_2 = np.histogram(img_array[:, :, 2], bins=bins_per_channel, range=(0, 256))[0]

    hist = np.concatenate([hist_0, hist_1, hist_2])
    hist = hist / (hist.sum() + 1e-10)

    return hist
