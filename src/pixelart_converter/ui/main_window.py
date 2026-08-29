from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from pixelart_converter.errors import ConversionError
from pixelart_converter.logging_config import get_logger
from pixelart_converter.ui.preview import NearestNeighborPreview, load_gif_preview

_logger = get_logger("ui")

_UNSET = "—"


class MainWindow(QMainWindow):
    """Main window: input picker and nearest-neighbor GIF preview (T4-1)."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("pixelart-converter")
        self.resize(960, 640)

        self._last_error: ConversionError | None = None
        self._input_path: str | None = None

        self._build_ui()

    def _build_ui(self) -> None:
        central = QWidget(self)
        root = QVBoxLayout(central)

        body = QHBoxLayout()
        body.addWidget(self._build_input_panel(), stretch=3)
        body.addWidget(self._build_options_placeholder(), stretch=2)
        root.addLayout(body, stretch=1)
        root.addWidget(self._build_actions_placeholder())

        self._error_label = QLabel("", central)
        self._error_label.setWordWrap(True)
        self._error_label.hide()
        root.addWidget(self._error_label)

        self.setCentralWidget(central)

    def _build_input_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)

        picker_row = QHBoxLayout()
        self._browse_button = QPushButton(self.tr("Select GIF..."))
        self._browse_button.clicked.connect(self._on_browse)
        self.path_label = QLabel(self.tr("No file selected"))
        self.path_label.setObjectName("inputPathLabel")
        self.path_label.setWordWrap(True)
        self.path_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        picker_row.addWidget(self._browse_button)
        picker_row.addWidget(self.path_label, stretch=1)
        layout.addLayout(picker_row)

        self.preview_widget = NearestNeighborPreview(panel)
        self.preview_widget.setObjectName("gifPreview")
        layout.addWidget(self.preview_widget, stretch=1)

        self.preview_status_label = QLabel("")
        self.preview_status_label.setObjectName("previewStatusLabel")
        self.preview_status_label.setWordWrap(True)
        self.preview_status_label.hide()
        layout.addWidget(self.preview_status_label)

        self.width_label = QLabel(_UNSET)
        self.width_label.setObjectName("widthLabel")
        self.height_label = QLabel(_UNSET)
        self.height_label.setObjectName("heightLabel")
        self.frame_count_label = QLabel(_UNSET)
        self.frame_count_label.setObjectName("frameCountLabel")

        meta = QFormLayout()
        meta.addRow(self.tr("Width"), self.width_label)
        meta.addRow(self.tr("Height"), self.height_label)
        meta.addRow(self.tr("Frames"), self.frame_count_label)
        layout.addLayout(meta)
        return panel

    def _build_options_placeholder(self) -> QWidget:
        box = QGroupBox(self.tr("Output options"))
        layout = QVBoxLayout(box)
        hint = QLabel(self.tr("Format options will appear here."))
        hint.setEnabled(False)
        hint.setWordWrap(True)
        layout.addWidget(hint)
        layout.addStretch()
        return box

    def _build_actions_placeholder(self) -> QWidget:
        bar = QWidget()
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(0, 0, 0, 0)
        output_hint = QLabel(self.tr("Output path will be chosen when converting."))
        output_hint.setEnabled(False)
        output_hint.setWordWrap(True)
        convert_button = QPushButton(self.tr("Convert"))
        convert_button.setEnabled(False)
        convert_button.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        layout.addWidget(output_hint, stretch=1)
        layout.addWidget(convert_button)
        return bar

    @property
    def last_error(self) -> ConversionError | None:
        """Last error passed to :meth:`show_error` (for tests and smoke)."""
        return self._last_error

    @property
    def input_path(self) -> str | None:
        """Currently selected input path, even if preview failed to load."""
        return self._input_path

    @property
    def preview_transformation_mode(self) -> Qt.TransformationMode:
        """Scaling used by the GIF preview (nearest-neighbor)."""
        return self.preview_widget.transformation_mode

    def set_input_path(self, path: str | Path) -> None:
        """Record an input GIF and refresh preview plus metadata labels."""
        self._input_path = str(path)
        self.path_label.setText(self._input_path)
        self._load_preview(self._input_path)

    def _on_browse(self) -> None:
        start_dir = ""
        if self._input_path:
            start_dir = str(Path(self._input_path).parent)
        chosen, _filter = QFileDialog.getOpenFileName(
            self,
            self.tr("Select GIF"),
            start_dir,
            self.tr("GIF images (*.gif)"),
        )
        if chosen:
            self.set_input_path(chosen)

    def _load_preview(self, path: str) -> None:
        try:
            data = load_gif_preview(path)
        except Exception as exc:
            _logger.warning("Failed to load GIF preview: %s (%s)", path, exc)
            self._show_preview_unavailable()
            return

        self.preview_widget.set_pixmap(data.pixmap)
        self.width_label.setText(str(data.width))
        self.height_label.setText(str(data.height))
        self.frame_count_label.setText(str(data.frame_count))
        self.preview_status_label.hide()
        self.preview_status_label.clear()

    def _show_preview_unavailable(self) -> None:
        self.preview_widget.clear_preview()
        self.width_label.setText(_UNSET)
        self.height_label.setText(_UNSET)
        self.frame_count_label.setText(_UNSET)
        self.preview_status_label.setText(
            self.tr("Preview could not be loaded. You can still convert this file.")
        )
        self.preview_status_label.show()

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
