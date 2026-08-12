from __future__ import annotations

import json
import math
import os
import subprocess
from fractions import Fraction
from pathlib import Path
from typing import Iterable

from .models import EncodeSettings, ResolutionMode, VideoMetadata


SUPPORTED_EXTENSIONS = frozenset(
    {
        ".mp4",
        ".mov",
        ".avi",
        ".mkv",
        ".wmv",
        ".flv",
        ".webm",
        ".m4v",
        ".3gp",
        ".mpg",
        ".mpeg",
        ".m2v",
        ".ts",
        ".mts",
        ".m2ts",
        ".vob",
        ".asf",
        ".f4v",
        ".ogv",
    }
)


class MediaProbeError(RuntimeError):
    pass


def _creation_flags() -> int:
    return subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def parse_frame_rate(value: str | None) -> float:
    if not value or value in {"0/0", "N/A"}:
        return 0.0
    try:
        return float(Fraction(value))
    except (ValueError, ZeroDivisionError):
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0


def format_frame_rate(value: float) -> str:
    if value <= 0:
        return "Unknown"
    common_rates = {
        23.976: "23.976",
        29.97: "29.97",
        59.94: "59.94",
    }
    for rate, label in common_rates.items():
        if math.isclose(value, rate, abs_tol=0.01):
            return label
    if math.isclose(value, round(value), abs_tol=0.001):
        return str(int(round(value)))
    return f"{value:.3f}".rstrip("0").rstrip(".")


def discover_media(paths: Iterable[Path]) -> list[Path]:
    discovered: set[Path] = set()
    for candidate in paths:
        candidate = candidate.expanduser().resolve()
        if candidate.is_file() and candidate.suffix.lower() in SUPPORTED_EXTENSIONS:
            discovered.add(candidate)
        elif candidate.is_dir():
            for file_path in candidate.rglob("*"):
                if file_path.is_file() and file_path.suffix.lower() in SUPPORTED_EXTENSIONS:
                    discovered.add(file_path.resolve())
    return sorted(discovered, key=lambda path: path.name.lower())


def probe_media(ffprobe_path: Path, media_path: Path, timeout_seconds: int = 30) -> VideoMetadata:
    command = [
        str(ffprobe_path),
        "-v",
        "error",
        "-show_streams",
        "-show_format",
        "-of",
        "json",
        str(media_path),
    ]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
            creationflags=_creation_flags(),
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise MediaProbeError(f"Could not inspect {media_path.name}: {error}") from error

    if result.returncode != 0:
        detail = result.stderr.strip() or "ffprobe returned an unknown error"
        raise MediaProbeError(f"Could not inspect {media_path.name}: {detail}")

    try:
        payload = json.loads(result.stdout)
        streams = payload.get("streams", [])
        video_stream = next(stream for stream in streams if stream.get("codec_type") == "video")
    except (json.JSONDecodeError, StopIteration, TypeError) as error:
        raise MediaProbeError(f"No readable video stream was found in {media_path.name}") from error

    audio_stream = next((stream for stream in streams if stream.get("codec_type") == "audio"), None)
    average_rate = parse_frame_rate(video_stream.get("avg_frame_rate"))
    nominal_rate = parse_frame_rate(video_stream.get("r_frame_rate"))
    selected_rate = average_rate or nominal_rate
    duration = _first_float(video_stream.get("duration"), payload.get("format", {}).get("duration"))
    rotation = _extract_rotation(video_stream)
    variable_rate = bool(average_rate and nominal_rate and not math.isclose(average_rate, nominal_rate, abs_tol=0.02))

    return VideoMetadata(
        path=media_path,
        width=int(video_stream.get("width") or 0),
        height=int(video_stream.get("height") or 0),
        duration_seconds=duration,
        fps=selected_rate,
        fps_text=format_frame_rate(selected_rate),
        video_codec=str(video_stream.get("codec_name") or "unknown"),
        pixel_format=str(video_stream.get("pix_fmt") or "unknown"),
        audio_codec=str(audio_stream.get("codec_name")) if audio_stream else None,
        has_audio=audio_stream is not None,
        rotation=rotation,
        is_variable_frame_rate=variable_rate,
        format_name=str(payload.get("format", {}).get("format_name") or ""),
    )


def validate_encoded_media(
    source: VideoMetadata,
    output: VideoMetadata,
    settings: EncodeSettings,
) -> list[str]:
    errors: list[str] = []
    if output.width <= 0 or output.height <= 0:
        errors.append("The output has invalid dimensions.")
    if output.duration_seconds <= 0:
        errors.append("The output duration is invalid.")
    elif source.duration_seconds > 0:
        allowed_delta = max(1.5, source.duration_seconds * 0.02)
        if abs(output.duration_seconds - source.duration_seconds) > allowed_delta:
            errors.append("The output duration differs too much from the source.")

    if settings.frame_rate and output.fps:
        if not math.isclose(output.fps, settings.frame_rate, abs_tol=0.06):
            errors.append(
                f"Expected {format_frame_rate(settings.frame_rate)} fps, got {output.fps_text} fps."
            )

    target = resolution_bounds(settings.resolution)
    if target:
        max_width, max_height = target
        if output.display_width > max_width + 2 or output.display_height > max_height + 2:
            errors.append("The output exceeds the selected resolution bounds.")
    elif settings.resolution == ResolutionMode.SOURCE:
        if abs(output.display_width - source.display_width) > 2 or abs(output.display_height - source.display_height) > 2:
            errors.append("The source resolution was not preserved.")
    return errors


def resolution_bounds(mode: ResolutionMode) -> tuple[int, int] | None:
    return {
        ResolutionMode.UHD_2160: (3840, 2160),
        ResolutionMode.FULL_HD_1080: (1920, 1080),
        ResolutionMode.HD_720: (1280, 720),
    }.get(mode)


def _first_float(*values: object) -> float:
    for value in values:
        try:
            if value not in {None, "N/A"}:
                return float(value)
        except (TypeError, ValueError):
            continue
    return 0.0


def _extract_rotation(video_stream: dict[str, object]) -> int:
    tags = video_stream.get("tags")
    if isinstance(tags, dict) and "rotate" in tags:
        try:
            return int(float(str(tags["rotate"]))) % 360
        except (TypeError, ValueError):
            pass
    side_data = video_stream.get("side_data_list")
    if isinstance(side_data, list):
        for item in side_data:
            if isinstance(item, dict) and "rotation" in item:
                try:
                    return int(float(str(item["rotation"]))) % 360
                except (TypeError, ValueError):
                    continue
    return 0

