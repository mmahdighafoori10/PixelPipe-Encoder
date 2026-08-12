from pathlib import Path

from pixelpipe.commands import build_ffmpeg_command, build_scale_filter, encoder_attempts
from pixelpipe.models import (
    AudioMode,
    EncodeSettings,
    EncoderPreference,
    FFmpegCapabilities,
    ResolutionMode,
    VideoMetadata,
)


def metadata(audio_codec: str | None = "aac") -> VideoMetadata:
    return VideoMetadata(
        path=Path("source.mkv"),
        width=3840,
        height=2160,
        duration_seconds=30,
        fps=29.97,
        fps_text="29.97",
        video_codec="hevc",
        pixel_format="yuv420p10le",
        audio_codec=audio_codec,
        has_audio=audio_codec is not None,
    )


def test_keep_source_uses_passthrough_without_forced_rate() -> None:
    command = build_ffmpeg_command(
        Path("ffmpeg.exe"),
        Path("source.mkv"),
        Path("output.mp4"),
        metadata(),
        EncodeSettings(frame_rate=None),
        EncoderPreference.CPU,
    )
    assert "passthrough" in command
    assert "-r:v" not in command


def test_fixed_rate_uses_cfr() -> None:
    command = build_ffmpeg_command(
        Path("ffmpeg.exe"),
        Path("source.mkv"),
        Path("output.mp4"),
        metadata(),
        EncodeSettings(frame_rate=25),
        EncoderPreference.CPU,
    )
    assert command[command.index("-r:v") + 1] == "25"
    assert "cfr" in command


def test_remove_audio_omits_audio_stream() -> None:
    command = build_ffmpeg_command(
        Path("ffmpeg.exe"),
        Path("source.mkv"),
        Path("output.mp4"),
        metadata(),
        EncodeSettings(audio=AudioMode.REMOVE),
        EncoderPreference.CPU,
    )
    assert "-an" in command
    assert "-c:a" not in command


def test_1080p_filter_has_bounds_and_no_upscale() -> None:
    scale = build_scale_filter(
        EncodeSettings(resolution=ResolutionMode.FULL_HD_1080, no_upscale=True)
    )
    assert "min(iw\\,1920)" in scale
    assert "min(ih\\,1080)" in scale
    assert "force_original_aspect_ratio=decrease" in scale


def test_auto_encoder_falls_back_to_cpu() -> None:
    attempts = encoder_attempts(
        EncoderPreference.AUTO,
        FFmpegCapabilities(frozenset({"h264_nvenc", "libx264"})),
    )
    assert attempts == [EncoderPreference.NVIDIA, EncoderPreference.CPU]

