from __future__ import annotations

import os
import platform
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import (
    QColor,
    QCloseEvent,
    QDesktopServices,
    QDragEnterEvent,
    QDropEvent,
    QIcon,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPixmap,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QStatusBar,
    QSystemTrayIcon,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .dependencies import (
    FFMPEG_BUILD_URL,
    FFMPEG_GUIDE_URL,
    FFmpegInstallation,
    locate_ffmpeg,
)
from .media import SUPPORTED_EXTENSIONS, discover_media
from .models import (
    AudioMode,
    EncodeJob,
    EncodeSettings,
    EncoderPreference,
    JobStatus,
    QualityProfile,
    ResolutionMode,
    VideoMetadata,
)
from .paths import APP_NAME, resource_path
from .styles import APP_STYLE_SHEET
from .workers import DependencyInstallThread, EncoderThread, ProbeThread


STATUS_COLORS = {
    JobStatus.PENDING.value: QColor("#9FB3C8"),
    JobStatus.ANALYZING.value: QColor("#67C8FF"),
    JobStatus.ENCODING.value: QColor("#F6C75C"),
    JobStatus.PAUSED.value: QColor("#F6C75C"),
    JobStatus.DONE.value: QColor("#72E3B1"),
    JobStatus.FAILED.value: QColor("#FF9D8D"),
    JobStatus.SKIPPED.value: QColor("#B8A6E8"),
    JobStatus.CANCELLED.value: QColor("#9AABBD"),
}


class HeroBanner(QFrame):
    dependency_clicked = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setMinimumHeight(172)
        self.setMaximumHeight(172)
        self._background = QPixmap(str(resource_path("assets/splash.png")))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 20, 28, 20)
        layout.setSpacing(4)

        top_row = QHBoxLayout()
        brand = QLabel("PIXELPIPE ENCODER")
        brand.setStyleSheet("color:#65CAFF; font-weight:750; letter-spacing:1.5px;")
        top_row.addWidget(brand)
        top_row.addStretch()
        self._dependency_status = QLabel("Checking FFmpeg...")
        self._dependency_status.setObjectName("statusMissing")
        top_row.addWidget(self._dependency_status)
        self._dependency_button = QToolButton()
        self._dependency_button.setText("Manage")
        self._dependency_button.setToolTip("Manage FFmpeg installation")
        self._dependency_button.clicked.connect(self.dependency_clicked)
        top_row.addWidget(self._dependency_button)
        layout.addLayout(top_row)

        layout.addStretch()
        title = QLabel("Make encoding feel effortless.")
        title.setObjectName("titleLabel")
        layout.addWidget(title)
        subtitle = QLabel("Drop a queue, choose the result, and let the pipeline handle the boring part.")
        subtitle.setObjectName("mutedLabel")
        subtitle.setStyleSheet("font-size:11pt; color:#B9CDE3;")
        layout.addWidget(subtitle)
        layout.addStretch()

    def set_dependency(self, installation: FFmpegInstallation | None) -> None:
        if installation:
            self._dependency_status.setText("● FFmpeg ready")
            self._dependency_status.setObjectName("statusReady")
            self._dependency_status.setToolTip(installation.version)
        else:
            self._dependency_status.setText("● FFmpeg required")
            self._dependency_status.setObjectName("statusMissing")
            self._dependency_status.setToolTip("FFmpeg and ffprobe were not found")
        self._dependency_status.style().unpolish(self._dependency_status)
        self._dependency_status.style().polish(self._dependency_status)

    def paintEvent(self, event: object) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        clip_path = QPainterPath()
        clip_path.addRoundedRect(self.rect(), 16, 16)
        painter.setClipPath(clip_path)

        if not self._background.isNull():
            scaled = self._background.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = max((scaled.width() - self.width()) // 2, 0)
            y = max((scaled.height() - self.height()) // 2, 0)
            painter.drawPixmap(self.rect(), scaled, scaled.rect().adjusted(x, y, -x, -y))

        gradient = QLinearGradient(0, 0, self.width(), 0)
        gradient.setColorAt(0.0, QColor(4, 16, 35, 245))
        gradient.setColorAt(0.58, QColor(4, 16, 35, 215))
        gradient.setColorAt(1.0, QColor(4, 16, 35, 75))
        painter.fillRect(self.rect(), gradient)
        painter.end()
        super().paintEvent(event)  # type: ignore[arg-type]


class DropArea(QFrame):
    clicked = Signal()
    paths_dropped = Signal(list)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("dropArea")
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(8)
        icon = QLabel("＋")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet("font-size:38pt; color:#35B9FF; font-weight:300;")
        layout.addWidget(icon)
        title = QLabel("Drop videos or folders here")
        title.setObjectName("sectionTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        subtitle = QLabel("MP4, MKV, MOV, WebM, MTS and more · or click to browse")
        subtitle.setObjectName("mutedLabel")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

    def mousePressEvent(self, event: object) -> None:
        self.clicked.emit()
        super().mousePressEvent(event)  # type: ignore[arg-type]

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        paths = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
        if paths:
            self.paths_dropped.emit(paths)
            event.acceptProposedAction()


class DropTable(QTableWidget):
    paths_dropped = Signal(list)

    def __init__(self) -> None:
        super().__init__(0, 8)
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DropOnly)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.verticalHeader().setVisible(False)
        self.setHorizontalHeaderLabels(
            ["File", "Size", "Resolution", "FPS", "Duration", "Video", "Audio", "Status"]
        )
        header = self.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, 8):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        if event.mimeData().hasUrls():
            paths = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
            if paths:
                self.paths_dropped.emit(paths)
                event.acceptProposedAction()
                return
        super().dropEvent(event)


class SettingsPanel(QScrollArea):
    def __init__(self, settings: QSettings) -> None:
        super().__init__()
        self._settings = settings
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        content.setObjectName("settingsContent")
        self.setWidget(content)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 4, 0)
        layout.setSpacing(10)

        output_group = QGroupBox("OUTPUT")
        output_form = QFormLayout(output_group)
        output_form.setVerticalSpacing(10)

        self.resolution_combo = QComboBox()
        self.resolution_combo.addItem("Keep source", ResolutionMode.SOURCE.value)
        self.resolution_combo.addItem("4K / 2160p", ResolutionMode.UHD_2160.value)
        self.resolution_combo.addItem("1080p", ResolutionMode.FULL_HD_1080.value)
        self.resolution_combo.addItem("720p", ResolutionMode.HD_720.value)
        output_form.addRow("Resolution", self.resolution_combo)

        self.fps_combo = QComboBox()
        self.fps_combo.setEditable(True)
        self.fps_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.fps_combo.addItem("Keep source timing", None)
        for label, value in (
            ("23.976", 23.976),
            ("24", 24.0),
            ("25", 25.0),
            ("29.97", 29.97),
            ("30", 30.0),
            ("50", 50.0),
            ("59.94", 59.94),
            ("60", 60.0),
        ):
            self.fps_combo.addItem(label, value)
        self.fps_combo.setToolTip("Choose a preset or type a custom frame rate")
        output_form.addRow("Frame rate", self.fps_combo)

        self.quality_combo = QComboBox()
        self.quality_combo.addItem("High quality", QualityProfile.HIGH.value)
        self.quality_combo.addItem("Balanced", QualityProfile.BALANCED.value)
        self.quality_combo.addItem("Smaller file", QualityProfile.SMALL.value)
        self.quality_combo.setCurrentIndex(1)
        output_form.addRow("Quality", self.quality_combo)

        self.encoder_combo = QComboBox()
        self.encoder_combo.addItem("Auto · GPU then CPU", EncoderPreference.AUTO.value)
        self.encoder_combo.addItem("NVIDIA NVENC", EncoderPreference.NVIDIA.value)
        self.encoder_combo.addItem("CPU · x264", EncoderPreference.CPU.value)
        output_form.addRow("Encoder", self.encoder_combo)
        layout.addWidget(output_group)

        audio_group = QGroupBox("AUDIO")
        audio_layout = QVBoxLayout(audio_group)
        self.audio_combo = QComboBox()
        self.audio_combo.addItem("Keep audio when compatible", AudioMode.KEEP.value)
        self.audio_combo.addItem("Convert audio to AAC", AudioMode.AAC.value)
        self.audio_combo.addItem("Remove audio · mute output", AudioMode.REMOVE.value)
        audio_layout.addWidget(self.audio_combo)
        audio_hint = QLabel("Removing audio skips the track entirely and encodes faster.")
        audio_hint.setWordWrap(True)
        audio_hint.setObjectName("mutedLabel")
        audio_layout.addWidget(audio_hint)
        layout.addWidget(audio_group)

        files_group = QGroupBox("FILES")
        files_layout = QVBoxLayout(files_group)
        output_row = QHBoxLayout()
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("Same folder as each source")
        self.output_edit.setReadOnly(True)
        output_row.addWidget(self.output_edit)
        browse_output = QToolButton()
        browse_output.setText("…")
        browse_output.setToolTip("Choose output folder")
        browse_output.clicked.connect(self._browse_output)
        output_row.addWidget(browse_output)
        files_layout.addLayout(output_row)
        self.no_upscale_check = QCheckBox("Never upscale smaller videos")
        self.no_upscale_check.setChecked(True)
        files_layout.addWidget(self.no_upscale_check)
        self.move_originals_check = QCheckBox("Move originals after verified output")
        self.move_originals_check.setToolTip("Moves sources into an old_files folder only after verification")
        files_layout.addWidget(self.move_originals_check)
        layout.addWidget(files_group)

        experience_group = QGroupBox("EXPERIENCE")
        experience_layout = QVBoxLayout(experience_group)
        self.app_sounds_check = QCheckBox("Completion sound")
        self.app_sounds_check.setChecked(True)
        self.app_sounds_check.setToolTip("Mute this to keep PixelPipe completely quiet")
        experience_layout.addWidget(self.app_sounds_check)
        layout.addWidget(experience_group)
        layout.addStretch()
        self._load()

    def collect(self) -> EncodeSettings:
        fps: float | None
        if self.fps_combo.currentIndex() == 0:
            fps = None
        else:
            data = self.fps_combo.currentData()
            try:
                fps = float(data if data is not None else self.fps_combo.currentText().strip())
            except (TypeError, ValueError) as error:
                raise ValueError("Frame rate must be a number such as 25, 29.97, or 60.") from error
            if not 1 <= fps <= 240:
                raise ValueError("Frame rate must be between 1 and 240 fps.")

        output_text = self.output_edit.text().strip()
        return EncodeSettings(
            resolution=ResolutionMode(self.resolution_combo.currentData()),
            frame_rate=fps,
            quality=QualityProfile(self.quality_combo.currentData()),
            encoder=EncoderPreference(self.encoder_combo.currentData()),
            audio=AudioMode(self.audio_combo.currentData()),
            output_directory=Path(output_text) if output_text else None,
            no_upscale=self.no_upscale_check.isChecked(),
            move_originals=self.move_originals_check.isChecked(),
            app_sounds=self.app_sounds_check.isChecked(),
        )

    def save(self) -> None:
        self._settings.setValue("resolution", self.resolution_combo.currentData())
        self._settings.setValue("fps_index", self.fps_combo.currentIndex())
        self._settings.setValue("quality", self.quality_combo.currentData())
        self._settings.setValue("encoder", self.encoder_combo.currentData())
        self._settings.setValue("audio", self.audio_combo.currentData())
        self._settings.setValue("output_directory", self.output_edit.text())
        self._settings.setValue("no_upscale", self.no_upscale_check.isChecked())
        self._settings.setValue("move_originals", self.move_originals_check.isChecked())
        self._settings.setValue("app_sounds", self.app_sounds_check.isChecked())

    def _load(self) -> None:
        _select_data(
            self.resolution_combo,
            _safe_enum(ResolutionMode, self._settings.value("resolution", "source"), ResolutionMode.SOURCE),
        )
        self.fps_combo.setCurrentIndex(int(self._settings.value("fps_index", 0)))
        _select_data(
            self.quality_combo,
            _safe_enum(QualityProfile, self._settings.value("quality", "balanced"), QualityProfile.BALANCED),
        )
        _select_data(
            self.encoder_combo,
            _safe_enum(EncoderPreference, self._settings.value("encoder", "auto"), EncoderPreference.AUTO),
        )
        _select_data(
            self.audio_combo,
            _safe_enum(AudioMode, self._settings.value("audio", "keep"), AudioMode.KEEP),
        )
        self.output_edit.setText(str(self._settings.value("output_directory", "")))
        self.no_upscale_check.setChecked(_as_bool(self._settings.value("no_upscale", True)))
        self.move_originals_check.setChecked(_as_bool(self._settings.value("move_originals", False)))
        self.app_sounds_check.setChecked(_as_bool(self._settings.value("app_sounds", True)))

    def _browse_output(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self,
            "Choose output folder",
            self.output_edit.text() or str(Path.home()),
        )
        if directory:
            self.output_edit.setText(directory)


class FFmpegDialog(QDialog):
    def __init__(
        self,
        existing: FFmpegInstallation | None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.installation = existing
        self._install_thread: DependencyInstallThread | None = None
        self.setWindowTitle("FFmpeg setup")
        self.setMinimumWidth(560)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        title = QLabel("FFmpeg is the engine behind PixelPipe")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)
        self.description = QLabel()
        self.description.setWordWrap(True)
        self.description.setObjectName("mutedLabel")
        layout.addWidget(self.description)
        self._update_description()

        self.message_label = QLabel("")
        self.message_label.setWordWrap(True)
        self.message_label.hide()
        layout.addWidget(self.message_label)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)

        primary_row = QHBoxLayout()
        self.install_button = QPushButton("Install automatically" if not existing else "Update automatically")
        self.install_button.setObjectName("primaryButton")
        self.install_button.clicked.connect(self._install_automatically)
        primary_row.addWidget(self.install_button)
        self.choose_button = QPushButton("Choose existing folder")
        self.choose_button.clicked.connect(self._choose_existing)
        primary_row.addWidget(self.choose_button)
        layout.addLayout(primary_row)

        links_row = QHBoxLayout()
        guide_button = QPushButton("Open official guide")
        guide_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(FFMPEG_GUIDE_URL)))
        links_row.addWidget(guide_button)
        builds_button = QPushButton("Open Windows builds")
        builds_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(FFMPEG_BUILD_URL)))
        links_row.addWidget(builds_button)
        diagnostics_button = QPushButton("Copy diagnostics")
        diagnostics_button.clicked.connect(self._copy_diagnostics)
        links_row.addWidget(diagnostics_button)
        layout.addLayout(links_row)

        footer = QHBoxLayout()
        footer.addStretch()
        close_button = QPushButton("Continue" if existing else "Close")
        close_button.clicked.connect(self.accept if existing else self.reject)
        footer.addWidget(close_button)
        layout.addLayout(footer)

    def reject(self) -> None:
        if self._install_thread and self._install_thread.isRunning():
            self._install_thread.cancel()
        super().reject()

    def _update_description(self) -> None:
        if self.installation:
            self.description.setText(
                f"Ready via {self.installation.source}.\n{self.installation.version}"
            )
        else:
            self.description.setText(
                "FFmpeg and ffprobe were not found. PixelPipe can download a verified Windows build "
                "into your local app-data folder. Administrator access is not required and the system PATH is not changed."
            )

    def _install_automatically(self) -> None:
        self.install_button.setEnabled(False)
        self.choose_button.setEnabled(False)
        self.progress_bar.setValue(0)
        self.progress_bar.show()
        self.message_label.setText("Starting secure download...")
        self.message_label.setStyleSheet("color:#9CC9E8;")
        self.message_label.show()
        self._install_thread = DependencyInstallThread()
        self._install_thread.progress_changed.connect(self._on_progress)
        self._install_thread.installed.connect(self._on_installed)
        self._install_thread.failed.connect(self._on_install_failed)
        self._install_thread.start()

    def _choose_existing(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Choose the folder containing ffmpeg.exe")
        if not directory:
            return
        installation = locate_ffmpeg(Path(directory))
        if not installation:
            self._show_error(
                "That folder does not contain a working ffmpeg.exe and ffprobe.exe. "
                "Choose the bin folder that contains both files."
            )
            return
        self.installation = installation
        self.accept()

    def _on_progress(self, percent: int, message: str) -> None:
        self.progress_bar.setValue(percent)
        self.message_label.setText(message)

    def _on_installed(self, installation: FFmpegInstallation) -> None:
        self.installation = installation
        self.progress_bar.setValue(100)
        self.message_label.setText("FFmpeg installed and verified successfully.")
        QTimer.singleShot(450, self.accept)

    def _on_install_failed(self, message: str) -> None:
        self.install_button.setEnabled(True)
        self.choose_button.setEnabled(True)
        self._show_error(
            f"Automatic setup could not finish.\n\n{message}\n\n"
            "Use 'Open official guide' or select an existing FFmpeg bin folder."
        )

    def _show_error(self, message: str) -> None:
        self.message_label.setText(message)
        self.message_label.setStyleSheet("color:#FF9D8D;")
        self.message_label.show()

    def _copy_diagnostics(self) -> None:
        diagnostics = (
            f"{APP_NAME} FFmpeg diagnostics\n"
            f"OS: {platform.platform()}\n"
            f"Architecture: {platform.machine()}\n"
            f"FFmpeg detected: {'yes' if self.installation else 'no'}\n"
            f"Source: {self.installation.source if self.installation else 'none'}\n"
            f"Version: {self.installation.version if self.installation else 'unknown'}"
        )
        QApplication.clipboard().setText(diagnostics)
        self.message_label.setText("Diagnostics copied to the clipboard.")
        self.message_label.setStyleSheet("color:#72E3B1;")
        self.message_label.show()


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(QIcon(str(resource_path("assets/app_icon.ico"))))
        self.resize(1240, 790)
        self.setMinimumSize(980, 680)
        self.setStyleSheet(APP_STYLE_SHEET)

        self.settings = QSettings("PixelPipe", APP_NAME)
        self.installation: FFmpegInstallation | None = None
        self.jobs: list[EncodeJob] = []
        self._active_rows: list[int] = []
        self._probe_thread: ProbeThread | None = None
        self._encoder_thread: EncoderThread | None = None

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(18, 18, 18, 12)
        root.setSpacing(14)

        self.hero = HeroBanner()
        self.hero.dependency_clicked.connect(self.show_dependency_dialog)
        root.addWidget(self.hero)

        body = QHBoxLayout()
        body.setSpacing(14)
        body.addWidget(self._build_queue_panel(), 3)
        self.settings_panel = SettingsPanel(self.settings)
        self.settings_panel.setMinimumWidth(315)
        self.settings_panel.setMaximumWidth(360)
        body.addWidget(self.settings_panel, 1)
        root.addLayout(body, 1)
        root.addWidget(self._build_control_bar())

        status_bar = QStatusBar()
        self.setStatusBar(status_bar)
        status_bar.showMessage("Ready. Add videos to begin.")

        self._tray = QSystemTrayIcon(self.windowIcon(), self)
        self._tray.setToolTip(APP_NAME)
        self._tray.show()
        self._set_busy(False)
        QTimer.singleShot(250, self._initial_dependency_check)

    def _build_queue_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("surface")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel("Encode queue")
        title.setObjectName("sectionTitle")
        header.addWidget(title)
        header.addStretch()
        self.add_files_button = QPushButton("＋ Add videos")
        self.add_files_button.clicked.connect(self.add_files)
        header.addWidget(self.add_files_button)
        self.add_folder_button = QPushButton("Add folder")
        self.add_folder_button.clicked.connect(self.add_folder)
        header.addWidget(self.add_folder_button)
        self.remove_button = QPushButton("Remove")
        self.remove_button.clicked.connect(self.remove_selected)
        header.addWidget(self.remove_button)
        layout.addLayout(header)

        self.queue_stack = QStackedWidget()
        self.drop_area = DropArea()
        self.drop_area.clicked.connect(self.add_files)
        self.drop_area.paths_dropped.connect(self.add_paths)
        self.table = DropTable()
        self.table.paths_dropped.connect(self.add_paths)
        self.queue_stack.addWidget(self.drop_area)
        self.queue_stack.addWidget(self.table)
        layout.addWidget(self.queue_stack, 1)
        return panel

    def _build_control_bar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("surface")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(8)
        self.overall_progress = QProgressBar()
        self.overall_progress.setRange(0, 100)
        self.overall_progress.setValue(0)
        self.overall_progress.setMinimumWidth(220)
        layout.addWidget(self.overall_progress, 1)
        self.open_output_button = QPushButton("Open output")
        self.open_output_button.clicked.connect(self.open_output_folder)
        layout.addWidget(self.open_output_button)
        self.pause_button = QPushButton("⏸ Pause")
        self.pause_button.clicked.connect(self.toggle_pause)
        layout.addWidget(self.pause_button)
        self.skip_button = QPushButton("⏭ Skip current")
        self.skip_button.setToolTip("Stop this file and continue with the next one")
        self.skip_button.clicked.connect(self.skip_current)
        layout.addWidget(self.skip_button)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setObjectName("dangerButton")
        self.cancel_button.clicked.connect(self.cancel_encoding)
        layout.addWidget(self.cancel_button)
        self.start_button = QPushButton("▶ Start encoding")
        self.start_button.setObjectName("primaryButton")
        self.start_button.clicked.connect(self.start_encoding)
        layout.addWidget(self.start_button)
        return bar

    def _initial_dependency_check(self) -> None:
        stored_path = str(self.settings.value("ffmpeg_directory", ""))
        custom_path = Path(stored_path) if stored_path else None
        try:
            self._apply_installation(locate_ffmpeg(custom_path))
        except OSError as error:
            self._apply_installation(None)
            QMessageBox.critical(
                self,
                "PixelPipe data folder",
                "PixelPipe could not access its local data folder.\n\n"
                f"{error}\n\nCheck folder permissions and try again.",
            )
        if not self.installation:
            self.show_dependency_dialog()

    def show_dependency_dialog(self) -> None:
        dialog = FFmpegDialog(self.installation, self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.installation:
            self._apply_installation(dialog.installation)

    def _apply_installation(self, installation: FFmpegInstallation | None) -> None:
        self.installation = installation
        self.hero.set_dependency(installation)
        if installation:
            self.settings.setValue("ffmpeg_directory", str(installation.ffmpeg.parent))
            self.statusBar().showMessage(f"FFmpeg ready via {installation.source}", 5000)
        else:
            self.statusBar().showMessage("FFmpeg is required before files can be analyzed or encoded.")
        self._update_controls()

    def add_files(self) -> None:
        extensions = " ".join(f"*{suffix}" for suffix in sorted(SUPPORTED_EXTENSIONS))
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Choose videos",
            str(Path.home()),
            f"Video files ({extensions});;All files (*.*)",
        )
        if paths:
            self.add_paths(paths)

    def add_folder(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Choose a folder", str(Path.home()))
        if directory:
            self.add_paths([directory])

    def add_paths(self, raw_paths: list[str]) -> None:
        if not self.installation:
            self.show_dependency_dialog()
            if not self.installation:
                return
        if self._probe_thread and self._probe_thread.isRunning():
            QMessageBox.information(self, APP_NAME, "Please wait for the current files to finish analyzing.")
            return

        discovered = discover_media(Path(raw_path) for raw_path in raw_paths)
        existing = {job.source for job in self.jobs}
        new_paths = [path for path in discovered if path not in existing]
        if not new_paths:
            QMessageBox.information(self, APP_NAME, "No new supported video files were found.")
            return

        for path in new_paths:
            job = EncodeJob(source=path, status=JobStatus.ANALYZING)
            self.jobs.append(job)
            self._append_job_row(job)
        self.queue_stack.setCurrentWidget(self.table)
        self._update_controls()
        self.statusBar().showMessage(f"Analyzing {len(new_paths)} file(s)...")
        self._probe_thread = ProbeThread(self.installation.ffprobe, new_paths)
        self._probe_thread.probed.connect(self._on_probed)
        self._probe_thread.failed.connect(self._on_probe_failed)
        self._probe_thread.finished.connect(self._on_probe_finished)
        self._probe_thread.start()

    def _append_job_row(self, job: EncodeJob) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        size = job.source.stat().st_size if job.source.exists() else 0
        values = [job.source.name, _human_size(size), "…", "…", "…", "…", "…", job.status.value]
        for column, value in enumerate(values):
            item = QTableWidgetItem(value)
            if column == 0:
                item.setToolTip(str(job.source))
            self.table.setItem(row, column, item)
        self._paint_status(row, job.status.value)

    def _on_probed(self, path_text: str, metadata: VideoMetadata) -> None:
        row = self._row_for_path(Path(path_text))
        if row is None:
            return
        job = self.jobs[row]
        job.metadata = metadata
        job.status = JobStatus.PENDING
        self.table.item(row, 2).setText(f"{metadata.resolution_label} · {metadata.display_width}×{metadata.display_height}")
        fps_suffix = " VFR" if metadata.is_variable_frame_rate else ""
        self.table.item(row, 3).setText(f"{metadata.fps_text}{fps_suffix}")
        self.table.item(row, 4).setText(_duration_text(metadata.duration_seconds))
        self.table.item(row, 5).setText(metadata.video_codec.upper())
        self.table.item(row, 6).setText(metadata.audio_codec.upper() if metadata.audio_codec else "No audio")
        self._set_table_status(row, JobStatus.PENDING.value, "Ready")

    def _on_probe_failed(self, path_text: str, message: str) -> None:
        row = self._row_for_path(Path(path_text))
        if row is None:
            return
        self.jobs[row].status = JobStatus.FAILED
        self.jobs[row].message = message
        self._set_table_status(row, JobStatus.FAILED.value, message)

    def _on_probe_finished(self) -> None:
        ready = sum(1 for job in self.jobs if job.metadata)
        self.statusBar().showMessage(f"{ready} file(s) ready.")
        self._update_controls()

    def remove_selected(self) -> None:
        rows = sorted({index.row() for index in self.table.selectionModel().selectedRows()}, reverse=True)
        for row in rows:
            self.table.removeRow(row)
            self.jobs.pop(row)
        if not self.jobs:
            self.queue_stack.setCurrentWidget(self.drop_area)
        self._update_controls()

    def start_encoding(self) -> None:
        if not self.installation:
            self.show_dependency_dialog()
            if not self.installation:
                return
        if self._probe_thread and self._probe_thread.isRunning():
            QMessageBox.information(self, APP_NAME, "Please wait until file analysis finishes.")
            return
        eligible = [
            (index, job)
            for index, job in enumerate(self.jobs)
            if job.metadata and job.status not in {JobStatus.ENCODING, JobStatus.DONE}
        ]
        if not eligible:
            QMessageBox.information(self, APP_NAME, "Add a video or remove completed items before starting.")
            return
        try:
            encode_settings = self.settings_panel.collect()
        except ValueError as error:
            QMessageBox.warning(self, "Check settings", str(error))
            return

        if encode_settings.output_directory:
            try:
                encode_settings.output_directory.mkdir(parents=True, exist_ok=True)
            except OSError as error:
                QMessageBox.critical(self, "Output folder", f"Could not use the output folder:\n{error}")
                return

        self.settings_panel.save()
        self._active_rows = [index for index, _job in eligible]
        active_jobs = [job for _index, job in eligible]
        for row in self._active_rows:
            self.jobs[row].status = JobStatus.PENDING
            self._set_table_status(row, JobStatus.PENDING.value, "Queued")
        self.overall_progress.setValue(0)
        self._encoder_thread = EncoderThread(self.installation, active_jobs, encode_settings)
        self._encoder_thread.job_status_changed.connect(self._on_job_status)
        self._encoder_thread.job_progress_changed.connect(self._on_job_progress)
        self._encoder_thread.overall_progress_changed.connect(
            lambda value: self.overall_progress.setValue(round(value))
        )
        self._encoder_thread.log_message.connect(lambda message: self.statusBar().showMessage(message, 8000))
        self._encoder_thread.pause_changed.connect(self._on_pause_changed)
        self._encoder_thread.queue_finished.connect(self._on_queue_finished)
        self._set_busy(True)
        self.statusBar().showMessage("Encoding started.")
        self._encoder_thread.start()

    def _on_job_status(self, worker_index: int, status: str, message: str) -> None:
        if worker_index >= len(self._active_rows):
            return
        row = self._active_rows[worker_index]
        self._set_table_status(row, status, message)

    def _on_job_progress(self, worker_index: int, progress: float) -> None:
        if worker_index >= len(self._active_rows):
            return
        row = self._active_rows[worker_index]
        self.table.item(row, 7).setText(f"Encoding {progress:.0f}%")
        self._paint_status(row, JobStatus.ENCODING.value)

    def _on_pause_changed(self, paused: bool) -> None:
        self.pause_button.setText("▶ Resume" if paused else "⏸ Pause")
        self.statusBar().showMessage("Encoding paused." if paused else "Encoding resumed.")

    def _on_queue_finished(self, success: bool, message: str) -> None:
        self._set_busy(False)
        self.pause_button.setText("⏸ Pause")
        self.statusBar().showMessage(message)
        if self.settings_panel.app_sounds_check.isChecked():
            _play_completion_sound(success)
        if QSystemTrayIcon.isSystemTrayAvailable():
            self._tray.showMessage(
                "PixelPipe finished" if success else "PixelPipe stopped",
                message,
                QSystemTrayIcon.MessageIcon.Information if success else QSystemTrayIcon.MessageIcon.Warning,
                7000,
            )

    def toggle_pause(self) -> None:
        if self._encoder_thread:
            self._encoder_thread.toggle_pause()

    def skip_current(self) -> None:
        if self._encoder_thread and self._encoder_thread.isRunning():
            self._encoder_thread.skip_current()
            self.statusBar().showMessage("Skipping the current file...")

    def cancel_encoding(self) -> None:
        if not self._encoder_thread or not self._encoder_thread.isRunning():
            return
        answer = QMessageBox.question(
            self,
            "Cancel encoding?",
            "The current partial output will be removed. Completed files will be kept.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._encoder_thread.request_cancel()

    def open_output_folder(self) -> None:
        output_text = self.settings_panel.output_edit.text().strip()
        if output_text:
            destination = Path(output_text)
        else:
            completed = next((job.output for job in reversed(self.jobs) if job.output), None)
            destination = completed.parent if completed else (self.jobs[0].source.parent if self.jobs else Path.home())
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(destination)))

    def closeEvent(self, event: QCloseEvent) -> None:
        self.settings_panel.save()
        if self._encoder_thread and self._encoder_thread.isRunning():
            answer = QMessageBox.question(
                self,
                "Exit PixelPipe?",
                "Encoding is still running. Exit and cancel the queue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self._encoder_thread.request_cancel()
            self._encoder_thread.wait(4000)
        if self._probe_thread and self._probe_thread.isRunning():
            self._probe_thread.requestInterruption()
            self._probe_thread.wait(1500)
        self._tray.hide()
        event.accept()

    def _set_busy(self, busy: bool) -> None:
        for widget in (
            self.add_files_button,
            self.add_folder_button,
            self.remove_button,
            self.settings_panel,
            self.start_button,
        ):
            widget.setEnabled(not busy)
        self.pause_button.setEnabled(busy)
        self.skip_button.setEnabled(busy)
        self.cancel_button.setEnabled(busy)
        self.open_output_button.setEnabled(bool(self.jobs))

    def _update_controls(self) -> None:
        busy = bool(self._encoder_thread and self._encoder_thread.isRunning())
        if busy:
            return
        has_ready = any(job.metadata and job.status != JobStatus.DONE for job in self.jobs)
        self.start_button.setEnabled(bool(self.installation and has_ready))
        self.remove_button.setEnabled(bool(self.jobs))
        self.open_output_button.setEnabled(bool(self.jobs))
        self.pause_button.setEnabled(False)
        self.skip_button.setEnabled(False)
        self.cancel_button.setEnabled(False)

    def _row_for_path(self, path: Path) -> int | None:
        resolved = path.resolve()
        return next((index for index, job in enumerate(self.jobs) if job.source == resolved), None)

    def _set_table_status(self, row: int, status: str, message: str) -> None:
        item = self.table.item(row, 7)
        item.setText(status)
        item.setToolTip(message)
        self._paint_status(row, status)

    def _paint_status(self, row: int, status: str) -> None:
        item = self.table.item(row, 7)
        item.setForeground(STATUS_COLORS.get(status, QColor("#C7D5E5")))


def _select_data(combo: QComboBox, value: object) -> None:
    index = combo.findData(getattr(value, "value", value))
    if index >= 0:
        combo.setCurrentIndex(index)


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).lower() in {"1", "true", "yes"}


def _safe_enum(enum_type: type, value: object, default: object) -> object:
    try:
        return enum_type(value)
    except (TypeError, ValueError):
        return default


def _human_size(size_bytes: int) -> str:
    size = float(size_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.0f} {unit}" if unit in {"B", "KB"} else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def _duration_text(seconds: float) -> str:
    total = max(int(round(seconds)), 0)
    hours, remainder = divmod(total, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:d}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes:d}:{seconds:02d}"


def _play_completion_sound(success: bool) -> None:
    if os.name != "nt":
        QApplication.beep()
        return
    try:
        import winsound

        winsound.MessageBeep(winsound.MB_OK if success else winsound.MB_ICONHAND)
    except Exception:
        QApplication.beep()
