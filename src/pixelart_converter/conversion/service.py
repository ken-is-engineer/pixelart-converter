"""ConversionService: preflight jobs and run supported FFmpeg conversions."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
from typing import TextIO

from PIL import Image

from pixelart_converter.conversion.binary import resolve_ffmpeg
from pixelart_converter.conversion.command import FFmpegCommandBuilder
from pixelart_converter.conversion.encoder import (
    ALLOWED_MP4_ENCODERS,
    EncoderResult,
    resolve_encoder,
)
from pixelart_converter.errors import ConversionError, ErrorCode
from pixelart_converter.models import (
    ConversionJob,
    FrameRange,
    JPEGOutput,
    MultipleFrames,
    OutputFormat,
    PNGOutput,
    SingleFrame,
)

ProgressCallback = Callable[[float], None]
_CANCEL_TIMEOUT_SECONDS = 2.0


class ConversionService:
    """Validate that a job can run, then convert.

    GIF conversion supports the common Phase 3 options. MP4 loop-count
    and duration jobs encode with the hardware encoder selected at
    preflight. JPEG and PNG frame selections are validated before FFmpeg.
    """

    def __init__(self) -> None:
        self._process: subprocess.Popen[str] | None = None
        self._process_lock = threading.Lock()
        self._cancelled = threading.Event()

    def preflight(self, job: ConversionJob) -> EncoderResult | None:
        """Ensure bundled ffmpeg (and for MP4, a HW encoder) is available.

        Never searches PATH. Does not start an encode subprocess.

        Returns the selected encoder for MP4, or ``None`` for other formats.
        """
        if job.output_format is OutputFormat.MP4:
            return self._preflight_mp4()
        resolve_ffmpeg()
        return None

    def convert(
        self,
        job: ConversionJob,
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        """Preflight, then encode.

        GIF output uses the common command builder. MP4 jobs invoke the
        builder (hardware ``-c:v`` only) and a cancellable subprocess.
        JPEG/PNG jobs validate the GIF and every requested index before
        resolving or starting FFmpeg. Progress callbacks receive elapsed
        output seconds reported by FFmpeg.
        """
        self._cancelled.clear()
        if job.output_format is OutputFormat.GIF:
            argv = FFmpegCommandBuilder().build(job)
        elif isinstance(job.output, (JPEGOutput, PNGOutput)):
            self._validate_still_frames(job)
            self.preflight(job)
            argv = FFmpegCommandBuilder().build(job)
        elif job.output_format is OutputFormat.MP4:
            self.preflight(job)
            argv = FFmpegCommandBuilder().build(job)
        else:
            raise NotImplementedError(
                "This output format is not implemented yet; conversion was not started."
            )

        if self._cancelled.is_set():
            raise ConversionError.from_code(ErrorCode.CANCELLED)
        self._encode(argv, job.resolved_output_path(), progress_callback)

    def cancel(self) -> None:
        """Cancel the active encode, escalating from terminate to kill."""
        self._cancelled.set()
        with self._process_lock:
            process = self._process
        if process is None or process.poll() is not None:
            return

        process.terminate()
        try:
            process.wait(timeout=_CANCEL_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            process.kill()

    def _encode(
        self,
        argv: list[str],
        output_path: Path,
        progress_callback: ProgressCallback | None,
    ) -> None:
        output_path = output_path.resolve()
        output_dir = output_path.parent
        try:
            temp_dir = Path(
                tempfile.mkdtemp(
                    prefix=f".{output_path.stem}-",
                    dir=output_dir,
                )
            )
        except OSError as exc:
            raise ConversionError.from_code(
                ErrorCode.OUTPUT_PATH,
                detail=f"could not create temporary output: {exc}",
            ) from exc

        final_ffmpeg_path = Path(argv[-1])
        temp_ffmpeg_path = temp_dir / final_ffmpeg_path.name
        encode_argv = [
            *argv[:-1],
            "-progress",
            "pipe:1",
            "-nostats",
            str(temp_ffmpeg_path),
        ]
        stderr_tail: deque[str] = deque(maxlen=40)
        process: subprocess.Popen[str] | None = None
        stderr_thread: threading.Thread | None = None
        last_progress: float | None = None

        try:
            if self._cancelled.is_set():
                raise ConversionError.from_code(ErrorCode.CANCELLED)
            process = subprocess.Popen(
                encode_argv,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
            with self._process_lock:
                self._process = process
            if self._cancelled.is_set():
                process.terminate()

            stderr_thread = threading.Thread(
                target=_drain_stderr,
                args=(process.stderr, stderr_tail),
                daemon=True,
            )
            stderr_thread.start()
            if process.stdout is not None:
                for line in process.stdout:
                    seconds = _parse_progress_seconds(line)
                    if (
                        seconds is not None
                        and seconds != last_progress
                        and progress_callback is not None
                    ):
                        progress_callback(seconds)
                        last_progress = seconds

            returncode = process.wait()
            stderr_thread.join()
            if self._cancelled.is_set():
                raise ConversionError.from_code(ErrorCode.CANCELLED)
            if returncode != 0:
                raise ConversionError.from_code(
                    ErrorCode.UNKNOWN,
                    detail=(
                        f"ffmpeg exited with status {returncode}; "
                        f"stderr tail: {''.join(stderr_tail).strip()}"
                    ),
                )

            self._publish_outputs(temp_dir, final_ffmpeg_path, output_dir)
        except OSError as exc:
            if self._cancelled.is_set():
                raise ConversionError.from_code(ErrorCode.CANCELLED) from exc
            raise ConversionError.from_code(
                ErrorCode.UNKNOWN,
                detail=f"could not run or publish ffmpeg output: {exc}",
            ) from exc
        finally:
            with self._process_lock:
                if self._process is process:
                    self._process = None
            if process is not None:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=_CANCEL_TIMEOUT_SECONDS)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                if stderr_thread is not None:
                    stderr_thread.join()
                if process.stdout is not None:
                    process.stdout.close()
                if process.stderr is not None:
                    process.stderr.close()
            shutil.rmtree(temp_dir, ignore_errors=True)

    def _publish_outputs(
        self,
        temp_dir: Path,
        final_ffmpeg_path: Path,
        output_dir: Path,
    ) -> None:
        generated = [path for path in temp_dir.iterdir() if path.is_file()]
        if not generated:
            raise ConversionError.from_code(
                ErrorCode.UNKNOWN,
                detail="ffmpeg succeeded without creating an output file",
            )

        if "%" not in final_ffmpeg_path.name:
            named = temp_dir / final_ffmpeg_path.name
            source = named if named.is_file() else generated[0]
            if source is generated[0] and len(generated) != 1:
                raise ConversionError.from_code(
                    ErrorCode.UNKNOWN,
                    detail="ffmpeg wrote multiple files for a single-file output",
                )
            os.replace(source, output_dir / final_ffmpeg_path.name)
            return

        for temp_output in generated:
            os.replace(temp_output, output_dir / temp_output.name)

    def _validate_still_frames(self, job: ConversionJob) -> None:
        output = job.output
        if not isinstance(output, (JPEGOutput, PNGOutput)):
            raise TypeError("still-frame validation requires JPEG or PNG output")

        try:
            with Image.open(job.input_path) as image:
                if image.format != "GIF":
                    raise ConversionError.from_code(
                        ErrorCode.INVALID_INPUT,
                        detail=f"input format is {image.format!r}, expected GIF",
                    )
                frame_count = image.n_frames
        except (OSError, ValueError) as exc:
            raise ConversionError.from_code(
                ErrorCode.INVALID_INPUT,
                detail=f"could not read GIF frame count: {exc}",
            ) from exc

        invalid_index = _first_out_of_range_index(output.frames, frame_count)
        if invalid_index is not None:
            raise ConversionError.from_code(
                ErrorCode.INVALID_INPUT,
                message=(
                    f"Frame index {invalid_index} is out of range for a GIF "
                    f"with {frame_count} frame(s)."
                ),
                detail=(
                    f"requested frame {invalid_index}; frame count is {frame_count}"
                ),
            )

    def _preflight_mp4(self) -> EncoderResult:
        # Missing bundled binary is a different failure from "HW encoder
        # listed but unavailable". Do not rewrite the user message.
        resolve_ffmpeg()
        encoder = resolve_encoder()
        if encoder is None or encoder.name not in ALLOWED_MP4_ENCODERS:
            raise _mp4_encoder_unavailable(
                detail=(
                    "bundled ffmpeg has no hardware H.264 encoder"
                    if encoder is None
                    else f"refusing encoder {encoder.name!r}"
                ),
            )
        return encoder


def _mp4_encoder_unavailable(*, detail: str | None) -> ConversionError:
    """User-facing MP4 failure: HW H.264 missing, no system/GPL ffmpeg fallback."""
    return ConversionError.from_code(
        ErrorCode.ENCODER_UNAVAILABLE,
        detail=detail,
    )


def _first_out_of_range_index(
    frames: object, frame_count: int
) -> int | None:
    if isinstance(frames, SingleFrame):
        return frames.index if frames.index >= frame_count else None
    if isinstance(frames, MultipleFrames):
        for item in frames.items:
            if isinstance(item, FrameRange):
                if item.end >= frame_count:
                    return max(item.start, frame_count)
            elif item >= frame_count:
                return item
    return None


def _drain_stderr(
    stderr: TextIO | None,
    destination: deque[str],
) -> None:
    if stderr is not None:
        destination.extend(stderr)


def _parse_progress_seconds(line: str) -> float | None:
    key, separator, value = line.strip().partition("=")
    if not separator:
        return None
    if key in {"out_time_us", "out_time_ms"}:
        try:
            return int(value) / 1_000_000
        except ValueError:
            return None
    if key != "out_time":
        return None

    parts = value.split(":")
    if len(parts) != 3:
        return None
    try:
        hours, minutes, seconds = map(float, parts)
    except ValueError:
        return None
    return hours * 3600 + minutes * 60 + seconds
