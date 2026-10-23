# PixelPipe Encoder for macOS (preview)

Choose **arm64** for Apple Silicon (M-series) or **x86_64** for Intel Macs.
The app targets macOS 13 or newer. Homebrew may require a newer macOS version;
see its official system requirements before installing it.

## Install

1. Open the DMG and drag **PixelPipe Encoder.app** into **Applications**.
2. Eject the DMG and open PixelPipe from Applications.
3. If macOS blocks the preview because the developer cannot be verified, follow
   Apple's instructions at https://support.apple.com/102445 and use **System
   Settings > Privacy & Security > Open Anyway** for this app only.

This preview is ad-hoc signed for compatibility, but is **not Developer ID
signed or notarized by Apple**. Do not disable Gatekeeper system-wide. Verify
the DMG against its accompanying SHA-256 file before opening it.

## FFmpeg setup

Python is included in the app; it does not need a separate installation.
FFmpeg and ffprobe are separate tools and are not bundled in the DMG.

PixelPipe detects existing installations, including `/opt/homebrew/bin` on
Apple Silicon and `/usr/local/bin` on Intel, even when launched from Finder.
If neither tool is found, click **Install automatically** to install the
Homebrew `ffmpeg` formula. This requires an existing, working Homebrew
installation and an internet connection. Homebrew's own dependencies and
Command Line Tools requirements still apply.

If Homebrew is missing, use **Get Homebrew** (https://brew.sh), follow its
installation instructions, then try automatic setup again. Alternatively,
install both tools using the providers listed at https://ffmpeg.org/download.html
and select their folder with **Choose existing folder**.

App tools/data use `~/Library/Application Support/PixelPipe Encoder`.
Preferences use macOS's native settings storage. This preview uses CPU x264
encoding; Apple VideoToolbox acceleration is not included yet.

## Build on a Mac

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-build.txt
python -m pytest -q
python tools/build_macos.py
```

The build script creates a native `.app`, a verified compressed DMG with an
Applications shortcut, and a SHA-256 file in `dist/`. Build separately on
Apple Silicon and Intel; the script cannot build a macOS app on Windows.

The **Build macOS DMG** GitHub Actions workflow builds and checks both
architectures and uploads the DMGs as workflow artifacts.
