"""ConversionService: preflight bundled FFmpeg and fail MP4 without a HW encoder."""

from __future__ import annotations

from pixelart_converter.conversion.binary import resolve_ffmpeg
from pixelart_converter.conversion.encoder import EncoderResult, resolve_encoder
from pixelart_converter.errors import ConversionError, ErrorCode
from pixelart_converter.models import ConversionJob, OutputFormat

_ALLOWED_MP4_ENCODERS = frozenset({"h264_videotoolbox", "h264_mf"})


class ConversionService:
    """Validate that a job can run, then convert.

    Encode argv and the FFmpeg subprocess belong to Phase 3. This task only
    refuses to start an MP4 conversion when no hardware H.264 encoder exists,
    and never falls back to PATH or GPL ffmpeg.
    """

    def preflight(self, job: ConversionJob) -> EncoderResult | None:
        """Ensure bundled ffmpeg (and for MP4, a HW encoder) is available.

        Never searches PATH. Does not start an encode subprocess.

        Returns the selected encoder for MP4, or ``None`` for other formats.
        """
        if job.output_format is OutputFormat.MP4:
            return self._preflight_mp4()
        resolve_ffmpeg()
        return None

    def convert(self, job: ConversionJob) -> None:
        """Preflight, then encode.

        Encoding is not implemented yet (T3). Preflight still fails closed
        so a missing encoder never reaches a conversion subprocess.
        """
        self.preflight(job)
        raise NotImplementedError(
            "FFmpeg encode is not implemented yet; conversion was not started."
        )

    def _preflight_mp4(self) -> EncoderResult:
        # Missing bundled binary is a different failure from "HW encoder
        # listed but unavailable". Do not rewrite the user message.
        resolve_ffmpeg()
        encoder = resolve_encoder()
        if encoder is None or encoder.name not in _ALLOWED_MP4_ENCODERS:
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
