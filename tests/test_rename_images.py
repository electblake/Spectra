import numpy as np
import pytest

from app.main import rename_images


@pytest.mark.parametrize("include_existing_temp", [False, True])
def test_rename_images_preserves_existing_temp_file(tmp_path, include_existing_temp):
    original = tmp_path / "-22__25_.JPG"
    original.write_bytes(b"original image")
    existing_temp = tmp_path / "__temp_00001.JPG"
    existing_temp.write_bytes(b"existing image")
    items = [(original, np.zeros(1))]
    if include_existing_temp:
        items.append((existing_temp, np.zeros(1)))

    rename_images(items, prefix="sorted_", count_start=10000, backup=False)

    assert (tmp_path / "sorted_10000.JPG").read_bytes() == b"original image"
    second = tmp_path / "sorted_10001.JPG" if include_existing_temp else existing_temp
    assert second.read_bytes() == b"existing image"
    assert {path.name for path in tmp_path.iterdir()} == {
        "sorted_10000.JPG", second.name, "rename_mapping.csv",
    }
