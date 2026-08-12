from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from pixelpipe.commands import build_ffmpeg_command  # noqa: E402
from pixelpipe.media import probe_media, validate_encoded_media  # noqa: E402
from pixelpipe.models import (  # noqa: E402
    AudioMode,
    EncodeSettings,
    EncoderPreference,
    QualityProfile,
    ResolutionMode,
)


def main() -> int:
    ffmpeg = Path(shutil.which("ffmpeg") or "")
    ffprobe = Path(shutil.which("ffprobe") or "")
    if not ffmpeg.is_file() or not ffprobe.is_file():
        raise RuntimeError("FFmpeg and ffprobe are required for the integration check.")

    fixture_directory = PROJECT_ROOT / ".test-media"
    fixture_directory.mkdir(parents=True, exist_ok=True)
    source_4k = fixture_directory / "source-4k-29.97.mp4"
    source_720 = fixture_directory / "source-720-25.mp4"
    output_1080 = fixture_directory / "output-1080-keep-fps-muted.mp4"
    output_30 = fixture_directory / "output-720-30-fps.mp4"

    create_fixture(
        ffmpeg,
        source_4k,
        size="3840x2160",
        rate="30000/1001",
        with_audio=True,
    )
    create_fixture(
        ffmpeg,
        source_720,
        size="1280x720",
        rate="25",
        with_audio=True,
    )

    source_4k_metadata = probe_media(ffprobe, source_4k)
    keep_fps_settings = EncodeSettings(
        resolution=ResolutionMode.FULL_HD_1080,
        frame_rate=None,
        quality=QualityProfile.SMALL,
        encoder=EncoderPreference.CPU,
        audio=AudioMode.REMOVE,
    )
    run(
        build_ffmpeg_command(
            ffmpeg,
            source_4k,
            output_1080,
            source_4k_metadata,
            keep_fps_settings,
            EncoderPreference.CPU,
        )
    )
    output_1080_metadata = probe_media(ffprobe, output_1080)
    assert not validate_encoded_media(source_4k_metadata, output_1080_metadata, keep_fps_settings)
    assert (output_1080_metadata.width, output_1080_metadata.height) == (1920, 1080)
    assert output_1080_metadata.fps_text == "29.97"
    assert not output_1080_metadata.has_audio

    source_720_metadata = probe_media(ffprobe, source_720)
    fixed_fps_settings = EncodeSettings(
        resolution=ResolutionMode.SOURCE,
        frame_rate=30,
        quality=QualityProfile.SMALL,
        encoder=EncoderPreference.CPU,
        audio=AudioMode.AAC,
    )
    run(
        build_ffmpeg_command(
            ffmpeg,
            source_720,
            output_30,
            source_720_metadata,
            fixed_fps_settings,
            EncoderPreference.CPU,
        )
    )
    output_30_metadata = probe_media(ffprobe, output_30)
    assert not validate_encoded_media(source_720_metadata, output_30_metadata, fixed_fps_settings)
    assert (output_30_metadata.width, output_30_metadata.height) == (1280, 720)
    assert output_30_metadata.fps_text == "30"
    assert output_30_metadata.has_audio

    print("integration-ok")
    print(
        f"4K -> {output_1080_metadata.width}x{output_1080_metadata.height}, "
        f"{output_1080_metadata.fps_text} fps, audio={output_1080_metadata.has_audio}"
    )
    print(
        f"720p -> {output_30_metadata.width}x{output_30_metadata.height}, "
        f"{output_30_metadata.fps_text} fps, audio={output_30_metadata.has_audio}"
    )
    return 0


def create_fixture(
    ffmpeg: Path,
    destination: Path,
    *,
    size: str,
    rate: str,
    with_audio: bool,
) -> None:
    command = [
        str(ffmpeg),
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"testsrc2=size={size}:rate={rate}",
    ]
    if with_audio:
        command.extend(["-f", "lavfi", "-i", "sine=frequency=660:sample_rate=48000"])
    command.extend(
        [
            "-t",
            "1.2",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-crf",
            "35",
            "-pix_fmt",
            "yuv420p",
        ]
    )
    if with_audio:
        command.extend(["-c:a", "aac", "-b:a", "96k", "-shortest"])
    command.append(str(destination))
    run(command)


def run(command: list[str]) -> None:
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"Command failed: {command[0]}")


if __name__ == "__main__":
    raise SystemExit(main())

