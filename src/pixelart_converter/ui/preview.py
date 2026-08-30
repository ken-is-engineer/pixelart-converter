"""GIF preview widget that upscales with nearest-neighbor filtering."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QPointF, QSize, Qt
from PySide6.QtGui import QImage, QPainter, QPixmap
from PySide6.QtWidgets import QSizePolicy, QWidget


# Nearest-neighbor. SmoothTransformation would blur pixel art.
PREVIEW_TRANSFORMATION = Qt.TransformationMode.FastTransformation


@dataclass(frozen=True)
class GifPreviewData:
    """First frame and metadata loaded from an input GIF."""

    pixmap: QPixmap
    width: int
    height: int
    frame_count: int


def load_gif_preview(path: Path | str) -> GifPreviewData:
    """Load the first frame of a GIF for preview.

    Raises OSError or PIL errors when the file cannot be decoded. Callers
    must treat failure as preview-only; conversion may still be attempted.
    """
    with Image.open(path) as image:
        width, height = image.size
        frame_count = getattr(image, "n_frames", 1)
        image.seek(0)
        frame = image.convert("RGBA")
        buffer = frame.tobytes("raw", "RGBA")

    qimage = QImage(
        buffer,
        width,
        height,
        width * 4,
        QImage.Format.Format_RGBA8888,
    )
    if qimage.isNull():
        raise ValueError(f"Could not convert GIF frame to an image: {path}")
    pixmap = QPixmap.fromImage(qimage.copy())
    if pixmap.isNull():
        raise ValueError(f"Could not convert GIF frame to a pixmap: {path}")
    return GifPreviewData(
        pixmap=pixmap,
        width=width,
        height=height,
        frame_count=frame_count,
    )


class NearestNeighborPreview(QWidget):
    """Paints a pixmap scaled with :data:`PREVIEW_TRANSFORMATION`."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._pixmap = QPixmap()
        self.setMinimumSize(160, 160)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    @property
    def transformation_mode(self) -> Qt.TransformationMode:
        """Scaling algorithm used for display and :meth:`scaled_pixmap`."""
        return PREVIEW_TRANSFORMATION

    def has_preview(self) -> bool:
        return not self._pixmap.isNull()

    def source_pixmap_size(self) -> QSize:
        return self._pixmap.size()

    def set_pixmap(self, pixmap: QPixmap | None) -> None:
        self._pixmap = pixmap if pixmap is not None else QPixmap()
        self.update()

    def clear_preview(self) -> None:
        self.set_pixmap(None)

    def scaled_pixmap(self, target: QSize) -> QPixmap:
        """Scale the source with the same nearest-neighbor mode as painting."""
        if self._pixmap.isNull() or not target.isValid():
            return QPixmap()
        return self._pixmap.scaled(
            target,
            Qt.AspectRatioMode.KeepAspectRatio,
            self.transformation_mode,
        )

    def paintEvent(self, _event) -> None:  # noqa: N802 - Qt override
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        if self._pixmap.isNull():
            return

        dpr = self.devicePixelRatioF() or 1.0
        target = QSize(
            max(1, int(self.width() * dpr)),
            max(1, int(self.height() * dpr)),
        )
        scaled = self.scaled_pixmap(target)
        if scaled.isNull():
            return
        scaled.setDevicePixelRatio(dpr)
        logical_w = scaled.width() / dpr
        logical_h = scaled.height() / dpr
        x = (self.width() - logical_w) / 2
        y = (self.height() - logical_h) / 2
        painter.drawPixmap(QPointF(x, y), scaled)
