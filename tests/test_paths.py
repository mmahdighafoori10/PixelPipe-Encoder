from pathlib import Path
from types import SimpleNamespace

import pixelpipe.paths as paths


def test_macos_uses_application_support(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("PIXELPIPE_DATA_DIR", raising=False)
    monkeypatch.setattr(paths, "sys", SimpleNamespace(platform="darwin"))
    monkeypatch.setattr(paths.Path, "home", lambda: tmp_path)
    expected = tmp_path / "Library" / "Application Support" / paths.APP_NAME
    assert paths.user_data_directory() == expected
    assert expected.is_dir()


def test_explicit_data_directory_overrides_macos_default(monkeypatch, tmp_path: Path) -> None:
    expected = tmp_path / "custom"
    monkeypatch.setenv("PIXELPIPE_DATA_DIR", str(expected))
    monkeypatch.setattr(paths, "sys", SimpleNamespace(platform="darwin"))
    assert paths.user_data_directory() == expected
