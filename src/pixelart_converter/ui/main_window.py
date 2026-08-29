from PySide6.QtWidgets import QLabel, QMainWindow, QMessageBox, QVBoxLayout, QWidget

from pixelart_converter.errors import ConversionError
from pixelart_converter.logging_config import get_logger

_logger = get_logger("ui")


class MainWindow(QMainWindow):
    """Main window shell. Conversion controls are added in later tasks."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("pixelart-converter")
        self.resize(960, 640)

        self._last_error: ConversionError | None = None

        central = QWidget(self)
        layout = QVBoxLayout(central)
        self._error_label = QLabel("", central)
        self._error_label.setWordWrap(True)
        self._error_label.hide()
        layout.addWidget(self._error_label)
        layout.addStretch()
        self.setCentralWidget(central)

    @property
    def last_error(self) -> ConversionError | None:
        """Last error passed to :meth:`show_error` (for tests and smoke)."""
        return self._last_error

    def show_error(self, error: ConversionError, *, show_dialog: bool = True) -> None:
        """Display a classified conversion error in the UI and log it."""
        self._last_error = error
        _logger.error(error.log_message())

        self._error_label.setText(error.message)
        self._error_label.show()

        if show_dialog:
            QMessageBox.critical(
                self,
                self.tr("Conversion failed"),
                error.message,
            )
