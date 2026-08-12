from __future__ import annotations

import os
import shutil
import subprocess
import threading
from pathlib import Path

import psutil
from PySide6.QtCore import QThread, Signal

from .commands import (
    build_ffmpeg_command,
    detect_capabilities,
    encoder_attempts,
)
from .dependencies import (
    FFmpegInstallation,
    InstallationCancelled,
    install_ffmpeg,
)
from .media import MediaProbeError, probe_media, validate_encoded_media
from .models import (
    EncodeJob,
    EncodeSettings,
    EncoderPreference,
    FFmpegCapabilities,
    JobStatus,
    VideoMetadata,
)
from .paths import unique_output_path


class ProbeThread(QThread):
    probed = Signal(str, object)
    failed = Signal(str, str)

    def __init__(self, ffprobe_path: Path, paths: list[Path]) -> None:
        super().__init__()
        self._ffprobe_path = ffprobe_path
        self._paths = paths

    def run(self) -> None:
        for path in self._paths:
            if self.isInterruptionRequested():
                return
            try:
                metadata = probe_media(self._ffprobe_path, path)
                self.probed.emit(str(path), metadata)
            except MediaProbeError as error:
                self.failed.emit(str(path), str(error))


class DependencyInstallThread(QThread):
    progress_changed = Signal(int, str)
    installed = Signal(object)
    failed = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._cancel_event = threading.Event()

    def cancel(self) -> None:
        self._cancel_event.set()

    def run(self) -> None:
        try:
            installation = install_ffmpeg(
                progress=lambda percent, message: self.progress_changed.emit(percent, message),
                cancel_event=self._cancel_event,
            )
            self.installed.emit(installation)
        except InstallationCancelled:
            self.failed.emit("FFmpeg installation was cancelled.")
        except Exception as error:
            self.failed.emit(str(error))


class EncoderThread(QThread):
    job_status_changed = Signal(int, str, str)
    job_progress_changed = Signal(int, float)
    overall_progress_changed = Signal(float)
    log_message = Signal(str)
    pause_changed = Signal(bool)
    queue_finished = Signal(bool, str)

    def __init__(
        self,
        installation: FFmpegInstallation,
        jobs: list[EncodeJob],
        settings: EncodeSettings,
    ) -> None:
        super().__init__()
        self._installation = installation
        self._jobs = jobs
        self._settings = settings
        self._cancel_event = threading.Event()
        self._skip_event = threading.Event()
        self._process_lock = threading.Lock()
        self._current_process: subprocess.Popen[str] | None = None
        self._is_paused = False

    def request_cancel(self) -> None:
        self._cancel_event.set()
        self._stop_current_process()

    def skip_current(self) -> None:
        self._skip_event.set()
        self._stop_current_process()

    def toggle_pause(self) -> bool:
        with self._process_lock:
            process = self._current_process
            if not process or process.poll() is not None:
                return False
            try:
                psutil_process = psutil.Process(process.pid)
                if self._is_paused:
                    psutil_process.resume()
                    self._is_paused = False
                else:
                    psutil_process.suspend()
                    self._is_paused = True
                self.pause_changed.emit(self._is_paused)
                return True
            except (psutil.Error, OSError) as error:
                self.log_message.emit(f"Pause/resume failed: {error}")
                return False

    def run(self) -> None:
        capabilities = detect_capabilities(self._installation.ffmpeg)
        self.log_message.emit(
            "NVIDIA NVENC detected." if capabilities.has_nvenc else "NVENC unavailable; CPU encoding will be used."
        )
        completed = 0
        successful = 0

        for index, job in enumerate(self._jobs):
            if self._cancel_event.is_set():
                self._mark_remaining_cancelled(index)
                break
            if not job.metadata:
                self._set_status(index, JobStatus.FAILED, "Missing source metadata")
                completed += 1
                continue

            self._skip_event.clear()
            output_path = unique_output_path(job.source, self._settings.output_directory)
            job.output = output_path
            self._set_status(index, JobStatus.ENCODING, "Starting encode")
            succeeded = self._encode_job(index, job, output_path, capabilities)

            if self._cancel_event.is_set():
                self._set_status(index, JobStatus.CANCELLED, "Cancelled")
                self._remove_partial(output_path)
                self._mark_remaining_cancelled(index + 1)
                break
            if self._skip_event.is_set():
                self._set_status(index, JobStatus.SKIPPED, "Skipped by user")
                self._remove_partial(output_path)
            elif succeeded:
                successful += 1
                self._set_status(index, JobStatus.DONE, f"Saved to {output_path.name}")
                self.job_progress_changed.emit(index, 100.0)
                if self._settings.move_originals:
                    self._move_original(job.source)
            else:
                self._set_status(index, JobStatus.FAILED, job.message or "Encoding failed")

            completed += 1
            self.overall_progress_changed.emit((completed / max(len(self._jobs), 1)) * 100)

        if self._cancel_event.is_set():
            self.queue_finished.emit(False, "Encoding was cancelled.")
        else:
            self.queue_finished.emit(
                successful > 0,
                f"Finished {successful} of {len(self._jobs)} file(s).",
            )

    def _encode_job(
        self,
        index: int,
        job: EncodeJob,
        output_path: Path,
        capabilities: FFmpegCapabilities,
    ) -> bool:
        assert job.metadata is not None
        attempts = encoder_attempts(self._settings.encoder, capabilities)
        last_error = ""

        for attempt_number, encoder in enumerate(attempts):
            if self._cancel_event.is_set() or self._skip_event.is_set():
                return False
            if attempt_number > 0:
                self.log_message.emit("GPU encoding failed; retrying safely with CPU x264.")
                self._set_status(index, JobStatus.ENCODING, "GPU unavailable — retrying with CPU")
                self._remove_partial(output_path)

            command = build_ffmpeg_command(
                self._installation.ffmpeg,
                job.source,
                output_path,
                job.metadata,
                self._settings,
                encoder,
            )
            self.log_message.emit(
                f"Encoding {job.source.name} with {'NVIDIA NVENC' if encoder == EncoderPreference.NVIDIA else 'CPU x264'}"
            )
            return_code, error_text = self._run_process(index, command, job.metadata.duration_seconds)
            if self._cancel_event.is_set() or self._skip_event.is_set():
                return False
            if return_code == 0 and output_path.is_file() and output_path.stat().st_size > 0:
                try:
                    output_metadata = probe_media(self._installation.ffprobe, output_path)
                    validation_errors = validate_encoded_media(job.metadata, output_metadata, self._settings)
                    if validation_errors:
                        job.message = " ".join(validation_errors)
                        return False
                    return True
                except MediaProbeError as error:
                    job.message = f"Output verification failed: {error}"
                    return False

            last_error = error_text.strip() or f"FFmpeg exited with code {return_code}."
            if encoder != EncoderPreference.NVIDIA or len(attempts) == 1:
                break

        job.message = _concise_error(last_error)
        return False

    def _run_process(
        self,
        index: int,
        command: list[str],
        duration_seconds: float,
    ) -> tuple[int, str]:
        creation_flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            creationflags=creation_flags,
        )
        with self._process_lock:
            self._current_process = process
            self._is_paused = False

        assert process.stdout is not None
        for raw_line in process.stdout:
            if self._cancel_event.is_set() or self._skip_event.is_set():
                self._stop_current_process()
                break
            key, separator, value = raw_line.strip().partition("=")
            if not separator:
                continue
            seconds = _progress_seconds(key, value)
            if seconds is not None and duration_seconds > 0:
                percent = min(max((seconds / duration_seconds) * 100, 0.0), 99.5)
                self.job_progress_changed.emit(index, percent)

        return_code = process.wait()
        error_text = process.stderr.read() if process.stderr else ""
        with self._process_lock:
            self._current_process = None
            if self._is_paused:
                self._is_paused = False
                self.pause_changed.emit(False)
        return return_code, error_text

    def _stop_current_process(self) -> None:
        with self._process_lock:
            process = self._current_process
            if not process or process.poll() is not None:
                return
            try:
                psutil.Process(process.pid).kill()
            except (psutil.Error, OSError):
                try:
                    process.kill()
                except OSError:
                    pass

    def _set_status(self, index: int, status: JobStatus, message: str) -> None:
        job = self._jobs[index]
        job.status = status
        job.message = message
        self.job_status_changed.emit(index, status.value, message)

    def _mark_remaining_cancelled(self, start_index: int) -> None:
        for index in range(start_index, len(self._jobs)):
            self._set_status(index, JobStatus.CANCELLED, "Queue cancelled")

    def _move_original(self, source: Path) -> None:
        old_directory = source.parent / "old_files"
        old_directory.mkdir(parents=True, exist_ok=True)
        destination = old_directory / source.name
        suffix = 2
        while destination.exists():
            destination = old_directory / f"{source.stem}_{suffix}{source.suffix}"
            suffix += 1
        shutil.move(str(source), str(destination))

    @staticmethod
    def _remove_partial(path: Path) -> None:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass


def _progress_seconds(key: str, value: str) -> float | None:
    if key in {"out_time_us", "out_time_ms"}:
        try:
            return int(value) / 1_000_000
        except ValueError:
            return None
    if key == "out_time":
        try:
            hours, minutes, seconds = value.split(":")
            return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
        except (ValueError, TypeError):
            return None
    return None


def _concise_error(error_text: str) -> str:
    lines = [line.strip() for line in error_text.splitlines() if line.strip()]
    if not lines:
        return "FFmpeg could not encode this file."
    return " ".join(lines[-3:])[:600]
