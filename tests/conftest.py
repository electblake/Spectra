import pytest
from PySide6.QtWidgets import QApplication

from app import config
from app.ui.controller import Controller
from app.workers import video_frames


@pytest.fixture(autouse=True)
def isolated_video_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(video_frames, "user_cache_path", lambda *args, **kwargs: tmp_path / "cache")


@pytest.fixture(scope="session")
def qapp():
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    return app


@pytest.fixture
def controller(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "user_config_path", lambda *args, **kwargs: tmp_path)
    return Controller()
