import numpy as np
import pytest

from app.events import Log
from app.main import rename_images, rename_media


@pytest.mark.parametrize("rename", [rename_images, rename_media])
@pytest.mark.parametrize("separator", ["_", "-", ""])
@pytest.mark.parametrize("prefix", ["Lauren_Cohan", "manual_", ""])
@pytest.mark.parametrize("parse_dates", [False, True])
def test_shared_separator_in_prefix_and_date(tmp_path, rename, separator, prefix, parse_dates):
    original = tmp_path / "original-2026-10-25.JPG"
    original.write_bytes(b"source media")
    options = {"folder_path": tmp_path} if rename is rename_media else {}
    rename(
        [(original, np.zeros(1))], prefix=prefix, separator=separator,
        parse_dates=parse_dates, backup=False, **options,
    )
    expected_prefix = {
        "Lauren_Cohan": {"_": "Lauren_Cohan_", "-": "Lauren_Cohan-", "": "Lauren_Cohan"},
        "manual_": {"_": "manual_", "-": "manual_-", "": "manual_"},
        "": {"_": "", "-": "", "": ""},
    }[prefix][separator]
    expected = expected_prefix + "1"
    if parse_dates:
        expected += separator + "2026-10-25"
    expected += ".JPG"
    assert (tmp_path / expected).read_bytes() == b"source media"
    assert f'"{original.name}","{expected}"' in (tmp_path / "rename_mapping.csv").read_text()


@pytest.mark.parametrize("rename", [rename_images, rename_media])
@pytest.mark.parametrize("prefix", ["saved_", "saved"])
@pytest.mark.parametrize("original_name,expected", [
    ("photo-2026-10-25.JPG", "saved_1_2026-10-25.JPG"),
    ("photo.JPG", "saved_1.JPG"),
])
def test_shared_separator_preview_matches_rename(tmp_path, rename, prefix, original_name, expected):
    original = tmp_path / original_name
    original.write_bytes(b"original")
    items = [(original, np.zeros(1))]
    events = []
    options = {"folder_path": tmp_path} if rename is rename_media else {}
    rename(items, prefix=prefix, parse_dates=True, dry_run=True, report=events.append, **options)
    assert list(tmp_path.iterdir()) == [original]
    assert any(isinstance(event, Log) and f"→ {expected}" in event.text for event in events)
    rename(items, prefix=prefix, parse_dates=True, backup=False, **options)
    assert (tmp_path / expected).read_bytes() == b"original"


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


@pytest.mark.parametrize("rename", [rename_images, rename_media])
@pytest.mark.parametrize("destination, relative", [
    ("{workFolder}", "media"),
    ("{workFolder}/Data", "media/Data"),
    ("{workFolder}/../Data", "Data"),
    ("{workFolder}/../../Data", "../Data"),
    ("Data", "media/Data"),
    ("../Data", "Data"),
    ("absolute", "absolute"),
])
@pytest.mark.parametrize("dry_run", [False, True])
def test_mapping_csv_destination(tmp_path, rename, destination, relative, dry_run):
    tmp_path = tmp_path / "nested"
    tmp_path.mkdir()
    folder = tmp_path / "media"
    folder.mkdir()
    original = folder / "original.JPG"
    original.write_bytes(b"source media")
    expected_folder = (tmp_path / relative).resolve()
    if destination == "absolute":
        destination = str(expected_folder)
    options = {"folder_path": folder} if rename is rename_media else {}

    rename(
        [(original, np.zeros(1))], prefix="sorted_", backup=False,
        dry_run=dry_run, mapping_csv_folder=destination, **options,
    )

    mapping = expected_folder / "rename_mapping.csv"
    if dry_run:
        assert original.read_bytes() == b"source media"
        assert not mapping.exists()
        if expected_folder != folder:
            assert not expected_folder.exists()
    else:
        assert (folder / "sorted_1.JPG").read_bytes() == b"source media"
        assert mapping.read_text(encoding="utf-8") == (
            'Original Name,New Name\n"original.JPG","sorted_1.JPG"\n'
        )
        if expected_folder != folder:
            assert not (folder / "rename_mapping.csv").exists()


@pytest.mark.parametrize("rename", [rename_images, rename_media])
@pytest.mark.parametrize("dry_run", [False, True])
@pytest.mark.parametrize("overwrite", [False, True])
def test_mapping_csv_conflicts(tmp_path, rename, dry_run, overwrite):
    folder = tmp_path / "media"
    folder.mkdir()
    original = folder / "original.JPG"
    original.write_bytes(b"source media")
    destination = tmp_path / "Data"
    destination.mkdir()
    existing = {
        "rename_mapping.csv": b"first mapping",
        "rename_mapping_1.csv": b"second mapping",
        "rename_mapping_3.csv": b"later mapping",
    }
    for name, content in existing.items():
        (destination / name).write_bytes(content)
    options = {"folder_path": folder} if rename is rename_media else {}

    rename(
        [(original, np.zeros(1))], prefix="sorted_", backup=False,
        dry_run=dry_run, mapping_csv_folder="{workFolder}/../Data", **options,
        overwrite_mapping_csv=overwrite,
    )

    for name, content in existing.items():
        if dry_run or not overwrite or name != "rename_mapping.csv":
            assert (destination / name).read_bytes() == content
    if dry_run:
        assert {path.name for path in destination.iterdir()} == set(existing)
    else:
        mapping_name = "rename_mapping.csv" if overwrite else "rename_mapping_2.csv"
        assert {path.name for path in destination.iterdir()} == set(existing) | {mapping_name}
        assert (destination / mapping_name).read_text(encoding="utf-8") == (
            'Original Name,New Name\n"original.JPG","sorted_1.JPG"\n'
        )
