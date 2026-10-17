import pytest

from app.workers import video_frames


@pytest.fixture(autouse=True)
def isolated_video_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(video_frames, "user_cache_path", lambda *args, **kwargs: tmp_path / "cache")
