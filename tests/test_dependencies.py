from pathlib import Path
from threading import Event
from types import SimpleNamespace
import zipfile

import pytest
import pixelpipe.dependencies as dependencies

from pixelpipe.dependencies import (
    DependencyError,
    InstallationCancelled,
    _raise_if_cancelled,
    _safe_extract_zip,
)


def test_safe_extract_zip_extracts_normal_members(tmp_path: Path) -> None:
    archive = tmp_path / "safe.zip"
    with zipfile.ZipFile(archive, "w") as package:
        package.writestr("ffmpeg/bin/ffmpeg.exe", b"test")

    destination = tmp_path / "out"
    _safe_extract_zip(archive, destination, Event())

    assert (destination / "ffmpeg" / "bin" / "ffmpeg.exe").read_bytes() == b"test"


def test_safe_extract_zip_rejects_path_traversal(tmp_path: Path) -> None:
    archive = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive, "w") as package:
        package.writestr("../outside.exe", b"unsafe")

    with pytest.raises(DependencyError, match="unsafe path"):
        _safe_extract_zip(archive, tmp_path / "out", Event())

    assert not (tmp_path / "outside.exe").exists()


def test_cancelled_dependency_action_stops_immediately() -> None:
    cancel = Event()
    cancel.set()

    with pytest.raises(InstallationCancelled):
        _raise_if_cancelled(cancel)


def test_macos_install_does_not_download_windows_build(monkeypatch) -> None:
    expected = object()
    monkeypatch.setattr(dependencies, "sys", SimpleNamespace(platform="darwin"))
    monkeypatch.setattr(dependencies, "_install_macos_ffmpeg", lambda report, cancel: expected)
    monkeypatch.setattr(
        dependencies, "_download_checksum",
        lambda cancel: pytest.fail("macOS attempted to download a Windows build"),
    )
    assert dependencies.install_ffmpeg() is expected


def test_macos_missing_homebrew_provides_recovery_guide(monkeypatch) -> None:
    monkeypatch.setattr(dependencies, "find_homebrew", lambda: None)
    with pytest.raises(DependencyError, match="https://brew.sh/"):
        dependencies._install_macos_ffmpeg(lambda percent, message: None, Event())


def test_macos_finder_launch_checks_homebrew_without_path(monkeypatch, tmp_path: Path) -> None:
    expected = object()
    monkeypatch.setattr(dependencies, "sys", SimpleNamespace(platform="darwin"))
    monkeypatch.setattr(dependencies, "tools_directory", lambda: tmp_path / "tools")
    monkeypatch.setattr(dependencies, "resource_path", lambda path: tmp_path / path)
    monkeypatch.setattr(dependencies.shutil, "which", lambda executable: None)
    monkeypatch.setattr(
        dependencies, "validate_ffmpeg_directory",
        lambda directory, source: expected if directory == Path("/opt/homebrew/bin").resolve() else None,
    )
    assert dependencies.locate_ffmpeg() is expected


def test_unix_cached_installation_uses_names_without_exe(monkeypatch, tmp_path: Path) -> None:
    binary = tmp_path / "ffmpeg" / "versions" / "abc123" / "bin" / "ffmpeg"
    binary.parent.mkdir(parents=True)
    binary.touch()
    expected = object()
    monkeypatch.setattr(dependencies, "sys", SimpleNamespace(platform="linux"))
    monkeypatch.setattr(dependencies, "os", SimpleNamespace(name="posix"))
    monkeypatch.setattr(dependencies, "tools_directory", lambda: tmp_path)
    monkeypatch.setattr(dependencies, "resource_path", lambda path: tmp_path / "missing" / path)
    monkeypatch.setattr(dependencies.shutil, "which", lambda executable: None)
    monkeypatch.setattr(
        dependencies, "validate_ffmpeg_directory",
        lambda directory, source: expected if directory == binary.parent else None,
    )
    assert dependencies.locate_ffmpeg() is expected
