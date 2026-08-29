"""QObject worker that runs ConversionService off the GUI thread."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot

from pixelart_converter.conversion.service import ConversionService
from pixelart_converter.errors import ConversionError, ErrorCode
from pixelart_converter.models import ConversionJob


class ConversionWorker(QObject):
    """Call :meth:`ConversionService.convert` and forward progress via signals.

    Widgets must never be touched from this object after it is moved to a
    worker thread; slots on the window should use queued connections.
    """

    progress = Signal(float)
    succeeded = Signal()
    failed = Signal(object)

    def __init__(self, service: ConversionService, job: ConversionJob) -> None:
        super().__init__()
        self._service = service
        self._job = job

    @Slot()
    def run(self) -> None:
        try:
            self._service.convert(self._job, self._emit_progress)
        except ConversionError as error:
            self.failed.emit(error)
        except Exception as exc:
            self.failed.emit(
                ConversionError.from_code(ErrorCode.UNKNOWN, detail=repr(exc))
            )
        else:
            self.succeeded.emit()

    def _emit_progress(self, seconds: float) -> None:
        self.progress.emit(seconds)
