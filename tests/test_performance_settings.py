import numpy as np
import pytest
from PIL import Image

from app import config
from app.main import calculate_visual_features, sort_with_tight_clustering


@pytest.mark.parametrize("optimization", config.RESIZE_REDUCING_GAPS)
def test_parallel_sort_preserves_features_and_order(tmp_path, optimization):
    rng = np.random.default_rng(42)
    paths = []
    for index in range(6):
        path = tmp_path / f"{index}.png"
        Image.fromarray(rng.integers(0, 256, (480, 640, 3), dtype=np.uint8)).save(path)
        paths.append(path)
    gap = config.RESIZE_REDUCING_GAPS[optimization]
    expected = {path: calculate_visual_features(str(path), reducing_gap=gap) for path in paths}
    serial = sort_with_tight_clustering(paths, 0.5, feature_workers=1, reducing_gap=gap)
    parallel = sort_with_tight_clustering(paths, 0.5, feature_workers=4, reducing_gap=gap)
    assert [path for path, _ in parallel] == [path for path, _ in serial]
    for path, feature in parallel:
        np.testing.assert_array_equal(feature, expected[path])
        assert feature.shape == (219,)
        assert np.isfinite(feature).all()


def test_performance_settings_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "user_config_path", lambda *args, **kwargs: tmp_path)
    defaults, loaded_path = config.read_user_settings()
    assert loaded_path is None
    assert defaults["feature_workers"] == 4
    assert defaults["png_compress_level"] == 1
    assert defaults["resize_optimization"] == "Default"
    values = defaults | {
        "feature_workers": 2, "png_compress_level": 9, "resize_optimization": "High",
    }
    config.save_user_settings(**values)
    loaded, loaded_path = config.read_user_settings()
    assert loaded == values
    assert loaded_path == tmp_path / "settings.ini"
