"""A bounded, unattended smoke check for the packaged application."""
from __future__ import annotations

import json
import os
from pathlib import Path

from PySide6.QtWidgets import QApplication

from .dependencies import locate_ffmpeg
from .ui import MainWindow


def run_smoke_test(app: QApplication, window: MainWindow) -> int:
    window.hide()
    app.processEvents()
    installation = locate_ffmpeg()
    screenshot = window.grab()
    result = {
        "ui_loaded": not screenshot.isNull(),
        "ffmpeg_found": installation is not None,
        "ffmpeg_version": installation.version if installation else None,
    }
    destination = os.environ.get("PIXELPIPE_SMOKE_REPORT")
    if destination:
        report_path = Path(destination)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
        screenshot.save(str(report_path.with_suffix(".png")))
    window.close()
    return 0 if all((result["ui_loaded"], result["ffmpeg_found"])) else 1
