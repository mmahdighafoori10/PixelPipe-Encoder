from pathlib import Path

import pytest

from pixelpipe.media import format_frame_rate, parse_frame_rate
from pixelpipe.models import VideoMetadata


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("30000/1001", 29.97002997),
        ("24000/1001", 23.97602398),
        ("25/1", 25.0),
        ("0/0", 0.0),
    ],
)
def test_parse_frame_rate(raw: str, expected: float) -> None:
    assert parse_frame_rate(raw) == pytest.approx(expected)


def test_format_frame_rate_preserves_common_fractional_rates() -> None:
    assert format_frame_rate(30000 / 1001) == "29.97"
    assert format_frame_rate(60000 / 1001) == "59.94"


def test_resolution_label_detects_4k() -> None:
    metadata = VideoMetadata(
        path=Path("clip.mp4"),
        width=3840,
        height=2160,
        duration_seconds=10,
        fps=60,
        fps_text="60",
        video_codec="h264",
        pixel_format="yuv420p",
        audio_codec="aac",
        has_audio=True,
    )
    assert metadata.resolution_label == "4K"


def test_rotation_swaps_display_dimensions() -> None:
    metadata = VideoMetadata(
        path=Path("phone.mp4"),
        width=1920,
        height=1080,
        duration_seconds=10,
        fps=30,
        fps_text="30",
        video_codec="h264",
        pixel_format="yuv420p",
        audio_codec="aac",
        has_audio=True,
        rotation=90,
    )
    assert (metadata.display_width, metadata.display_height) == (1080, 1920)

