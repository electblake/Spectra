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


@pytest.mark.parametrize("include_videos", [False, True])
@pytest.mark.parametrize("index,expected", [(0, "photo"), (-1, "Lauren_Cohan"), (-2, "Television")])
def test_folder_prefix_replaces_stale_prefix(monkeypatch, include_videos, index, expected):
    request = application.RunRequest(**(config.default_settings() | {
        "folder_path": "F:/Television/Lauren_Cohan/photo/",
        "file_prefix": "stale_", "prefix_from_folder": True,
        "prefix_folder_index": index, "include_videos": include_videos,
    }))
    monkeypatch.setattr(main, "get_image_files", Mock(return_value=["image.png"]))
    monkeypatch.setattr(main, "get_video_image_files", Mock(return_value=["frame.png"]))
    monkeypatch.setattr(main, "sort_with_tight_clustering", Mock(return_value=[("ordered", [])]))
    rename_images = Mock()
    rename_media = Mock()
    monkeypatch.setattr(main, "rename_images", rename_images)
    monkeypatch.setattr(main, "rename_media", rename_media)
    application.run_sorting(request, threading.Event(), Mock())
    rename = rename_media if include_videos else rename_images
    assert rename.call_args.kwargs["prefix"] == expected


@pytest.mark.parametrize("folder,index", [("", 0), ("F:/", 0), ("F:/photo", -1), ("//server/share/photo", -1)])
def test_invalid_folder_prefix_does_not_partially_change_settings(controller, folder, index):
    controller.setSetting("folder_path", folder)
    controller.setSetting("prefix_folder_index", index)
    original = controller.settings
    changed = Mock()
    controller.settingsChanged.connect(changed)
    with pytest.raises(IndexError):
        controller.setSetting("prefix_from_folder", True)
    assert controller.settings == original
    changed.assert_not_called()
