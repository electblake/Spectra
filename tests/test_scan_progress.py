from types import SimpleNamespace

from app import main


def test_large_discovery_reports_before_finishing(tmp_path, monkeypatch, capsys):
    entry = SimpleNamespace(name="image.jpg", path=str(tmp_path / "image.jpg"), is_file=lambda: True)

    class Entries:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def __iter__(self):
            for i in range(33000):
                if i == 500:
                    assert "500 entries checked, 500 images found" in capsys.readouterr().out
                yield entry

    monkeypatch.setattr(main.os, "scandir", lambda folder: Entries())
    assert len(main.get_image_files(tmp_path)) == 33000
    output = capsys.readouterr().out
    assert "33000 entries checked, 33000 images found" in output
    assert "Scanning image files 1/1" in output
