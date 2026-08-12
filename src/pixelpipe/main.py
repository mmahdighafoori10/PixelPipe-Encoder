from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from .paths import APP_NAME, resource_path
from .styles import APP_STYLE_SHEET
from .ui import MainWindow


def main() -> int:
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("PixelPipe")
    app.setWindowIcon(QIcon(str(resource_path("assets/app_icon.ico"))))
    app.setStyle("Fusion")
    app.setStyleSheet(APP_STYLE_SHEET)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

