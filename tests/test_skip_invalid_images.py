import numpy as np
import pytest
from PIL import Image

from app.main import calculate_visual_features, rename_images, sort_with_tight_clustering


@pytest.mark.parametrize("feature_workers", [1, 4])
def test_bad_files_are_reported_and_skipped_without_losing_valid_results(
    tmp_path, capsys, feature_workers,
):
    rng = np.random.default_rng(42)
    valid_paths = []
    for index in range(3):
        path = tmp_path / f"valid_{index}.png"
        Image.fromarray(rng.integers(0, 256, (100, 100, 3), dtype=np.uint8)).save(path)
        valid_paths.append(path)

    truncated = tmp_path / "truncated.jpg"
    Image.fromarray(rng.integers(0, 256, (100, 100, 3), dtype=np.uint8)).save(truncated)
    truncated.write_bytes(truncated.read_bytes()[:-100])
    with pytest.raises(ValueError, match="truncated"):
        calculate_visual_features(str(truncated))

    corrupt = tmp_path / "corrupt.png"
    corrupt.write_bytes(b"not an image")
    missing = tmp_path / "missing.png"
    unchanged = {path: path.read_bytes() for path in [truncated, corrupt]}
    expected = sort_with_tight_clustering(valid_paths, 0.5)
    capsys.readouterr()

    paths = [valid_paths[0], truncated, corrupt, valid_paths[1], missing, valid_paths[2]]
    result = sort_with_tight_clustering(paths, 0.5, feature_workers=feature_workers)

    assert [path for path, _ in result] == [path for path, _ in expected]
    for (_, actual), (_, feature) in zip(result, expected):
        np.testing.assert_array_equal(actual, feature)
    output = capsys.readouterr().out
    for path in [truncated, corrupt, missing]:
        assert f"Warning: Skipping {path}:" in output
    assert "image file is truncated" in output
    assert "Processing visual features 6/6" in output
    assert "3 processed, 3 skipped" in output

    rename_images(result, prefix="sorted_", backup=False)
    for path, content in unchanged.items():
        assert path.read_bytes() == content
    assert len(list(tmp_path.glob("sorted_*.png"))) == 3


def test_single_surviving_image_can_be_sorted_with_automatic_threshold(tmp_path, capsys):
    valid = tmp_path / "valid.png"
    Image.new("RGB", (20, 20), "red").save(valid)
    result = sort_with_tight_clustering([tmp_path / "missing.png", valid])
    assert [path for path, _ in result] == [valid]
    assert "1 processed, 1 skipped" in capsys.readouterr().out


def test_all_invalid_files_are_reported_before_no_valid_images_error(tmp_path, capsys):
    paths = [tmp_path / "missing_1.png", tmp_path / "missing_2.png"]
    with pytest.raises(ValueError, match="No valid images found"):
        sort_with_tight_clustering(paths)
    output = capsys.readouterr().out
    for path in paths:
        assert f"Warning: Skipping {path}:" in output
    assert "Processing visual features 2/2" in output
    assert "0 processed, 2 skipped" in output
