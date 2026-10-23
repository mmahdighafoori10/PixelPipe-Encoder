"""Build the native .app and a drag-to-Applications DMG on macOS."""
from __future__ import annotations

import hashlib
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    if sys.platform != "darwin":
        raise SystemExit("Build this package on macOS, or use the Build macOS DMG GitHub workflow.")
    from PIL import Image

    architecture = platform.machine()
    if architecture not in {"arm64", "x86_64"}:
        raise SystemExit(f"Unsupported Mac architecture: {architecture}")
    with Image.open(PROJECT_ROOT / "assets" / "app_icon.png") as icon:
        icon.save(PROJECT_ROOT / "assets" / "app_icon.icns", format="ICNS")
    subprocess.run(
        [sys.executable, "-m", "PyInstaller", "PixelPipeEncoder.spec", "--noconfirm", "--clean"],
        cwd=PROJECT_ROOT,
        check=True,
    )
    app = PROJECT_ROOT / "dist" / "PixelPipe Encoder.app"
    subprocess.run(["codesign", "--verify", "--deep", "--strict", str(app)], check=True)
    output = PROJECT_ROOT / "dist" / f"PixelPipe-Encoder-macOS-0.1.0-{architecture}.dmg"
    if output.exists():
        raise SystemExit(f"A DMG already exists at {output}; move it before rebuilding.")
    with tempfile.TemporaryDirectory(prefix="pixelpipe-dmg-") as staging:
        stage = Path(staging)
        shutil.copytree(app, stage / app.name, symlinks=True)
        (stage / "Applications").symlink_to("/Applications", target_is_directory=True)
        shutil.copy2(PROJECT_ROOT / "MACOS.md", stage / "Read Me.md")
        subprocess.run(
            ["hdiutil", "create", "-volname", "PixelPipe Encoder", "-srcfolder", str(stage),
             "-format", "UDZO", str(output)],
            check=True,
        )
    subprocess.run(["hdiutil", "verify", str(output)], check=True)
    digest = hashlib.sha256()
    with output.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    output.with_suffix(".dmg.sha256").write_text(
        f"{digest.hexdigest()}  {output.name}\n", encoding="utf-8"
    )
    print(f"DMG ready: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
