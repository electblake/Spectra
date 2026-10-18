import threading
from unittest.mock import Mock

import pytest

from app import application, config, main


@pytest.mark.parametrize("prefix", ["manual_", "", "Custom prefix-é_"])
@pytest.mark.parametrize("separator", ["_", "."])
def test_manual_prefix_passed_to_rename(tmp_path, monkeypatch, prefix, separator):
    options = config.default_settings() | {
        "folder_path": str(tmp_path), "file_prefix": prefix,
        "separator": separator, "include_videos": False,
    }
    request = application.RunRequest(**options)
    monkeypatch.setattr(main, "get_image_files", Mock(return_value=[tmp_path / "a.png"]))
    monkeypatch.setattr(main, "sort_with_tight_clustering", Mock(return_value=[("ordered", [])]))
    rename = Mock()
    monkeypatch.setattr(main, "rename_images", rename)
    result = application.run_sorting(request, threading.Event(), Mock())
    assert rename.call_args.kwargs["prefix"] == prefix
    assert rename.call_args.kwargs["separator"] == separator
    assert result.request == request
    assert not result.stopped
