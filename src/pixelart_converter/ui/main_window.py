from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QThread, Slot
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from pixelart_converter.conversion.service import ConversionService
from pixelart_converter.errors import ConversionError, ErrorCode
from pixelart_converter.logging_config import get_logger
from pixelart_converter.models import (
    AllFrames,
    CommonOptions,
    ConversionJob,
    FrameSelection,
    GIFOutput,
    JPEGOutput,
    MP4Options,
    MP4Output,
    OutputFormat,
    PNGOutput,
    ScaleAlgorithm,
    SingleFrame,
)
from pixelart_converter.ui.options import parse_frame_list
from pixelart_converter.ui.preview import NearestNeighborPreview, load_gif_preview
from pixelart_converter.ui.worker import ConversionWorker

_logger = get_logger("ui")

_UNSET = "—"
_MAX_DIMENSION = 16384
_OUTPUT_FILTERS = {
    OutputFormat.MP4: "MP4 video (*.mp4)",
    OutputFormat.JPEG: "JPEG images (*.jpg *.jpeg)",
    OutputFormat.PNG: "PNG images (*.png)",
    OutputFormat.GIF: "GIF images (*.gif)",
}


class MainWindow(QMainWindow):
    """Main window: options, convert/cancel, and worker-thread progress (T4-3)."""

    def __init__(self, service: ConversionService | None = None) -> None:
        super().__init__()
        self.setWindowTitle("pixelart-converter")
        self.resize(960, 640)

        self._service = service if service is not None else ConversionService()
        self._last_error: ConversionError | None = None
        self._input_path: str | None = None
        self._converting = False
        self._thread: QThread | None = None
        self._worker: ConversionWorker | None = None

        self._build_ui()
        self._sync_option_widgets()

    def _build_ui(self) -> None:
        central = QWidget(self)
        root = QVBoxLayout(central)

        body = QHBoxLayout()
        self._input_panel = self._build_input_panel()
        self._options_panel = self._build_options_panel()
        body.addWidget(self._input_panel, stretch=3)
        body.addWidget(self._options_panel, stretch=2)
        root.addLayout(body, stretch=1)
        root.addWidget(self._build_actions_bar())
        self._connect_option_signals()

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

    def _build_options_panel(self) -> QWidget:
        box = QGroupBox(self.tr("Output options"))
        layout = QVBoxLayout(box)

        layout.addLayout(self._build_format_row())
        self.mp4_group = self._build_mp4_group()
        self.frame_group = self._build_frame_group()
        layout.addWidget(self.mp4_group)
        layout.addWidget(self.frame_group)
        layout.addWidget(self._build_common_group())
        layout.addStretch()
        return box

    def _connect_option_signals(self) -> None:
        for radio in (
            self.format_mp4_radio,
            self.format_jpeg_radio,
            self.format_png_radio,
            self.format_gif_radio,
        ):
            radio.toggled.connect(self._sync_option_widgets)
        self.mp4_loop_radio.toggled.connect(self._sync_mp4_fields)
        self.mp4_duration_radio.toggled.connect(self._sync_mp4_fields)
        for radio in (
            self.frame_single_radio,
            self.frame_list_radio,
            self.frame_all_radio,
        ):
            radio.toggled.connect(self._sync_frame_fields)
        self.format_mp4_radio.setChecked(True)
        self.mp4_loop_radio.setChecked(True)
        self.frame_single_radio.setChecked(True)

    def _build_format_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addWidget(QLabel(self.tr("Format")))
        self.format_mp4_radio = QRadioButton(self.tr("MP4"))
        self.format_jpeg_radio = QRadioButton(self.tr("JPEG"))
        self.format_png_radio = QRadioButton(self.tr("PNG"))
        self.format_gif_radio = QRadioButton(self.tr("GIF"))
        self.format_mp4_radio.setObjectName("formatMp4Radio")
        self.format_jpeg_radio.setObjectName("formatJpegRadio")
        self.format_png_radio.setObjectName("formatPngRadio")
        self.format_gif_radio.setObjectName("formatGifRadio")

        self._format_buttons = QButtonGroup(self)
        self._format_buttons.setExclusive(True)
        for radio in (
            self.format_mp4_radio,
            self.format_jpeg_radio,
            self.format_png_radio,
            self.format_gif_radio,
        ):
            self._format_buttons.addButton(radio)
            row.addWidget(radio)
        row.addStretch()
        return row

    def _build_mp4_group(self) -> QGroupBox:
        group = QGroupBox(self.tr("MP4 playback"))
        group.setObjectName("mp4Group")
        layout = QFormLayout(group)

        self.mp4_loop_radio = QRadioButton(self.tr("Loop count"))
        self.mp4_duration_radio = QRadioButton(self.tr("Duration (seconds)"))
        self.mp4_loop_radio.setObjectName("mp4LoopRadio")
        self.mp4_duration_radio.setObjectName("mp4DurationRadio")
        self._mp4_mode_buttons = QButtonGroup(group)
        self._mp4_mode_buttons.setExclusive(True)
        self._mp4_mode_buttons.addButton(self.mp4_loop_radio)
        self._mp4_mode_buttons.addButton(self.mp4_duration_radio)

        self.mp4_loop_spin = QSpinBox()
        self.mp4_loop_spin.setObjectName("mp4LoopSpin")
        self.mp4_loop_spin.setRange(1, 9999)
        self.mp4_loop_spin.setValue(1)

        self.mp4_duration_spin = QDoubleSpinBox()
        self.mp4_duration_spin.setObjectName("mp4DurationSpin")
        self.mp4_duration_spin.setDecimals(2)
        self.mp4_duration_spin.setRange(0.01, 86_400.0)
        self.mp4_duration_spin.setSingleStep(0.5)
        self.mp4_duration_spin.setValue(1.0)

        layout.addRow(self.mp4_loop_radio, self.mp4_loop_spin)
        layout.addRow(self.mp4_duration_radio, self.mp4_duration_spin)
        return group

    def _build_frame_group(self) -> QGroupBox:
        group = QGroupBox(self.tr("JPEG / PNG frames"))
        group.setObjectName("frameGroup")
        layout = QFormLayout(group)

        self.frame_single_radio = QRadioButton(self.tr("Single frame"))
        self.frame_list_radio = QRadioButton(self.tr("List or range"))
        self.frame_all_radio = QRadioButton(self.tr("All frames"))
        self.frame_single_radio.setObjectName("frameSingleRadio")
        self.frame_list_radio.setObjectName("frameListRadio")
        self.frame_all_radio.setObjectName("frameAllRadio")
        self._frame_mode_buttons = QButtonGroup(group)
        self._frame_mode_buttons.setExclusive(True)
        for radio in (
            self.frame_single_radio,
            self.frame_list_radio,
            self.frame_all_radio,
        ):
            self._frame_mode_buttons.addButton(radio)

        self.frame_index_spin = QSpinBox()
        self.frame_index_spin.setObjectName("frameIndexSpin")
        self.frame_index_spin.setRange(0, 999_999)
        self.frame_index_spin.setValue(0)

        self.frame_list_edit = QLineEdit()
        self.frame_list_edit.setObjectName("frameListEdit")
        self.frame_list_edit.setPlaceholderText("0,2,4-6")

        layout.addRow(self.frame_single_radio, self.frame_index_spin)
        layout.addRow(self.frame_list_radio, self.frame_list_edit)
        layout.addRow(self.frame_all_radio)
        return group

    def _build_common_group(self) -> QGroupBox:
        group = QGroupBox(self.tr("Common"))
        group.setObjectName("commonGroup")
        layout = QFormLayout(group)

        self.output_width_spin = _optional_dimension_spin()
        self.output_width_spin.setObjectName("outputWidthSpin")
        self.output_height_spin = _optional_dimension_spin()
        self.output_height_spin.setObjectName("outputHeightSpin")

        self.scale_combo = QComboBox()
        self.scale_combo.setObjectName("scaleCombo")
        for algorithm, label in (
            (ScaleAlgorithm.NEIGHBOR, self.tr("Nearest neighbor")),
            (ScaleAlgorithm.BILINEAR, self.tr("Bilinear")),
            (ScaleAlgorithm.BICUBIC, self.tr("Bicubic")),
        ):
            self.scale_combo.addItem(label, algorithm.value)

        self.strip_metadata_check = QCheckBox(self.tr("Strip metadata"))
        self.strip_metadata_check.setObjectName("stripMetadataCheck")

        layout.addRow(self.tr("Width"), self.output_width_spin)
        layout.addRow(self.tr("Height"), self.output_height_spin)
        layout.addRow(self.tr("Scale algorithm"), self.scale_combo)
        layout.addRow(self.strip_metadata_check)
        return group

    def _build_actions_bar(self) -> QWidget:
        bar = QWidget()
        outer = QVBoxLayout(bar)
        outer.setContentsMargins(0, 0, 0, 0)

        row = QHBoxLayout()
        row.addWidget(QLabel(self.tr("Output")))
        self.output_path_edit = QLineEdit()
        self.output_path_edit.setObjectName("outputPathEdit")
        self.output_path_edit.setPlaceholderText(
            self.tr("Default from input name")
        )
        row.addWidget(self.output_path_edit, stretch=1)

        self.browse_output_button = QPushButton(self.tr("Browse..."))
        self.browse_output_button.setObjectName("browseOutputButton")
        self.browse_output_button.clicked.connect(self._on_browse_output)
        row.addWidget(self.browse_output_button)

        self.convert_button = QPushButton(self.tr("Convert"))
        self.convert_button.setObjectName("convertButton")
        self.convert_button.setEnabled(False)
        self.convert_button.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        self.convert_button.clicked.connect(self._on_convert)
        row.addWidget(self.convert_button)

        self.cancel_button = QPushButton(self.tr("Cancel"))
        self.cancel_button.setObjectName("cancelButton")
        self.cancel_button.setEnabled(False)
        self.cancel_button.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        self.cancel_button.clicked.connect(self._on_cancel)
        row.addWidget(self.cancel_button)
        outer.addLayout(row)

        self._output_sequence_hint = QLabel("", bar)
        self._output_sequence_hint.setObjectName("outputSequenceHint")
        self._output_sequence_hint.setWordWrap(True)
        self._output_sequence_hint.hide()
        outer.addWidget(self._output_sequence_hint)

        progress_row = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("progressBar")
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        progress_row.addWidget(self.progress_bar, stretch=1)
        self.progress_label = QLabel("")
        self.progress_label.setObjectName("progressLabel")
        progress_row.addWidget(self.progress_label)
        outer.addLayout(progress_row)
        return bar

    def _sync_option_widgets(self) -> None:
        fmt = self.current_output_format()
        is_mp4 = fmt is OutputFormat.MP4
        is_image = fmt in (OutputFormat.JPEG, OutputFormat.PNG)
        self.mp4_group.setVisible(is_mp4)
        self.mp4_group.setEnabled(is_mp4)
        self.frame_group.setVisible(is_image)
        self.frame_group.setEnabled(is_image)
        if is_mp4:
            self._sync_mp4_fields()
        if is_image:
            self._sync_frame_fields()
        self._sync_output_sequence_hint()

    def _sync_mp4_fields(self) -> None:
        use_loop = self.mp4_loop_radio.isChecked()
        self.mp4_loop_spin.setEnabled(use_loop)
        self.mp4_duration_spin.setEnabled(not use_loop)

    def _sync_frame_fields(self) -> None:
        self.frame_index_spin.setEnabled(self.frame_single_radio.isChecked())
        self.frame_list_edit.setEnabled(self.frame_list_radio.isChecked())
        self._sync_output_sequence_hint()

    def _sync_output_sequence_hint(self) -> None:
        fmt = self.current_output_format()
        if fmt not in (OutputFormat.JPEG, OutputFormat.PNG):
            self._output_sequence_hint.hide()
            return
        if not (
            self.frame_list_radio.isChecked() or self.frame_all_radio.isChecked()
        ):
            self._output_sequence_hint.hide()
            return
        ext = "png" if fmt is OutputFormat.PNG else "jpg"
        self._output_sequence_hint.setText(
            self.tr(
                "Multiple frames are saved as a numbered sequence "
                "(e.g. name_000.{0}), not a single file."
            ).format(ext)
        )
        self._output_sequence_hint.show()

    def current_output_format(self) -> OutputFormat:
        """Return the format currently selected in the form."""
        if self.format_jpeg_radio.isChecked():
            return OutputFormat.JPEG
        if self.format_png_radio.isChecked():
            return OutputFormat.PNG
        if self.format_gif_radio.isChecked():
            return OutputFormat.GIF
        return OutputFormat.MP4

    def set_output_format(self, fmt: OutputFormat) -> None:
        """Select an output format (used by tests and later convert wiring)."""
        radios = {
            OutputFormat.MP4: self.format_mp4_radio,
            OutputFormat.JPEG: self.format_jpeg_radio,
            OutputFormat.PNG: self.format_png_radio,
            OutputFormat.GIF: self.format_gif_radio,
        }
        radios[fmt].setChecked(True)

    def build_job(self) -> ConversionJob:
        """Collect a ConversionJob from the form without running FFmpeg."""
        if not self._input_path:
            raise ValueError("input path is required")
        output_path = self.output_path_edit.text().strip() or None
        fmt = self.current_output_format()
        if fmt is OutputFormat.MP4:
            output: MP4Output | JPEGOutput | PNGOutput | GIFOutput = MP4Output(
                self._mp4_options(),
                output_path=output_path,
            )
        elif fmt is OutputFormat.JPEG:
            output = JPEGOutput(self._frame_selection(), output_path=output_path)
        elif fmt is OutputFormat.PNG:
            output = PNGOutput(self._frame_selection(), output_path=output_path)
        else:
            output = GIFOutput(output_path=output_path)
        return ConversionJob(
            self._input_path,
            output,
            common=self._common_options(),
        )

    def _mp4_options(self) -> MP4Options:
        if self.mp4_loop_radio.isChecked():
            return MP4Options(loop_count=self.mp4_loop_spin.value())
        return MP4Options(duration_seconds=self.mp4_duration_spin.value())

    def _frame_selection(self) -> FrameSelection:
        if self.frame_all_radio.isChecked():
            return AllFrames()
        if self.frame_list_radio.isChecked():
            return parse_frame_list(self.frame_list_edit.text())
        return SingleFrame(self.frame_index_spin.value())

    def _common_options(self) -> CommonOptions:
        width = self.output_width_spin.value() or None
        height = self.output_height_spin.value() or None
        try:
            algorithm = ScaleAlgorithm(self.scale_combo.currentData())
        except (TypeError, ValueError):
            algorithm = ScaleAlgorithm.NEIGHBOR
        return CommonOptions(
            width=width,
            height=height,
            scale_algorithm=algorithm,
            strip_metadata=self.strip_metadata_check.isChecked(),
        )

    @property
    def last_error(self) -> ConversionError | None:
        """Last error passed to :meth:`show_error` (for tests and smoke)."""
        return self._last_error

    @property
    def is_converting(self) -> bool:
        """True while a worker is running convert (for tests and UI lock)."""
        return self._converting

    @property
    def conversion_worker(self) -> ConversionWorker | None:
        """Active worker object, if a conversion is in flight."""
        return self._worker

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
        self.convert_button.setEnabled(not self._converting)

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

    def _on_browse_output(self) -> None:
        start = self.output_path_edit.text().strip()
        if not start and self._input_path:
            start = str(Path(self._input_path).parent)
        chosen, _filter = QFileDialog.getSaveFileName(
            self,
            self.tr("Output file"),
            start,
            self.tr(_OUTPUT_FILTERS[self.current_output_format()]),
        )
        if chosen:
            self.output_path_edit.setText(chosen)

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

    def closeEvent(self, event: QCloseEvent) -> None:
        """Cancel an in-flight convert so the worker thread can finish."""
        if self._thread is not None:
            self._service.cancel()
            self._thread.quit()
            self._thread.wait(5_000)
        super().closeEvent(event)

    def _on_convert(self) -> None:
        if self._converting or self._thread is not None:
            return
        try:
            job = self.build_job()
        except ValueError as exc:
            self.show_error(
                ConversionError.from_code(
                    ErrorCode.INVALID_INPUT,
                    message=str(exc),
                    detail=str(exc),
                )
            )
            return
        self._start_conversion(job)

    def _on_cancel(self) -> None:
        if not self._converting:
            return
        self._service.cancel()

    def _start_conversion(self, job: ConversionJob) -> None:
        self._last_error = None
        self._error_label.hide()
        self._error_label.clear()
        self._set_converting(True)

        thread = QThread(self)
        worker = ConversionWorker(self._service, job)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(
            self._on_convert_progress,
            Qt.ConnectionType.QueuedConnection,
        )
        worker.succeeded.connect(thread.quit)
        worker.failed.connect(thread.quit)
        worker.succeeded.connect(
            self._on_convert_succeeded,
            Qt.ConnectionType.QueuedConnection,
        )
        worker.failed.connect(
            self._on_convert_failed,
            Qt.ConnectionType.QueuedConnection,
        )
        thread.finished.connect(self._on_worker_thread_finished)
        self._thread = thread
        self._worker = worker
        thread.start()

    def _set_converting(self, converting: bool) -> None:
        self._converting = converting
        self._input_panel.setEnabled(not converting)
        self._options_panel.setEnabled(not converting)
        self.output_path_edit.setEnabled(not converting)
        self.browse_output_button.setEnabled(not converting)
        self.convert_button.setEnabled(not converting and self._input_path is not None)
        self.cancel_button.setEnabled(converting)
        if converting:
            self.progress_bar.setRange(0, 0)
            self.progress_label.setText(self.tr("Converting…"))

    @Slot(float)
    def _on_convert_progress(self, seconds: float) -> None:
        self.progress_label.setText(self.tr("{0:.2f}s").format(seconds))

    @Slot()
    def _on_convert_succeeded(self) -> None:
        self._set_converting(False)
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(1)
        self.progress_label.setText(self.tr("Done"))

    @Slot(object)
    def _on_convert_failed(self, error: object) -> None:
        self._set_converting(False)
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0)
        self.progress_label.clear()
        if not isinstance(error, ConversionError):
            error = ConversionError.from_code(ErrorCode.UNKNOWN, detail=repr(error))
        self.show_error(
            error,
            show_dialog=error.code is not ErrorCode.CANCELLED,
        )

    @Slot()
    def _on_worker_thread_finished(self) -> None:
        worker = self._worker
        thread = self._thread
        self._worker = None
        self._thread = None
        if worker is not None:
            worker.deleteLater()
        if thread is not None:
            thread.deleteLater()


def _optional_dimension_spin() -> QSpinBox:
    spin = QSpinBox()
    spin.setRange(0, _MAX_DIMENSION)
    spin.setSpecialValueText("original")
    spin.setValue(0)
    return spin
