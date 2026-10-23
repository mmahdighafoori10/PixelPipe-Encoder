from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import Callable

from .paths import resource_path, tools_directory


FFMPEG_DOWNLOAD_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
FFMPEG_CHECKSUM_URL = f"{FFMPEG_DOWNLOAD_URL}.sha256"
FFMPEG_GUIDE_URL = (
    "https://ffmpeg.org/download.html#build-mac"
    if sys.platform == "darwin"
    else "https://ffmpeg.org/download.html#build-windows"
)
FFMPEG_BUILD_URL = (
    "https://formulae.brew.sh/formula/ffmpeg"
    if sys.platform == "darwin"
    else "https://www.gyan.dev/ffmpeg/builds/"
)
HOMEBREW_GUIDE_URL = "https://brew.sh/"
ProgressCallback = Callable[[int, str], None]


class DependencyError(RuntimeError):
    pass


class InstallationCancelled(DependencyError):
    pass


@dataclass(frozen=True)
class FFmpegInstallation:
    ffmpeg: Path
    ffprobe: Path
    version: str
    source: str


def locate_ffmpeg(custom_path: Path | None = None) -> FFmpegInstallation | None:
    candidates: list[tuple[Path, str]] = []
    if custom_path:
        candidates.extend(_candidate_directories(custom_path, "Selected folder"))

    candidates.extend(
        [
            (resource_path("tools/ffmpeg/bin"), "Bundled with PixelPipe"),
            (tools_directory() / "ffmpeg" / "bin", "Installed by PixelPipe"),
        ]
    )
    ffmpeg_on_path = shutil.which("ffmpeg")
    if ffmpeg_on_path:
        candidates.append((Path(ffmpeg_on_path).resolve().parent, "System PATH"))
    if sys.platform == "darwin":
        # Finder-launched applications do not inherit a terminal's Homebrew PATH.
        candidates.extend(
            (Path(prefix) / "bin", "Homebrew / local installation")
            for prefix in ("/opt/homebrew", "/usr/local", "/opt/local")
        )

    tools_root = tools_directory() / "ffmpeg"
    if tools_root.exists():
        executable = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
        for ffmpeg_file in sorted(tools_root.glob(f"versions/*/bin/{executable}"), reverse=True):
            candidates.append((ffmpeg_file.parent, "Installed by PixelPipe"))

    seen: set[Path] = set()
    for directory, source in candidates:
        directory = directory.resolve()
        if directory in seen:
            continue
        seen.add(directory)
        installation = validate_ffmpeg_directory(directory, source)
        if installation:
            return installation
    return None


def validate_ffmpeg_directory(directory: Path, source: str) -> FFmpegInstallation | None:
    ffmpeg = directory / ("ffmpeg.exe" if os.name == "nt" else "ffmpeg")
    ffprobe = directory / ("ffprobe.exe" if os.name == "nt" else "ffprobe")
    if not ffmpeg.is_file() or not ffprobe.is_file():
        return None
    try:
        version = _read_version(ffmpeg)
        _read_version(ffprobe)
    except (OSError, subprocess.SubprocessError):
        return None
    return FFmpegInstallation(ffmpeg, ffprobe, version, source)


def install_ffmpeg(
    progress: ProgressCallback | None = None,
    cancel_event: Event | None = None,
) -> FFmpegInstallation:
    report = progress or (lambda _percent, _message: None)
    cancel = cancel_event or Event()
    _raise_if_cancelled(cancel)
    if sys.platform == "darwin":
        return _install_macos_ffmpeg(report, cancel)
    if os.name != "nt":
        raise DependencyError("Install FFmpeg with your system package manager, then choose its bin folder.")
    report(1, "Preparing the FFmpeg download...")

    expected_hash = _download_checksum(cancel)
    install_root = tools_directory() / "ffmpeg"
    version_root = install_root / "versions" / expected_hash[:12]
    existing = validate_ffmpeg_directory(version_root / "bin", "Installed by PixelPipe")
    if existing:
        report(100, "FFmpeg is ready.")
        return existing

    install_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="pixelpipe-ffmpeg-", dir=install_root) as temp_name:
        temp_path = Path(temp_name)
        archive_path = temp_path / "ffmpeg.zip"
        extract_path = temp_path / "extracted"
        _download_archive(archive_path, report, cancel)
        report(82, "Verifying the downloaded archive...")
        actual_hash = _sha256(archive_path, cancel)
        if actual_hash.lower() != expected_hash.lower():
            raise DependencyError(
                "FFmpeg download verification failed. The file was not installed."
            )

        report(88, "Extracting FFmpeg...")
        _safe_extract_zip(archive_path, extract_path, cancel)
        ffmpeg_file = next(extract_path.rglob("ffmpeg.exe"), None)
        if not ffmpeg_file:
            raise DependencyError("The FFmpeg archive did not contain ffmpeg.exe.")
        ffprobe_file = ffmpeg_file.parent / "ffprobe.exe"
        if not ffprobe_file.is_file():
            raise DependencyError("The FFmpeg archive did not contain ffprobe.exe.")

        destination_bin = version_root / "bin"
        destination_bin.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ffmpeg_file, destination_bin / "ffmpeg.exe")
        shutil.copy2(ffprobe_file, destination_bin / "ffprobe.exe")
        _copy_license_files(ffmpeg_file.parent.parent, version_root)
        (version_root / "install.json").write_text(
            json.dumps(
                {
                    "download_url": FFMPEG_DOWNLOAD_URL,
                    "sha256": expected_hash,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    installation = validate_ffmpeg_directory(version_root / "bin", "Installed by PixelPipe")
    if not installation:
        raise DependencyError("FFmpeg was installed but could not be started.")
    report(100, "FFmpeg was installed successfully.")
    return installation


def find_homebrew() -> Path | None:
    candidates = [Path("/opt/homebrew/bin/brew"), Path("/usr/local/bin/brew")]
    on_path = shutil.which("brew")
    if on_path:
        candidates.insert(0, Path(on_path))
    return next((path for path in candidates if path.is_file() and os.access(path, os.X_OK)), None)


def _install_macos_ffmpeg(report: ProgressCallback, cancel: Event) -> FFmpegInstallation:
    brew = find_homebrew()
    if brew is None:
        raise DependencyError(
            f"Homebrew was not found. Install Homebrew from {HOMEBREW_GUIDE_URL}, "
            "then click Install automatically again. You can also install FFmpeg and "
            "ffprobe yourself and choose their folder."
        )
    report(5, "Installing FFmpeg with Homebrew. This may take several minutes...")
    environment = os.environ.copy()
    environment.update(HOMEBREW_NO_AUTO_UPDATE="1", HOMEBREW_NO_ENV_HINTS="1")
    # Include Homebrew for child commands when launched from Finder.
    environment["PATH"] = str(brew.parent) + os.pathsep + environment.get("PATH", "")
    with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as log:
        process = subprocess.Popen(
            [str(brew), "install", "ffmpeg"],
            stdout=log,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            env=environment,
            start_new_session=True,
        )
        deadline = time.monotonic() + 1200
        try:
            while process.poll() is None:
                _raise_if_cancelled(cancel)
                if time.monotonic() > deadline:
                    raise DependencyError("Homebrew setup timed out. Check the installation in Terminal.")
                cancel.wait(0.2)
            _raise_if_cancelled(cancel)
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
        if process.returncode:
            log.seek(0)
            details = log.read()[-1500:].strip()
            raise DependencyError(
                "Homebrew could not install FFmpeg. Open Terminal and run 'brew install ffmpeg'. "
                f"See {HOMEBREW_GUIDE_URL} for help.\n{details}"
            )
    report(95, "Checking FFmpeg and ffprobe...")
    installation = validate_ffmpeg_directory(brew.parent, "Installed with Homebrew")
    if installation is None:
        installation = locate_ffmpeg()
    if installation is None:
        raise DependencyError("FFmpeg installation finished, but ffmpeg and ffprobe could not be started.")
    report(100, "FFmpeg is installed and ready.")
    return installation


def _candidate_directories(path: Path, source: str) -> list[tuple[Path, str]]:
    resolved = path.expanduser().resolve()
    if resolved.is_file():
        resolved = resolved.parent
    return [(resolved, source), (resolved / "bin", source)]


def _read_version(executable: Path) -> str:
    result = subprocess.run(
        [str(executable), "-version"],
        capture_output=True,
        text=True,
        timeout=15,
        check=True,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    first_line = result.stdout.splitlines()[0] if result.stdout else executable.name
    return first_line.strip()


def _download_checksum(cancel: Event) -> str:
    _raise_if_cancelled(cancel)
    request = urllib.request.Request(
        FFMPEG_CHECKSUM_URL,
        headers={"User-Agent": "PixelPipe-Encoder/0.1"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = response.read(4096).decode("utf-8", errors="replace")
    except (OSError, urllib.error.URLError) as error:
        raise DependencyError(f"Could not download the FFmpeg checksum: {error}") from error
    match = re.search(r"\b[a-fA-F0-9]{64}\b", payload)
    if not match:
        raise DependencyError("The FFmpeg checksum response was not valid.")
    return match.group(0)


def _download_archive(path: Path, report: ProgressCallback, cancel: Event) -> None:
    request = urllib.request.Request(
        FFMPEG_DOWNLOAD_URL,
        headers={"User-Agent": "PixelPipe-Encoder/0.1"},
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response, path.open("wb") as output:
            total = int(response.headers.get("Content-Length") or 0)
            downloaded = 0
            while True:
                _raise_if_cancelled(cancel)
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                output.write(chunk)
                downloaded += len(chunk)
                if total:
                    percent = 5 + int((downloaded / total) * 75)
                    report(min(percent, 80), "Downloading FFmpeg...")
    except InstallationCancelled:
        raise
    except (OSError, urllib.error.URLError) as error:
        raise DependencyError(f"Could not download FFmpeg: {error}") from error


def _sha256(path: Path, cancel: Event) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            _raise_if_cancelled(cancel)
            digest.update(chunk)
    return digest.hexdigest()


def _safe_extract_zip(archive: Path, destination: Path, cancel: Event) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    destination_root = destination.resolve()
    with zipfile.ZipFile(archive) as package:
        for member in package.infolist():
            _raise_if_cancelled(cancel)
            target = (destination / member.filename).resolve()
            if os.path.commonpath([str(destination_root), str(target)]) != str(destination_root):
                raise DependencyError("The FFmpeg archive contained an unsafe path.")
            package.extract(member, destination)


def _copy_license_files(source_root: Path, destination_root: Path) -> None:
    license_directory = destination_root / "licenses"
    license_directory.mkdir(parents=True, exist_ok=True)
    for pattern in ("LICENSE*", "README*"):
        for source in source_root.glob(pattern):
            if source.is_file():
                shutil.copy2(source, license_directory / source.name)


def _raise_if_cancelled(cancel: Event) -> None:
    if cancel.is_set():
        raise InstallationCancelled("FFmpeg installation was cancelled.")

