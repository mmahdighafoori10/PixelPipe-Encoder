from __future__ import annotations

import os
import sys
from pathlib import Path


APP_NAME = "PixelPipe Encoder"
APP_SLUG = "PixelPipeEncoder"


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def resource_path(relative_path: str | Path) -> Path:
    bundle_root = Path(getattr(sys, "_MEIPASS", project_root()))
    return bundle_root / Path(relative_path)


def user_data_directory() -> Path:
    override = os.environ.get("PIXELPIPE_DATA_DIR")
    if override:
        path = Path(override).expanduser().resolve()
    else:
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        path = base / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def tools_directory() -> Path:
    path = user_data_directory() / "tools"
    path.mkdir(parents=True, exist_ok=True)
    return path


def logs_directory() -> Path:
    path = user_data_directory() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def unique_output_path(source: Path, output_directory: Path | None) -> Path:
    destination = output_directory or source.parent
    destination.mkdir(parents=True, exist_ok=True)
    candidate = destination / f"{source.stem}_encoded.mp4"
    index = 2
    while candidate.exists():
        candidate = destination / f"{source.stem}_encoded_{index}.mp4"
        index += 1
    return candidate
