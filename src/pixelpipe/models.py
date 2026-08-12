from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class ResolutionMode(str, Enum):
    SOURCE = "source"
    UHD_2160 = "2160p"
    FULL_HD_1080 = "1080p"
    HD_720 = "720p"


class QualityProfile(str, Enum):
    HIGH = "high"
    BALANCED = "balanced"
    SMALL = "small"


class EncoderPreference(str, Enum):
    AUTO = "auto"
    NVIDIA = "nvidia"
    CPU = "cpu"


class AudioMode(str, Enum):
    KEEP = "keep"
    AAC = "aac"
    REMOVE = "remove"


class JobStatus(str, Enum):
    PENDING = "Pending"
    ANALYZING = "Analyzing"
    ENCODING = "Encoding"
    PAUSED = "Paused"
    DONE = "Done"
    FAILED = "Failed"
    SKIPPED = "Skipped"
    CANCELLED = "Cancelled"


@dataclass(frozen=True)
class VideoMetadata:
    path: Path
    width: int
    height: int
    duration_seconds: float
    fps: float
    fps_text: str
    video_codec: str
    pixel_format: str
    audio_codec: str | None
    has_audio: bool
    rotation: int = 0
    is_variable_frame_rate: bool = False
    format_name: str = ""

    @property
    def display_width(self) -> int:
        return self.height if abs(self.rotation) % 180 == 90 else self.width

    @property
    def display_height(self) -> int:
        return self.width if abs(self.rotation) % 180 == 90 else self.height

    @property
    def resolution_label(self) -> str:
        long_edge = max(self.display_width, self.display_height)
        short_edge = min(self.display_width, self.display_height)
        if long_edge >= 3800 and short_edge >= 2100:
            return "4K"
        if long_edge >= 2500 and short_edge >= 1400:
            return "1440p"
        if long_edge >= 1900 and short_edge >= 1060:
            return "1080p"
        if long_edge >= 1260 and short_edge >= 700:
            return "720p"
        return f"{self.display_width}x{self.display_height}"


@dataclass(frozen=True)
class EncodeSettings:
    resolution: ResolutionMode = ResolutionMode.SOURCE
    frame_rate: float | None = None
    quality: QualityProfile = QualityProfile.BALANCED
    encoder: EncoderPreference = EncoderPreference.AUTO
    audio: AudioMode = AudioMode.KEEP
    output_directory: Path | None = None
    no_upscale: bool = True
    move_originals: bool = False
    app_sounds: bool = True


@dataclass
class EncodeJob:
    source: Path
    metadata: VideoMetadata | None = None
    status: JobStatus = JobStatus.PENDING
    progress: float = 0.0
    output: Path | None = None
    message: str = ""


@dataclass(frozen=True)
class FFmpegCapabilities:
    encoders: frozenset[str]

    @property
    def has_nvenc(self) -> bool:
        return "h264_nvenc" in self.encoders

