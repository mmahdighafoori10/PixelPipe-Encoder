from pathlib import Path
from threading import Event
import zipfile

import pytest

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
