from __future__ import annotations

import os
import subprocess
from pathlib import Path

from .media import format_frame_rate, resolution_bounds
from .models import (
    AudioMode,
    EncodeSettings,
    EncoderPreference,
    FFmpegCapabilities,
    QualityProfile,
    ResolutionMode,
    VideoMetadata,
)


MP4_COPY_AUDIO_CODECS = frozenset({"aac", "mp3", "ac3", "eac3", "alac"})


def detect_capabilities(ffmpeg_path: Path) -> FFmpegCapabilities:
    command = [str(ffmpeg_path), "-hide_banner", "-encoders"]
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    encoders: set[str] = set()
    if result.returncode == 0:
        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 2 and len(parts[0]) == 6:
                encoders.add(parts[1])
    return FFmpegCapabilities(frozenset(encoders))


def encoder_attempts(
    preference: EncoderPreference,
    capabilities: FFmpegCapabilities,
) -> list[EncoderPreference]:
    if preference == EncoderPreference.CPU:
        return [EncoderPreference.CPU]
    if preference == EncoderPreference.NVIDIA:
        return [EncoderPreference.NVIDIA]
    if capabilities.has_nvenc:
        return [EncoderPreference.NVIDIA, EncoderPreference.CPU]
    return [EncoderPreference.CPU]


def build_ffmpeg_command(
    ffmpeg_path: Path,
    source: Path,
    output: Path,
    metadata: VideoMetadata,
    settings: EncodeSettings,
    encoder: EncoderPreference,
) -> list[str]:
    command = [
        str(ffmpeg_path),
        "-hide_banner",
        "-y",
        "-loglevel",
        "error",
        "-i",
        str(source),
        "-map",
        "0:v:0",
    ]

    command.extend(_audio_mapping_args(metadata, settings.audio))
    command.extend(["-map_metadata", "0", "-map_chapters", "0"])

    video_filter = build_scale_filter(settings)
    if video_filter:
        command.extend(["-vf", video_filter])

    if settings.frame_rate is None:
        command.extend(["-fps_mode:v", "passthrough"])
    else:
        command.extend(
            [
                "-r:v",
                format_frame_rate(settings.frame_rate),
                "-fps_mode:v",
                "cfr",
            ]
        )

    command.extend(_video_encoder_args(encoder, settings.quality))
    command.extend(_audio_codec_args(metadata, settings.audio))
    command.extend(
        [
            "-movflags",
            "+faststart",
            "-progress",
            "pipe:1",
            "-nostats",
            str(output),
        ]
    )
    return command


def build_scale_filter(settings: EncodeSettings) -> str:
    target = resolution_bounds(settings.resolution)
    if settings.resolution == ResolutionMode.SOURCE or target is None:
        return "scale=trunc(iw/2)*2:trunc(ih/2)*2"

    max_width, max_height = target
    if settings.no_upscale:
        width = f"min(iw\\,{max_width})"
        height = f"min(ih\\,{max_height})"
    else:
        width = str(max_width)
        height = str(max_height)
    return (
        f"scale=w='{width}':h='{height}':"
        "force_original_aspect_ratio=decrease:force_divisible_by=2"
    )


def _video_encoder_args(
    encoder: EncoderPreference,
    quality: QualityProfile,
) -> list[str]:
    if encoder == EncoderPreference.NVIDIA:
        quality_map = {
            QualityProfile.HIGH: ("p6", "19"),
            QualityProfile.BALANCED: ("p5", "23"),
            QualityProfile.SMALL: ("p4", "28"),
        }
        preset, cq = quality_map[quality]
        return [
            "-c:v",
            "h264_nvenc",
            "-preset",
            preset,
            "-tune",
            "hq",
            "-rc",
            "vbr",
            "-cq",
            cq,
            "-b:v",
            "0",
            "-profile:v",
            "high",
            "-pix_fmt",
            "yuv420p",
        ]

    quality_map = {
        QualityProfile.HIGH: ("medium", "18"),
        QualityProfile.BALANCED: ("medium", "22"),
        QualityProfile.SMALL: ("fast", "27"),
    }
    preset, crf = quality_map[quality]
    return [
        "-c:v",
        "libx264",
        "-preset",
        preset,
        "-crf",
        crf,
        "-profile:v",
        "high",
        "-pix_fmt",
        "yuv420p",
    ]


def _audio_mapping_args(metadata: VideoMetadata, mode: AudioMode) -> list[str]:
    if mode == AudioMode.REMOVE or not metadata.has_audio:
        return ["-an"]
    return ["-map", "0:a:0?"]


def _audio_codec_args(metadata: VideoMetadata, mode: AudioMode) -> list[str]:
    if mode == AudioMode.REMOVE or not metadata.has_audio:
        return []
    if mode == AudioMode.KEEP and metadata.audio_codec in MP4_COPY_AUDIO_CODECS:
        return ["-c:a", "copy"]
    return ["-c:a", "aac", "-b:a", "192k"]

