# Changelog

## macOS preview

- Added native Apple Silicon and Intel app/DMG builds on macOS runners.
- Added Finder-compatible FFmpeg discovery and automatic setup via existing Homebrew.
- Added macOS Application Support paths, a native app icon, and platform-specific help.
- Added packaged GUI smoke checks and real encoding checks for both Mac architectures.
- The initial Mac preview uses CPU x264 and is not Apple-notarized.

## 0.1.0 — Initial release

- Added a queue-based Windows desktop interface.
- Added FFprobe metadata detection, including 4K and fractional/VFR frame rates.
- Added source, 2160p, 1080p, and 720p output resolution choices.
- Added source timing, fixed frame-rate, quality, encoder, and audio controls.
- Added NVIDIA NVENC with CPU x264 fallback.
- Added pause, resume, skip, cancel, completion sounds, and verified outputs.
- Added automatic FFmpeg discovery and SHA-256-verified per-user installation.
- Added Windows installer and portable ZIP distributions.
